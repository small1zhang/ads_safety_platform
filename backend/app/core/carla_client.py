#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backend/app/core/carla_client.py - CARLA客户端

提供：
- CARLA服务器连接
- 实时数据采集
- 场景控制
"""

import asyncio
import random
import time
from typing import Dict, Any, Optional


class CARLAClient:
    """CARLA客户端"""
    
    def __init__(self, host: str = "localhost", port: int = 2000):
        self.host = host
        self.port = port
        self._connected = False
        self._connection_attempts = 0
    
    async def connect(self) -> bool:
        """连接到CARLA服务器"""
        self._connection_attempts += 1
        
        # 模拟连接过程
        await asyncio.sleep(1.0)
        
        # 50%概率连接成功（模拟）
        if random.random() > 0.5 or self._connection_attempts > 3:
            self._connected = True
            return True
        
        return False
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected
    
    async def disconnect(self):
        """断开连接"""
        self._connected = False
    
    async def get_data(self) -> Dict[str, Any]:
        """获取CARLA数据"""
        if not self._connected:
            return {}
        
        # 模拟获取数据
        await asyncio.sleep(0.1)
        
        return {
            "ego": {
                "x": random.uniform(-50, 50),
                "y": random.uniform(-50, 50),
                "speed": random.uniform(0, 30),
                "yaw": random.uniform(0, 360)
            },
            "vehicles": [
                {
                    "id": i,
                    "x": random.uniform(-50, 50),
                    "y": random.uniform(-50, 50),
                    "speed": random.uniform(0, 20)
                }
                for i in range(random.randint(0, 8))
            ],
            "timestamp": time.time()
        }
    
    async def set_scenario(self, scenario: str) -> bool:
        """设置场景"""
        if not self._connected:
            return False
        
        await asyncio.sleep(0.5)
        return True