#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CARLA 可视化服务 - 独立的可视化模块，不影响现有功能

功能：
- 抓取CARLA鸟瞰图
- 叠加实时风险状态文字
- MJPEG流式推送到Web

注意：此模块是独立的可选服务，不影响主API和检测器
"""

import os
import sys
import time
import threading
import json
import queue
from typing import Optional, Dict, Any
from datetime import datetime

# OpenCV
import cv2
import numpy as np

# CARLA可选导入 - 如果CARLA模块存在则导入，否则降级到模拟模式
try:
    import carla
    HAS_CARLA = True
except ImportError:
    carla = None
    HAS_CARLA = False

# FastAPI
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


class CarlaVisualizer:
    """CARLA 可视化器 - 叠加风险信息到画面"""
    
    def __init__(self, host="localhost", port=2000):
        self.host = host
        self.port = port
        self.client = None
        self.world = None
        self.spectator = None
        
        # 当前事件信息（从检测器共享）
        self.current_event: Optional[Dict[str, Any]] = None
        self.event_lock = threading.Lock()
        
        # 风险历史
        self.risk_history: list = []
        
        # 控制标志
        self.running = False
        self.frame_queue = queue.Queue(maxsize=2)
        
    def connect(self) -> bool:
        """连接CARLA"""
        if not HAS_CARLA:
            print("⚠️ CARLA模块不可用，运行在模拟模式")
            self.client = None
            self.world = None
            return False
            
        try:
            self.client = carla.Client(self.host, self.port)
            self.client.set_timeout(10.0)
            self.world = self.client.get_world()
            self.spectator = self.world.get_spectator()
            return True
        except Exception as e:
            print(f"CARLA连接失败: {e}")
            return False
    
    def set_event(self, event: Dict[str, Any]):
        """设置当前事件（从主检测器调用）"""
        with self.event_lock:
            self.current_event = event
            self.risk_history.append(event)
            if len(self.risk_history) > 10:
                self.risk_history = self.risk_history[-10:]
    
    def get_risk_color(self, risk_level: str) -> tuple:
        """获取风险等级颜色 (BGR格式)"""
        colors = {
            "CRITICAL": (0, 0, 255),    # 红
            "HIGH": (0, 165, 255),       # 橙
            "MEDIUM": (0, 215, 255),     # 黄
            "LOW": (0, 255, 0),          # 绿
            "SAFE": (200, 200, 200),     # 灰
        }
        return colors.get(risk_level, (255, 255, 255))
    
    def get_bird_eye_view(self) -> Optional[np.ndarray]:
        """获取CARLA鸟瞰图 - 模拟模式"""
        try:
            img_size = 600
            scale = 1.5
            img = np.zeros((img_size, img_size, 3), dtype=np.uint8)
            img[:] = (40, 40, 40)
            
            center_x = img_size // 2
            center_y = img_size // 2
            
            # 绘制网格
            for i in range(0, img_size, 30):
                cv2.line(img, (i, 0), (i, img_size), (60, 60, 60), 1)
                cv2.line(img, (0, i), (img_size, i), (60, 60, 60), 1)
            
            # 模拟车辆数据（如果真实CARLA不可用）
            if not HAS_CARLA or self.world is None:
                # 绘制模拟车辆
                import random
                random.seed(int(time.time()) % 1000)
                
                # 自车（中心）
                cv2.circle(img, (center_x, center_y), 12, (0, 255, 0), -1)
                cv2.putText(img, "EGO", (center_x-15, center_y+4), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
                
                # 周围车辆（随机位置）
                for i in range(3):
                    x = center_x + random.randint(-150, 150)
                    y = center_y + random.randint(-150, 150)
                    if abs(x-center_x) < 20 and abs(y-center_y) < 20:
                        continue
                    cv2.circle(img, (x, y), 8, (255, 255, 255), 2)
                
                # 行人
                for i in range(2):
                    x = center_x + random.randint(-200, 200)
                    y = center_y + random.randint(-200, 200)
                    cv2.circle(img, (x, y), 5, (255, 0, 255), -1)
                
                return img
            
            # 真实CARLA模式 - 获取实际车辆数据
            actors = self.world.get_actors()
            vehicles = actors.filter('vehicle.*')
            
            if not vehicles:
                return img
            
            ego = None
            for v in vehicles:
                if v.attributes.get('role_name') == 'ego':
                    ego = v
                    break
            if ego is None:
                ego = list(vehicles)[0]
            
            ego_transform = ego.get_transform()
            ego_loc = ego_transform.location
            
            # 绘制所有车辆
            for v in vehicles:
                t = v.get_transform()
                v_loc = t.location
                
                dx = (v_loc.x - ego_loc.x) * scale
                dy = -(v_loc.y - ego_loc.y) * scale
                
                px = int(center_x + dx)
                py = int(center_y + dy)
                
                if 0 <= px < img_size and 0 <= py < img_size:
                    is_ego = v.id == ego.id
                    color = (0, 255, 0) if is_ego else (255, 255, 255)
                    size = 12 if is_ego else 8
                    
                    yaw_rad = np.radians(t.rotation.yaw - ego_transform.rotation.yaw)
                    dx_front = size * np.cos(yaw_rad)
                    dy_front = size * np.sin(yaw_rad)
                    
                    cv2.circle(img, (px, py), size, color, -1 if is_ego else 2)
                    end_x = int(px + dx_front)
                    end_y = int(py - dy_front)
                    cv2.arrowedLine(img, (px, py), (end_x, end_y), color, 2)
            
            # 绘制行人
            pedestrians = actors.filter('walker.*')
            for p in pedestrians:
                t = p.get_transform()
                p_loc = t.location
                dx = (p_loc.x - ego_loc.x) * scale
                dy = -(p_loc.y - ego_loc.y) * scale
                px = int(center_x + dx)
                py = int(center_y + dy)
                if 0 <= px < img_size and 0 <= py < img_size:
                    cv2.circle(img, (px, py), 5, (255, 0, 255), -1)
            
            # 绘制交通灯
            lights = actors.filter('traffic.traffic_light')
            for light in lights:
                t = light.get_transform()
                l_loc = t.location
                dx = (l_loc.x - ego_loc.x) * scale
                dy = -(l_loc.y - ego_loc.y) * scale
                px = int(center_x + dx)
                py = int(center_y + dy)
                if 0 <= px < img_size and 0 <= py < img_size:
                    if HAS_CARLA:
                        state = light.get_light_state()
                        if state == carla.TrafficLightState.Red:
                            color = (0, 0, 255)
                        elif state == carla.TrafficLightState.Yellow:
                            color = (0, 215, 255)
                        else:
                            color = (0, 255, 0)
                    else:
                        color = (0, 255, 0)
                    cv2.rectangle(img, (px-4, py-4), (px+4, py+4), color, -1)
            
            return img
            
        except Exception as e:
            print(f"获取鸟瞰图失败: {e}")
            return None
    
    def overlay_risk_info(self, img: np.ndarray) -> np.ndarray:
        """叠加风险信息到图像"""
        h, w = img.shape[:2]
        
        with self.event_lock:
            event = self.current_event
        
        # 顶部状态条
        overlay = img.copy()
        cv2.rectangle(overlay, (0, 0), (w, 100), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)
        
        if event:
            risk_level = event.get("risk_level", "SAFE")
            scenario = event.get("scenario_name", "未知")
            color = self.get_risk_color(risk_level)
            
            # 大标题
            cv2.putText(img, "ADS Safety Platform - Real-time Detection",
                       (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            
            # 风险等级（大字）
            cv2.rectangle(img, (10, 35), (200, 80), color, -1)
            cv2.putText(img, risk_level, (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
            
            # 场景名
            cv2.putText(img, f"Scenario: {scenario}", 
                       (220, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # 风险指数
            risk_index = event.get("risk_index", 0)
            cv2.putText(img, f"Risk Index: {risk_index:.3f}",
                       (220, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        else:
            # 安全状态
            cv2.putText(img, "ADS Safety Platform - Real-time Detection",
                       (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.rectangle(img, (10, 35), (200, 80), (50, 200, 50), -1)
            cv2.putText(img, "SAFE", (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
            cv2.putText(img, "No anomaly detected", (220, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        
        # 底部状态栏
        cv2.rectangle(img, (0, h-30), (w, h), (0, 0, 0), -1)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(img, f"Time: {timestamp} | Connected to CARLA", 
                   (10, h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        
        return img
    
    def get_frame_bytes(self) -> Optional[bytes]:
        """获取一帧的JPEG字节流"""
        try:
            img = self.get_bird_eye_view()
            if img is None:
                return None
            
            img = self.overlay_risk_info(img)
            
            # 编码为JPEG
            _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return buffer.tobytes()
        except Exception as e:
            print(f"生成帧失败: {e}")
            return None


# 全局可视化器实例
visualizer = CarlaVisualizer()


# 创建独立的FastAPI应用（不影响主API）
viz_app = FastAPI(title="CARLA Visualizer", version="1.0.0")
viz_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@viz_app.get("/api/carla/view")
def carla_view():
    """获取一帧CARLA可视化画面 (MJPEG格式)"""
    img_bytes = visualizer.get_frame_bytes()
    if img_bytes is None:
        return Response(content=b"", media_type="image/jpeg", status_code=503)
    return Response(content=img_bytes, media_type="image/jpeg")


@viz_app.get("/api/carla/event")
def carla_current_event():
    """获取当前正在显示的事件"""
    with visualizer.event_lock:
        return visualizer.current_event or {"risk_level": "SAFE", "scenario_name": "无"}


@viz_app.post("/api/carla/event/update")
async def carla_event_update(event: Dict[str, Any]):
    """更新可视化器中的当前事件（主检测器调用）"""
    visualizer.set_event(event)
    return {"success": True}


@viz_app.get("/api/carla/health")
def carla_viz_health():
    """可视化器健康检查"""
    return {
        "status": "healthy",
        "carla_connected": visualizer.world is not None,
        "running": visualizer.running
    }


@viz_app.get("/carla-viewer")
def carla_viewer_page():
    """CARLA可视化页面"""
    html_path = "/home/aisecurity/01_ZHB/output/carla_viewer.html"
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="text/html")
    return Response(content="<h1>CARLA Viewer not found</h1>", media_type="text/html")


def run_visualizer_server(host="0.0.0.0", port=8001):
    """运行可视化服务器"""
    print(f"启动CARLA可视化服务器: http://{host}:{port}/carla-viewer")
    uvicorn.run(viz_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    # 启动可视化服务
    if visualizer.connect():
        visualizer.running = True
        print("✅ 已连接CARLA仿真环境")
    else:
        print("⚠️ CARLA未连接，运行在无CARLA模式")
    
    run_visualizer_server()
