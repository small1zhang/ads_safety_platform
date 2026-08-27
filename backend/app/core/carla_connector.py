#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CARLA连接器 - 使用Python 3.7调用CARLA
"""

import sys
import json
import time
import math

# 添加CARLA Python API路径
sys.path.insert(0, '/home/aisecurity/Carla0915/PythonAPI')

try:
    import carla
    CLIENT = None
    
    def connect(host='localhost', port=2000):
        global CLIENT
        CLIENT = carla.Client(host, port)
        CLIENT.set_timeout(10.0)
        return True
    
    def get_vehicles():
        if CLIENT is None:
            return []
        world = CLIENT.get_world()
        return world.get_actors().filter('vehicle.*')
    
    def get_ego_vehicle():
        vehicles = get_vehicles()
        for v in vehicles:
            if v.attributes.get('role_name') == 'ego':
                return v
        return vehicles[0] if vehicles else None
    
    def get_data():
        """获取CARLA数据"""
        result = {
            "connected": False,
            "ego": None,
            "vehicles": [],
            "pedestrians": []
        }
        
        try:
            if CLIENT is None:
                connect()
            
            world = CLIENT.get_world()
            actors = world.get_actors()
            
            # 获取车辆
            ego = get_ego_vehicle()
            vehicles = []
            
            for actor in actors.filter('vehicle.*'):
                t = actor.get_transform()
                v = actor.get_velocity()
                speed = math.sqrt(v.x**2 + v.y**2 + v.z**2)
                
                is_ego = ego and actor.id == ego.id
                vehicles.append({
                    "id": actor.id,
                    "x": t.location.x,
                    "y": t.location.y,
                    "z": t.location.z,
                    "speed": speed,
                    "is_ego": is_ego
                })
                
                if is_ego:
                    result["ego"] = {
                        "x": t.location.x,
                        "y": t.location.y,
                        "z": t.location.z,
                        "speed": speed,
                        "yaw": t.rotation.yaw
                    }
            
            # 获取行人
            pedestrians = []
            for actor in actors.filter('walker.*'):
                t = actor.get_transform()
                v = actor.get_velocity()
                speed = math.sqrt(v.x**2 + v.y**2 + v.z**2)
                pedestrians.append({
                    "id": actor.id,
                    "x": t.location.x,
                    "y": t.location.y,
                    "z": t.location.z,
                    "speed": speed
                })
            
            result["connected"] = True
            result["vehicles"] = vehicles
            result["pedestrians"] = pedestrians
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    if __name__ == "__main__":
        # 命令行测试
        print("连接CARLA...")
        if connect():
            print("✅ 连接成功")
            data = get_data()
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print("❌ 连接失败")

except ImportError as e:
    print(f"无法导入carla: {e}", file=sys.stderr)
    sys.exit(1)
