#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版 main.py - ADS Safety Platform
"""

import os
import asyncio
from fastapi import FastAPI, WebSocket, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

from app.core.detector_simple import AnomalyDetector

app = FastAPI(title="ADS Safety Platform", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

detector = AnomalyDetector()

# ===== API端点 =====

@app.get("/api/health")
async def health():
    return {"status": "healthy", "carla_connected": False, "timestamp": datetime.now().isoformat()}

@app.get("/api/detect/history")
async def detect_history(limit: int = 50):
    return {"history": detector.get_history(limit), "stats": detector.get_stats()}

@app.post("/api/detect/run")
async def detect_run(background_tasks=None):
    """启动持续检测"""
    from fastapi.concurrency import run_in_threadpool
    asyncio.ensure_future(detector.run_continuous(duration=None, interval=2.0, inject_anomalies=True))
    return {"success": True, "message": "检测已启动"}

@app.post("/api/detect/start")
async def detect_start():
    """启动持续检测"""
    asyncio.ensure_future(detector.run_continuous(duration=None, interval=2.0, inject_anomalies=True))
    return {"success": True, "message": "检测已启动"}

@app.post("/api/detect/stop")
async def detect_stop():
    detector.stop()
    return {"success": True, "message": "检测已停止"}

@app.get("/output/{filename:path}")
async def get_output(filename: str):
    from fastapi.responses import FileResponse
    filepath = os.path.join("/home/aisecurity/01_ZHB/output", filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="text/html")
    raise HTTPException(status_code=404, detail="Not found")

@app.get("/dashboard")
async def dashboard():
    from fastapi.responses import FileResponse
    filepath = "/home/aisecurity/01_ZHB/output/detection_dashboard.html"
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="text/html")
    raise HTTPException(status_code=404, detail="Dashboard not found")

@app.websocket("/api/ws/detection")
async def ws_detection(websocket: WebSocket):
    await websocket.accept()
    try:
        async for event in detector.subscribe():
            await websocket.send_json(event)
    except:
        pass
    finally:
        await websocket.close()
