"""
规则引擎生成器 (v3 §4.3)
复用 SpatioTemporalKG 的规则引擎架构
"""
import numpy as np
from typing import Dict, Any, List, Optional

from ..ontology.types import EntityType, RuleRelationType
from ..scenario.nodes import SafetyViolation


class RuleEnforcer:
    """
    规则融合引擎
    
    将物理引擎（轨迹预测）与逻辑引擎（交规规则）统一到图结构中
    """
    
    def __init__(self):
        # RSS 参数
        self.rss_params = {
            'rho': 0.3,           # 反应时间 (s)
            'a_max_accel': 0.5,   # 后车最大加速 (m/s²)
            'a_min_brake': 3.0,   # 后车最小制动 (m/s²)
            'a_brake': 8.0,       # 前车最大制动 (m/s²)
        }
    
    def enforce(self, scene_snapshot: Dict[str, Any], 
                physics_results: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        执行规则检查，生成违规节点
        
        参数:
            scene_snapshot: 场景快照
            physics_results: 物理引擎输出（轨迹簇、碰撞检测等）
        
        返回:
            违规节点列表
        """
        violations = []
        
        # 1. RSS 安全距离检查
        rss_violations = self._check_rss(scene_snapshot)
        violations.extend(rss_violations)
        
        # 2. 交规规则检查
        traffic_violations = self._check_traffic_rules(scene_snapshot)
        violations.extend(traffic_violations)
        
        # 3. 物理预测碰撞检查
        if physics_results:
            collision_violations = self._check_predicted_collisions(
                physics_results
            )
            violations.extend(collision_violations)
        
        return violations
    
    def _check_rss(self, scene_snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        RSS 安全距离检查
        
        使用责任安全间距 (Responsibility-Sensitive Safety) 模型
        """
        violations = []
        vehicles = scene_snapshot.get('vehicles', [])
        
        # 找出自车
        ego = next((v for v in vehicles if v.get('role_name') == 'ego'), None)
        if not ego:
            return violations
        
        # 检查所有前车
        for v in vehicles:
            if v.get('entity_id') == ego.get('entity_id'):
                continue
            
            # 计算 RSS 纵向安全距离
            d_min = self._compute_rss_distance(
                v_a=ego.get('speed', 0),
                v_b=v.get('speed', 0),
                **self.rss_params
            )
            
            # 计算实际距离
            dx = v['x'] - ego['x']
            dy = v['y'] - ego['y']
            distance = np.sqrt(dx**2 + dy**2)
            
            if distance < d_min:
                violations.append({
                    'entity_id': f"sv_rss_{ego.get('entity_id')}_{v.get('entity_id')}",
                    'entity_type': EntityType.SAFETY_VIOLATION,
                    'rule_code': 'RSS_LONG',
                    'severity': 'HIGH',
                    'message': f"后车与前车距离 {distance:.1f}m 小于安全距离 {d_min:.1f}m",
                    'evidence': {
                        'ego_id': ego.get('entity_id'),
                        'npc_id': v.get('entity_id'),
                        'distance': float(distance),
                        'd_min': float(d_min),
                        'ego_speed': float(ego.get('speed', 0)),
                        'npc_speed': float(v.get('speed', 0)),
                    }
                })
        
        return violations
    
    def _check_traffic_rules(self, scene_snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """交规规则检查"""
        violations = []
        vehicles = scene_snapshot.get('vehicles', [])
        traffic_lights = scene_snapshot.get('traffic_lights', [])
        
        # 检查闯红灯 (R2)
        tl_violations = self._check_red_light(vehicles, traffic_lights)
        violations.extend(tl_violations)
        
        return violations
    
    def _check_red_light(self, vehicles: List[Dict], 
                         traffic_lights: List[Dict]) -> List[Dict[str, Any]]:
        """
        检查闯红灯行为
        
        简化实现：检测红灯附近的车辆
        """
        violations = []
        
        for v in vehicles:
            if v.get('role_name') != 'ego':
                continue
            
            # 查找最近的红灯
            for tl in traffic_lights:
                if tl.get('state') != 'Red':
                    continue
                
                dx = tl['x'] - v['x']
                dy = tl['y'] - v['y']
                distance = np.sqrt(dx**2 + dy**2)
                
                # 如果在红灯附近且车速较快，可能是闯红灯
                if distance < 5.0 and v.get('speed', 0) > 2.0:
                    violations.append({
                        'entity_id': f"sv_r2_{v.get('entity_id')}_{tl.get('entity_id')}",
                        'entity_type': EntityType.SAFETY_VIOLATION,
                        'rule_code': 'R2_RED_LIGHT',
                        'severity': 'CRITICAL',
                        'message': f"自车在红灯 {distance:.1f}m 处以 {v.get('speed', 0):.1f}m/s 行驶",
                        'evidence': {
                            'ego_id': v.get('entity_id'),
                            'tl_id': tl.get('entity_id'),
                            'distance': float(distance),
                            'ego_speed': float(v.get('speed', 0)),
                        }
                    })
        
        return violations
    
    def _check_predicted_collisions(self, physics_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """检查物理引擎预测的碰撞"""
        violations = []
        
        for collision in physics_results.get('collisions', []):
            violations.append({
                'entity_id': f"sv_collision_{collision.get('frame_id', 0)}",
                'entity_type': EntityType.SAFETY_VIOLATION,
                'rule_code': 'PREDICTED_COLLISION',
                'severity': 'CRITICAL',
                'message': collision.get('message', '预测碰撞'),
                'evidence': collision,
            })
        
        return violations
    
    def _compute_rss_distance(self, v_a: float, v_b: float, 
                              rho: float, a_max_accel: float,
                              a_min_brake: float, a_brake: float) -> float:
        """
        计算 RSS 纵向安全距离
        
        公式:
        d_min = max(0, v_a * rho + 0.5 * a_max_accel * rho² + 
                   (v_a + a_max_accel * rho)² / (2 * a_min_brake) - 
                   v_b² / (2 * a_brake))
        """
        term1 = v_a * rho
        term2 = 0.5 * a_max_accel * (rho ** 2)
        term3 = (v_a + a_max_accel * rho) ** 2 / (2 * a_min_brake)
        term4 = (v_b ** 2) / (2 * a_brake)
        
        d_min = max(0, term1 + term2 + term3 - term4)
        
        return d_min


def create_rule_enforcer() -> RuleEnforcer:
    """工厂函数：创建规则引擎"""
    return RuleEnforcer()