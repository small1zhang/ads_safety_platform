#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CARLA场景注入器 - 定期注入合理的异常场景
"""

import random
import time
import math
from typing import Optional, List, Dict, Any


class CarlaScenarioInjector:
    """周期性地在CARLA中注入危险场景"""
    
    def __init__(self, carla_module=None):
        self.client = None
        self.world = None
        self._last_injection_time = 0
        self._injection_interval = 25.0  # 每25秒注入一个场景
        self._carla_module = carla_module
        self._connected = False
        self._injected_actors = []  # 记录注入的actor
        self._scenario_index = 0
        
        # 场景模板
        self.scenarios = [
            "front_brake",       # 前车急刹
            "tailgating",        # 跟车过近
            "speeding",          # 超速
            "pedestrian_cross",  # 行人横穿
            "red_light_run",     # 红灯闯行
        ]
    
    def connect(self, host="localhost", port=2000, timeout=10.0) -> bool:
        """连接CARLA服务器"""
        try:
            if self._carla_module is None:
                import carla
                self._carla_module = carla
            
            self.client = self._carla_module.Client(host, port)
            self.client.set_timeout(timeout)
            self.world = self.client.get_world()
            self._connected = True
            print(f"✅ 已连接到CARLA场景注入器")
            return True
        except Exception as e:
            print(f"❌ CARLA连接失败: {e}")
            self._connected = False
            return False
    
    def is_connected(self) -> bool:
        return self._connected and self.world is not None
    
    def should_inject(self) -> bool:
        """检查是否应该注入下一个场景"""
        return (time.time() - self._last_injection_time) >= self._injection_interval
    
    def inject_next_scenario(self, ego_actor=None) -> Optional[Dict[str, Any]]:
        """
        注入下一个异常场景并返回描述。
        每25秒调用一次。
        """
        if not self.is_connected():
            return None
        
        # 清理过期的注入actor
        self._cleanup_old_actors()
        
        scenario = self.scenarios[self._scenario_index % len(self.scenarios)]
        self._scenario_index += 1
        self._last_injection_time = time.time()
        
        try:
            if scenario == "front_brake":
                return self._inject_front_brake(ego_actor)
            elif scenario == "tailgating":
                return self._inject_tailgating(ego_actor)
            elif scenario == "speeding":
                return self._inject_speeding(ego_actor)
            elif scenario == "pedestrian_cross":
                return self._inject_pedestrian(ego_actor)
            elif scenario == "red_light_run":
                return self._inject_red_light(ego_actor)
        except Exception as e:
            print(f"场景注入失败: {e}")
        
        return None
    
    def _cleanup_old_actors(self):
        """清理之前注入的actor"""
        try:
            if not self.world:
                return
            for actor in self._injected_actors:
                try:
                    if actor.is_alive:
                        actor.destroy()
                except:
                    pass
            self._injected_actors = []
        except:
            pass
    
    def _inject_front_brake(self, ego_actor=None) -> Dict[str, Any]:
        """前车急刹场景"""
        carla = self._carla_module
        if ego_actor is None:
            # 默认在地图中找个位置
            spawn_points = self.world.get_map().get_spawn_points()
            if not spawn_points:
                return None
            ego_actor = self.world.try_spawn_actor(
                self._get_vehicle_bp(),
                random.choice(spawn_points)
            )
            if ego_actor is None:
                return None
            self._injected_actors.append(ego_actor)
        
        ego_transform = ego_actor.get_transform()
        # 在自车前方20米处生成一辆紧急制动的车辆
        forward = ego_transform.get_forward_vector()
        front_location = ego_transform.location + forward * 20
        
        # 紧急制动车辆
        brake_actor = self.world.try_spawn_actor(
            self._get_vehicle_bp(),
            carla.Transform(front_location, ego_transform.rotation)
        )
        if brake_actor:
            brake_actor.enable_constant_velocity(carla.Vector3D(0, 0, 0))  # 停止
            self._injected_actors.append(brake_actor)
        
        return {
            "scenario": "front_brake",
            "description": "前车急刹",
            "risk_level": "CRITICAL",
            "triggered_at": time.time()
        }
    
    def _inject_tailgating(self, ego_actor=None) -> Dict[str, Any]:
        """跟车过近场景"""
        carla = self._carla_module
        if ego_actor is None:
            spawn_points = self.world.get_map().get_spawn_points()
            if not spawn_points:
                return None
            ego_actor = self.world.try_spawn_actor(
                self._get_vehicle_bp(),
                random.choice(spawn_points)
            )
            if ego_actor is None:
                return None
            self._injected_actors.append(ego_actor)
        
        ego_transform = ego_actor.get_transform()
        forward = ego_transform.get_forward_vector()
        # 极近距离的车辆
        close_location = ego_transform.location + forward * 3
        close_actor = self.world.try_spawn_actor(
            self._get_vehicle_bp(),
            carla.Transform(close_location, ego_transform.rotation)
        )
        if close_actor:
            self._injected_actors.append(close_actor)
        
        return {
            "scenario": "tailgating",
            "description": "跟车过近",
            "risk_level": "HIGH",
            "triggered_at": time.time()
        }
    
    def _inject_speeding(self, ego_actor=None) -> Dict[str, Any]:
        """超速行驶"""
        carla = self._carla_module
        if ego_actor is None:
            spawn_points = self.world.get_map().get_spawn_points()
            if not spawn_points:
                return None
            ego_actor = self.world.try_spawn_actor(
                self._get_vehicle_bp(),
                random.choice(spawn_points)
            )
            if ego_actor is None:
                return None
            self._injected_actors.append(ego_actor)
        
        # 设置超速
        ego_actor.enable_constant_velocity(carla.Vector3D(35, 0, 0))  # 35 m/s = 126 km/h
        
        return {
            "scenario": "speeding",
            "description": "超速行驶",
            "risk_level": "HIGH",
            "triggered_at": time.time()
        }
    
    def _inject_pedestrian(self, ego_actor=None) -> Dict[str, Any]:
        """行人横穿"""
        carla = self._carla_module
        if ego_actor is None:
            spawn_points = self.world.get_map().get_spawn_points()
            if not spawn_points:
                return None
            ego_actor = self.world.try_spawn_actor(
                self._get_vehicle_bp(),
                random.choice(spawn_points)
            )
            if ego_actor is None:
                return None
            self._injected_actors.append(ego_actor)
        
        ego_transform = ego_actor.get_transform()
        # 在自车前方生成行人
        forward = ego_transform.get_forward_vector()
        ped_location = ego_transform.location + forward * 15
        
        walker_bp = self.world.get_blueprint_library().find('walker.pedestrian.0001')
        if walker_bp:
            ped_actor = self.world.try_spawn_actor(walker_bp, carla.Transform(ped_location))
            if ped_actor:
                # 让行人走向自车
                walker_controller_bp = self.world.get_blueprint_library().find('controller.ai.walker')
                if walker_controller_bp:
                    controller = self.world.spawn_actor(
                        walker_controller_bp, carla.Transform(), ped_actor
                    )
                    if controller:
                        controller.start()
                        controller.go_to_location(ego_transform.location)
                        controller.set_max_speed(1.0)
                        self._injected_actors.append(controller)
                self._injected_actors.append(ped_actor)
        
        return {
            "scenario": "pedestrian_cross",
            "description": "行人横穿",
            "risk_level": "CRITICAL",
            "triggered_at": time.time()
        }
    
    def _inject_red_light(self, ego_actor=None) -> Dict[str, Any]:
        """红灯闯行场景"""
        return {
            "scenario": "red_light_run",
            "description": "红灯闯行",
            "risk_level": "HIGH",
            "triggered_at": time.time()
        }
    
    def _get_vehicle_bp(self):
        """获取一个车辆蓝图"""
        blueprints = self.world.get_blueprint_library().filter('vehicle.tesla.*')
        if not blueprints:
            blueprints = self.world.get_blueprint_library().filter('vehicle.*')
        return random.choice(blueprints)


# 全局单例
_global_injector = None

def get_injector():
    global _global_injector
    if _global_injector is None:
        _global_injector = CarlaScenarioInjector()
    return _global_injector
