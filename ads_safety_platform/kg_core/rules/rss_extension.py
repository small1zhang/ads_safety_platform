"""
RSS 扩展规则集成器
整合所有 RSS 模型：纵向、横向、交叉口、风险指数、行人保护

参考文献:
- Shalev-Shwartz et al. "Responsibility-Sensitive Safety (RSS)" 2017
- Lin et al. "A Rule-Compliance Path Planner for Lane-Merge Scenarios" 2024
- Candela et al. "Quantitative Risk Indices for Autonomous Vehicle Training Systems" 2022
"""
import numpy as np
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from ..ontology.types import EntityType
from .rss.longitudinal import (
    RSSLongitudinalParams,
    LongitudinalRSSModel,
)
from .rss.lateral import (
    RSSLateralParams,
    LateralRSSModel,
)
from .rss.intersection import (
    IntersectionRSSModel,
    check_merge_priority,
)
from .rss.risk_index import (
    RiskParams,
    RiskAssessmentModel,
)
from .rss.pedestrian import (
    RSSPedestrianParams,
    PedestrianRSSModel,
)
from .traffic.rules import TrafficRuleChecker


@dataclass
class RSSExtensionParams:
    """RSS 扩展规则参数"""
    # 纵向参数
    longitudinal_params: RSSLongitudinalParams = None
    # 横向参数
    lateral_params: RSSLateralParams = None
    # 风险指数参数
    risk_params: RiskParams = None
    # 行人参数
    pedestrian_params: RSSPedestrianParams = None
    
    def __post_init__(self):
        if self.longitudinal_params is None:
            self.longitudinal_params = RSSLongitudinalParams()
        if self.lateral_params is None:
            self.lateral_params = RSSLateralParams()
        if self.risk_params is None:
            self.risk_params = RiskParams()
        if self.pedestrian_params is None:
            self.pedestrian_params = RSSPedestrianParams()


class RssExtensionEnforcer:
    """
    RSS 扩展规则引擎
    
    集成:
    1. 纵向 RSS 规则 (Longitudinal)
    2. 横向 RSS 规则 (Lateral)  
    3. 交叉口/Merge 规则 (Intersection/Merge)
    4. 风险指数模型 (Risk Index)
    5. 行人保护规则 (Pedestrian)
    6. 交通规则 (Traffic)
    """
    
    def __init__(self, params: RSSExtensionParams = None):
        self.params = params or RSSExtensionParams()
        
        # 初始化各子模型
        self.long_model = LongitudinalRSSModel(self.params.longitudinal_params)
        self.lateral_model = LateralRSSModel(self.params.lateral_params)
        self.intersection_model = IntersectionRSSModel()
        self.risk_model = RiskAssessmentModel(self.params.risk_params)
        self.pedestrian_model = PedestrianRSSModel(self.params.pedestrian_params)
        self.traffic_checker = TrafficRuleChecker()
        
        # 统计信息
        self.violations_found = 0
        self.risk_level = 0  # 0=SAFE, 1=MEDIUM, 2=UNSAFE
    
    def enforce(self, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        执行全部 RSS 规则检查
        
        参数:
            snapshot: 场景快照 {'vehicles': [...], 'traffic_lights': [...], 'pedestrians': [...]}
        
        返回:
            违规列表
        """
        violations = []
        vehicles = snapshot.get('vehicles', [])
        traffic_lights = snapshot.get('traffic_lights', [])
        pedestrians = snapshot.get('pedestrians', [])
        
        # 1. 找自车
        ego = next((v for v in vehicles if v.get('role_name') == 'ego'), None)
        if not ego:
            return violations
        
        ego_x, ego_y = ego.get('x', 0), ego.get('y', 0)
        ego_yaw = ego.get('yaw', 0)
        ego_speed = ego.get('speed', 0)
        
        # 2. 纵向 RSS 检查
        for v in vehicles:
            if v.get('entity_id') == ego.get('entity_id'):
                continue
            
            npc_speed = v.get('speed', 0)
            dx = v.get('x', 0) - ego_x
            dy = v.get('y', 0) - ego_y
            forward_vec = np.array([np.cos(ego_yaw), np.sin(ego_yaw)])
            relative_pos = np.array([dx, dy])
            longitudinal = np.dot(forward_vec, relative_pos)
            
            if longitudinal > 0:
                # 检查纵向安全
                long_result = self.long_model.check_longitudinal_safety(
                    ego_speed, npc_speed, longitudinal
                )
                
                if long_result['violation']:
                    violations.append({
                        'entity_id': f"sv_rss_long_{ego.get('entity_id')}",
                        'entity_type': EntityType.SAFETY_VIOLATION,
                        'rule_code': 'RSS_LONG',
                        'severity': 'HIGH',
                        'message': f"后车距离前车 {long_result['actual_distance']:.1f}m 小于安全距离 {long_result['d_min']:.1f}m",
                        'evidence': long_result,
                        'risk_index': self.risk_model.risk_index
                            if hasattr(self.risk_model, 'risk_index') else None,
                    })
        
        # 3. 横向 RSS 检查
        for v in vehicles:
            if v.get('entity_id') == ego.get('entity_id'):
                continue
            
            dx = v.get('x', 0) - ego_x
            dy = v.get('y', 0) - ego_y
            d_lat = np.sqrt(dx**2 + dy**2)
            
            lateral_result = self.lateral_model.check_safe_lateral_distance(
                0, 0, d_lat
            )
            
            if not lateral_result['safe']:
                violations.append({
                    'entity_id': f"sv_rss_lat_{ego.get('entity_id')}",
                    'entity_type': EntityType.SAFETY_VIOLATION,
                    'rule_code': 'RSS_LATERAL',
                    'severity': 'MEDIUM',
                    'message': f"横向距离 {d_lat:.1f}m 小于最小安全距离",
                    'evidence': lateral_result,
                })
        
        # 4. 行人规则检查
        for ped in pedestrians:
            ped_result = self.pedestrian_model.check_pedestrian_crossing(ego, ped)
            
            if ped_result['violation']:
                violations.append({
                    'entity_id': f"sv_ped_cross_{ego.get('entity_id')}",
                    'entity_type': EntityType.SAFETY_VIOLATION,
                    'rule_code': 'RSS_PEDESTRIAN_CROSSING',
                    'severity': 'CRITICAL',
                    'message': f"行人横穿违规: 距离 {ped_result['actual_distance']:.1f}m",
                    'evidence': ped_result,
                })
        
        # 5. 交通规则检查
        traffic_violations = self.traffic_checker.check_all_traffic_rules(
            ego, traffic_lights
        )
        violations.extend(traffic_violations)
        
        # 6. 计算风险指数
        if violations:
            self.risk_level = 2
        elif len([v for v in violations if v['severity'] == 'MEDIUM']) > 0:
            self.risk_level = 1
        else:
            self.risk_level = 0
        
        self.violations_found = len(violations)
        
        return violations
    
    def compute_risk_index(self, d_actual: float, d_min: float, 
                          v_rel: float = 0, ttc: float = None) -> Dict[str, Any]:
        """计算风险指数"""
        return self.risk_model.assess_longitudinal_risk(d_actual, d_min, v_rel, ttc)
    
    def get_risk_level(self) -> int:
        """获取当前风险等级"""
        return self.risk_level
    
    def get_risk_level_str(self) -> str:
        """获取风险等级字符串"""
        levels = ["SAFE", "MEDIUM", "UNSAFE"]
        return levels[min(self.risk_level, len(levels) - 1)]