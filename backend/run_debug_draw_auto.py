#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CARLA Debug Draw 自动演示
在CARLA窗口中自动展示风险状态变化

启动方式：
    python run_debug_draw_auto.py
"""

import sys
import os
import time
import threading
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import carla
import numpy as np


class CarlaAutoDemo:
    """CARLA Debug Draw 自动演示"""
    
    def __init__(self, host="localhost", port=2000):
        self.host = host
        self.port = port
        self.client = None
        self.world = None
        self.ego_vehicle = None
        self.running = False
        self.draw_thread = None
        
        self.current_event = None
        self.event_lock = threading.Lock()
        
        self.colors = {
            "CRITICAL": carla.Color(255, 0, 0, 255),
            "HIGH": carla.Color(255, 165, 0, 255),
            "MEDIUM": carla.Color(255, 255, 0, 255),
            "LOW": carla.Color(0, 255, 0, 255),
            "SAFE": carla.Color(0, 200, 0, 255),
        }
    
    def connect(self) -> bool:
        try:
            self.client = carla.Client(self.host, self.port)
            self.client.set_timeout(10.0)
            self.world = self.client.get_world()
            print(f"✅ 已连接CARLA")
            return True
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False
    
    def spawn_vehicles(self):
        """创建测试车辆"""
        blueprint_library = self.world.get_blueprint_library()
        vehicles = self.world.get_actors().filter('vehicle.*')
        
        if len(vehicles) > 0:
            for v in vehicles:
                if v.attributes.get('role_name') == 'ego':
                    self.ego_vehicle = v
                    return
            self.ego_vehicle = list(vehicles)[0]
            print(f"找到车辆: {self.ego_vehicle.type_id}")
            return
        
        print("创建测试车辆...")
        spawn_points = self.world.get_map().get_spawn_points()
        
        bp = blueprint_library.filter('vehicle.tesla.model3')[0]
        bp.set_attribute('role_name', 'ego')
        self.ego_vehicle = self.world.spawn_actor(bp, random.choice(spawn_points))
        
        for i in range(3):
            bp = blueprint_library.filter('vehicle.*')[random.randint(0, 10)]
            self.world.spawn_actor(bp, random.choice(spawn_points))
        
        time.sleep(1)
        print(f"创建完成: {len(self.world.get_actors().filter('vehicle.*'))} 辆车")
    
    def set_event(self, event):
        with self.event_lock:
            self.current_event = event
    
    def start_draw(self):
        self.running = True
        self.draw_thread = threading.Thread(target=self._draw_loop, daemon=True)
        self.draw_thread.start()
        print("✅ Debug Draw线程已启动")
    
    def _draw_loop(self):
        while self.running:
            try:
                self._draw_frame()
                time.sleep(0.1)
            except Exception as e:
                print(f"绘制错误: {e}")
                time.sleep(1)
    
    def _draw_frame(self):
        if self.world is None or self.ego_vehicle is None:
            return
        
        try:
            event = self.current_event
            ego_transform = self.ego_vehicle.get_transform()
            ego_loc = ego_transform.location
            
            if event:
                risk_level = event.get("risk_level", "SAFE")
                scenario = event.get("scenario_name", "Unknown")
                color = self.colors.get(risk_level, self.colors["SAFE"])
                
                # 风险等级（大字）
                text_pos = carla.Location(x=ego_loc.x, y=ego_loc.y, z=ego_loc.z + 4.0)
                self.world.debug.draw_string(
                    text_pos, f"RISK: {risk_level}",
                    draw_shadow=True, color=color, life_time=0.15
                )
                
                # 场景名
                scene_pos = carla.Location(x=ego_loc.x, y=ego_loc.y, z=ego_loc.z + 3.0)
                self.world.debug.draw_string(
                    scene_pos, scenario,
                    draw_shadow=True, color=carla.Color(255, 255, 255, 255), life_time=0.15
                )
                
                # 风险圆圈
                risk_radius = {"CRITICAL": 12, "HIGH": 8, "MEDIUM": 5, "LOW": 3}.get(risk_level, 5)
                for angle in range(0, 360, 20):
                    rad = np.radians(angle)
                    x = ego_loc.x + risk_radius * np.cos(rad)
                    y = ego_loc.y + risk_radius * np.sin(rad)
                    self.world.debug.draw_point(
                        carla.Location(x=x, y=y, z=ego_loc.z),
                        size=0.1, color=color, life_time=0.15
                    )
                
                # 红色边界框
                self.world.debug.draw_box(
                    carla.BoundingBox(ego_transform.location, carla.Vector3D(2.0, 1.0, 1.5)),
                    ego_transform.rotation,
                    thickness=0.1, color=color, life_time=0.15
                )
            else:
                self.world.debug.draw_string(
                    carla.Location(x=ego_loc.x, y=ego_loc.y, z=ego_loc.z + 3.0),
                    "SAFE", draw_shadow=True, color=self.colors["SAFE"], life_time=0.15
                )
        
        except Exception as e:
            print(f"绘制帧失败: {e}")
    
    def auto_demo(self):
        """自动演示模式"""
        scenarios = [
            ({"scenario_name": "前车急刹", "risk_level": "CRITICAL", "risk_index": 0.85}, 4),
            ({"scenario_name": "行人横穿", "risk_level": "HIGH", "risk_index": 0.65}, 4),
            (None, 3),  # SAFE
            ({"scenario_name": "违规变道", "risk_level": "MEDIUM", "risk_index": 0.45}, 4),
            (None, 3),  # SAFE
            ({"scenario_name": "跟车过近", "risk_level": "HIGH", "risk_index": 0.7}, 4),
            (None, 3),  # SAFE
        ]
        
        self.start_draw()
        print()
        print("开始自动演示... (每4秒切换状态)")
        print("在CARLA窗口中查看风险状态叠加效果")
        print("按 Ctrl+C 停止")
        print()
        
        idx = 0
        while self.running:
            event, duration = scenarios[idx % len(scenarios)]
            self.set_event(event)
            
            if event:
                print(f"  [{idx+1}] {event['scenario_name']} ({event['risk_level']})")
            else:
                print(f"  [{idx+1}] SAFE")
            
            idx += 1
            time.sleep(duration)
        
        self.set_event(None)


def main():
    server = CarlaAutoDemo()
    
    if not server.connect():
        print("请确保CARLA正在运行")
        sys.exit(1)
    
    server.spawn_vehicles()
    server.auto_demo()


if __name__ == "__main__":
    main()
