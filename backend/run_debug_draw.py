#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CARLA Debug Draw 可视化服务
在CARLA窗口中直接叠加实时风险状态

启动方式：
    python run_debug_draw.py

需要在有图形界面的机器上运行CARLA客户端
"""

import sys
import os
import time
import threading
import random

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import carla
import numpy as np


class CarlaDebugDrawServer:
    """
    CARLA Debug Draw 可视化服务
    在CARLA UE4窗口中实时显示风险状态
    """
    
    def __init__(self, host="localhost", port=2000):
        self.host = host
        self.port = port
        self.client = None
        self.world = None
        self.ego_vehicle = None
        self.running = False
        self.draw_thread = None
        
        # 当前事件
        self.current_event = None
        self.event_lock = threading.Lock()
        
        # 颜色定义 (carla.Color)
        self.colors = {
            "CRITICAL": carla.Color(255, 0, 0, 255),     # 红
            "HIGH": carla.Color(255, 165, 0, 255),       # 橙
            "MEDIUM": carla.Color(255, 255, 0, 255),     # 黄
            "LOW": carla.Color(0, 255, 0, 255),          # 绿
            "SAFE": carla.Color(0, 200, 0, 255),          # 深绿
        }
    
    def connect(self) -> bool:
        """连接CARLA"""
        try:
            self.client = carla.Client(self.host, self.port)
            self.client.set_timeout(10.0)
            self.world = self.client.get_world()
            print(f"✅ 已连接CARLA ({self.host}:{self.port})")
            return True
        except Exception as e:
            print(f"❌ CARLA连接失败: {e}")
            return False
    
    def spawn_test_vehicles(self):
        """创建测试车辆（如果场景为空）"""
        blueprint_library = self.world.get_blueprint_library()
        vehicles = self.world.get_actors().filter('vehicle.*')
        
        if len(vehicles) > 0:
            # 找ego
            for v in vehicles:
                if v.attributes.get('role_name') == 'ego':
                    self.ego_vehicle = v
                    return
            self.ego_vehicle = list(vehicles)[0]
            print(f"找到车辆: {self.ego_vehicle.type_id}")
            return
        
        print("场景为空，创建测试车辆...")
        # 生成车辆
        spawn_points = self.world.get_map().get_spawn_points()
        
        # 创建Ego车辆
        bp = blueprint_library.filter('vehicle.tesla.model3')[0]
        bp.set_attribute('role_name', 'ego')
        spawn_point = random.choice(spawn_points)
        self.ego_vehicle = self.world.spawn_actor(bp, spawn_point)
        print(f"创建Ego车辆: {self.ego_vehicle.type_id}")
        
        # 创建周围车辆
        for i in range(3):
            bp = blueprint_library.filter('vehicle.*')[random.randint(0, 10)]
            spawn_point = random.choice(spawn_points)
            self.world.spawn_actor(bp, spawn_point)
        
        time.sleep(1)
        print(f"创建完成，共 {len(self.world.get_actors().filter('vehicle.*'))} 辆车")
    
    def set_event(self, event):
        """设置当前事件（从检测器调用）"""
        with self.event_lock:
            self.current_event = event
    
    def get_current_event(self):
        """获取当前事件"""
        with self.event_lock:
            return self.current_event
    
    def start(self):
        """启动Debug Draw"""
        if self.running:
            print("Debug Draw已在运行")
            return
        
        self.running = True
        self.draw_thread = threading.Thread(target=self._draw_loop, daemon=True)
        self.draw_thread.start()
        print("✅ Debug Draw线程已启动")
        print("   打开CARLA窗口查看实时风险状态叠加")
    
    def stop(self):
        """停止Debug Draw"""
        self.running = False
        if self.draw_thread:
            self.draw_thread.join(timeout=2)
        # 清除绘制
        try:
            self.world.debug.clear_all()
        except:
            pass
        print("Debug Draw已停止")
    
    def _draw_loop(self):
        """绘制循环"""
        frame_count = 0
        while self.running:
            try:
                self._draw_frame()
                frame_count += 1
                time.sleep(0.1)  # 10 FPS
            except Exception as e:
                print(f"绘制错误: {e}")
                time.sleep(1)
        
        # 退出时清除
        try:
            self.world.debug.clear_all()
        except:
            pass
    
    def _draw_frame(self):
        """绘制当前帧"""
        if self.world is None:
            return
        
        try:
            # 清除上一帧
            # carla debug draw是累积的，这里用短life_time
            
            event = self.get_current_event()
            
            if self.ego_vehicle is None:
                vehicles = self.world.get_actors().filter('vehicle.*')
                if vehicles:
                    for v in vehicles:
                        if v.attributes.get('role_name') == 'ego':
                            self.ego_vehicle = v
                            break
                    if self.ego_vehicle is None:
                        self.ego_vehicle = list(vehicles)[0]
            
            if self.ego_vehicle is None:
                return
            
            ego_transform = self.ego_vehicle.get_transform()
            ego_loc = ego_transform.location
            
            if event:
                risk_level = event.get("risk_level", "SAFE")
                scenario = event.get("scenario_name", "Unknown")
                color = self.colors.get(risk_level, self.colors["SAFE"])
                
                # 1. 在ego上方显示风险等级（大字）
                text_pos = carla.Location(x=ego_loc.x, y=ego_loc.y, z=ego_loc.z + 3.5)
                risk_text = f"WARNING {risk_level}"
                self.world.debug.draw_string(
                    text_pos, risk_text,
                    draw_shadow=True,
                    color=color,
                    life_time=0.2
                )
                
                # 2. 在下方显示场景名
                scenario_pos = carla.Location(x=ego_loc.x, y=ego_loc.y, z=ego_loc.z + 2.5)
                self.world.debug.draw_string(
                    scenario_pos, f"[{scenario}]",
                    draw_shadow=True,
                    color=carla.Color(255, 255, 255, 255),
                    life_time=0.2
                )
                
                # 3. 绘制风险区域圆圈
                risk_radius = {
                    "CRITICAL": 15.0,
                    "HIGH": 12.0,
                    "MEDIUM": 8.0,
                    "LOW": 5.0,
                }.get(risk_level, 8.0)
                
                for angle in range(0, 360, 15):
                    rad = np.radians(angle)
                    x = ego_loc.x + risk_radius * np.cos(rad)
                    y = ego_loc.y + risk_radius * np.sin(rad)
                    self.world.debug.draw_point(
                        carla.Location(x=x, y=y, z=ego_loc.z - 0.5),
                        size=0.1,
                        color=color,
                        life_time=0.2
                    )
                
                # 4. 绘制连接线到附近车辆
                vehicles = self.world.get_actors().filter('vehicle.*')
                for v in vehicles:
                    if v.id == self.ego_vehicle.id:
                        continue
                    v_loc = v.get_transform().location
                    dist = np.sqrt((v_loc.x - ego_loc.x)**2 + (v_loc.y - ego_loc.y)**2)
                    if dist < risk_radius * 1.5:
                        self.world.debug.draw_line(
                            ego_loc + carla.Location(z=1),
                            v_loc + carla.Location(z=1),
                            thickness=0.05,
                            color=color,
                            life_time=0.2
                        )
                
                # 5. 绘制边界框
                self.world.debug.draw_box(
                    carla.BoundingBox(ego_transform.location, carla.Vector3D(2.0, 1.0, 1.5)),
                    ego_transform.rotation,
                    thickness=0.1,
                    color=color,
                    life_time=0.2
                )
                
            else:
                # 安全状态
                safe_pos = carla.Location(x=ego_loc.x, y=ego_loc.y, z=ego_loc.z + 3.0)
                self.world.debug.draw_string(
                    safe_pos, "SAFE",
                    draw_shadow=True,
                    color=self.colors["SAFE"],
                    life_time=0.2
                )
                
                # 绿色边界框
                self.world.debug.draw_box(
                    carla.BoundingBox(ego_transform.location, carla.Vector3D(2.0, 1.0, 1.5)),
                    ego_transform.rotation,
                    thickness=0.05,
                    color=self.colors["SAFE"],
                    life_time=0.2
                )
            
        except Exception as e:
            print(f"绘制帧失败: {e}")
    
    def simulate_events(self):
        """模拟事件流（用于测试）"""
        scenarios = [
            ("前车急刹", "CRITICAL"),
            ("行人横穿", "HIGH"),
            ("违规变道", "MEDIUM"),
            ("跟车过近", "LOW"),
            (None, None),
        ]
        
        idx = 0
        while self.running:
            scenario_name, risk_level = scenarios[idx % len(scenarios)]
            
            if scenario_name:
                event = {
                    "scenario_id": idx + 1,
                    "scenario_name": scenario_name,
                    "risk_level": risk_level,
                    "risk_index": random.random() * 0.5 + 0.5,
                    "timestamp": time.time(),
                }
                self.set_event(event)
                print(f"[模拟] 事件: {scenario_name} ({risk_level})")
            else:
                self.set_event(None)
                print(f"[模拟] SAFE")
            
            idx += 1
            time.sleep(3)
    
    def run_interactive(self):
        """交互式运行"""
        print("=" * 50)
        print("  CARLA Debug Draw 可视化")
        print("=" * 50)
        print()
        print("命令:")
        print("  1 - 模拟前车急刹 (CRITICAL)")
        print("  2 - 模拟行人横穿 (HIGH)")
        print("  3 - 模拟违规变道 (MEDIUM)")
        print("  4 - 模拟跟车过近 (HIGH)")
        print("  5 - 安全状态 (SAFE)")
        print("  q - 退出")
        print()
        
        self.start()
        
        # 启动模拟线程
        sim_thread = threading.Thread(target=self.simulate_events, daemon=True)
        sim_thread.start()
        
        # 交互循环
        while True:
            cmd = input("\n请输入命令: ").strip()
            if cmd == 'q':
                break
            elif cmd == '1':
                self.set_event({"scenario_id": 1, "scenario_name": "前车急刹", "risk_level": "CRITICAL", "risk_index": 0.9})
            elif cmd == '2':
                self.set_event({"scenario_id": 2, "scenario_name": "行人横穿", "risk_level": "HIGH", "risk_index": 0.7})
            elif cmd == '3':
                self.set_event({"scenario_id": 3, "scenario_name": "违规变道", "risk_level": "MEDIUM", "risk_index": 0.5})
            elif cmd == '4':
                self.set_event({"scenario_id": 4, "scenario_name": "跟车过近", "risk_level": "HIGH", "risk_index": 0.75})
            elif cmd == '5':
                self.set_event(None)
        
        self.stop()
        print("退出Debug Draw")


def main():
    server = CarlaDebugDrawServer()
    
    if not server.connect():
        print("无法连接到CARLA，请确保CARLA正在运行")
        sys.exit(1)
    
    server.spawn_test_vehicles()
    server.run_interactive()


if __name__ == "__main__":
    main()
