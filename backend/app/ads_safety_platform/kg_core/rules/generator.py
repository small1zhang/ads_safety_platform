"""
规则引擎生成器 (v3 §4.3)
集成 RSS 纵向安全距离模型和交规规则
参考文献: 
- Shalev-Shwartz et al. "Responsibility-Sensitive Safety (RSS)" 2017
- Rizaldi et al. "Towards a Logic-Based Approach to Formal Verification of ADS" 2017
"""
import numpy as np
from typing import Dict, Any, List, Optional

from ..ontology.types import EntityType, RuleRelationType
from ..scenario.nodes import SafetyViolation
from .rss.model import RSSSafetyChecker, RSSParams, compute_d_min_long, compute_d_min_lat
from .traffic.rules import TrafficRuleChecker


class RuleEnforcer:
    """
    规则融合引擎
    
    将物理引擎（轨迹预测）与逻辑引擎（交规规则）统一到图结构中
    
    参考文献:
    - Shalev-Shwartz et al. "Responsibility-Sensitive Safety (RSS)" 2017
    - Rizaldi et al. "Towards a Logic-Based Approach to Formal Verification of ADS" 2017
    """
    
    def __init__(self, rss_params: RSSParams = None):
        # RSS 参数 (参考 Mobileye RSS 配置)
        self.rss_params = rss_params or RSSParams(
            rho=0.5,           # 反应时间 (s)
            a_max_accel=2.0,   # 后车最大加速 (m/s²)
            a_min_brake=4.0,   # 后车最小制动 (m/s²)
            a_brake=8.0,       # 前车最大制动 (m/s²)
        )
        
        # RSS 安全检查器
        self.rss_checker = RSSSafetyChecker(self.rss_params)
        
        # 交通规则检查器
        self.traffic_checker = TrafficRuleChecker()
    
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
        
        # 2. 交通规则检查
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
        RSS 安全距离检查 (基于 RSS 标准)
        
        参考文献: Shalev-Shwartz et al. 2017
        
        实现:
        1. 纵向安全距离检查
        2. 横向安全距离检查
        3. 反应不当检测
        4. TTC 检测
        """
        violations = []
        vehicles = scene_snapshot.get('vehicles', [])
        
        # 找出自车
        ego = next((v for v in vehicles if v.get('role_name') == 'ego'), None)
        if not ego:
            return violations
        
        ego_x, ego_y = ego.get('x', 0), ego.get('y', 0)
        ego_yaw = ego.get('yaw', 0)
        ego_speed = ego.get('speed', 0)
        
        # 检查所有其他车辆
        for v in vehicles:
            if v.get('entity_id') == ego.get('entity_id'):
                continue
            
            npc_x, npc_y = v.get('x', 0), v.get('y', 0)
            npc_speed = v.get('speed', 0)
            
            # 计算距离
            dx = npc_x - ego_x
            dy = npc_y - ego_y
            distance = np.sqrt(dx**2 + dy**2)
            
            # 简化：如果 NPC 在ego前面
            forward_vec = np.array([np.cos(ego_yaw), np.sin(ego_yaw)])
            relative_pos = np.array([dx, dy])
            longitudinal = np.dot(forward_vec, relative_pos)
            
            if longitudinal > 0:  # NPC 在 ego 前方
                # 1. 纵向安全距离检查
                long_result = self.rss_checker.check_longitudinal_safety(
                    ego_speed=ego_speed,
                    npc_speed=npc_speed,
                    actual_distance=longitudinal
                )
                
                if long_result['violation']:
                    violations.append({
                        'entity_id': f"sv_rss_{ego.get('entity_id')}_{v.get('entity_id')}",
                        'entity_type': EntityType.SAFETY_VIOLATION,
                        'rule_code': 'RSS_LONG',
                        'severity': 'HIGH',
                        'message': f"后车与前车距离 {long_result['actual_distance']:.1f}m 小于安全距离 {long_result['d_min']:.1f}m",
                        'evidence': {
                            'ego_id': ego.get('entity_id'),
                            'npc_id': v.get('entity_id'),
                            'actual_distance': float(long_result['actual_distance']),
                            'd_min': float(long_result['d_min']),
                            'margin': float(long_result['margin']),
                            'ego_speed': float(ego_speed),
                            'npc_speed': float(npc_speed),
                        }
                    })
                
                # 2. 反应不当检查
                proper_response = self.rss_checker.check_proper_response(
                    ego_speed=ego_speed,
                    npc_speed=npc_speed,
                    actual_distance=longitudinal,
                )
                
                if not proper_response['proper_response']:
                    violations.append({
                        'entity_id': f"sv_rr_{ego.get('entity_id')}_{v.get('entity_id')}",
                        'entity_type': EntityType.SAFETY_VIOLATION,
                        'rule_code': 'RSS_PROPER_RESPONSE',
                        'severity': 'HIGH',
                        'message': f"反应不当: 实际距离 {longitudinal:.1f}m 小于要求的 {proper_response['d_min_long']:.1f}m",
                        'evidence': {
                            'ego_id': ego.get('entity_id'),
                            'npc_id': v.get('entity_id'),
                            'actual_distance': float(longitudinal),
                            'd_min_long': float(proper_response['d_min_long']),
                            'ego_speed': float(ego_speed),
                            'npc_speed': float(npc_speed),
                        }
                    })
                
                # 3. TTC 检查
                ttc_result = self.rss_checker.check_ttc(
                    ego_speed=ego_speed,
                    npc_speed=npc_speed,
                    distance=longitudinal,
                    ttc_threshold=3.0  # 3秒阈值
                )
                
                if ttc_result['violation']:
                    violations.append({
                        'entity_id': f"sv_ttc_{ego.get('entity_id')}_{v.get('entity_id')}",
                        'entity_type': EntityType.SAFETY_VIOLATION,
                        'rule_code': 'RSS_TTC',
                        'severity': 'CRITICAL',
                        'message': f"碰撞时间过短: TTC={ttc_result['ttc']:.1f}s < 阈值 {ttc_result['threshold']}s",
                        'evidence': {
                            'ego_id': ego.get('entity_id'),
                            'npc_id': v.get('entity_id'),
                            'ttc': float(ttc_result['ttc']),
                            'threshold': float(ttc_result['threshold']),
                            'ego_speed': float(ego_speed),
                            'npc_speed': float(npc_speed),
                        }
                    })
        
        return violations
    
    def _check_traffic_rules(self, scene_snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """交通规则检查"""
        violations = []
        vehicles = scene_snapshot.get('vehicles', [])
        traffic_lights = scene_snapshot.get('traffic_lights', [])
        
        # 使用交通规则检查器
        traffic_violations = self.traffic_checker.check_all_traffic_rules(
            ego=next((v for v in vehicles if v.get('role_name') == 'ego'), {}),
            traffic_lights=traffic_lights
        )
        violations.extend(traffic_violations)
        
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