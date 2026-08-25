"""
空间关系计算 (v3 §2.8)
复用 SpatioTemporalKG 的空间关系算法
"""
import numpy as np
from typing import Dict, Any, List, Optional


def compute_ahead_of(v1: Dict[str, Any], v2: Dict[str, Any], 
                     threshold: float = 0.0) -> bool:
    """
    计算 v1 是否在 v2 前方
    
    条件：
    1. 同车道或近距离
    2. 纵向距离 > 0
    """
    dx = v1['x'] - v2['x']
    dy = v1['y'] - v2['y']
    
    # 使用 v2 的航向角计算纵向分量
    yaw_v2 = v2.get('yaw', 0.0)
    forward_vec = np.array([np.cos(yaw_v2), np.sin(yaw_v2)])
    relative_pos = np.array([dx, dy])
    longitudinal = np.dot(forward_vec, relative_pos)
    
    return longitudinal > threshold


def compute_beside(v1: Dict[str, Any], v2: Dict[str, Any],
                   lateral_threshold: float = 3.0,
                   longitudinal_threshold: float = 5.0) -> bool:
    """
    计算 v1 是否在 v2 旁边
    
    条件：
    1. |横向距离| < lateral_threshold
    2. |纵向距离| < longitudinal_threshold
    """
    dx = v1['x'] - v2['x']
    dy = v1['y'] - v2['y']
    
    yaw_v2 = v2.get('yaw', 0.0)
    forward_vec = np.array([np.cos(yaw_v2), np.sin(yaw_v2)])
    lateral_vec = np.array([-np.sin(yaw_v2), np.cos(yaw_v2)])
    
    relative_pos = np.array([dx, dy])
    longitudinal = abs(np.dot(forward_vec, relative_pos))
    lateral = abs(np.dot(lateral_vec, relative_pos))
    
    return lateral < lateral_threshold and longitudinal < longitudinal_threshold


def compute_nearby_pedestrian(vehicle: Dict[str, Any], 
                              pedestrian: Dict[str, Any],
                              distance_threshold: float = 20.0) -> bool:
    """
    计算车辆是否在行人附近
    """
    dx = vehicle['x'] - pedestrian['x']
    dy = vehicle['y'] - pedestrian['y']
    distance = np.sqrt(dx**2 + dy**2)
    
    return distance < distance_threshold


def compute_controlled_by(vehicle: Dict[str, Any],
                          traffic_light: Dict[str, Any],
                          distance_threshold: float = 50.0) -> bool:
    """
    计算交通灯是否控制车辆
    
    简化实现：距离在阈值内且在同一道路上
    """
    dx = vehicle['x'] - traffic_light['x']
    dy = vehicle['y'] - traffic_light['y']
    distance = np.sqrt(dx**2 + dy**2)
    
    if distance > distance_threshold:
        return False
    
    # 简化：同方向
    yaw_tl = traffic_light.get('yaw', 0.0)
    yaw_v = vehicle.get('yaw', 0.0)
    
    angle_diff = abs(yaw_tl - yaw_v)
    angle_diff = min(angle_diff, 2 * np.pi - angle_diff)
    
    return angle_diff < np.pi / 4  # 45度内


def compute_in_lane(vehicle: Dict[str, Any],
                    lane: Dict[str, Any],
                    lateral_threshold: float = 2.0) -> bool:
    """
    计算车辆是否在车道内
    """
    # 简化实现：基于横向距离
    dx = vehicle['x'] - lane.get('x', 0)
    dy = vehicle['y'] - lane.get('y', 0)
    
    yaw_lane = lane.get('yaw', 0.0)
    lateral_vec = np.array([-np.sin(yaw_lane), np.cos(yaw_lane)])
    relative_pos = np.array([dx, dy])
    lateral = abs(np.dot(lateral_vec, relative_pos))
    
    return lateral < lateral_threshold


def compute_all_spatial_relations(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    计算当前帧的所有空间关系
    
    返回关系列表，每个关系包含 src_id, dst_id, relation_type
    """
    relations = []
    
    vehicles = snapshot.get('vehicles', [])
    pedestrians = snapshot.get('pedestrians', [])
    traffic_lights = snapshot.get('traffic_lights', [])
    
    # 1. 车辆间关系
    for i, v1 in enumerate(vehicles):
        for j, v2 in enumerate(vehicles[i+1:], i+1):
            # ahead_of 关系
            if compute_ahead_of(v1, v2):
                relations.append({
                    'src_id': v1['entity_id'],
                    'dst_id': v2['entity_id'],
                    'relation_type': 'ahead_of',
                })
            
            # beside 关系
            if compute_beside(v1, v2):
                relations.append({
                    'src_id': v1['entity_id'],
                    'dst_id': v2['entity_id'],
                    'relation_type': 'beside',
                })
    
    # 2. 车辆-行人关系
    for v in vehicles:
        for p in pedestrians:
            if compute_nearby_pedestrian(v, p):
                relations.append({
                    'src_id': v['entity_id'],
                    'dst_id': p['entity_id'],
                    'relation_type': 'nearby_pedestrian',
                })
    
    # 3. 交通灯控制关系
    for v in vehicles:
        for tl in traffic_lights:
            if compute_controlled_by(v, tl):
                relations.append({
                    'src_id': tl['entity_id'],
                    'dst_id': v['entity_id'],
                    'relation_type': 'controlled_by',
                })
    
    return relations