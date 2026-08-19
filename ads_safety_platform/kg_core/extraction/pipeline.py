"""
数据提取器编排器
整合所有提取器，输出标准化字典
"""
import math
from typing import Dict, Any, List


class ExtractionPipeline:
    """数据提取器编排器"""
    
    def __init__(self, carla_world=None):
        """
        初始化提取器
        
        参数:
            carla_world: CARLA World 对象 (可选，离线模式可为 None)
        """
        self.world = carla_world
    
    def process_frame(self, raw_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        处理单帧数据
        
        参数:
            raw_data: 从 CARLA 提取的原始数据字典 (可选)
        
        返回:
            标准化的帧数据字典
        """
        if raw_data is not None:
            # 离线模式：直接使用提供的数据
            return self._process_raw_data(raw_data)
        elif self.world is not None:
            # 在线模式：从 CARLA 实时提取
            return self._extract_from_carla()
        else:
            raise ValueError("必须提供 raw_data 或初始化 carla_world")
    
    def _process_raw_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理提供的原始数据"""
        vehicles = []
        for v in raw_data.get('vehicles', []):
            vehicle = self._normalize_vehicle_data(v)
            vehicles.append(vehicle)
        
        pedestrians = []
        for p in raw_data.get('pedestrians', []):
            pedestrian = self._normalize_pedestrian_data(p)
            pedestrians.append(pedestrian)
        
        traffic_lights = []
        for tl in raw_data.get('traffic_lights', []):
            traffic_light = self._normalize_traffic_light_data(tl)
            traffic_lights.append(traffic_light)
        
        return {
            'vehicles': vehicles,
            'pedestrians': pedestrians,
            'traffic_lights': traffic_lights,
            'timestamp': raw_data.get('timestamp', 0),
        }
    
    def _normalize_vehicle_data(self, v: Dict) -> Dict[str, Any]:
        """标准化车辆数据"""
        location = v.get('location', {})
        velocity = v.get('velocity', {})
        transform = v.get('transform', {})
        control = v.get('control', {})
        
        return {
            'entity_id': f"veh_{v.get('id', 'unknown')}",
            'type_id': v.get('type_id', 'vehicle.unknown'),
            'role_name': v.get('role_name', 'npc'),
            'x': location.get('x', 0),
            'y': location.get('y', 0),
            'z': location.get('z', 0),
            'vx': velocity.get('x', 0),
            'vy': velocity.get('y', 0),
            'speed': math.sqrt(velocity.get('x', 0)**2 + velocity.get('y', 0)**2),
            'yaw': math.radians(transform.get('yaw', 0)),
            'throttle': control.get('throttle', 0),
            'brake': control.get('brake', 0),
            'steer': control.get('steer', 0),
        }
    
    def _normalize_pedestrian_data(self, p: Dict) -> Dict[str, Any]:
        """标准化行人数据"""
        location = p.get('location', {})
        velocity = p.get('velocity', {})
        
        vx = velocity.get('x', 0)
        vy = velocity.get('y', 0)
        speed = math.sqrt(vx**2 + vy**2)
        
        return {
            'entity_id': f"ped_{p.get('id', 'unknown')}",
            'x': location.get('x', 0),
            'y': location.get('y', 0),
            'z': location.get('z', 0),
            'vx': vx,
            'vy': vy,
            'speed': speed,
            'yaw': math.atan2(vy, vx) if speed > 0.1 else 0.0,
        }
    
    def _normalize_traffic_light_data(self, tl: Dict) -> Dict[str, Any]:
        """标准化交通灯数据"""
        location = tl.get('location', {})
        
        return {
            'entity_id': f"tl_{tl.get('id', 'unknown')}",
            'x': location.get('x', 0),
            'y': location.get('y', 0),
            'z': location.get('z', 0),
            'state': tl.get('state', 'Green'),
        }
    
    def _extract_from_carla(self) -> Dict[str, Any]:
        """从 CARLA 实时提取数据"""
        if not self.world:
            raise RuntimeError("CARLA world 未初始化")
        
        vehicles = []
        for actor in self.world.get_actors().filter('vehicle.*'):
            if not actor.is_alive:
                continue
            
            location = actor.get_location()
            velocity = actor.get_velocity()
            transform = actor.get_transform()
            control = actor.get_control()
            
            vx, vy = velocity.x, velocity.y
            speed = math.sqrt(vx**2 + vy**2)
            
            vehicles.append({
                'entity_id': f"veh_{actor.id}",
                'type_id': actor.type_id,
                'role_name': actor.attributes.get('role_name', 'npc'),
                'x': location.x,
                'y': location.y,
                'z': location.z,
                'vx': vx,
                'vy': vy,
                'speed': speed,
                'yaw': math.radians(transform.rotation.yaw),
                'throttle': control.throttle,
                'brake': control.brake,
                'steer': control.steer,
            })
        
        pedestrians = []
        for actor in self.world.get_actors().filter('walker.pedestrian*'):
            if not actor.is_alive:
                continue
            
            location = actor.get_location()
            velocity = actor.get_velocity()
            
            vx, vy = velocity.x, velocity.y
            speed = math.sqrt(vx**2 + vy**2)
            
            pedestrians.append({
                'entity_id': f"ped_{actor.id}",
                'x': location.x,
                'y': location.y,
                'z': location.z,
                'vx': vx,
                'vy': vy,
                'speed': speed,
                'yaw': math.atan2(vy, vx) if speed > 0.1 else 0.0,
            })
        
        traffic_lights = []
        for actor in self.world.get_actors().filter('traffic.traffic_light*'):
            if not actor.is_alive:
                continue
            
            location = actor.get_location()
            state = actor.get_state()
            
            traffic_lights.append({
                'entity_id': f"tl_{actor.id}",
                'x': location.x,
                'y': location.y,
                'z': location.z,
                'state': state.name if hasattr(state, 'name') else str(state),
            })
        
        return {
            'vehicles': vehicles,
            'pedestrians': pedestrians,
            'traffic_lights': traffic_lights,
            'timestamp': time.time(),
        }