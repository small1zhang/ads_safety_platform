"""
RSS 量化风险指数模型 (Risk Index)

参考文献:
- Candela, Eduardo et al. "Quantitative Risk Indices for Autonomous Vehicle Training Systems" (2022)
- arXiv:2104.12945

该工作扩展了 RSS，提出了连续的风险指数，而非二元的"安全/不安全"判定。

核心思想:
1. 风险指数 RI ∈ [0, 1]
2. RI = 0 表示完全安全
3. RI = 1 表示必然碰撞
4. 通过车辆动力学和驾驶者风险偏好进行量化
"""
import numpy as np
from dataclasses import dataclass
from typing import Dict, Any, Tuple


@dataclass
class RiskParams:
    """风险模型参数"""
    alpha: float = 1.0      # 风险敏感度 参数 α
    beta: float = 1.0       # 场景复杂度 参数 β  
    gamma: float = 1.0      # 约束权重 参数 γ
    risk_threshold: float = 0.5  # 风险阈值


def compute_risk_index(d_actual: float,
                       d_min: float,
                       v_rel: float,
                       params: RiskParams = None) -> float:
    """
    计算风险指数 (Risk Index)
    
    公式 (基于 Candela et al. 2022 的简化实现):
    
    RI = 1 - exp(-α * (d_min / d_actual))  if d_actual > 0
    RI = 1  if d_actual <= 0
    
    参数:
        d_actual: 实际距离 (m)
        d_min: 最小安全距离 (m)
        v_rel: 相对速度 (m/s)
        params: 风险参数
    
    返回:
        RI: 风险指数 [0, 1]
    """
    if params is None:
        params = RiskParams()
    
    if d_actual <= 0:
        return 1.0  # 必然碰撞
    
    if d_actual >= d_min:
        return 0.0  # 完全安全
    
    # 计算风险指数
    # 使用指数函数建模风险随距离下降的增加
    ratio = d_min / d_actual
    alpha = params.alpha
    
    # 基于比例的风险计算
    # 当 ratio > 1 时，d_actual < d_min，表示危险
    if ratio > 1:
        # 风险指数: 随着实际距离减小而增加
        RI = 1.0 - np.exp(-alpha * (ratio - 1.0))
        return min(1.0, max(0.0, RI))
    else:
        # 实际距离大于安全距离，理论上风险为0
        # 但考虑相对速度，仍可能存在风险
        RI = 1.0 - np.exp(-alpha * (1.0 / ratio) * (v_rel / 30.0) ** 2)
        return min(1.0, max(0.0, RI))


def compute_risk_index_comprehensive(d_actual: float,
                                     d_min: float,
                                     v_rel: float,
                                     ttc: float = None,
                                     params: RiskParams = None) -> Dict[str, float]:
    """
    综合风险指数计算
    
    考虑多个因素:
    1. 距离比例风险
    2. 相对速度风险
    3. 碰撞时间(TTC)风险
    
    参数:
        d_actual: 实际距离
        d_min: 最小安全距离
        v_rel: 相对速度
        ttc: 碰撞时间
        params: 风险参数
    
    返回:
        {
            'risk_index': float,      # 总风险指数 [0,1]
            'distance_risk': float,   # 距离风险
            'speed_risk': float,      # 速度风险
            'ttc_risk': float,        # TTC风险
            'overall_risk': str,      # 风险等级 "LOW", "MEDIUM", "HIGH", "CRITICAL"
        }
    """
    if params is None:
        params = RiskParams()
    
    # 1. 距离风险
    distance_risk = compute_risk_index(d_actual, d_min, v_rel, params)
    
    # 2. 速度风险 (相对速度越大，风险越高)
    speed_risk = min(1.0, (abs(v_rel) / 30.0) ** 2)  # 假设 30 m/s 约等于 108 km/h
    
    # 3. TTC风险
    if ttc is None or ttc <= 0:
        ttc_risk = 1.0  # 无法计算 TTC，风险最高
    else:
        # TTC 越小，风险越高
        ttc_risk = min(1.0, max(0.0, 3.0 / ttc))  # 3 秒以下即为高风险
        ttc_risk = ttc_risk ** 2  # 二次放大
    
    # 综合风险指数
    # 使用加权平均
    alpha = params.alpha
    beta = params.beta
    gamma = params.gamma
    
    overall_risk = (
        alpha * distance_risk + 
        beta * speed_risk + 
        gamma * ttc_risk
    ) / (alpha + beta + gamma)
    
    overall_risk = min(1.0, max(0.0, overall_risk))
    
    # 风险等级划分
    if overall_risk < 0.2:
        risk_level = "LOW"
    elif overall_risk < 0.5:
        risk_level = "MEDIUM"
    elif overall_risk < 0.8:
        risk_level = "HIGH"
    else:
        risk_level = "CRITICAL"
    
    return {
        'risk_index': overall_risk,
        'distance_risk': distance_risk,
        'speed_risk': speed_risk,
        'ttc_risk': ttc_risk,
        'overall_risk': risk_level,
        'd_actual': d_actual,
        'd_min': d_min,
        'v_rel': v_rel,
        'ttc': ttc,
    }


class RiskAssessmentModel:
    """
    风险评估模型 (基于 Candela et al. 2022)
    
    提供 continuous risk score 代替二元判定
    """
    
    def __init__(self, params: RiskParams = None):
        self.params = params or RiskParams()
    
    def assess_longitudinal_risk(self,
                                d_actual: float,
                                d_min: float,
                                v_rel: float,
                                ttc: float = None) -> Dict[str, Any]:
        """
        评估纵向风险
        """
        return compute_risk_index_comprehensive(d_actual, d_min, v_rel, ttc, self.params)
    
    def risk_to_binary(self, risk_index: float, threshold: float = 0.3) -> bool:
        """
        将连续风险指数转换为二元判定
        
        返回:
            True: 存在风险 (unsafe)
            False: 安全 (safe)
        """
        return risk_index >= threshold
    
    def get_risk_color(self, risk_index: float) -> str:
        """
        根据风险指数返回颜色代码 (用于可视化)
        """
        if risk_index < 0.2:
            return "green"
        elif risk_index < 0.5:
            return "yellow"
        elif risk_index < 0.8:
            return "orange"
        else:
            return "red"


def generate_risk_report(risk_assessment: Dict[str, Any]) -> str:
    """
    生成风险报告 (自然语言描述)
    """
    ri = risk_assessment['risk_index']
    level = risk_assessment['overall_risk']
    d_actual = risk_assessment['d_actual']
    d_min = risk_assessment['d_min']
    
    if ri < 0.1:
        return f"检测到无风险情况：实际距离 {d_actual:.1f}m 远大于安全距离 {d_min:.1f}m。"
    elif ri < 0.3:
        return f"风险较低：实际距离 {d_actual:.1f}m 略小于安全距离 {d_min:.1f}m。建议注意保持车距。"
    elif ri < 0.6:
        return f"风险中等：实际距离 {d_actual:.1f}m 显著小于安全距离 {d_min:.1f}m。需要立即行驶缓慢。"
    else:
        return f"风险极高：实际距离 {d_actual:.1f}m 远小于安全距离 {d_min:.1f}m。建议紧急制动！"