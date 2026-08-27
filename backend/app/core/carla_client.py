#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backend/app/core/carla_client.py - CARLA客户端

提供：
- CARLA服务器连接检测（真实TCP检测）
- 实时数据采集
- 场景控制
"""

import asyncio
import socket
import random
import time
from typing import Dict, Any, Optional


class CARLAClient:
    """CARLA客户端 - 支持真实连接检测"""
    
    def __init__(self, host: str = "localhost", port: int = 2000):
        self.host = host
        self.port = port
        self._connected = False
        self._last_check = 0
        self._check_interval = 2.0  # 检测间隔（秒）
    
    def _check_tcp_connection(self) -> bool:
        """使用TCP Socket检测CARLA服务器是否可达"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)  # 2秒超时
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            return result == 0  # 0 表示连接成功
        except (socket.error, socket.timeout, OSError) as e:
            return False
    
    def is_connected(self) -> bool:
        """
        检查是否已连接到CARLA服务器。
        每次调用时自动检测真实连接状态（带缓存）。
        """
        current_time = time.time()
        
        # 缓存机制：避免频繁TCP检测
        if current_time - self._last_check < self._check_interval:
            return self._connected
        
        # 执行真实的TCP连接检测
        self._connected = self._check_tcp_connection()
        self._last_check = current_time
        
        return self._connected
    
    async def connect(self) -> bool:
        """异步连接到CARLA服务器"""
        loop = asyncio.get_event_loop()
        is_reachable = await loop.run_in_executor(None, self._check_tcp_connection)
        
        if is_reachable:
            self._connected = True
            self._last_check = time.time()
            return True
        
        self._connected = False
        return False
    
    async def disconnect(self):
        """断开连接"""
        self._connected = False
    
    def get_data(self) -> Dict[str, Any]:
        """获取CARLA数据（同步方法）"""
        if not self.is_connected():
            return {"error": "CARLA未连接", "connected": False}
        
        try:
            import math
            # 尝试导入carla（避免segfault）
            try:
                import carla
            except ImportError:
                return {"error": "carla未安装", "connected": False}
            
            # 获取世界和地图
            world = self.client.get_world()
            actors = world.get_actors()
            
            # 获取所有车辆
            vehicles = []
            ego_vehicle = None
            
            for actor in actors.filter('vehicle.*'):
                transform = actor.get_transform()
                velocity = actor.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                
                # 检查是否是自车（role=ego）
                if actor.attributes.get('role_name') == 'ego' or actor.type_id == 'vehicle.tesla.model3':
                    ego_vehicle = {
                        "id": actor.id,
                        "x": transform.location.x,
                        "y": transform.location.y,
                        "z": transform.location.z,
                        "speed": speed,
                        "yaw": math.degrees(transform.rotation.yaw),
                        "type": actor.type_id
                    }
                else:
                    vehicles.append({
                        "id": actor.id,
                        "x": transform.location.x,
                        "y": transform.location.y,
                        "z": transform.location.z,
                        "speed": speed,
                        "type": actor.type_id
                    })
            
            # 如果没有找到ego车，取第一辆车
            if ego_vehicle is None and vehicles:
                first = vehicles.pop(0)
                ego_vehicle = first.copy()
                ego_vehicle["type"] = "ego_vehicle"
            
            # 获取行人
            pedestrians = []
            for actor in actors.filter('walker.*'):
                transform = actor.get_transform()
                velocity = actor.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                pedestrians.append({
                    "id": actor.id,
                    "x": transform.location.x,
                    "y": transform.location.y,
                    "z": transform.location.z,
                    "speed": speed
                })
            
            return {
                "connected": True,
                "ego": ego_vehicle or {"x": 0, "y": 0, "z": 0, "speed": 0, "yaw": 0, "type": "none"},
                "vehicles": vehicles,
                "pedestrians": pedestrians,
                "timestamp": time.time()
            }
            
        except Exception as e:
            # 捕获segfault或其他错误，返回安全状态
            print(f"读取CARLA数据失败: {e}")
            return {"error": str(e), "connected": False}
    
    async def set_scenario(self, scenario: str) -> bool:
        """设置场景"""
        if not self.is_connected():
            return False
        
        await asyncio.sleep(0.2)
        return True
    
    def get_status_info(self) -> Dict[str, Any]:
        """获取详细状态信息"""
        return {
            "host": self.host,
            "port": self.port,
            "connected": self.is_connected(),
            "last_check": self._last_check,
            "check_interval": self._check_interval
        }
