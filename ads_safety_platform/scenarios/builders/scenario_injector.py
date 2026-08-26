#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scenario_injector.py - 场景注入模块

功能：
1. 创建可配置的RSS验证场景
2. 支持不同交通情况（直行、转弯、并线、交叉口等）
3. 生成用于测试的合成场景数据

用法：
    from scenarios.builders import ScenarioBuilder
    
    # 创建直行场景
    builder = ScenarioBuilder()
    scenario = builder.create_straight_road_scenario()
    
    # 创建交叉口场景
    scenario = builder.create_intersection_scenario()
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum


class ScenarioType(Enum):
    """场景类型"""
    STRAIGHT_ROAD = "straight_road"      # 直行道路
    INTERSECTION = "intersection"        # 交叉口
    MERGE = "merge"                      # 合流
    LANE_CHANGE = "lane_change"          # 变道
    ROUNDABOUT = "roundabout"            # 环岛
    PARKING = "parking"                  # 停车场
    PEDESTRIAN_CROSSING = "pedestrian_crossing"  # 人行横道


class TrafficLightState(Enum):
    """交通灯状态"""
    RED = "Red"
    GREEN = "Green"
    YELLOW = "Yellow"


@dataclass
class VehicleConfig:
    """车辆配置"""
    x: float = 0.0
    y: float = 0.0
    speed: float = 10.0
    yaw: float = 0.0
    length: float = 4.5
    width: float = 1.8
    vehicle_type: str = "vehicle.default"
    role: str = "npc"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'x': self.x,
            'y': self.y,
            'speed': self.speed,
            'yaw': self.yaw,
            'length': self.length,
            'width': self.width,
            'type': self.vehicle_type,
            'role': self.role
        }


@dataclass
class TrafficLightConfig:
    """交通灯配置"""
    x: float = 0.0
    y: float = 0.0
    state: TrafficLightState = TrafficLightState.RED
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'x': self.x,
            'y': self.y,
            'state': self.state.value
        }


@dataclass
class PedestrianConfig:
    """行人配置"""
    x: float = 0.0
    y: float = 0.0
    speed: float = 1.0
    direction: float = 0.0  # 移动方向角度
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'x': self.x,
            'y': self.y,
            'speed': self.speed,
            'direction': self.direction
        }


@dataclass
class Scenario:
    """场景数据结构"""
    name: str = ""
    scenario_type: ScenarioType = ScenarioType.STRAIGHT_ROAD
    ego_vehicle: VehicleConfig = field(default_factory=VehicleConfig)
    vehicles: List[VehicleConfig] = field(default_factory=list)
    traffic_lights: List[TrafficLightConfig] = field(default_factory=list)
    pedestrians: List[PedestrianConfig] = field(default_factory=list)
    timestamp: str = ""
    description: str = ""
    expected_violations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'type': self.scenario_type.value,
            'timestamp': self.timestamp,
            'description': self.description,
            'ego_vehicle': self.ego_vehicle.to_dict(),
            'vehicles': [v.to_dict() for v in self.vehicles],
            'traffic_lights': [tl.to_dict() for tl in self.traffic_lights],
            'pedestrians': [p.to_dict() for p in self.pedestrians],
            'expected_violations': self.expected_violations
        }
    
    def save_to_file(self, file_path: str) -> None:
        """保存场景到文件"""
        import json
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load_from_file(cls, file_path: str) -> 'Scenario':
        """从文件加载场景"""
        import json
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        scenario = cls()
        scenario.name = data.get('name', '')
        scenario.scenario_type = ScenarioType(data.get('type', 'straight_road'))
        scenario.timestamp = data.get('timestamp', '')
        scenario.description = data.get('description', '')
        scenario.expected_violations = data.get('expected_violations', [])
        
        # 加载自车
        ego_data = data.get('ego_vehicle', {})
        scenario.ego_vehicle = VehicleConfig(**ego_data)
        
        # 加载车辆
        for v_data in data.get('vehicles', []):
            scenario.vehicles.append(VehicleConfig(**v_data))
        
        # 加载交通灯
        for tl_data in data.get('traffic_lights', []):
            tl = TrafficLightConfig(**tl_data)
            tl.state = TrafficLightState(tl_data.get('state', 'Red'))
            scenario.traffic_lights.append(tl)
        
        # 加载行人
        for p_data in data.get('pedestrians', []):
            scenario.pedestrians.append(PedestrianConfig(**p_data))
        
        return scenario


class ScenarioBuilder:
    """场景构建器"""
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        random.seed(seed)
    
    def create_straight_road_scenario(
        self,
        ego_speed: float = 15.0,
        num_vehicles: int = 5,
        road_length: float = 100.0
    ) -> Scenario:
        """创建直行道路场景"""
        scenario = Scenario(
            name="直行道路场景",
            scenario_type=ScenarioType.STRAIGHT_ROAD,
            description="自车在直行道路上，前方有多辆车"
        )
        
        # 自车在道路中间
        scenario.ego_vehicle = VehicleConfig(
            x=0, y=0, speed=ego_speed, yaw=0,
            vehicle_type="vehicle.ego", role="ego"
        )
        
        # 前方车辆，间隔10-30米
        for i in range(num_vehicles):
            distance = 15 + i * 20 + random.uniform(-5, 5)
            scenario.vehicles.append(VehicleConfig(
                x=distance, y=random.uniform(-1, 1), 
                speed=random.uniform(8, 12), yaw=0,
                vehicle_type=f"vehicle.npc_{i}", role="npc"
            ))
        
        # 设置预期违规
        if ego_speed > 15:
            scenario.expected_violations.append("RSS_LONGITUDINAL")
        
        return scenario
    
    def create_intersection_scenario(
        self,
        ego_speed: float = 12.0,
        crossing_vehicle_speed: float = 10.0,
        distance_to_intersection: float = 20.0
    ) -> Scenario:
        """创建交叉口场景 - 用于验证右侧优先规则"""
        scenario = Scenario(
            name="交叉口场景",
            scenario_type=ScenarioType.INTERSECTION,
            description="自车接近交叉口，右侧有车辆同时到达"
        )
        
        # 自车从西向东
        scenario.ego_vehicle = VehicleConfig(
            x=-distance_to_intersection, y=0, 
            speed=ego_speed, yaw=0,
            vehicle_type="vehicle.ego", role="ego"
        )
        
        # 右侧车辆从北向南（在自车右侧）
        scenario.vehicles.append(VehicleConfig(
            x=0, y=distance_to_intersection, 
            speed=crossing_vehicle_speed, yaw=-math.pi/2,
            vehicle_type="vehicle.npc_0", role="npc"
        ))
        
        # 左侧车辆从南向北（在自车左侧）
        scenario.vehicles.append(VehicleConfig(
            x=0, y=-distance_to_intersection, 
            speed=crossing_vehicle_speed, yaw=math.pi/2,
            vehicle_type="vehicle.npc_1", role="npc"
        ))
        
        # 交叉口中心的交通灯
        scenario.traffic_lights.append(TrafficLightConfig(
            x=0, y=0, state=TrafficLightState.GREEN
        ))
        
        # 预期违规：如果右侧车辆先到，自车应该让行
        scenario.expected_violations.append("RIGHT_OF_WAY")
        
        return scenario
    
    def create_merge_scenario(
        self,
        ego_speed: float = 12.0,
        main_road_speed: float = 10.0,
        merge_distance: float = 30.0
    ) -> Scenario:
        """创建合流场景 - 用于验证合流优先规则"""
        scenario = Scenario(
            name="合流场景",
            scenario_type=ScenarioType.MERGE,
            description="自车从匝道合流到主路，主路有车辆"
        )
        
        # 自车在匝道上，准备合流
        scenario.ego_vehicle = VehicleConfig(
            x=-10, y=merge_distance, 
            speed=ego_speed, yaw=-math.pi/4,
            vehicle_type="vehicle.ego", role="ego"
        )
        
        # 主路车辆
        for i in range(3):
            scenario.vehicles.append(VehicleConfig(
                x=-20 + i * 15, y=0, 
                speed=main_road_speed, yaw=0,
                vehicle_type=f"vehicle.npc_{i}", role="npc"
            ))
        
        # 预期违规：合流时的安全距离
        scenario.expected_violations.append("MERGE_SAFETY")
        
        return scenario
    
    def create_lane_change_scenario(
        self,
        ego_speed: float = 15.0,
        adjacent_speed: float = 12.0,
        lane_width: float = 3.5
    ) -> Scenario:
        """创建变道场景 - 用于验证横向安全规则"""
        scenario = Scenario(
            name="变道场景",
            scenario_type=ScenarioType.LANE_CHANGE,
            description="自车尝试变道，相邻车道有车辆"
        )
        
        # 自车在左侧车道
        scenario.ego_vehicle = VehicleConfig(
            x=0, y=0, 
            speed=ego_speed, yaw=0,
            vehicle_type="vehicle.ego", role="ego"
        )
        
        # 相邻车道的车辆（右侧）
        scenario.vehicles.append(VehicleConfig(
            x=10, y=lane_width, 
            speed=adjacent_speed, yaw=0,
            vehicle_type="vehicle.npc_0", role="npc"
        ))
        
        # 后方车辆
        scenario.vehicles.append(VehicleConfig(
            x=-15, y=0, 
            speed=adjacent_speed, yaw=0,
            vehicle_type="vehicle.npc_1", role="npc"
        ))
        
        # 预期违规：变道时的横向安全
        scenario.expected_violations.append("LANE_CHANGE_SAFETY")
        
        return scenario
    
    def create_red_light_scenario(
        self,
        ego_speed: float = 15.0,
        distance_to_light: float = 10.0
    ) -> Scenario:
        """创建红灯场景 - 用于验证红灯停车规则"""
        scenario = Scenario(
            name="红灯场景",
            scenario_type=ScenarioType.STRAIGHT_ROAD,
            description="自车接近红灯，需要停车"
        )
        
        # 自车
        scenario.ego_vehicle = VehicleConfig(
            x=-distance_to_light, y=0, 
            speed=ego_speed, yaw=0,
            vehicle_type="vehicle.ego", role="ego"
        )
        
        # 红灯
        scenario.traffic_lights.append(TrafficLightConfig(
            x=0, y=0, state=TrafficLightState.RED
        ))
        
        # 预期违规：红灯停车
        scenario.expected_violations.append("TRAFFIC_LIGHT")
        
        return scenario
    
    def create_pedestrian_crossing_scenario(
        self,
        ego_speed: float = 10.0,
        pedestrian_speed: float = 1.0,
        distance_to_crossing: float = 15.0
    ) -> Scenario:
        """创建人行横道场景 - 用于验证行人安全规则"""
        scenario = Scenario(
            name="人行横道场景",
            scenario_type=ScenarioType.PEDESTRIAN_CROSSING,
            description="自车接近人行横道，有行人正在穿越"
        )
        
        # 自车
        scenario.ego_vehicle = VehicleConfig(
            x=-distance_to_crossing, y=0, 
            speed=ego_speed, yaw=0,
            vehicle_type="vehicle.ego", role="ego"
        )
        
        # 行人在人行横道上
        scenario.pedestrians.append(PedestrianConfig(
            x=0, y=2, 
            speed=pedestrian_speed, direction=math.pi/2
        ))
        
        # 预期违规：行人安全
        scenario.expected_violations.append("PEDESTRIAN_SAFETY")
        
        return scenario
    
    def create_custom_scenario(
        self,
        name: str,
        ego_config: VehicleConfig,
        vehicle_configs: List[VehicleConfig],
        traffic_light_configs: Optional[List[TrafficLightConfig]] = None,
        pedestrian_configs: Optional[List[PedestrianConfig]] = None,
        description: str = "",
        expected_violations: Optional[List[str]] = None
    ) -> Scenario:
        """创建自定义场景"""
        scenario = Scenario(
            name=name,
            scenario_type=ScenarioType.STRAIGHT_ROAD,
            ego_vehicle=ego_config,
            vehicles=vehicle_configs,
            traffic_lights=traffic_light_configs or [],
            pedestrians=pedestrian_configs or [],
            description=description,
            expected_violations=expected_violations or []
        )
        return scenario


# 预设场景
class ScenarioPresets:
    """预设场景集合"""
    
    @staticmethod
    def get_preset_scenarios() -> List[Scenario]:
        """获取所有预设场景"""
        builder = ScenarioBuilder()
        
        return [
            # 1. 直行道路 - 安全距离验证
            builder.create_straight_road_scenario(
                ego_speed=20.0,  # 超速
                num_vehicles=3,
                road_length=80.0
            ),
            
            # 2. 交叉口 - 右侧优先验证
            builder.create_intersection_scenario(
                ego_speed=12.0,
                crossing_vehicle_speed=10.0,
                distance_to_intersection=15.0
            ),
            
            # 3. 合流 - 合流安全验证
            builder.create_merge_scenario(
                ego_speed=12.0,
                main_road_speed=10.0,
                merge_distance=25.0
            ),
            
            # 4. 变道 - 横向安全验证
            builder.create_lane_change_scenario(
                ego_speed=15.0,
                adjacent_speed=12.0,
                lane_width=3.5
            ),
            
            # 5. 红灯 - 红灯停车验证
            builder.create_red_light_scenario(
                ego_speed=15.0,
                distance_to_light=8.0  # 太近了
            ),
            
            # 6. 人行横道 - 行人安全验证
            builder.create_pedestrian_crossing_scenario(
                ego_speed=12.0,
                pedestrian_speed=1.0,
                distance_to_crossing=10.0
            ),
        ]


if __name__ == "__main__":
    # 示例：生成预设场景并保存
    builder = ScenarioBuilder()
    
    # 创建并保存所有预设场景
    presets = ScenarioPresets.get_preset_scenarios()
    
    import os
    output_dir = "scenarios/data"
    os.makedirs(output_dir, exist_ok=True)
    
    for i, scenario in enumerate(presets):
        scenario.timestamp = f"2026-08-24T19:00:{i*10:02d}.000000"
        scenario.save_to_file(f"{output_dir}/preset_{i+1:02d}.json")
        print(f"保存预设场景 {i+1}: {scenario.name}")
    
    print(f"\n已保存 {len(presets)} 个预设场景到 {output_dir}/")