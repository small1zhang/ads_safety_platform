#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
carla_connector.py - CARLA仿真环境连接模块

功能：
1. 连接到运行中的CARLA服务器
2. 提取车辆、行人、交通灯等实体状态
3. 将实体状态转换为场景数据格式
4. 支持实时数据采集和离线模式

依赖：
- carla Python API (pip install carla)
- CARLA服务器运行在localhost:2000

用法：
    from scenarios.builders.carla_connector import CarlaClient, ScenarioExtractor
    
    # 连接CARLA
    client = CarlaClient(host="localhost", port=2000, timeout=10.0)
    
    # 提取场景数据
    extractor = ScenarioExtractor(client)
    scenario = extractor.extract_current_scene(ego_actor_id=123)
    
    # 验证场景
    validator = ScenarioValidator()
    result = validator.validate(scenario)
"""

import sys
import math
import time
import random
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple

from scenarios.builders.scenario_injector import (
    Scenario, VehicleConfig, TrafficLightConfig, PedestrianConfig,
    ScenarioType, TrafficLightState
)


@dataclass
class CarlaActorState:
    """CARLA实体状态"""
    actor_id: int
    actor_type: str
    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float
    yaw: float
    pitch: float = 0.0
    roll: float = 0.0
    is_alive: bool = True


class CARLAAvailableError(Exception):
    """CARLA不可用时抛出"""
    pass


class CARLAClient:
    """CARLA客户端封装"""
    
    def __init__(self, host: str = "localhost", port: int = 2000, timeout: float = 10.0):
        """
        初始化CARLA客户端
        
        参数:
            host: CARLA服务器主机地址
            port: CARLA服务器端口
            timeout: 连接超时时间
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.client = None
        self.world = None
        self.map = None
        self._connected = False
        self._carla_module = None
        
        try:
            import carla
            self._carla_module = carla
            self._connect()
        except ImportError:
            print("警告: CARLA Python模块未安装")
            print("       请安装: pip install carla")
            print("       或从 https://carla.org/download 获取")
            self._connected = False
    
    def _connect(self) -> bool:
        """建立与CARLA服务器的连接"""
        if self._carla_module is None:
            raise CARLAAvailableError("CARLA模块未安装")
        
        try:
            self.client = self._carla_module.Client(self.host, self.port)
            self.client.set_timeout(self.timeout)
            
            # 加载地图
            self.world = self.client.get_world()
            self.map = self.world.get_map()
            self._connected = True
            return True
        except Exception as e:
            print(f"CARLA连接失败: {e}")
            self._connected = False
            return False
    
    def is_connected(self) -> bool:
        """检查是否已连接到CARLA"""
        if not self._connected or self.client is None:
            # 尝试重新连接
            return self._connect()
        try:
            self.client.get_world()
            return True
        except:
            return self._connect()
    
    def get_world(self):
        """获取当前世界"""
        if not self._connected:
            raise CARLAAvailableError("未连接到CARLA服务器")
        return self.world
    
    def get_map(self):
        """获取当前地图"""
        if not self._connected:
            raise CARLAAvailableError("未连接到CARLA服务器")
        return self.map
    
    def get_all_vehicles(self) -> List[CarlaActorState]:
        """获取所有车辆状态"""
        if not self._connected:
            return []
        
        actors = self.world.get_actors()
        vehicles = []
        
        for actor in actors.filter('vehicle.*'):
            transform = actor.get_transform()
            velocity = actor.get_velocity()
            
            state = CarlaActorState(
                actor_id=actor.id,
                actor_type=actor.type_id,
                x=transform.location.x,
                y=transform.location.y,
                z=transform.location.z,
                vx=velocity.x,
                vy=velocity.y,
                vz=velocity.z,
                yaw=math.radians(transform.rotation.yaw),
                pitch=math.radians(transform.rotation.pitch),
                roll=math.radians(transform.rotation.roll)
            )
            vehicles.append(state)
        
        return vehicles
    
    def get_all_pedestrians(self) -> List[CarlaActorState]:
        """获取所有行人状态"""
        if not self._connected:
            return []
        
        actors = self.world.get_actors()
        pedestrians = []
        
        for actor in actors.filter('walker.pedestrian.*'):
            transform = actor.get_transform()
            velocity = actor.get_velocity()
            
            state = CarlaActorState(
                actor_id=actor.id,
                actor_type=actor.type_id,
                x=transform.location.x,
                y=transform.location.y,
                z=transform.location.z,
                vx=velocity.x,
                vy=velocity.y,
                vz=velocity.z,
                yaw=math.radians(transform.rotation.yaw)
            )
            pedestrians.append(state)
        
        return pedestrians
    
    def get_all_traffic_lights(self) -> List[Dict[str, Any]]:
        """获取所有交通灯状态"""
        if not self._connected:
            return []
        
        actors = self.world.get_actors()
        lights = []
        
        for actor in actors.filter('traffic.traffic_light'):
            transform = actor.get_transform()
            state = actor.get_light_state()
            
            light_state = {
                'actor_id': actor.id,
                'x': transform.location.x,
                'y': transform.location.y,
                'z': transform.location.z,
                'state': state.color.name if hasattr(state.color, 'name') else 'Red',
                'is_intersection': actor.is_intersection if hasattr(actor, 'is_intersection') else False
            }
            lights.append(light_state)
        
        return lights
    
    def get_ego_vehicle(self, ego_id: Optional[int] = None) -> Optional[CarlaActorState]:
        """获取指定ego车辆状态"""
        if not self._connected:
            return None
        
        actors = self.world.get_actors()
        
        if ego_id is not None:
            for actor in actors.filter('vehicle.*'):
                if actor.id == ego_id:
                    transform = actor.get_transform()
                    velocity = actor.get_velocity()
                    
                    return CarlaActorState(
                        actor_id=actor.id,
                        actor_type=actor.type_id,
                        x=transform.location.x,
                        y=transform.location.y,
                        z=transform.location.z,
                        vx=velocity.x,
                        vy=velocity.y,
                        vz=velocity.z,
                        yaw=math.radians(transform.rotation.yaw)
                    )
        else:
            # 默认返回第一个车辆作为ego
            vehicles = actors.filter('vehicle.*')
            if vehicles:
                actor = vehicles[0]
                transform = actor.get_transform()
                velocity = actor.get_velocity()
                
                return CarlaActorState(
                    actor_id=actor.id,
                    actor_type=actor.type_id,
                    x=transform.location.x,
                    y=transform.location.y,
                    z=transform.location.z,
                    vx=velocity.x,
                    vy=velocity.y,
                    vz=velocity.z,
                    yaw=math.radians(transform.rotation.yaw)
                )
        
        return None
    
    def close(self):
        """断开连接"""
        self._connected = False
        self.client = None
        self.world = None
        self.map = None


class ScenarioExtractor:
    """场景数据提取器 - 从CARLA提取场景数据"""
    
    def __init__(self, client: CARLAClient):
        self.client = client
    
    def extract_current_scene(self, ego_actor_id: Optional[int] = None) -> Scenario:
        """
        从当前CARLA场景提取Scenario数据
        
        参数:
            ego_actor_id: ego车辆ID (none为自动检测)
        
        返回:
            Scenario对象
        """
        if not self.client.is_connected():
            raise CARLAAvailableError("未连接到CARLA服务器")
        
        # 获取ego车辆
        ego_state = self.client.get_ego_vehicle(ego_actor_id)
        if ego_state is None:
            raise ValueError("未找到ego车辆")
        
        # 创建场景
        scenario = Scenario(
            name=f"CARLA实时场景 - Actor {ego_actor_id or ego_state.actor_id}",
            scenario_type=ScenarioType.STRAIGHT_ROAD,
            description="从CARLA实时仿真提取的场景"
        )
        
        # 设置ego车辆配置
        speed = math.sqrt(ego_state.vx**2 + ego_state.vy**2)
        scenario.ego_vehicle = VehicleConfig(
            x=ego_state.x, y=ego_state.y,
            speed=speed, yaw=ego_state.yaw,
            vehicle_type=ego_state.actor_type, role="ego"
        )
        
        # 获取所有车辆
        all_vehicles = self.client.get_all_vehicles()
        for v in all_vehicles:
            if v.actor_id != ego_state.actor_id:
                v_speed = math.sqrt(v.vx**2 + v.vy**2)
                scenario.vehicles.append(VehicleConfig(
                    x=v.x, y=v.y,
                    speed=v_speed, yaw=v.yaw,
                    vehicle_type=v.actor_type, role="npc"
                ))
        
        # 获取交通灯
        for light in self.client.get_all_traffic_lights():
            scenario.traffic_lights.append(TrafficLightConfig(
                x=light['x'], y=light['y'],
                state=TrafficLightState(light['state'])
            ))
        
        # 获取行人
        for ped in self.client.get_all_pedestrians():
            ped_speed = math.sqrt(ped.vx**2 + ped.vy**2)
            scenario.pedestrians.append(PedestrianConfig(
                x=ped.x, y=ped.y,
                speed=ped_speed, direction=ped.yaw
            ))
        
        return scenario


class CARLAFallback:
    """CARLA不可用时的备用方案"""
    
    @staticmethod
    def generate_random_scenario(seed: int = 42) -> Scenario:
        """生成随机场景（用于演示）"""
        random.seed(seed)
        
        from scenarios.builders.scenario_injector import ScenarioBuilder
        builder = ScenarioBuilder(seed=seed)
        
        # 随机选择场景类型
        scenario_type = random.choice([
            'straight_road', 'intersection', 'merge', 
            'lane_change', 'red_light', 'pedestrian_crossing'
        ])
        
        if scenario_type == 'straight_road':
            return builder.create_straight_road_scenario(
                ego_speed=random.uniform(15, 25),
                num_vehicles=random.randint(2, 5),
                road_length=100.0
            )
        elif scenario_type == 'intersection':
            return builder.create_intersection_scenario()
        elif scenario_type == 'merge':
            return builder.create_merge_scenario()
        elif scenario_type == 'lane_change':
            return builder.create_lane_change_scenario()
        elif scenario_type == 'red_light':
            return builder.create_red_light_scenario()
        else:
            return builder.create_pedestrian_crossing_scenario()


# 主验证流程
def run_carla_validation(
    host: str = "localhost",
    port: int = 2000,
    ego_id: Optional[int] = None,
    timeout: float = 10.0
) -> Tuple[Scenario, Any]:
    """
    运行CARLA场景验证
    
    返回:
        (scenario, validation_result)
    """
    # 尝试连接CARLA
    try:
        client = CARLAClient(host, port, timeout)
        
        if client.is_connected():
            print(f"✅ 已连接到CARLA服务器 {host}:{port}")
            
            # 提取场景
            extractor = ScenarioExtractor(client)
            scenario = extractor.extract_current_scene(ego_id)
            
            # 验证
            from scenarios.builders.scenario_validator import ScenarioValidator
            validator = ScenarioValidator()
            result = validator.validate(scenario)
            
            client.close()
            return scenario, result
    except Exception as e:
        print(f"CARLA连接失败: {e}")
    
    # 使用备用方案
    print("⚠️ 使用备用模式：生成随机场景")
    scenario = CARLAFallback.generate_random_scenario()
    
    from scenarios.builders.scenario_validator import ScenarioValidator
    validator = ScenarioValidator()
    result = validator.validate(scenario)
    
    return scenario, result


if __name__ == "__main__":
    # 测试CARLA连接
    print("测试CARLA连接...")
    
    try:
        client = CARLAClient()
        if client.is_connected():
            print("✅ CARLA连接成功")
            
            ego = client.get_ego_vehicle()
            if ego:
                print(f"Ego车辆: ID={ego.actor_id}, Type={ego.actor_type}")
                print(f"位置: ({ego.x:.2f}, {ego.y:.2f})")
                print(f"速度: {math.sqrt(ego.vx**2 + ego.vy**2):.2f} m/s")
        else:
            print("⚠️ CARLA不可用")
    except CARLAAvailableError as e:
        print(f"CARLA不可用: {e}")
        print("建议:")
        print("  1. 启动CARLA模拟器: ./CarlaUE4.sh")
        print("  2. 安装CARLA Python API: pip install carla")
        print("  3. 或使用备用模式")