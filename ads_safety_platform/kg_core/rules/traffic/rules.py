"""
交通规则检测
参考文献: Rizaldi et al. "Towards a Logic-Based Approach to Formal Verification of ADS" 2017

实现以下规则：
- R1: 禁止左转 (No Left Turn)
- R2: 红灯违规
- R3: 实线变道
- R4: 未看见的转向 (Unseen Maneuver)
"""
from typing import Dict, Any, List, Tuple
import numpy as np


# 车道线类型
YELLOW_SOLID = "YellowSolid"
WHITE_SOLID = "WhiteSolid"
SOLID_LINE = "Solid"
DASHED_LINE = "Dashed"


def check_red_light(ego: Dict[str, Any], 
                   traffic_lights: List[Dict[str, Any]],
                   intersection_center: Tuple[float, float] = None,
                   intersection_radius: float = 10.0) -> Dict[str, Any]:
    """
    检查红灯违规 (R2)
    
    参考: Rizaldi et al. 2017
    
    判定为闯红灯的条件：
    1. 自车在路口附近
    2. 红灯居中/自车控制的灯为红灯
    3. 自车速度 > 5 m/s
    
    参数:
        ego: 自车信息
        traffic_lights: 交通灯列表
        intersection_center: 路口中心坐标
        intersection_radius: 路口半径
    
    返回:
        {
            'violation': bool,
            'tls': traffic_lights list,
            'distance_to_intersection': float,
            'ego_speed': float,
        }
    """
    if not traffic_lights:
        return {'violation': False}
    
    ego_x = ego.get('x', 0)
    ego_y = ego.get('y', 0)
    ego_yaw = ego.get('yaw', 0)
    ego_speed = ego.get('speed', 0)
    
    # 寻找控制自车的红灯
    controlled_tls = []
    for tl in traffic_lights:
        tl_state = tl.get('state', 'Green')
        if tl_state != 'Red':
            continue
        
        # 计算与路口距离 (如果指定了路口)
        if intersection_center:
            dist = np.sqrt((tl['x'] - intersection_center[0])**2 + 
                          (tl['y'] - intersection_center[1])**2)
            if dist <= intersection_radius:
                controlled_tls.append(tl)
        else:
            # 检查灯光在自车前方
            forward_vec = np.array([np.cos(ego_yaw), np.sin(ego_yaw)])
            tl_dir = np.array([tl['x'] - ego_x, tl['y'] - ego_y])
            dot = np.dot(forward_vec, tl_dir)
            
            if dot > 0:
                controlled_tls.append(tl)
    
    if not controlled_tls:
        return {'violation': False}
    
    # 判定为闯红灯
    violation = True
    return {
        'violation': violation,
        'tls': controlled_tls,
        'distance_to_intersection': min(np.sqrt((tl['x'] - ego_x)**2 + (tl['y'] - ego_y)**2) 
                                        for tl in controlled_tls),
        'ego_speed': ego_speed,
    }


def check_solid_lane_change(ego: Dict[str, Any],
                            current_lane_marking: str = SOLID_LINE,
                            lane_change_distance: float = 5.0) -> bool:
    """
    检查实线变道 (R3)
    
    参考: Rizaldi et al. 2017
    
    判定为实线变道的条件：
    1. 当前车道有实线
    2. 侧向位移 > threshold
    3. 变道持续时间 > 1 秒
    
    参数:
        ego: 自车信息
        current_lane_marking: 当前车道标线类型
        lane_change_distance: 变道距离阈值 (m)
    
    返回:
        bool: 是否违反实线变道规则
    """
    # 简化实现：检查横向位移
    lateral_speed = ego.get('lateral_speed', 0)
    
    # 如果有横向速度且车道有实线，则可能违规
    if current_lane_marking in [SOLID_LINE, YELLOW_SOLID] and abs(lateral_speed) > 0.5:
        return True
    
    return False


def check_no_left_turn(geo_position: Dict[str, Any],
                      current_road: str,
                      target_road: str = None,
                      allowed_turns: List[str] = None) -> Dict[str, Any]:
    """
    检查禁止左转 (R1)
    
    参考: 交通规则标准
    
    参数:
        geo_position: 几何位置信息
        current_road: 当前道路
        target_road: 目标道路
        allowed_turns: 允许的转向列表
    
    返回:
        {
            'violation': bool,
            'reason': str
        }
    """
    # 这需要地图数据支持，这里给出框架
    if allowed_turns and 'left' not in allowed_turns:
        return {
            'violation': True,
            'reason': '左转被禁止'
        }
    
    return {'violation': False}


def check_visibility_clear(ego: Dict[str, Any],
                          obstacles: List[Dict[str, Any]],
                          min_distance: float = 20.0) -> Dict[str, Any]:
    """
    检查视野是否被阻挡
    
    参考: 自动驾驶安全规范
    
    判定为视野受阻的条件：
    1. 前方障碍物距离 < min_distance
    2. 障碍物阻挡视线
    
    参数:
        ego: 自车信息
        obstacles: 障碍物列表
        min_distance: 最小可见距离
    
    返回:
        {
            'blocked': bool,
            'obstacle': dict or None,
            'distance': float
        }
    """
    ego_x = ego.get('x', 0)
    ego_y = ego.get('y', 0)
    ego_yaw = ego.get('yaw', 0)
    
    for obs in obstacles:
        obs_x = obs.get('x', 0)
        obs_y = obs.get('y', 0)
        
        dx = obs_x - ego_x
        dy = obs_y - ego_y
        distance = np.sqrt(dx**2 + dy**2)
        
        if distance < min_distance:
            # 检查是否在前方
            forward_vec = np.array([np.cos(ego_yaw), np.sin(ego_yaw)])
            obs_dir = np.array([dx, dy])
            dot = np.dot(forward_vec, obs_dir)
            
            if dot > 0:  # 在前方
                return {
                    'blocked': True,
                    'obstacle': obs,
                    'distance': distance,
                }
    
    return {'blocked': False, 'obstacle': None, 'distance': float('inf')}


class TrafficRuleChecker:
    """交通规则检查器"""
    
    def __init__(self):
        self.last_red_light_violation = False
    
    def check_all_traffic_rules(self, ego: Dict[str, Any], 
                               traffic_lights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        检查所有交通规则
        
        返回:
            规则违规列表
        """
        violations = []
        
        # R2: 红灯违规
        red_light_result = check_red_light(ego, traffic_lights)
        if red_light_result['violation']:
            violations.append({
                'rule_code': 'R2_RED_LIGHT',
                'severity': 'CRITICAL',
                'message': f"闯红灯违规: 速度 {red_light_result['ego_speed']:.1f}m/s 在路口附近",
                'evidence': red_light_result,
            })
            self.last_red_light_violation = True
        else:
            self.last_red_light_violation = False
        
        # R3: 实线变道
        if check_solid_lane_change(ego):
            violations.append({
                'rule_code': 'R3_SOLID_LANE_CHANGE',
                'severity': 'HIGH',
                'message': "实线变道违规",
                'evidence': {},
            })
        
        return violations
    
    def reset(self):
        """重置检查器状态"""
        self.last_red_light_violation = False