"""
行为检测器 (v3 §3.4)
复用 SpatioTemporalKG 的检测算法
"""
import math
from typing import Dict, Any, Optional

import numpy as np


def detect_following(ego: Dict[str, Any], npc: Dict[str, Any],
                     same_lane_threshold: float = 2.0,
                     distance_threshold: float = 12.0) -> bool:
    """
    检测跟车行为
    
    条件：
    1. 两车在同一车道（横向距离 < threshold）
    2. NPC 在自车前方（纵向距离 > 0）
    3. 纵向距离 < distance_threshold
    """
    dx = npc['x'] - ego['x']
    dy = npc['y'] - ego['y']
    distance = math.sqrt(dx**2 + dy**2)
    
    if distance >= distance_threshold:
        return False
    
    # 判断是否在前方
    yaw_ego = ego.get('yaw', 0.0)
    forward_vec = np.array([np.cos(yaw_ego), np.sin(yaw_ego)])
    relative_pos = np.array([dx, dy])
    longitudinal = np.dot(forward_vec, relative_pos)
    
    # 横向距离
    lateral_vec = np.array([-np.sin(yaw_ego), np.cos(yaw_ego)])
    lateral = abs(np.dot(lateral_vec, relative_pos))
    
    return longitudinal > 0 and lateral < same_lane_threshold


def detect_approaching(ego: Dict[str, Any], npc: Dict[str, Any],
                       distance_threshold: float = 20.0,
                       relative_speed_threshold: float = 1.0) -> bool:
    """
    检测接近行为
    
    条件：
    1. 距离 < distance_threshold
    2. 相对速度 > relative_speed_threshold（自车更快）
    """
    dx = npc['x'] - ego['x']
    dy = npc['y'] - ego['y']
    distance = math.sqrt(dx**2 + dy**2)
    
    if distance >= distance_threshold:
        return False
    
    # 计算相对速度
    rel_vx = ego.get('vx', 0) - npc.get('vx', 0)
    rel_vy = ego.get('vy', 0) - npc.get('vy', 0)
    relative_speed = math.sqrt(rel_vx**2 + rel_vy**2)
    
    return relative_speed > relative_speed_threshold


def detect_changing_lane(vehicle: Dict[str, Any],
                         lateral_speed_threshold: float = 0.5) -> bool:
    """
    检测变道行为
    
    条件：
    横向速度 > lateral_speed_threshold
    """
    yaw = vehicle.get('yaw', 0.0)
    vx = vehicle.get('vx', 0)
    vy = vehicle.get('vy', 0)
    
    # 计算横向速度
    lateral_vec = np.array([-math.sin(yaw), math.cos(yaw)])
    velocity_vec = np.array([vx, vy])
    lateral_speed = abs(np.dot(lateral_vec, velocity_vec))
    
    return lateral_speed > lateral_speed_threshold


def detect_standing_still(vehicle: Dict[str, Any],
                          speed_threshold: float = 0.1,
                          duration_frames: int = 3,
                          frame_counter: int = 0) -> bool:
    """
    检测静止行为
    
    条件：
    1. 速度 < speed_threshold
    2. 持续 duration_frames 帧
    """
    speed = vehicle.get('speed', 0)
    return speed < speed_threshold


def detect_yielding_to(vehicle: Dict[str, Any],
                       pedestrian: Dict[str, Any],
                       distance_threshold: float = 8.0) -> bool:
    """
    检测礼让行人行为
    
    条件：
    1. 车辆速度降低
    2. 行人在前方
    3. 距离 < distance_threshold
    """
    speed = vehicle.get('speed', 0)
    if speed > 5.0:  # 车辆速度较快，不认为是礼让
        return False
    
    dx = pedestrian['x'] - vehicle['x']
    dy = pedestrian['y'] - vehicle['y']
    distance = math.sqrt(dx**2 + dy**2)
    
    return distance < distance_threshold


def detect_opposite_direction(vehicle1: Dict[str, Any],
                              vehicle2: Dict[str, Any],
                              yaw_diff_threshold: float = 143.0) -> bool:
    """
    检测对向行驶
    
    条件：
    航向角差 > yaw_diff_threshold 度
    """
    yaw1 = vehicle1.get('yaw', 0.0)
    yaw2 = vehicle2.get('yaw', 0.0)
    
    # 计算航向角差
    diff = abs(yaw1 - yaw2)
    diff = min(diff, 2 * math.pi - diff)
    diff_deg = math.degrees(diff)
    
    return diff_deg > yaw_diff_threshold


def detect_approaching_pedestrian(vehicle: Dict[str, Any],
                                  pedestrian: Dict[str, Any],
                                  distance_threshold: float = 20.0,
                                  vehicle_speed_threshold: float = 5.0) -> bool:
    """
    检测接近行人行为
    
    条件：
    1. 距离 < distance_threshold
    2. 车辆速度 > vehicle_speed_threshold
    """
    dx = pedestrian['x'] - vehicle['x']
    dy = pedestrian['y'] - vehicle['y']
    distance = math.sqrt(dx**2 + dy**2)
    
    if distance >= distance_threshold:
        return False
    
    speed = vehicle.get('speed', 0)
    return speed > vehicle_speed_threshold


def detect_approaching_intersection(vehicle: Dict[str, Any],
                                   intersection_distance: float = 15.0) -> bool:
    """
    检测接近路口
    
    简化实现：检查是否在路口附近
    """
    # TODO: 需要从地图数据获取路口信息
    return False


def detect_overtaking(ego: Dict[str, Any],
                      npc: Dict[str, Any],
                      speed_diff_threshold: float = 2.0) -> bool:
    """
    检测超车行为
    
    条件：
    1. 两车并排
    2. 自车速度 > NPC 速度 + threshold
    """
    # 检查是否并排
    dx = npc['x'] - ego['x']
    dy = npc['y'] - ego['y']
    distance = math.sqrt(dx**2 + dy**2)
    
    if distance > 10.0:  # 距离太远
        return False
    
    # 检查速度差
    ego_speed = ego.get('speed', 0)
    npc_speed = npc.get('speed', 0)
    
    return ego_speed > npc_speed + speed_diff_threshold


def detect_wrong_side_meeting(vehicle1: Dict[str, Any],
                              vehicle2: Dict[str, Any],
                              distance_threshold: float = 30.0) -> bool:
    """
    检测逆行相遇
    
    条件：
    1. 对向行驶
    2. 距离 < distance_threshold
    """
    if not detect_opposite_direction(vehicle1, vehicle2):
        return False
    
    dx = vehicle2['x'] - vehicle1['x']
    dy = vehicle2['y'] - vehicle1['y']
    distance = math.sqrt(dx**2 + dy**2)
    
    return distance < distance_threshold


def detect_crossing(pedestrian: Dict[str, Any],
                    vehicle: Dict[str, Any],
                    angle_threshold: float = 60.0) -> bool:
    """
    检测行人横穿
    
    条件：
    1. 行人在人行横道上
    2. 行人移动方向与车辆方向夹角 > angle_threshold
    """
    # TODO: 需要行人横道数据
    return False