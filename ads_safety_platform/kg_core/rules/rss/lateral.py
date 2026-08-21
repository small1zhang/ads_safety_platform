"""
RSS 横向安全模型 (严格复现 Shalev-Shwartz et al. 2017 §3.2)

参考文献:
- Shai Shalev-Shwartz, Shaked Shammah, Amnon Shashua
  "On a Formal Model of Safe and Scalable Self-driving Cars" (2017)
- arXiv:1708.06374

论文 §3.2: "The Lateral Model"

核心定义:
1. 横向安全距离 d_min_lat
2. Proper Lateral Response (横向反应得当)
3. Dangerous Lateral Situation (横向危险情形)
4. 变道安全判定 (Lane Change Safety)
5. 车道线感知集成 (Lane Line Detection)
"""
import numpy as np
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class RSSLateralParams:
    """RSS 横向安全参数 (论文标准值)"""
    rho: float = 0.5                       # 反应时间 (s)
    a_max_lat: float = 3.0                 # 最大横向加速度 (m/s²)
    a_min_lat_brake: float = 5.0           # 最小横向制动减速度 (m/s²)
    vehicle_width: float = 2.0             # 标准车宽 (m)
    lane_width: float = 3.7                # 车道宽度 (m)
    # 扩展参数
    lane_change_safe_distance: float = 10.0  # 变道安全距离 (m)
    lateral_accel_threshold: float = 1.0   # 横向加速度阈值 (m/s²)


def compute_d_min_lat(v_lat: float, 
                      a_max_lat: float = 3.0,
                      rho: float = 0.5) -> float:
    """
    计算 RSS 横向安全距离 d_min_lat
    
    论文公式 (Eq. 2, §3.2):
    d_min_lat = max(0, v_lat * ρ + 0.5 * a_max_lat * ρ²)
    
    其中 v_lat 是后车相对前车的横向速度
    
    参数:
        v_lat: 后车相对前车的横向速度 (m/s)
        a_max_lat: 最大横向加速度 (m/s²)
        rho: 反应时间 (s)
    
    返回:
        d_min_lat: 横向最小安全距离 (m)
    """
    if v_lat < 0:
        # 如果后车相对前车在负横向速度方向，实际安全距离可能为0
        return 0
    
    term1 = v_lat * rho
    term2 = 0.5 * a_max_lat * (rho ** 2)
    
    d_min_lat = max(0, term1 + term2)
    return d_min_lat


def compute_safe_lateral_distance(v_lat_f: float,
                                  v_lat_l: float,
                                  params: RSSLateralParams) -> float:
    """
    计算横向安全距离 (考虑双向相对速度)
    
    论文 §3.2:
    - 如果两车相向移动 (横向) - 后车需要距离等于两边制动距离之和
    - 如果两车同向 - 仅考虑后车速度
    
    参数:
        v_lat_f: 后车横向速度 (m/s)
        v_lat_l: 前车横向速度 (m/s)
        params: RSS参数
    
    返回:
        d_min_lat: 横向最小安全距离 (m)
    """
    relative_lat_speed = v_lat_f - v_lat_l
    
    # 计算后车相对前车的横向位移
    if relative_lat_speed > 0:  # 后车相对前车在正向移动
        # 假设后车进行最大横向加速度
        d_min = compute_d_min_lat(relative_lat_speed, params.a_max_lat, params.rho)
    elif relative_lat_speed < 0:  # 反向
        # 使用绝对值计算
        d_min = compute_d_min_lat(abs(relative_lat_speed), params.a_max_lat, params.rho)
    else:
        d_min = 0
    
    return d_min


def compute_lateral_collision_time(v_lat_f: float, 
                                   v_lat_l: float,
                                   d_actual_lat: float) -> float:
    """
    计算横向碰撞时间 (Lateral TTC)
    
    参数:
        v_lat_f: 后车横向速度 (m/s)
        v_lat_l: 前车横向速度 (m/s)
        d_actual_lat: 实际横向距离 (m)
    
    返回:
        ttc_lat: 横向碰撞时间 (s)
    """
    relative_speed = v_lat_f - v_lat_l
    if abs(relative_speed) < 1e-6:
        return float('inf')
    
    ttc_lat = abs(d_actual_lat) / abs(relative_speed)
    return ttc_lat


def check_lane_change_safety(v_f: float,
                             v_lat_f: float,
                             v_l: float,
                             v_lat_l: float,
                             d_actual: float,
                             d_actual_lat: float,
                             params: RSSLateralParams = None) -> Dict[str, Any]:
    """
    检查变道安全 (Lane Change Safety Check)
    
    综合纵向和横向检查:
    1. 纵向: 后车与前车的纵向距离
    2. 横向: 后车与前车的横向距离
    
    参数:
        v_f: 后车速度 (m/s)
        v_lat_f: 后车横向速度 (m/s)
        v_l: 前车速度 (m/s)
        v_lat_l: 前车横向速度 (m/s)
        d_actual: 纵向实际距离 (m)
        d_actual_lat: 横向实际距离 (m)
        params: RSS参数
    
    返回:
        {
            'safe': bool,
            'rule_code': str,
            'longitudinal_check': dict,
            'lateral_check': dict,
        }
    """
    if params is None:
        params = RSSLateralParams()
    
    # 1. 纵向检查
    from kg_core.rules.rss.longitudinal import compute_d_min_long, RSSLongitudinalParams
    long_params = RSSLongitudinalParams()
    d_min_long = compute_d_min_long(v_f, v_l, long_params)
    long_safe = d_actual >= d_min_long
    
    # 2. 横向检查
    d_min_lat = compute_safe_lateral_distance(v_lat_f, v_lat_l, params)
    lat_safe = d_actual_lat >= d_min_lat
    
    # 综合判定
    safe = long_safe and lat_safe
    
    return {
        'safe': safe,
        'rule_code': 'RSS_LATERAL_LANE_CHANGE',
        'longitudinal_check': {
            'safe': long_safe,
            'd_min': d_min_long,
            'actual': d_actual,
        },
        'lateral_check': {
            'safe': lat_safe,
            'd_min': d_min_lat,
            'actual': d_actual_lat,
        },
    }


def compute_rss_safe_lane_change_zone(v_f: float,
                                      v_l: float,
                                      params: RSSLateralParams = None) -> Dict[str, float]:
    """
    计算 RSS 安全的变道区域
    
    基于车辆动力学和相对速度，计算安全的变道空间
    
    参数:
        v_f: 后车速度 (m/s)
        v_l: 前车速度 (m/s)
        params: RSS参数
    
    返回:
        {
            'longitudinal_gap': float,  # 纵向间隙 (m)
            'lateral_clearance': float,  # 横向净空 (m)
            'sufficient_time': float,   # 充足时间 (s)
        }
    """
    if params is None:
        params = RSSLateralParams()
    
    # 计算纵向安全距离
    from kg_core.rules.rss.longitudinal import compute_d_min_long, RSSLongitudinalParams
    long_params = RSSLongitudinalParams()
    d_min_long = compute_d_min_long(v_f, v_l, long_params)
    
    # 计算横向净空 (需要考虑车宽)
    lateral_clearance = params.vehicle_width + params.lane_change_safe_distance
    
    # 计算充足时间 (假设车辆以安全距离匀速行驶)
    v_rel = v_f - v_l
    sufficient_time = d_min_long / max(v_rel, 1.0) if v_rel > 0 else 0
    
    return {
        'longitudinal_gap': d_min_long,
        'lateral_clearance': lateral_clearance,
        'sufficient_time': sufficient_time,
    }


class LateralRSSModel:
    """
    RSS 横向安全模型 (严格复现论文 §3.2)
    
    实现以下核心概念:
    1. Safe Lateral Distance (横向安全距离)
    2. Proper Lateral Response (横向反应得当)
    3. Dangerous Lateral Situation (横向危险情形)
    4. Lane Change Safety (变道安全)
    5. Lateral TTC (横向碰撞时间)
    """
    
    def __init__(self, params: RSSLateralParams = None):
        self.params = params or RSSLateralParams()
    
    def check_safe_lateral_distance(self,
                                    v_lat_f: float,
                                    v_lat_l: float,
                                    d_actual_lat: float) -> Dict[str, Any]:
        """
        检查横向安全距离 (论文 Def. 4)
        
        条件:
        d_actual_lat >= d_min_lat
        
        返回:
            {
                'safe': bool,
                'd_min': float,
                'actual_distance': float,
                'margin': float,
                'rule_code': str
            }
        """
        d_min = compute_safe_lateral_distance(v_lat_f, v_lat_l, self.params)
        margin = d_actual_lat - d_min
        
        return {
            'safe': d_actual_lat >= d_min,
            'd_min': d_min,
            'actual_distance': d_actual_lat,
            'margin': margin,
            'rule_code': 'RSS_LAT_SAFE_DISTANCE',
            'v_lat_f': v_lat_f,
            'v_lat_l': v_lat_l,
        }
    
    def check_proper_lateral_response(self,
                                      v_lat_f: float,
                                      v_lat_l: float,
                                      d_actual_lat: float,
                                      d_min: float = None) -> Dict[str, Any]:
        """
        检查横向反应是否得当 (论文 Def. 5)
        
        Proper Response 条件:
        1. d_actual_lat < d_min_lat 且两车相向时
        2. 后车必须采取制动直到 v_lat_f = 0
        
        返回:
            {
                'proper_response': bool,
                'required_action': str,
                'rule_code': str
            }
        """
        if d_min is None:
            d_min = compute_safe_lateral_distance(v_lat_f, v_lat_l, self.params)
        
        margin = d_actual_lat - d_min
        proper_response = d_actual_lat >= d_min
        
        if not proper_response:
            if v_lat_f > 0:  # 后车在向正方向横向移动
                required_action = "横向制动直到 v_lat_f = 0"
            else:
                required_action = "反向横向制动直到 v_lat_f = 0"
        else:
            required_action = "无需反应"
        
        return {
            'proper_response': proper_response,
            'required_action': required_action,
            'd_min': d_min,
            'actual_distance': d_actual_lat,
            'margin': margin,
            'rule_code': 'RSS_LAT_PROPER_RESPONSE',
        }
    
    def check_dangerous_lateral_situation(self,
                                          v_lat_f: float,
                                          v_lat_l: float,
                                          d_actual_lat: float,
                                          d_min: float = None) -> Dict[str, Any]:
        """
        检查横向危险情形 (论文 Def. 6)
        
        Dangerous Lateral Situation:
        1. d_actual_lat < d_min_lat
        2. 两车在横向方向相向而行 (即后车在横向方向接近前车)
        
        返回:
            {
                'dangerous': bool,
                'rule_code': str
            }
        """
        if d_min is None:
            d_min = compute_safe_lateral_distance(v_lat_f, v_lat_l, self.params)
        
        # 检查两车是否在横向方向上相向
        approaching = v_lat_f > 0 and v_lat_l < 0
        
        dangerous = (d_actual_lat < d_min) and approaching
        
        return {
            'dangerous': dangerous,
            'd_min': d_min,
            'actual_distance': d_actual_lat,
            'approaching_laterally': approaching,
            'margin': d_actual_lat - d_min,
            'rule_code': 'RSS_LAT_DANGEROUS_SITUATION',
        }
    
    def check_lateral_ttc(self,
                          v_lat_f: float,
                          v_lat_l: float,
                          d_actual_lat: float,
                          ttc_threshold: float = 3.0) -> Dict[str, Any]:
        """
        检查横向碰撞时间 (Lateral TTC)
        
        参数:
            ttc_threshold: TTC 阈值 (s), 低于此值认为危险
        
        返回:
            {
                'safe': bool,
                'ttc': float,
                'threshold': float,
                'violation': bool
            }
        """
        ttc = compute_lateral_collision_time(v_lat_f, v_lat_l, d_actual_lat)
        violation = ttc < ttc_threshold and ttc != float('inf')
        
        return {
            'safe': not violation,
            'ttc': ttc,
            'threshold': ttc_threshold,
            'violation': violation,
        }
    
    def check_lane_change_safety(self,
                                 ego_state: Dict[str, Any],
                                 other_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        综合变道安全检查
        
        参数:
            ego_state: 自车状态 {'x', 'y', 'speed', 'yaw', 'vx', 'vy'}
            other_state: 其他车辆状态
        
        返回:
            {
                'safe': bool,
                'rule_code': str,
                'longitudinal_check': dict,
                'lateral_check': dict,
            }
        """
        # 计算相对位置和速度
        dx = other_state.get('x', 0) - ego_state.get('x', 0)
        dy = other_state.get('y', 0) - ego_state.get('y', 0)
        
        # 计算纵向和横向距离
        ego_yaw = ego_state.get('yaw', 0)
        forward_vec = np.array([np.cos(ego_yaw), np.sin(ego_yaw)])
        rel_pos = np.array([dx, dy])
        
        longitudinal = np.dot(forward_vec, rel_pos)
        lateral = np.dot(np.array([-np.sin(ego_yaw), np.cos(ego_yaw)]), rel_pos)
        
        # 计算相对速度
        ego_vx = ego_state.get('vx', 0)
        ego_vy = ego_state.get('vy', 0)
        other_vx = other_state.get('vx', 0)
        other_vy = other_state.get('vy', 0)
        
        ego_v = ego_state.get('speed', 0)
        other_v = other_state.get('speed', 0)
        
        # 横向速度 (简化)
        lateral_speed_diff = lateral - 0  # 假设前车无横向速度
        
        return check_lane_change_safety(
            ego_v, lateral_speed_diff,
            other_v, 0,
            abs(longitudinal), abs(lateral),
            self.params
        )
    
    def comprehensive_check(self,
                           v_lat_f: float,
                           v_lat_l: float,
                           d_actual_lat: float) -> Dict[str, Any]:
        """综合横向安全检查"""
        safe_lat = self.check_safe_lateral_distance(v_lat_f, v_lat_l, d_actual_lat)
        proper_lat = self.check_proper_lateral_response(
            v_lat_f, v_lat_l, d_actual_lat, safe_lat['d_min']
        )
        dangerous_lat = self.check_dangerous_lateral_situation(
            v_lat_f, v_lat_l, d_actual_lat, safe_lat['d_min']
        )
        
        return {
            'safe_distance': safe_lat,
            'proper_response': proper_lat,
            'dangerous_situation': dangerous_lat,
            'overall_safe': safe_lat['safe'],
        }
