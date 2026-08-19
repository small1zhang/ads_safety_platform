"""
快照构建器 (v3 §2.5)
将提取的原始数据构建为场景快照
"""
import time
from typing import Dict, Any, List

from ..ontology.types import EntityType
from .nodes import (
    VehicleEntity,
    PedestrianEntity,
    TrafficLightEntity,
    EnvironmentSnapshot,
    ScenarioSnapshot,
)


class SnapshotBuilder:
    """场景快照构建器"""
    
    def __init__(self):
        self.frame_counter = 0
    
    def build_snapshot(self, frame_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建单帧场景快照
        
        参数:
            frame_data: 从 CARLA 提取的原始数据
        
        返回:
            包含所有节点和关系的字典
        """
        self.frame_counter += 1
        
        # 1. 构建帧根节点
        snapshot = ScenarioSnapshot(
            entity_id=f"scene_{self.frame_counter}",
            entity_type=EntityType.SCENE_SNAPSHOT,
            frame_id=self.frame_counter,
            timestamp=time.time(),
            vehicle_count=len(frame_data.get('vehicles', [])),
            pedestrian_count=len(frame_data.get('pedestrians', [])),
            traffic_light_count=len(frame_data.get('traffic_lights', [])),
        )
        
        # 2. 构建实体节点
        vehicles = self._build_vehicle_entities(frame_data.get('vehicles', []))
        pedestrians = self._build_pedestrian_entities(frame_data.get('pedestrians', []))
        traffic_lights = self._build_traffic_light_entities(frame_data.get('traffic_lights', []))
        
        # 3. 构建环境节点
        env_snapshot = EnvironmentSnapshot(
            entity_id=f"env_{self.frame_counter}",
            entity_type=EntityType.ENV_SNAPSHOT,
            frame_id=self.frame_counter,
            timestamp=time.time(),
            weather="Clear",  # 占位，实际从 CARLA 获取
        )
        
        # 4. 构建包含关系
        contains_relations = self._build_contains_relations(
            snapshot.entity_id,
            vehicles,
            pedestrians,
            traffic_lights
        )
        
        return {
            'snapshot': snapshot.dict(),
            'environment': env_snapshot.dict(),
            'vehicles': [v.dict() for v in vehicles],
            'pedestrians': [p.dict() for p in pedestrians],
            'traffic_lights': [tl.dict() for tl in traffic_lights],
            'contains_relations': contains_relations,
        }
    
    def _build_vehicle_entities(self, raw_vehicles: List[Dict]) -> List[VehicleEntity]:
        """构建车辆实体列表"""
        entities = []
        for v in raw_vehicles:
            try:
                # 计算速度和航向角
                vx = v.get('velocity', {}).get('x', 0)
                vy = v.get('velocity', {}).get('y', 0)
                speed = (vx**2 + vy**2) ** 0.5
                
                # 航向角（从 CARLA 的 yaw 转换）
                transform = v.get('transform', {})
                yaw = transform.get('yaw', 0)
                import math
                yaw_rad = math.radians(yaw)
                
                entity = VehicleEntity(
                    entity_id=f"veh_{v.get('id', 'unknown')}",
                    entity_type=EntityType.VEHICLE,
                    actor_type=v.get('type_id', 'vehicle.unknown'),
                    role_name=v.get('role_name', 'npc'),
                    x=v.get('location', {}).get('x', 0),
                    y=v.get('location', {}).get('y', 0),
                    z=v.get('location', {}).get('z', 0),
                    speed=speed,
                    yaw=yaw_rad,
                    vx=vx,
                    vy=vy,
                    throttle=v.get('control', {}).get('throttle', 0),
                    brake=v.get('control', {}).get('brake', 0),
                    steer=v.get('control', {}).get('steer', 0),
                )
                entities.append(entity)
            except Exception as e:
                print(f"构建车辆实体失败: {e}")
                continue
        return entities
    
    def _build_pedestrian_entities(self, raw_pedestrians: List[Dict]) -> List[PedestrianEntity]:
        """构建行人实体列表"""
        entities = []
        for p in raw_pedestrians:
            try:
                vx = p.get('velocity', {}).get('x', 0)
                vy = p.get('velocity', {}).get('y', 0)
                speed = (vx**2 + vy**2) ** 0.5
                
                import math
                yaw_rad = math.atan2(vy, vx) if speed > 0.1 else 0.0
                
                entity = PedestrianEntity(
                    entity_id=f"ped_{p.get('id', 'unknown')}",
                    entity_type=EntityType.PEDESTRIAN,
                    x=p.get('location', {}).get('x', 0),
                    y=p.get('location', {}).get('y', 0),
                    z=p.get('location', {}).get('z', 0),
                    speed=speed,
                    yaw=yaw_rad,
                    vx=vx,
                    vy=vy,
                )
                entities.append(entity)
            except Exception as e:
                print(f"构建行人实体失败: {e}")
                continue
        return entities
    
    def _build_traffic_light_entities(self, raw_tls: List[Dict]) -> List[TrafficLightEntity]:
        """构建交通灯实体列表"""
        entities = []
        for tl in raw_tls:
            try:
                entity = TrafficLightEntity(
                    entity_id=f"tl_{tl.get('id', 'unknown')}",
                    entity_type=EntityType.TRAFFIC_LIGHT,
                    x=tl.get('location', {}).get('x', 0),
                    y=tl.get('location', {}).get('y', 0),
                    z=tl.get('location', {}).get('z', 0),
                    state=tl.get('state', 'Green'),
                )
                entities.append(entity)
            except Exception as e:
                print(f"构建交通灯实体失败: {e}")
                continue
        return entities
    
    def _build_contains_relations(self, 
                                  snapshot_id: str,
                                  vehicles: List[VehicleEntity],
                                  pedestrians: List[PedestrianEntity],
                                  traffic_lights: List[TrafficLightEntity]) -> List[Dict]:
        """构建包含关系"""
        relations = []
        
        for v in vehicles:
            relations.append({
                'src_id': snapshot_id,
                'dst_id': v.entity_id,
                'relation_type': 'containsVehicle',
            })
        
        for p in pedestrians:
            relations.append({
                'src_id': snapshot_id,
                'dst_id': p.entity_id,
                'relation_type': 'containsPedestrian',
            })
        
        for tl in traffic_lights:
            relations.append({
                'src_id': snapshot_id,
                'dst_id': tl.entity_id,
                'relation_type': 'containsTrafficLight',
            })
        
        return relations