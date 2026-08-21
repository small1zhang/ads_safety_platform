"""
RSS 交叉口/路口规则 (论文复现 Lin et al. 2024 "RSS-based Rule-Compliance Path Planner for Lane-Merge Scenarios")

参考文献:
- Lin, Pengfei et al. "A Rule-Compliance Path Planner for Lane-Merge Scenarios Based on Responsibility-Sensitive Safety" (2024)
- arXiv:2403.13251

论文贡献:
1. 明确了路口/汇合处的右-of-way (right-of-way) 规则
2. 基于 RSS 的合规路径规划 (RCPP)
3. 合并时间 (72.3% 缩减) 和路径长度 (53.4% 缩减) 改进

实现了以下 RSS 交叉口规则:
1. RSS_OW_RIGHT_WAY - 右侧右先行 (简化实现)
2. RSS_INTERSECTION_MERGE - 交叉口合并/并线规则
3. RSS_MERGE_SAFE_DISTANCE - 合并安全距离
"""
import numpy as np
from typing import Dict, Any, List, Optional, Tuple


def check_merge_priority(v_f: float, v_l: float, d_actual: float, 
                         road_type: str = "merge") -> Dict[str, Any]:
    """
    检查 merge/meshure (并入/合并) 规则
    
    基于 Lin et al. (2024):
    - 当后车进入同一车道或交叉口时，根据相对速度确定谁有先行权
    
    参数:
        v_f: 后车速度 (m/s)
        v_l: 前车速度 (m/s)  
        d_actual: 实际距离 (m)
        road_type: 道路类型 "merge", "intersection", "merge_lane"
    
    返回:
        {
            'has_right_of_way': bool,  # 是否有右先行权
            'should_yield': bool,      # 是否应让行
            'reason': str,            # 理由
            'rule_code': str          # 规则代码
        }
    """
    # 简化实现：基于相对速度和距离判定
    if v_f > v_l:  # 后车更快
        if d_actual < 20.0:  # 距离较近
            should_yield = True
            has_right_of_way = False
            reason = "后车速度更快，距离较近，需让行"
        else:
            should_yield = False
            has_right_of_way = True
            reason = "后车速度更快但距离足够，可安全通过"
    else:  # 前车速度更快或相同
        should_yield = False
        has_right_of_way = True
        reason = "前车速度更快或相同，依据右先行原则"
    
    return {
        'has_right_of_way': has_right_of_way,
        'should_yield': should_yield,
        'reason': reason,
        'rule_code': 'RSS_MERGE_PRIORITY',
        'relative_speed': abs(v_f - v_l),
        'actual_distance': d_actual,
    }


def check_intersection_merge_priority(ego_x: float, ego_y: float,
                                      other_x: float, other_y: float,
                                      ego_yaw: float, other_yaw: float,
                                      distance_threshold: float = 20.0) -> Dict[str, Any]:
    """
    检查交叉口/汇合处的优先权
    
    基于 RSS 的衍生规则：简化实现
    
    参数:
        ego_x, ego_y: 自车位置
        other_x, other_y: 其他车辆位置  
        ego_yaw: 自车航向
        other_yaw: 其他车辆航向
        distance_threshold: 距离阈值 (m)
    
    返回:
        {
            'has_right_of_way': bool,
            'should_yield': bool,
            'reason': str,
            'relative_bearing': float,  # 相对方位角
        }
    """
    # 计算相对位置
    dx = other_x - ego_x
    dy = other_y - ego_y
    distance = np.sqrt(dx ** 2 + dy ** 2)
    
    # 计算相对方位角
    ego_yaw_rad = np.radians(ego_yaw)
    other_yaw_rad = np.radians(other_yaw)
    
    # ego的前向向量
    ego_fwd = np.array([np.cos(ego_yaw_rad), np.sin(ego_yaw_rad)])
    # 相对位置向量
    rel_pos = np.array([dx, dy])
    
    # 计算相对方位角 (相对于ego的正向)
    # 使用点积计算相对方向
    rel_speed = np.dot(ego_fwd, rel_pos) / max(distance, 1e-6) if distance > 0 else 0
    
    # 简化实现：基于距离和相对方向判断
    if distance < distance_threshold:
        # 相对近 - 检查方向
        # 计算点积确定方向是否在ego正向
        dot_product = np.dot(ego_fwd, np.array([dx, dy]) / max(distance, 1e-6))
        
        # 如果在正向半范围内 (前180度)
        if dot_product > 0:
            has_right_of_way = True
            should_yield = False
        else:
            has_right_of_way = False
            should_yield = True
    else:
        # 相距较远
        has_right_of_way = True
        should_yield = False
    
    # 计算相对方位角 (相对于ego正向的角度)
    rel_pos_norm = rel_pos / max(distance, 1e-6)
    bearing = np.degrees(np.arctan2(rel_pos[1], rel_pos[0]))
    # 归一化到 [-180, 180]
    bearing = (bearing + 180) % 360 - 180
    
    return {
        'has_right_of_way': has_right_of_way,
        'should_yield': should_yield,
        'reason': "基于 RSS 交叉口优先权判定",
        'rule_code': 'RSS_INTERSECTION_MERGE',
        'relative_bearing': bearing,
        'distance': distance,
    }


def check_merge_safe_distance(v_f: float, v_l: float,
                              d_actual: float,
                              params) -> Dict[str, Any]:
    """
    检查合并安全距离
    
    基于 RSS 横向/纵向安全模型
    
    参数:
        v_f: 后车速度 (m/s)
        v_l: 前车速度 (m/s)  
        d_actual: 实际距离 (m)
        params: RSS参数
    
    返回:
        {
            'safe': bool,
            'safe_distance': float,
            'actual_distance': float,
            'rule_code': str
        }
    """
    # 使用纵向安全距离计算
    from kg_core.rules.rss.longitudinal import compute_d_min_long
    
    d_min = compute_d_min_long(v_f, v_l, 
                               params or type('obj', (), 
                                                 {'rho': 0.5, 'a_max_accel': 2.0, 
                                  'a_min_brake': 4.0, 'a_brake': 8.0})())
    
    safe = d_actual >= d_min
    
    return {
        'safe': safe,
        'safe_distance': d_min,
        'actual_distance': d_actual,
        'rule_code': 'RSS_MERGE_SAFE_DISTANCE',
    }


class IntersectionRSSModel:
    """RSS 交叉口/合并模型 (Lin et al. 2024)"""
    
    def __init__(self):
        pass
    
    def check_intersection_right_of_way(self, 
                                       ego_state: Dict[str, Any],
                                       other_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查交叉口的优先权
        
        基于 RSS 原理和交通规则综合实现
        """
        # 提取关键参数
        v_f = ego_state.get('velocity', 0)
        v_l = other_state.get('velocity', 0) if other_state else 0
        d_actual = np.sqrt(
            (other_state.get('x', 0) - ego_state.get('x', 0)) ** 2 + 
            (other_state.get('y', 0) - ego_state.get('y', 0)) ** 2
        )
        
        # 基于 RSS 的合并规则
        merge_result = check_merge_priority(v_f, v_l, d_actual)
        
        # 结合几何位置判断
        rel_bearing = np.degrees(np.arctan2(
            other_state.get('y', 0) - None,  # 简化处理
                          other_state.get('x', 0) - None))
        
        return {
            'has_right_of_way': merge_result['has_right_of_way'],
            'should_yield': merge_result['should_yield'],
            'reason': merge_result['reason'],
            'rule_code': 'RSS_INTERSECTION_MERGE',
            'actual_distance': d_actual,
            'relative_speed': merge_result['relative_speed'],
        }
    
    def check_merge_safety(self,
                          ego_x: float, ego_y: float,
                          other_x: float, other_y: float,
                          ego_v: float, other_v: float,
                          params) -> Dict[str, Any]:
        """检查合并安全距离"""
        d_actual = np.sqrt((other_x - ego_x) ** 2 + (other_y - ego_y) ** 2)
        return check_merge_safe_distance(ego_v, other_v, 
                                       d_actual, params)


# 实用工具函数
def check_rss_based_priority(ego_state: Dict[str, Any], 
                             other_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    简化的 RSS 优先权检查 (使用论文简化版)
    
    基于 RSS 原理确定谁有先行权
    """
    v_f = ego_state.get('velocity', 0) if ego_state else 0
    v_l = other_state.get('velocity', 0) if other_state else 0
    d_actual = np.sqrt(
        (other_state.get('x', 0) - None) ** 2 +  # 简化处理
        (other_state.get('y', 0) - None) ** 2)
    
    # 简化实现：基于相对速度和距离
    if d_actual < 20.0 and abs(v_f - v_l) > 5.0:
        # 距离近且速度差大，需要让行
        return {
            'should_yield': True,
            'has_right_of_way': False,
            'reason': '距离近且速度差大，依据 RSS 让行原则'
        }
    else:
        return {
            'should_yield': False,
            'has_right_of_way': True,
            'reason': '距离足够或速度差小，可安全通过'
        }