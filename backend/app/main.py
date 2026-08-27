#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backend/app/main.py - ADS Safety Platform 完整版本
包含：10秒/30秒/60秒检测模式
"""

import os
import asyncio
from fastapi import FastAPI, WebSocket, BackgroundTasks, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

from app.core.detector import AnomalyDetector

app = FastAPI(title="ADS Safety Platform", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

detector = AnomalyDetector()

# ===== 数据模型 =====
class DetectRequest(BaseModel):
    duration: Optional[float] = Field(None, description="检测时长（秒）")
    interval: Optional[float] = Field(1.0, description="检测间隔（秒）")
    inject_anomalies: bool = Field(True, description="是否注入异常场景")

# ===== API端点 =====

@app.get("/api/health")
async def health():
    # 实际检测CARLA连接状态
    carla_status = False
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        result = sock.connect_ex(('localhost', 2000))
        sock.close()
        carla_status = (result == 0)
    except:
        carla_status = False
    
    return {
        "status": "healthy",
        "carla_connected": carla_status,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/detect/history")
async def detect_history(limit: int = 50):
    return {"history": detector.get_history(limit), "stats": detector.get_stats()}

@app.get("/api/detect/event_graph/{event_id}")
async def get_event_graph(event_id: int):
    graph_path = detector.get_event_graph_path(event_id)
    if graph_path and os.path.exists(os.path.join("/home/aisecurity/01_ZHB/output", graph_path.lstrip("/output"))):
        from fastapi.responses import FileResponse
        return FileResponse(graph_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="图谱不存在")

@app.post("/api/detect/run")
async def detect_run(request: DetectRequest = Body(default=DetectRequest()), background_tasks: BackgroundTasks = None):
    """
    运行异常检测
    
    - **duration**: 检测时长（秒）（可选，如果不传则持续运行到停止）
    - **interval**: 采样间隔（秒）
    - **inject_anomalies**: 是否注入异常场景
    """
    # 后台任务运行检测
    background_tasks.add_task(
        detector.run_continuous,
        duration=request.duration if request.duration else None,
        interval=request.interval,
        carla_client=None,
        inject_anomalies=request.inject_anomalies
    )
    
    duration_text = f"{request.duration if request.duration else '持续'} 秒" if request.duration else "持续运行"
    return {"success": True, "message": f"已启动{duration_text}的异常检测", "status": "running"}

@app.post("/api/detect/start")
async def detect_start():
    """启动持续异常检测（实时模式）"""
    asyncio.ensure_future(detector.run_continuous(duration=None, interval=2.0, inject_anomalies=True))
    return {"success": True, "message": "持续实时检测已启动", "status": "running"}

@app.post("/api/detect/stop")
async def detect_stop():
    """停止持续检测"""
    detector.stop()
    return {"success": True, "message": "检测已停止"}

@app.get("/output/{filename:path}")
async def get_output_file(filename: str):
    """获取输出文件"""
    from fastapi.responses import FileResponse
    filepath = os.path.join("/home/aisecurity/01_ZHB/output", filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="text/html")
    raise HTTPException(status_code=404, detail="文件不存在")

@app.get("/dashboard")
async def dashboard():
    """仪表盘页面"""
    from fastapi.responses import FileResponse
    dashboard_path = "/home/aisecurity/01_ZHB/output/detection_dashboard.html"
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="仪表盘不存在")

@app.websocket("/api/ws/detection")
async def websocket_detection(websocket: WebSocket):
    """WebSocket实时检测推送"""
    await websocket.accept()
    try:
        async for event in detector.subscribe():
            await websocket.send_json(event)
    except:
        pass
    finally:
        await websocket.close()

# ===== 启动事件 =====

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    print(f"[INFO] ADS Safety Platform v2.0 启动")
    print(f"[INFO] 输出目录: /home/aisecurity/01_ZHB/output")
    
    # 创建输出目录
    os.makedirs("/home/aisecurity/01_ZHB/output", exist_ok=True)
    
    # 不在启动时自动启动检测，等待前端触发
    print(f"[INFO] 就绪，等待前端触发检测")
