#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CARLA 可视化服务（支持两种渲染方式）

渲染方式：
1. **CARLA Debug Draw API** - 在CARLA窗口中叠加文字（需要本地图形界面）
2. **OpenCV Bird's Eye View** - 生成鸟瞰图（带风险信息）推送到Web

注意：此模块是独立的可选服务，不影响主API和检测器

Python端：每帧从detector获取检测结果
渲染层：OpenCV cv2.putText 或 CARLA Debug Draw API
回调机制：检测器每帧调用visualizer.update_event()触发更新
"""

import os
import sys
import time
import threading
import queue
from typing import Optional, Dict, Any, Callable
from datetime import datetime

# OpenCV
import cv2
import numpy as np

# CARLA可选导入
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
    """CARLA 可视化器 - 同时支持CARLA Debug Draw + OpenCV鸟瞰图"""
    
    def __init__(self, host="localhost", port=2000):
        self.host = host
        self.port = port
        self.client = None
        self.world = None
        self.spectator = None
        self.ego_vehicle = None
        
        # 当前事件信息（从检测器共享）
        self.current_event: Optional[Dict[str, Any]] = None
        self.event_lock = threading.Lock()
        self.risk_history: list = []
        
        # 控制标志
        self.running = False
        self.frame_queue = queue.Queue(maxsize=2)
        self.draw_thread: Optional[threading.Thread] = None
        
        # 渲染模式
        self.render_mode = "birdseye"  # "debug_draw" 或 "birdseye"
    
    def connect(self) -> bool:
        """连接CARLA"""
        if not HAS_CARLA:
            print("⚠️ CARLA模块不可用，使用模拟模式")
            return False
        try:
            self.client = carla.Client(self.host, self.port)
            self.client.set_timeout(10.0)
            self.world = self.client.get_world()
            self.spectator = self.world.get_spectator()
            # 找ego车辆
            self._find_ego_vehicle()
            return True
        except Exception as e:
            print(f"CARLA连接失败: {e}")
            return False
    
    def _find_ego_vehicle(self):
        """查找自车（role_name=ego或第一辆车）"""
        if self.world is None:
            return
        try:
            vehicles = self.world.get_actors().filter('vehicle.*')
            for v in vehicles:
                if v.attributes.get('role_name') == 'ego':
                    self.ego_vehicle = v
                    return
            if vehicles and len(vehicles) > 0:
                self.ego_vehicle = list(vehicles)[0]
        except Exception as e:
            print(f"查找ego车辆失败: {e}")
    
    def set_event(self, event: Dict[str, Any]):
        """
        回调接口：每帧检测结果触发此函数
        由detector或外部调用，无需修改detector源代码
        """
        with self.event_lock:
            self.current_event = event
            self.risk_history.append(event)
            if len(self.risk_history) > 10:
                self.risk_history = self.risk_history[-10:]
    
    def get_current_event(self) -> Optional[Dict[str, Any]]:
        """获取当前事件（供API查询）"""
        with self.event_lock:
            return self.current_event
    
    def get_risk_color_bgr(self, risk_level: str) -> tuple:
        """OpenCV BGR格式颜色"""
        colors = {
            "CRITICAL": (0, 0, 255),    # 红
            "HIGH": (0, 165, 255),       # 橙
            "MEDIUM": (0, 215, 255),     # 黄
            "LOW": (0, 255, 0),          # 绿
            "SAFE": (200, 200, 200),
        }
        return colors.get(risk_level, (255, 255, 255))
    
    def get_risk_color_rgba(self, risk_level: str) -> tuple:
        """CARLA Color (R, G, B, A)"""
        colors = {
            "CRITICAL": carla.Color(255, 0, 0, 255),  # 红
            "HIGH": carla.Color(255, 165, 0, 255),    # 橙
            "MEDIUM": carla.Color(255, 255, 0, 255),  # 黄
            "LOW": carla.Color(0, 255, 0, 255),      # 绿
            "SAFE": carla.Color(200, 200, 200, 255),
        }
        return colors.get(risk_level, carla.Color(255, 255, 255, 255))
    
    # ================== 方式1: CARLA Debug Draw API ==================
    
    def start_debug_draw(self):
        """启动CARLA Debug Draw线程（需要在CARLA客户端图形界面运行）"""
        if not HAS_CARLA or self.world is None:
            print("⚠️ CARLA未连接，无法使用Debug Draw")
            return False
        
        if self.draw_thread is not None and self.draw_thread.is_alive():
            print("Debug Draw线程已在运行")
            return True
        
        self.running = True
        self.draw_thread = threading.Thread(target=self._debug_draw_loop, daemon=True)
        self.draw_thread.start()
        print("✅ CARLA Debug Draw线程已启动")
        return True
    
    def stop_debug_draw(self):
        """停止Debug Draw"""
        self.running = False
        if self.draw_thread is not None:
            self.draw_thread.join(timeout=2)
        # 清除所有debug绘制
        if HAS_CARLA and self.world is not None:
            try:
                self.world.debug.draw_pending_texts()  # 先绘制避免残留
                self.world.debug.clear_all()
            except:
                pass
        print("CARLA Debug Draw已停止")
    
    def _debug_draw_loop(self):
        """Debug Draw主循环 - 每帧绘制风险信息"""
        while self.running:
            try:
                self._draw_current_state()
                time.sleep(0.1)  # 10fps
            except Exception as e:
                print(f"Debug Draw错误: {e}")
                time.sleep(1)
    
    def _draw_current_state(self):
        """在CARLA世界中绘制当前状态"""
        if not HAS_CARLA or self.world is None:
            return
        
        try:
            # 清除上一帧的绘制
            self.world.debug.clear_pending_texts()  # 清除待绘制文本
            
            with self.event_lock:
                event = self.current_event
                risk_history = self.risk_history.copy()
            
            if self.ego_vehicle is None:
                self._find_ego_vehicle()
            
            # 在自车周围绘制风险信息
            if self.ego_vehicle is not None:
                ego_transform = self.ego_vehicle.get_transform()
                ego_loc = ego_transform.location
                
                if event:
                    risk_level = event.get("risk_level", "SAFE")
                    scenario = event.get("scenario_name", "Unknown")
                    color = self.get_risk_color_rgba(risk_level)
                    
                    # 在自车上方显示风险等级
                    risk_text = f"[{risk_level}] {scenario}"
                    self.world.debug.draw_string(
                        ego_loc + carla.Location(z=3.0),
                        risk_text,
                        draw_shadow=True,
                        color=color,
                        life_time=0.2
                    )
                    
                    # 在ego周围画一个圆圈表示风险区域
                    risk_radius = 10.0
                    if risk_level == "CRITICAL":
                        risk_radius = 15.0
                        z = 0.5
                    elif risk_level == "HIGH":
                        risk_radius = 12.0
                        z = 0.3
                    else:
                        risk_radius = 8.0
                        z = 0.1
                    
                    # 在地面画彩色圆
                    for angle in range(0, 360, 10):
                        rad = np.radians(angle)
                        x = ego_loc.x + risk_radius * np.cos(rad)
                        y = ego_loc.y + risk_radius * np.sin(rad)
                        self.world.debug.draw_point(
                            carla.Location(x=x, y=y, z=ego_loc.z - 0.5),
                            size=0.05,
                            color=color,
                            life_time=0.2
                        )
                    
                    # 绘制违规车辆（如果有）
                    for v_event in risk_history[-3:]:
                        if 'ego_x' in v_event and 'ego_y' in v_event:
                            vx = v_event.get('ego_x', 0)
                            vy = v_event.get('ego_y', 0)
                            self.world.debug.draw_string(
                                carla.Location(x=vx, y=vy, z=2.5),
                                f"#{v_event.get('scenario_id', '?')} {v_event.get('scenario_name', '')[:10]}",
                                draw_shadow=True,
                                color=color,
                                life_time=0.2
                            )
                else:
                    # 安全状态
                    self.world.debug.draw_string(
                        ego_loc + carla.Location(z=3.0),
                        "[SAFE] 正常行驶",
                        draw_shadow=True,
                        color=carla.Color(0, 255, 0, 255),
                        life_time=0.2
                    )
            
            # 绘制自车（如果有）
            if self.ego_vehicle is not None:
                bp = self.ego_vehicle.get_transform()
                self.world.debug.draw_box(
                    carla.BoundingBox(bp.location, carla.Vector3D(2.0, 1.0, 1.5)),
                    carla.Rotation(0, bp.rotation.yaw, 0),
                    thickness=0.1,
                    color=carla.Color(0, 200, 0, 255),
                    life_time=0.2
                )
            
        except Exception as e:
            print(f"绘制状态失败: {e}")
    
    # ================== 方式2: OpenCV 鸟瞰图 ==================
    
    def get_bird_eye_view(self) -> Optional[np.ndarray]:
        """获取CARLA鸟瞰图（OpenCV渲染）"""
        try:
            img_size = 600
            scale = 1.5
            img = np.zeros((img_size, img_size, 3), dtype=np.uint8)
            img[:] = (40, 40, 40)
            
            center_x = img_size // 2
            center_y = img_size // 2
            
            # 网格
            for i in range(0, img_size, 30):
                cv2.line(img, (i, 0), (i, img_size), (60, 60, 60), 1)
                cv2.line(img, (0, i), (img_size, i), (60, 60, 60), 1)
            
            # 尝试使用真实CARLA数据
            if HAS_CARLA and self.world is not None:
                try:
                    return self._render_birdseye_from_carla(img, img_size, center_x, center_y, scale)
                except Exception as e:
                    print(f"CARLA鸟瞰图渲染失败: {e}，使用模拟数据")
            
            # 模拟数据
            return self._render_birdseye_simulation(img, img_size, center_x, center_y)
            
        except Exception as e:
            print(f"获取鸟瞰图失败: {e}")
            return None
    
    def _render_birdseye_from_carla(self, img, img_size, center_x, center_y, scale):
        """从真实CARLA渲染鸟瞰图"""
        actors = self.world.get_actors()
        vehicles = actors.filter('vehicle.*')
        
        if not vehicles or len(vehicles) == 0:
            return self._render_birdseye_simulation(img, img_size, center_x, center_y)
        
        # 找ego
        ego = None
        for v in vehicles:
            if v.attributes.get('role_name') == 'ego':
                ego = v
                break
        if ego is None:
            ego = list(vehicles)[0]
        
        ego_transform = ego.get_transform()
        ego_loc = ego_transform.location
        ego_yaw = ego_transform.rotation.yaw
        
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
                yaw_rad = np.radians(t.rotation.yaw - ego_yaw)
                dx_front = size * np.cos(yaw_rad)
                dy_front = size * np.sin(yaw_rad)
                cv2.circle(img, (px, py), size, color, -1 if is_ego else 2)
                end_x = int(px + dx_front)
                end_y = int(py - dy_front)
                cv2.arrowedLine(img, (px, py), (end_x, end_y), color, 2)
        
        # 行人
        for p in actors.filter('walker.*'):
            t = p.get_transform()
            p_loc = t.location
            dx = (p_loc.x - ego_loc.x) * scale
            dy = -(p_loc.y - ego_loc.y) * scale
            px = int(center_x + dx)
            py = int(center_y + dy)
            if 0 <= px < img_size and 0 <= py < img_size:
                cv2.circle(img, (px, py), 5, (255, 0, 255), -1)
        
        # 交通灯
        for light in actors.filter('traffic.traffic_light'):
            t = light.get_transform()
            l_loc = t.location
            dx = (l_loc.x - ego_loc.x) * scale
            dy = -(l_loc.y - ego_loc.y) * scale
            px = int(center_x + dx)
            py = int(center_y + dy)
            if 0 <= px < img_size and 0 <= py < img_size:
                try:
                    state = light.get_light_state()
                    if state == carla.TrafficLightState.Red:
                        color = (0, 0, 255)
                    elif state == carla.TrafficLightState.Yellow:
                        color = (0, 215, 255)
                    else:
                        color = (0, 255, 0)
                except:
                    color = (0, 255, 0)
                cv2.rectangle(img, (px-4, py-4), (px+4, py+4), color, -1)
        
        return img
    
    def _render_birdseye_simulation(self, img, img_size, center_x, center_y):
        """模拟模式 - 随机生成车辆/行人"""
        import random
        random.seed(int(time.time() * 0.1) % 1000)
        
        # 自车
        cv2.circle(img, (center_x, center_y), 12, (0, 255, 0), -1)
        cv2.putText(img, "EGO", (center_x-15, center_y+4), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        # 朝向
        cv2.arrowedLine(img, (center_x, center_y), (center_x+15, center_y), (0, 255, 0), 2)
        
        # 周围车辆
        for i in range(4):
            x = center_x + random.randint(-200, 200)
            y = center_y + random.randint(-200, 200)
            if abs(x-center_x) < 25 and abs(y-center_y) < 25:
                continue
            cv2.circle(img, (x, y), 8, (255, 255, 255), 2)
        
        # 行人
        for i in range(2):
            x = center_x + random.randint(-250, 250)
            y = center_y + random.randint(-250, 250)
            cv2.circle(img, (x, y), 5, (255, 0, 255), -1)
        
        # 交通灯（模拟）
        light_x = center_x + 200
        light_y = center_y - 100
        cv2.rectangle(img, (light_x-5, light_y-5), (light_x+5, light_y+5), (0, 255, 0), -1)
        
        return img
    
    def overlay_risk_info(self, img: np.ndarray) -> np.ndarray:
        """叠加风险信息到OpenCV画面"""
        h, w = img.shape[:2]
        
        with self.event_lock:
            event = self.current_event
        
        # 顶部状态条
        overlay = img.copy()
        cv2.rectangle(overlay, (0, 0), (w, 100), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)
        
        if event:
            risk_level = event.get("risk_level", "SAFE")
            scenario = event.get("scenario_name", "Unknown")
            color = self.get_risk_color_bgr(risk_level)
            
            cv2.putText(img, "ADS Safety Platform - Real-time Detection",
                       (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.rectangle(img, (10, 35), (200, 80), color, -1)
            cv2.putText(img, risk_level, (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
            cv2.putText(img, f"Scenario: {scenario}", 
                       (220, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            risk_index = event.get("risk_index", 0)
            cv2.putText(img, f"Risk Index: {risk_index:.3f}",
                       (220, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        else:
            cv2.putText(img, "ADS Safety Platform - Real-time Detection",
                       (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.rectangle(img, (10, 35), (200, 80), (50, 200, 50), -1)
            cv2.putText(img, "SAFE", (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
            cv2.putText(img, "No anomaly detected", (220, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        
        # 底部
        cv2.rectangle(img, (0, h-30), (w, h), (0, 0, 0), -1)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(img, f"Time: {timestamp} | Mode: {self.render_mode}", 
                   (10, h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        
        return img
    
    def get_frame_bytes(self) -> Optional[bytes]:
        """获取一帧的JPEG字节流"""
        try:
            img = self.get_bird_eye_view()
            if img is None:
                return None
            img = self.overlay_risk_info(img)
            _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return buffer.tobytes()
        except Exception as e:
            print(f"生成帧失败: {e}")
            return None


# 全局可视化器实例
visualizer = CarlaVisualizer()

# 独立的FastAPI应用
viz_app = FastAPI(title="CARLA Visualizer", version="2.0.0")
viz_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@viz_app.get("/api/carla/view")
def carla_view():
    """获取一帧CARLA可视化画面 (JPEG格式)"""
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
    """
    每帧检测结果回调接口
    主检测器每帧可以调用此API更新可视化状态
    """
    visualizer.set_event(event)
    return {"success": True, "event_id": event.get("scenario_id")}


@viz_app.get("/api/carla/health")
def carla_viz_health():
    """可视化器健康检查"""
    return {
        "status": "healthy",
        "carla_connected": visualizer.world is not None,
        "render_mode": visualizer.render_mode,
        "running": visualizer.running,
        "has_carla_module": HAS_CARLA
    }


@viz_app.post("/api/carla/mode")
async def set_render_mode(mode: str):
    """切换渲染模式: 'debug_draw' 或 'birdseye'"""
    if mode not in ["debug_draw", "birdseye"]:
        return {"success": False, "error": "mode必须是 debug_draw 或 birdseye"}
    
    if mode == "debug_draw":
        visualizer.render_mode = "debug_draw"
        success = visualizer.start_debug_draw()
    else:
        visualizer.stop_debug_draw()
        visualizer.render_mode = "birdseye"
        success = True
    
    return {"success": success, "mode": mode}


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
    if visualizer.connect():
        visualizer.running = True
        print("✅ 已连接CARLA仿真环境")
    else:
        print("⚠️ CARLA未连接，运行在无CARLA模式")
    run_visualizer_server()
