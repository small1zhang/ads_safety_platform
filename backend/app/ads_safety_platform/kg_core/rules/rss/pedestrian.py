"""
RSS 行人/弱势道路使用者保护模型

参考文献:
- RSS 模型应用于 VRU (Vulnerable Road Users)
- Candela et al. "Quantitative Risk Indices for Autonomous Vehicle Training Systems" (2022)

实现以下规则:
1. RSS_PEDESTRIAN_CROSSING - 行人横穿道路
2. RSS_PEDESTRIAN_PROXIMITY - 行人在车道附近
3. RSS_YIELD_TO_PEDESTRIAN - 礼让行人规则
4. RSS_APPROACHING_PEDESTRIAN - 接近行人
"""
import numpy as np
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class RSSPedestrianParams:
    """RSS 行人保护参数"""
    d_min_pedestrian_crossing: float = 5.0   # 行人横穿时最小安全距离 (m)
    d_min_pedestrian_nearby: float = 3.0      # 行人在附近时的最小距离 (m)
    d_min_yield_zone: float = 5.0             # 礼让区域距离 (m)
    a_min_brake: float = 4.0                  # 最小制动减速度 (m/s²)
    rho: float = 0.5                          # 反应时间 (s)


def compute_pedestrian_crossing_distance(v_ego: float,
                                         v_ped: float,
                                         params: RSSPedestrianParams) -> float:
    """
    计算行人横穿时的安全距离
    
    基于 RSS 公式，考虑到行人的不确定行为
    """
    d_brake = (v_ego ** 2) / (2 * params.a_min_brake)
    d_reaction = v_ego * params.rho
    
    # 行人横穿安全距离 = 制动距离 + 反应距离 + 额外安全边距
    d_min = d_brake + d_reaction + params.d_min_pedestrian_crossing
    
    return d_min


def compute_yield_distance(v_ego: float,
                          v_ped: float,
                          crossing_angle: float,
                          params: RSSPedestrianParams) -> float:
    """
    计算礼让距离 (当行人横穿时)
    
    参数:
        v_ego: 自车速度 (m/s)
        v_ped: 行人速度 (m/s)
        crossing_angle: 行人横穿角度 (度)
        params: RSS参数
    
    返回:
        需要开始减速的距离 (m)
    """
    # 如果行人正在横穿或准备横穿
    if abs(crossing_angle) > 30 and abs(crossing_angle) < 150:
        # 行人横向移动
        d_min = compute_pedestrian_crossing_distance(v_ego, v_ped, params)
        return d_min
    
    return params.d_min_pedestrian_nearby


class PedestrianRSSModel:
    """
    RSS 行人保护模型
    
    实现以下规则:
    1. 行人横穿道路
    2. 行人在车道附近
    3. 礼让行人规则
    """
    
    def __init__(self, params: RSSPedestrianParams = None):
        self.params = params or RSSPedestrianParams()
    
    def check_pedestrian_crossing(self,
                                  ego_state: Dict[str, Any],
                                  ped_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查行人横穿道路规则 (RSS_PEDESTRIAN_CROSSING)
        
        条件:
        1. 行人在道路上或即将进入道路
        2. 行人与自车轨迹相交
        3. 自车需要礼让
        
        返回:
            {
                'violation': bool,
                'should_yield': bool,
                'safe_distance': float,
                'actual_distance': float,
                'rule_code': str
            }
        """
        # 计算距离
        dx = ped_state.get('x', 0) - ego_state.get('x', 0)
        dy = ped_state.get('y', 0) - ego_state.get('y', 0)
        d_actual = np.sqrt(dx ** 2 + dy ** 2)
        
        # 计算安全距离
        v_ego = ego_state.get('speed', 0)
        v_ped = ped_state.get('speed', 0)
        
        d_min = compute_pedestrian_crossing_distance(v_ego, v_ped, self.params)
        
        # 检查是否违规
        violation = d_actual < d_min and v_ego > 1.0
        
        return {
            'violation': violation,
            'should_yield': violation,
            'safe_distance': d_min,
            'actual_distance': d_actual,
            'rule_code': 'RSS_PEDESTRIAN_CROSSING',
            'ego_speed': v_ego,
            'ped_speed': v_ped,
        }
    
    def check_pedestrian_proximity(self,
                                   ego_state: Dict[str, Any],
                                   ped_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查行人是否在车道附近 (RSS_PEDESTRIAN_PROXIMITY)
        
        条件:
        1. 行人在车道附近 (< d_min_pedestrian_nearby)
        2. 自车速度 > 阈值
        
        返回:
            {
                'proximity_alert': bool,
                'distance': float,
                'rule_code': str
            }
        """
        dx = ped_state.get('x', 0) - ego_state.get('x', 0)
        dy = ped_state.get('y', 0) - ego_state.get('y', 0)
        d_actual = np.sqrt(dx ** 2 + dy ** 2)
        
        v_ego = ego_state.get('speed', 0)
        
        proximity_alert = d_actual < self.params.d_min_pedestrian_nearby and v_ego > 0.5
        
        return {
            'proximity_alert': proximity_alert,
            'distance': d_actual,
            'rule_code': 'RSS_PEDESTRIAN_PROXIMITY',
            'ego_speed': v_ego,
        }
    
    def check_yield_to_pedestrian(self,
                                  ego_state: Dict[str, Any],
                                  ped_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查礼让行人规则 (RSS_YIELD_TO_PEDESTRIAN)
        
        条件:
        1. 行人在人行横道上或接近人行横道
        2. 行人已经开始或准备横穿
        3. 自车没有礼让
        
        返回:
            {
                'violation': bool,
                'should_yield': bool,
                'crossing_angle': float,  # 行人横穿角度
                'rule_code': str
            }
        """
        # 计算行人的移动方向
        dx = ped_state.get('x', 0) - ego_state.get('x', 0)
        dy = ped_state.get('y', 0) - ego_state.get('y', 0)
        d_actual = np.sqrt(dx ** 2 + dy ** 2)
        
        # 计算自车和行人的方向
        ego_yaw = ego_state.get('yaw', 0)
        ped_yaw = ped_state.get('yaw', 0)
        
        # 简化：计算相对方位角
        # 如果行人的轨迹与自车轨迹相交
        ego_dir = np.array([np.cos(ego_yaw), np.sin(ego_yaw)])
        ped_dir = np.array([np.cos(ped_yaw), np.sin(ped_yaw)])
        
        rel_pos = np.array([dx, dy])
        
        # 检查行人是否在自车前方
        forward_dist = np.dot(ego_dir, rel_pos / max(d_actual, 1e-6)) if d_actual > 0 else 0
        
        # 计算横穿角度
        crossing_angle = 0
        if d_actual > 0:
            crossing_angle = np.degrees(np.arccos(
                np.clip(np.dot(ego_dir, ped_dir / np.linalg.norm(ped_dir)), -1, 1)
            ))
        
        # 判断是否需要礼让
        should_yield = (
            forward_dist > 0 and  # 行人在前方
            d_actual < self.params.d_min_yield_zone and  # 在礼让区域内
            abs(crossing_angle) > 30  # 横穿角度在30-150度之间
        )
        
        violation = should_yield and ego_state.get('speed', 0) > 0.5
        
        return {
            'violation': violation,
            'should_yield': should_yield,
            'crossing_angle': crossing_angle,
            'distance': d_actual,
            'rule_code': 'RSS_YIELD_TO_PEDESTRIAN',
            'ego_speed': ego_state.get('speed', 0),
            'ped_speed': ped_state.get('speed', 0),
        }
    
    def check_approaching_pedestrian(self,
                                     ego_state: Dict[str, Any],
                                     ped_state: Dict[str, Any],
                                     distance_threshold: float = 15.0) -> Dict[str, Any]:
        """
        检查接近行人 (RSS_APPROACHING_PEDESTRIAN)
        
        条件:
        1. 行人在距离阈值内
        2. 自车速度 > 行人速度
        3. 时间到碰撞 (TTC) < 阈值
        
        返回:
            {
                'dangerous': bool,
                'distance': float,
                'ttc': float,
                'rule_code': str
            }
        """
        dx = ped_state.get('x', 0) - ego_state.get('x', 0)
        dy = ped_state.get('y', 0) - ego_state.get('y', 0)
        d_actual = np.sqrt(dx ** 2 + dy ** 2)
        
        v_ego = ego_state.get('speed', 0)
        v_ped = ped_state.get('speed', 0)
        
        if v_ego <= v_ped:
            return {
                'dangerous': False,
                'distance': d_actual,
                'ttc': float('inf'),
                'rule_code': 'RSS_APPROACHING_PEDESTRIAN',
            }
        
        # 计算 TTC
        ttc = d_actual / (v_ego - v_ped) if (v_ego - v_ped) > 0 else float('inf')
        
        dangerous = d_actual < distance_threshold and ttc < 5.0
        
        return {
            'dangerous': dangerous,
            'distance': d_actual,
            'ttc': ttc,
            'rule_code': 'RSS_APPROACHING_PEDESTRIAN',
            'ego_speed': v_ego,
            'ped_speed': v_ped,
        }


def compute_pedestrian_risk_index(d_actual: float,
                                 v_rel: float,
                                 ttc: float = None,
                                 params: RSSPedestrianParams = None) -> float:
    """
    计算行人的风险指数
    
    参数:
        d_actual: 实际距离 (m)
        v_rel: 相对速度 (m/s)
        ttc: 碰撞时间 (s)
        params: RSS参数
    
    返回:
        RI: 风险指数 [0, 1]
    """
    if params is None:
        params = RSSPedestrianParams()
    
    # 基于距离的风险
    if d_actual <= 0:
        return 1.0
    
    if d_actual >= params.d_min_pedestrian_nearby:
        return 0.0
    
    # 指数风险模型
    ratio = params.d_min_pedestrian_nearby / d_actual
    RI = 1.0 - np.exp(-2.0 * (ratio - 1.0))
    
    # 结合 TTC
    if ttc is not None and ttc < 5.0:
        ttc_factor = max(0, 1.0 - ttc / 5.0)
        RI = max(RI, ttc_factor)
    
    return min(1.0, RI)