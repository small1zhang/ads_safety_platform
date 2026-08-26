"""
RSS 纵向安全距离模型
参考文献: Shalev-Shwartz et al. "Responsibility-Sensitive Safety (RSS)" 2017

核心公式:
d_min_long(A, B, t) = max(0, v_A * rho + 0.5 * a_max_accel * rho² + 
                       (v_A + a_max_accel * rho)² / (2 * a_min_brake) - 
                       v_b² / (2 * a_brake))

其中:
- v_A: 后车速度 (m/s)
- v_B: 前车速度 (m/s)
- rho: 反应时间 (s), 通常 0.5s
- a_max_accel: 后车最大加速 (m/s²)
- a_min_brake: 后车最小制动 (m/s²)
- a_brake: 前车最大制动 (m/s²)
"""
import numpy as np
from dataclasses import dataclass


@dataclass
class RSSParams:
    """RSS 参数配置"""
    rho: float = 0.5              # 反应时间 (s)
    a_max_accel: float = 2.0      # 后车最大加速 (m/s²)
    a_min_brake: float = 4.0      # 后车最小制动 (m/s²)
    a_brake: float = 8.0          # 前车最大制动 (m/s²)
    # 扩展参数
    a_comf_brake: float = 3.0     # 舒适制动 (m/s²)
    a_max_lat_accel: float = 3.0  # 最大侧向加速 (m/s²)
    lane_width: float = 3.7       # 车道宽度 (m)


def compute_d_min_long(v_a: float, v_b: float, params: RSSParams) -> float:
    """
    计算 RSS 纵向安全距离
    
    参数:
        v_a: 后车速度 (m/s)
        v_b: 前车速度 (m/s)
        params: RSS 参数
    
    返回:
        d_min_long: 最小安全距离 (m)
    """
    rho = params.rho
    a_max_accel = params.a_max_accel
    a_min_brake = params.a_min_brake
    a_brake = params.a_brake
    
    # 计算各项
    term1 = v_a * rho
    term2 = 0.5 * a_max_accel * (rho ** 2)
    term3 = (v_a + a_max_accel * rho) ** 2 / (2 * a_min_brake)
    term4 = (v_b ** 2) / (2 * a_brake)
    
    d_min_long = max(0, term1 + term2 + term3 - term4)
    
    return d_min_long


def compute_d_min_lat(v_a: float, params: RSSParams) -> float:
    """
    计算 RSS 横向安全距离
    
    参考文献: Shalev-Shwartz et al. 2017
    d_min_lat = max(0, v_a * rho + 0.5 * a_max_lat_accel * rho²)
    
    参数:
        v_a: 车辆速度 (m/s)
        params: RSS 参数
    
    返回:
        d_min_lat: 最小横向安全距离 (m)
    """
    rho = params.rho
    a_max_lat_accel = params.a_max_lat_accel
    
    d_min_lat = max(0, v_a * rho + 0.5 * a_max_lat_accel * (rho ** 2))
    
    return d_min_lat


def check_proper_response(v_a: float, v_b: float, 
                          actual_distance: float,
                          d_min_long: float) -> bool:
    """
    检查反应是否适当
    
    参考文献: Shalev-Shwartz et al. 2017
    如果实际距离小于 d_min_long，则后车反应不当
    
    参数:
        v_a: 后车速度
        v_b: 前车速度
        actual_distance: 实际距离
        d_min_long: RSS 最小距离
    
    返回:
        bool: True 表示反应适当, False 表示反应不当
    """
    return actual_distance >= d_min_long


def compute_ttc(v_a: float, v_b: float, distance: float) -> float:
    """
    计算碰撞时间 (Time To Collision, TTC)
    
    TTC = distance / (v_a - v_b)  if v_a > v_b else inf
    
    参数:
        v_a: 后车速度
        v_b: 前车速度
        distance: 距离
    
    返回:
        ttc: 碰撞时间 (s)
    """
    if v_a <= v_b:
        return float('inf')  # 不会追尾
    
    return distance / (v_a - v_b)


def compute_brake_distance(v: float, a: float) -> float:
    """
    计算制动距离
    
    d = v² / (2 * |a|)
    
    参数:
        v: 速度 (m/s)
        a: 制动加速度 (m/s²), 为负数
    
    返回:
        制动距离 (m)
    """
    if abs(a) < 1e-6:
        return float('inf')
    return (v ** 2) / (2 * abs(a))


class RSSSafetyChecker:
    """
    RSS 安全检查器
    
    实现完整的 RSS 规则检查:
    1. 纵向安全距离
    2. 横向安全距离
    3. 反应不当检测
    4. TTC 检测
    """
    
    def __init__(self, params: RSSParams = None):
        self.params = params or RSSParams()
    
    def check_longitudinal_safety(self, 
                                  ego_speed: float,
                                  npc_speed: float,
                                  actual_distance: float) -> dict:
        """
        纵向安全距离检查
        
        返回:
            {
                'safe': bool,
                'd_min': float,
                'actual_distance': float,
                'margin': float (实际距离 - 安全距离),
                'violation': bool (实际距离 < 安全距离)
            }
        """
        d_min = compute_d_min_long(ego_speed, npc_speed, self.params)
        margin = actual_distance - d_min
        
        return {
            'safe': actual_distance >= d_min,
            'd_min': d_min,
            'actual_distance': actual_distance,
            'margin': margin,
            'violation': actual_distance < d_min,
        }
    
    def check_lateral_safety(self,
                            ego_speed: float,
                            actual_lateral_distance: float) -> dict:
        """
        横向安全距离检查
        
        返回:
            {
                'safe': bool,
                'd_min_lat': float,
                'actual_distance': float,
                'violation': bool
            }
        """
        d_min_lat = compute_d_min_lat(ego_speed, self.params)
        violation = actual_lateral_distance < d_min_lat
        
        return {
            'safe': not violation,
            'd_min_lat': d_min_lat,
            'actual_distance': actual_lateral_distance,
            'violation': violation,
        }
    
    def check_proper_response(self,
                             ego_speed: float,
                             npc_speed: float,
                             actual_distance: float) -> dict:
        """
        反应不当检查
        
        返回:
            {
                'proper_response': bool,
                'd_min_long': float,
                'actual_distance': float,
                'reaction_time_margin': float
            }
        """
        d_min_long = compute_d_min_long(ego_speed, npc_speed, self.params)
        proper = actual_distance >= d_min_long
        
        return {
            'proper_response': proper,
            'd_min_long': d_min_long,
            'actual_distance': actual_distance,
            'reaction_time_margin': self.params.rho,
        }
    
    def check_ttc(self,
                 ego_speed: float,
                 npc_speed: float,
                 distance: float,
                 ttc_threshold: float = 3.0) -> dict:
        """
        TTC 检查
        
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
        ttc = compute_ttc(ego_speed, npc_speed, distance)
        violation = ttc < ttc_threshold
        
        return {
            'safe': not violation,
            'ttc': ttc,
            'threshold': ttc_threshold,
            'violation': violation,
        }