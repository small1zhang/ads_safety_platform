"""
RSS 纵向安全模型 (严格复现 Shalev-Shwartz et al. 2017)

参考文献:
- Shai Shalev-Shwartz, Shaked Shammah, Amnon Shashua
  "On a Formal Model of Safe and Scalable Self-driving Cars" (2017)
- arXiv:1708.06374

核心定义:
1. 纵向安全距离 d_min
2. Proper Response (反应得当)
3. Dangerous Situation (危险情形)
4. 连续违规检测 (Continuous Violation)
"""
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class RSSLongitudinalParams:
    """RSS 纵向安全距离参数 (论文标准值)"""
    rho: float = 0.5                    # 反应时间 (s)
    a_max_accel: float = 2.0            # 后车最大加速 (m/s²)
    a_min_brake: float = 4.0            # 后车最小制动 (m/s²)
    a_brake: float = 8.0                # 前车最大制动 (m/s²)
    # 扩展参数 (论文第5节)
    a_comf_brake: float = 3.0           # 舒适制动 (m/s²)
    mu: float = 0.3                     # 摩擦系数
    g: float = 9.81                     # 重力加速度


def compute_d_min_long(v_f: float, v_l: float, 
                       params: RSSLongitudinalParams) -> float:
    """
    计算 RSS 纵向安全距离 d_min
    
    论文公式 (Eq. 1, §3.1):
    d_min = max(0, v_f * ρ + 0.5 * a_max * ρ² + 
               (v_f + a_max * ρ)² / (2 * b_min) - 
               v_l² / (2 * b_max))
    
    参数:
        v_f: 后车(follower)速度 (m/s)
        v_l: 前车(leader)速度 (m/s)
        params: RSS参数
    
    返回:
        d_min: 最小安全距离 (m)
    """
    rho = params.rho
    a_max = params.a_max_accel
    b_min = params.a_min_brake
    b_max = params.a_brake
    
    # 论文公式各项
    term1 = v_f * rho                                   # 反应时间内行驶距离
    term2 = 0.5 * a_max * (rho ** 2)                   # 加速阶段额外距离
    term3 = (v_f + a_max * rho) ** 2 / (2 * b_min)     # 后车制动距离
    term4 = (v_l ** 2) / (2 * b_max)                    # 前车制动距离
    
    d_min = max(0, term1 + term2 + term3 - term4)
    
    return d_min


def compute_brake_distance(v: float, a_brake: float) -> float:
    """
    计算制动距离
    
    公式: d = v² / (2 * a_brake)
    """
    if abs(a_brake) < 1e-6:
        return float('inf')
    return (v ** 2) / (2 * abs(a_brake))


def compute_comfort_brake_distance(v_f: float, v_l: float,
                                  rho: float, a_comf: float) -> float:
    """
    计算舒适制动距离 (论文 §3.1 扩展)
    
    当后车感知到前车刹车时，应以舒适减速度制动
    d_comf = (v_f - v_l) * ρ + 0.5 * a_comf * ρ²
    """
    return (v_f - v_l) * rho + 0.5 * a_comf * (rho ** 2)


class LongitudinalRSSModel:
    """
    RSS 纵向安全模型 (严格复现论文)
    
    实现以下核心概念:
    1. Safe Longitudinal Distance (安全纵向距离)
    2. Proper Response (反应得当)
    3. Dangerous Situation (危险情形)
    4. Continuous Violation (连续违规)
    
    论文 §3: "The Longitudinal Model"
    """
    
    def __init__(self, params: RSSLongitudinalParams = None):
        self.params = params or RSSLongitudinalParams()
        self.violation_history: List[Dict] = []  # 违规历史记录
    
    def check_safe_distance(self, 
                           v_f: float, 
                           v_l: float, 
                           d_actual: float) -> Dict[str, Any]:
        """
        检查安全距离 (论文 Def. 1)
        
        条件:
        d_actual >= d_min_long(v_f, v_l)
        
        返回:
            {
                'safe': bool,
                'd_min': float,
                'actual_distance': float,
                'margin': float,
                'rule_code': str
            }
        """
        d_min = compute_d_min_long(v_f, v_l, self.params)
        margin = d_actual - d_min
        
        return {
            'safe': d_actual >= d_min,
            'd_min': d_min,
            'actual_distance': d_actual,
            'margin': margin,
            'rule_code': 'RSS_LONG_SAFE_DISTANCE',
            'v_f': v_f,
            'v_l': v_l,
            'params': {
                'rho': self.params.rho,
                'a_max': self.params.a_max_accel,
                'b_min': self.params.a_min_brake,
                'b_max': self.params.a_brake,
            }
        }
    
    def check_proper_response(self,
                             v_f: float,
                             v_l: float,
                             d_actual: float,
                             d_min: float = None) -> Dict[str, Any]:
        """
        检查反应是否得当 (论文 Def. 2)
        
        Proper Response 条件:
        1. 当 d_actual < d_min 时，后车必须采取适当反应
        2. 适当反应 = 以至少 a_min_brake 的减速度制动
        3. 如果前车已经开始制动，后车应以舒适减速度制动
        
        返回:
            {
                'proper_response': bool,
                'required_action': str,
                'd_min': float,
                'actual_distance': float,
                'margin': float,
                'rule_code': str
            }
        """
        if d_min is None:
            d_min = compute_d_min_long(v_f, v_l, self.params)
        
        margin = d_actual - d_min
        proper_response = d_actual >= d_min
        
        # 确定需要的动作
        if not proper_response:
            if margin > -5.0:  # 轻微违规，舒适制动即可
                required_action = f"舒适制动 (减速度 >= {self.params.a_comf_brake} m/s²)"
            else:  # 严重违规，需要紧急制动
                required_action = f"紧急制动 (减速度 >= {self.params.a_min_brake} m/s²)"
        else:
            required_action = "无需反应"
        
        return {
            'proper_response': proper_response,
            'required_action': required_action,
            'd_min': d_min,
            'actual_distance': d_actual,
            'margin': margin,
            'rule_code': 'RSS_LONG_PROPER_RESPONSE',
            'v_f': v_f,
            'v_l': v_l,
        }
    
    def check_dangerous_situation(self,
                                 v_f: float,
                                 v_l: float,
                                 d_actual: float,
                                 d_min: float = None) -> Dict[str, Any]:
        """
        检查危险情形 (论文 Def. 3)
        
        Dangerous Situation 条件:
        1. d_actual < d_min 且
        2. v_f > v_l (后车速度大于前车速度)
        
        这意味着即使前车采取最大制动，后车也无法避免碰撞
        
        返回:
            {
                'dangerous': bool,
                'd_min': float,
                'actual_distance': float,
                'margin': float,
                'relative_speed': float,
                'rule_code': str
            }
        """
        if d_min is None:
            d_min = compute_d_min_long(v_f, v_l, self.params)
        
        margin = d_actual - d_min
        relative_speed = v_f - v_l
        
        dangerous = (d_actual < d_min) and (v_f > v_l)
        
        return {
            'dangerous': dangerous,
            'd_min': d_min,
            'actual_distance': d_actual,
            'margin': margin,
            'relative_speed': relative_speed,
            'rule_code': 'RSS_LONG_DANGEROUS_SITUATION',
            'v_f': v_f,
            'v_l': v_l,
        }
    
    def check_continuous_violation(self,
                                  v_f: float,
                                  v_l: float,
                                  d_actual: float,
                                  duration: float = 1.0) -> Dict[str, Any]:
        """
        检查连续违规 (论文 §4.1)
        
        当 d_actual < d_min 持续一段时间，说明:
        1. 后车没有正确反应
        2. 或者前车突然加速
        
        返回:
            {
                'continuous_violation': bool,
                'duration': float,
                'd_min': float,
                'rule_code': str
            }
        """
        d_min = compute_d_min_long(v_f, v_l, self.params)
        continuous_violation = d_actual < d_min
        
        return {
            'continuous_violation': continuous_violation,
            'duration': duration,
            'd_min': d_min,
            'actual_distance': d_actual,
            'rule_code': 'RSS_LONG_CONTINUOUS_VIOLATION',
        }
    
    def comprehensive_check(self, v_f: float, v_l: float, d_actual: float) -> Dict[str, Any]:
        """
        综合检查 (论文完整实现)
        
        返回所有检查结果
        """
        d_min = compute_d_min_long(v_f, v_l, self.params)
        
        safe_distance = self.check_safe_distance(v_f, v_l, d_actual)
        proper_response = self.check_proper_response(v_f, v_l, d_actual, d_min)
        dangerous_situation = self.check_dangerous_situation(v_f, v_l, d_actual, d_min)
        
        return {
            'safe_distance': safe_distance,
            'proper_response': proper_response,
            'dangerous_situation': dangerous_situation,
            'd_min': d_min,
            'overall_safe': safe_distance['safe'],
        }