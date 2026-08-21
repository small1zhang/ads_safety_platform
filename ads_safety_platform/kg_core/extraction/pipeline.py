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
        # 支持两种格式：
        # 1. 嵌套格式: {'location': {'x': 0, 'y': 0}, 'velocity': {'x': 0, 'y': 15}}
        # 2. 扁平格式: {'x': 0, 'y': 0, 'vx': 0, 'vy': 15, 'speed': 15}
        
        # 位置
        if 'location' in v:
            x = v['location'].get('x', 0)
            y = v['location'].get('y', 0)
            z = v['location'].get('z', 0)
        else:
            x = v.get('x', 0)
            y = v.get('y', 0)
            z = v.get('z', 0)
        
        # 速度
        if 'velocity' in v:
            vx = v['velocity'].get('x', 0)
            vy = v['velocity'].get('y', 0)
        else:
            vx = v.get('vx', 0)
            vy = v.get('vy', 0)
        
        speed = v.get('speed', 0)
        if speed == 0 and (vx != 0 or vy != 0):
            speed = math.sqrt(vx**2 + vy**2)
        
        # 航向角
        if 'transform' in v:
            yaw = math.radians(v['transform'].get('yaw', 0))
        else:
            yaw = v.get('yaw', 0)
            # 如果 yaw 是角度，转换为弧度
            if abs(yaw) > math.pi:
                yaw = math.radians(yaw)
        
        # 控制
        if 'control' in v:
            throttle = v['control'].get('throttle', 0)
            brake = v['control'].get('brake', 0)
            steer = v['control'].get('steer', 0)
        else:
            throttle = v.get('throttle', 0)
            brake = v.get('brake', 0)
            steer = v.get('steer', 0)
        
        return {
            'entity_id': v.get('entity_id', f"veh_{id(v)}"),
            'type_id': v.get('type_id', 'vehicle.unknown'),
            'role_name': v.get('role_name', 'npc'),
            'x': x,
            'y': y,
            'z': z,
            'vx': vx,
            'vy': vy,
            'speed': speed,
            'yaw': yaw,
            'throttle': throttle,
            'brake': brake,
            'steer': steer,
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
        # 支持扁平格式
        return {
            'entity_id': f"tl_{tl.get('entity_id', tl.get('id', 'unknown'))}",
            'x': tl.get('x', 0),
            'y': tl.get('y', 0),
            'z': tl.get('z', 0),
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