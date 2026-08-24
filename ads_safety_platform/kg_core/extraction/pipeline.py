"""
数据提取器编排器
整合所有提取器，输出标准化字典

增强功能:
- 完善的CARLA数据提取
- 行人数据支持
- 交通灯状态解析
- 障碍物检测
- 数据验证和错误处理
"""
import math
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TrafficLightState(Enum):
    """交通灯状态枚举"""
    RED = "Red"
    YELLOW = "Yellow"
    GREEN = "Green"
    UNKNOWN = "Unknown"


@dataclass
class ValidationConfig:
    """数据验证配置"""
    max_vehicle_speed: float = 100.0  # 最大车速 (m/s)
    max_pedestrian_speed: float = 5.0  # 最大行人速度 (m/s)
    max_coordinate: float = 10000.0  # 最大坐标值
    min_coordinate: float = -10000.0  # 最小坐标值
    required_vehicle_fields: List[str] = None  # 必需车辆字段
    required_tl_fields: List[str] = None  # 必需交通灯字段
    
    def __post_init__(self):
        if self.required_vehicle_fields is None:
            self.required_vehicle_fields = ['x', 'y', 'speed']
        if self.required_tl_fields is None:
            self.required_tl_fields = ['x', 'y', 'state']


class ExtractionPipeline:
    """数据提取器编排器"""
    
    def __init__(self, carla_world=None, validation_config: ValidationConfig = None):
        """
        初始化提取器
        
        参数:
            carla_world: CARLA World 对象 (可选，离线模式可为 None)
            validation_config: 数据验证配置
        """
        self.world = carla_world
        self.validation_config = validation_config or ValidationConfig()
        self._frame_counter = 0
    
    def process_frame(self, raw_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        处理单帧数据
        
        参数:
            raw_data: 从 CARLA 提取的原始数据字典 (可选)
        
        返回:
            标准化的帧数据字典
        """
        self._frame_counter += 1
        
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
        try:
            vehicles = []
            for v in raw_data.get('vehicles', []):
                try:
                    vehicle = self._normalize_vehicle_data(v)
                    if self._validate_vehicle_data(vehicle):
                        vehicles.append(vehicle)
                    else:
                        logger.warning(f"车辆数据验证失败: {v.get('entity_id', 'unknown')}")
                except Exception as e:
                    logger.error(f"处理车辆数据失败: {e}")
                    continue
            
            pedestrians = []
            for p in raw_data.get('pedestrians', []):
                try:
                    pedestrian = self._normalize_pedestrian_data(p)
                    if self._validate_pedestrian_data(pedestrian):
                        pedestrians.append(pedestrian)
                    else:
                        logger.warning(f"行人数据验证失败: {p.get('entity_id', 'unknown')}")
                except Exception as e:
                    logger.error(f"处理行人数据失败: {e}")
                    continue
            
            traffic_lights = []
            for tl in raw_data.get('traffic_lights', []):
                try:
                    traffic_light = self._normalize_traffic_light_data(tl)
                    if self._validate_traffic_light_data(traffic_light):
                        traffic_lights.append(traffic_light)
                    else:
                        logger.warning(f"交通灯数据验证失败: {tl.get('entity_id', 'unknown')}")
                except Exception as e:
                    logger.error(f"处理交通灯数据失败: {e}")
                    continue
            
            # 提取障碍物
            obstacles = []
            for obs in raw_data.get('obstacles', []):
                try:
                    obstacle = self._normalize_obstacle_data(obs)
                    if self._validate_obstacle_data(obstacle):
                        obstacles.append(obstacle)
                except Exception as e:
                    logger.error(f"处理障碍物数据失败: {e}")
                    continue
            
            return {
                'vehicles': vehicles,
                'pedestrians': pedestrians,
                'traffic_lights': traffic_lights,
                'obstacles': obstacles,
                'timestamp': raw_data.get('timestamp', time.time()),
                'frame_id': self._frame_counter,
            }
        
        except Exception as e:
            logger.error(f"处理帧数据失败: {e}")
            # 返回空数据而不是崩溃
            return {
                'vehicles': [],
                'pedestrians': [],
                'traffic_lights': [],
                'obstacles': [],
                'timestamp': time.time(),
                'frame_id': self._frame_counter,
                'error': str(e),
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
        
        # 车辆尺寸 (可选)
        width = v.get('width', 2.0)
        length = v.get('length', 4.5)
        height = v.get('height', 1.8)
        
        return {
            'entity_id': v.get('entity_id', f"veh_{id(v)}"),
            'type_id': v.get('type_id', 'vehicle.unknown'),
            'role_name': v.get('role_name', 'npc'),
            'x': float(x),
            'y': float(y),
            'z': float(z),
            'vx': float(vx),
            'vy': float(vy),
            'speed': float(speed),
            'yaw': float(yaw),
            'throttle': float(throttle),
            'brake': float(brake),
            'steer': float(steer),
            'width': float(width),
            'length': float(length),
            'height': float(height),
        }
    
    def _normalize_pedestrian_data(self, p: Dict) -> Dict[str, Any]:
        """标准化行人数据"""
        # 支持嵌套和扁平格式
        if 'location' in p:
            x = p['location'].get('x', 0)
            y = p['location'].get('y', 0)
            z = p['location'].get('z', 0)
        else:
            x = p.get('x', 0)
            y = p.get('y', 0)
            z = p.get('z', 0)
            
        if 'velocity' in p:
            vx = p['velocity'].get('x', 0)
            vy = p['velocity'].get('y', 0)
        else:
            vx = p.get('vx', 0)
            vy = p.get('vy', 0)
        
        speed = math.sqrt(vx**2 + vy**2)
        
        # 航向角
        if 'transform' in p:
            yaw = math.radians(p['transform'].get('yaw', 0))
        else:
            yaw = p.get('yaw', 0)
            if abs(yaw) > math.pi:
                yaw = math.radians(yaw)
        
        return {
            'entity_id': f"ped_{p.get('id', p.get('entity_id', 'unknown'))}",
            'x': float(x),
            'y': float(y),
            'z': float(z),
            'vx': float(vx),
            'vy': float(vy),
            'speed': float(speed),
            'yaw': float(yaw),
        }
    
    def _normalize_traffic_light_data(self, tl: Dict) -> Dict[str, Any]:
        """标准化交通灯数据"""
        # 支持多种格式
        if 'location' in tl:
            x = tl['location'].get('x', 0)
            y = tl['location'].get('y', 0)
            z = tl['location'].get('z', 0)
        else:
            x = tl.get('x', 0)
            y = tl.get('y', 0)
            z = tl.get('z', 0)
        
        # 解析交通灯状态
        state = tl.get('state', 'Green')
        if isinstance(state, str):
            # 标准化状态字符串
            state = state.lower().capitalize()
            if state not in [s.value for s in TrafficLightState]:
                state = TrafficLightState.UNKNOWN.value
        elif hasattr(state, 'name'):
            # CARLA 的 state 对象
            state = state.name
            if state not in [s.value for s in TrafficLightState]:
                state = TrafficLightState.UNKNOWN.value
        else:
            state = TrafficLightState.UNKNOWN.value
        
        return {
            'entity_id': f"tl_{tl.get('entity_id', tl.get('id', 'unknown'))}",
            'x': float(x),
            'y': float(y),
            'z': float(z),
            'state': state,
        }
    
    def _normalize_obstacle_data(self, obs: Dict) -> Dict[str, Any]:
        """标准化障碍物数据"""
        if 'location' in obs:
            x = obs['location'].get('x', 0)
            y = obs['location'].get('y', 0)
            z = obs['location'].get('z', 0)
        else:
            x = obs.get('x', 0)
            y = obs.get('y', 0)
            z = obs.get('z', 0)
        
        if 'extent' in obs:
            width = obs['extent'].get('x', 1.0)
            length = obs['extent'].get('y', 1.0)
            height = obs['extent'].get('z', 1.0)
        else:
            width = obs.get('width', 1.0)
            length = obs.get('length', 1.0)
            height = obs.get('height', 1.0)
        
        return {
            'entity_id': f"obs_{obs.get('id', obs.get('entity_id', 'unknown'))}",
            'type_id': obs.get('type_id', 'obstacle.unknown'),
            'x': float(x),
            'y': float(y),
            'z': float(z),
            'width': float(width),
            'length': float(length),
            'height': float(height),
        }
    
    def _validate_vehicle_data(self, v: Dict) -> bool:
        """验证车辆数据"""
        config = self.validation_config
        
        # 检查必需字段
        for field in config.required_vehicle_fields:
            if field not in v:
                logger.warning(f"车辆缺少必需字段: {field}")
                return False
        
        # 检查数值范围
        if abs(v.get('x', 0)) > config.max_coordinate:
            return False
        if abs(v.get('y', 0)) > config.max_coordinate:
            return False
        if v.get('speed', 0) > config.max_vehicle_speed:
            return False
        
        return True
    
    def _validate_pedestrian_data(self, p: Dict) -> bool:
        """验证行人数据"""
        config = self.validation_config
        
        # 检查必需字段
        if 'x' not in p or 'y' not in p:
            return False
        
        # 检查数值范围
        if abs(p.get('x', 0)) > config.max_coordinate:
            return False
        if abs(p.get('y', 0)) > config.max_coordinate:
            return False
        if p.get('speed', 0) > config.max_pedestrian_speed:
            return False
        
        return True
    
    def _validate_traffic_light_data(self, tl: Dict) -> bool:
        """验证交通灯数据"""
        config = self.validation_config
        
        # 检查必需字段
        for field in config.required_tl_fields:
            if field not in tl:
                return False
        
        # 检查坐标范围
        if abs(tl.get('x', 0)) > config.max_coordinate:
            return False
        if abs(tl.get('y', 0)) > config.max_coordinate:
            return False
        
        # 检查状态有效性
        if tl.get('state') not in [s.value for s in TrafficLightState]:
            return False
        
        return True
    
    def _validate_obstacle_data(self, obs: Dict) -> bool:
        """验证障碍物数据"""
        config = self.validation_config
        
        # 检查必需字段
        if 'x' not in obs or 'y' not in obs:
            return False
        
        # 检查坐标范围
        if abs(obs.get('x', 0)) > config.max_coordinate:
            return False
        if abs(obs.get('y', 0)) > config.max_coordinate:
            return False
        
        return True
    
    def _extract_from_carla(self) -> Dict[str, Any]:
        """从 CARLA 实时提取数据"""
        if not self.world:
            raise RuntimeError("CARLA world 未初始化")
        
        try:
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
                
                # 获取车辆尺寸
                bounding_box = actor.bounding_box
                width = bounding_box.extent.y * 2  # CARLA 中 Y 是宽度
                length = bounding_box.extent.x * 2  # CARLA 中 X 是长度
                height = bounding_box.extent.z * 2
                
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
                    'width': width,
                    'length': length,
                    'height': height,
                })
            
            pedestrians = []
            for actor in self.world.get_actors().filter('walker.pedestrian*'):
                if not actor.is_alive:
                    continue
                
                location = actor.get_location()
                velocity = actor.get_velocity()
                
                vx, vy = velocity.x, velocity.y
                speed = math.sqrt(vx**2 + vy**2)
                
                # 获取行人尺寸
                bounding_box = actor.bounding_box
                width = bounding_box.extent.y * 2
                length = bounding_box.extent.x * 2
                height = bounding_box.extent.z * 2
                
                pedestrians.append({
                    'entity_id': f"ped_{actor.id}",
                    'x': location.x,
                    'y': location.y,
                    'z': location.z,
                    'vx': vx,
                    'vy': vy,
                    'speed': speed,
                    'yaw': math.atan2(vy, vx) if speed > 0.1 else 0.0,
                    'width': width,
                    'length': length,
                    'height': height,
                })
            
            traffic_lights = []
            for actor in self.world.get_actors().filter('traffic.traffic_light*'):
                if not actor.is_alive:
                    continue
                
                location = actor.get_location()
                state = actor.get_state()
                
                # 解析交通灯状态
                state_name = state.name if hasattr(state, 'name') else str(state)
                
                traffic_lights.append({
                    'entity_id': f"tl_{actor.id}",
                    'x': location.x,
                    'y': location.y,
                    'z': location.z,
                    'state': state_name,
                })
            
            # 提取障碍物 (静态障碍物)
            obstacles = []
            for actor in self.world.get_actors().filter('static.prop*'):
                if not actor.is_alive:
                    continue
                
                location = actor.get_location()
                bounding_box = actor.bounding_box
                
                obstacles.append({
                    'entity_id': f"obs_{actor.id}",
                    'type_id': actor.type_id,
                    'x': location.x,
                    'y': location.y,
                    'z': location.z,
                    'width': bounding_box.extent.y * 2,
                    'length': bounding_box.extent.x * 2,
                    'height': bounding_box.extent.z * 2,
                })
            
            return {
                'vehicles': vehicles,
                'pedestrians': pedestrians,
                'traffic_lights': traffic_lights,
                'obstacles': obstacles,
                'timestamp': time.time(),
                'frame_id': self._frame_counter,
            }
        
        except Exception as e:
            logger.error(f"从 CARLA 提取数据失败: {e}")
            return {
                'vehicles': [],
                'pedestrians': [],
                'traffic_lights': [],
                'obstacles': [],
                'timestamp': time.time(),
                'frame_id': self._frame_counter,
                'error': str(e),
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取提取统计信息"""
        return {
            'frame_counter': self._frame_counter,
            'validation_config': {
                'max_vehicle_speed': self.validation_config.max_vehicle_speed,
                'max_pedestrian_speed': self.validation_config.max_pedestrian_speed,
                'max_coordinate': self.validation_config.max_coordinate,
            }
        }
