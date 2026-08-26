#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backend/app/main.py - FastAPI 主入口

功能：
- 提供REST API接口
- 管理CARLA连接
- 运行异常检测
- 提供知识图谱数据
- 数据库持久化
"""

from fastapi import FastAPI, WebSocket, BackgroundTasks, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import asyncio
import json
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入配置
from app.config import Settings

# 导入核心模块
from app.core.detector import AnomalyDetector
from app.core.carla_client import CARLAClient

# 创建FastAPI应用
app = FastAPI(
    title="ADS Safety Platform API",
    description="自动驾驶安全验证平台 - 前后端分离版",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发模式下允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 加载配置
settings = Settings()

# 全局实例
carla_client: Optional[CARLAClient] = None
detector: AnomalyDetector = AnomalyDetector()

# ============== 数据模型 ==============

class RiskLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DetectionResult(BaseModel):
    """检测结果模型"""
    scenario_id: int = Field(description="场景ID")
    scenario_name: str = Field(description="场景名称")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    ego_x: float = Field(description="自车X坐标")
    ego_y: float = Field(description="自车Y坐标")
    ego_speed: float = Field(description="自车速度(m/s)")
    vehicle_count: int = Field(description="周围车辆数")
    violations: List[Dict[str, Any]] = Field(default_factory=list)
    risk_index: float = Field(ge=0, le=1)
    risk_level: RiskLevel
    duration_ms: float = Field(default=0)


class DetectionResponse(BaseModel):
    """检测响应模型"""
    success: bool
    results: List[DetectionResult]
    stats: Dict[str, Any]
    total_time: float


# ============== 健康检查 ==============

@app.get("/dashboard")
async def get_dashboard():
    """返回仪表盘HTML页面"""
    from fastapi.responses import FileResponse
    
    file_path = os.path.join(settings.output_dir, "detection_dashboard.html")
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="仪表盘未找到，请先运行检测")

@app.get("/api/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "ADS Safety Platform",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "carla_connected": carla_client.is_connected() if carla_client else False
    }


# ============== 配置端点 ==============

@app.get("/api/config")
async def get_config():
    """获取系统配置"""
    return {
        "carla_host": settings.carla_host,
        "carla_port": settings.carla_port,
        "detect_interval": settings.detect_interval,
        "max_scenarios": settings.max_scenarios,
        "risk_thresholds": {
            "critical": 0.7,
            "high": 0.4,
            "medium": 0.2,
            "low": 0.0
        }
    }


@app.post("/api/config")
async def update_config(config: Dict[str, Any]):
    """更新系统配置"""
    # 更新配置
    for key, value in config.items():
        setattr(settings, key, value)
    
    return {"success": True, "message": "配置已更新"}


# ============== 实时检测 ==============

class DetectRequest(BaseModel):
    """检测请求模型"""
    duration: float = Field(default=60, ge=1, le=3600, description="检测时长(秒)")
    interval: float = Field(default=1.0, ge=0.1, le=10, description="采样间隔(秒)")
    inject_anomalies: bool = Field(default=True, description="注入异常场景")


@app.post("/api/detect/run")
async def run_detection(
    request: DetectRequest = Body(default=DetectRequest()),
    background_tasks: BackgroundTasks = None
):
    """
    运行异常检测
    
    - **duration**: 检测时长（秒）
    - **interval**: 采样间隔（秒）
    - **inject_anomalies**: 是否注入异常场景（无CARLA时使用）
    """
    global carla_client
    
    # 尝试连接CARLA
    if not carla_client:
        carla_client = CARLAClient(
            host=settings.carla_host,
            port=settings.carla_port
        )
    
    if not carla_client.is_connected():
        # 使用备用模式
        inject_anomalies = True
    
    results = await detector.run_continuous(
        duration=request.duration,
        interval=request.interval,
        carla_client=carla_client,
        inject_anomalies=request.inject_anomalies
    )
    
    return results


@app.get("/api/detect/history")
async def get_detection_history(limit: int = 50):
    """获取检测历史"""
    history = detector.get_history(limit=limit)
    stats = detector.get_stats()
    
    return {
        "history": history,
        "stats": stats,
        "total": len(history)
    }


@app.get("/api/detect/latest")
async def get_latest_detection():
    """获取最新的检测结果"""
    latest = detector.get_latest()
    if latest:
        return latest
    raise HTTPException(status_code=404, detail="暂无检测结果")


# ============== 知识图谱 ==============

@app.get("/api/kg/latest")
async def get_latest_knowledge_graph():
    """获取最新的知识图谱数据"""
    kg_data = detector.get_knowledge_graph()
    if kg_data:
        return kg_data
    raise HTTPException(status_code=404, detail="暂无知识图谱数据")


@app.get("/api/kg/generate")
async def generate_knowledge_graph() -> Dict[str, Any]:
    """生成知识图谱"""
    kg_html = detector.generate_knowledge_graph_html()
    return {
        "success": True,
        "html_path": "/output/knowledge_graph.html",
        "timestamp": datetime.now().isoformat()
    }


# ============== WebSocket 实时推送 ==============

@app.websocket("/api/ws/detection")
async def websocket_detection(websocket: WebSocket):
    """
    WebSocket实时推送检测结果
    
    客户端连接后会接收实时检测结果
    """
    await websocket.accept()
    
    try:
        async for result in detector.stream_results():
            await websocket.send_json(result)
    except Exception as e:
        await websocket.close()
    finally:
        await websocket.close()


# ============== 输出端点 ==============

@app.get("/output/{filename:path}")
async def get_output_file(filename: str):
    """获取输出文件（HTML等）"""
    from fastapi.responses import FileResponse
    
    file_path = os.path.join(settings.output_dir, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="文件不存在")


# ============== 启动事件 ==============

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    print(f"[INFO] ADS Safety Platform v2.0 启动")
    print(f"[INFO] 监听地址: {settings.carla_host}:{settings.carla_port}")
    print(f"[INFO] 输出目录: {settings.output_dir}")
    
    # 创建输出目录
    os.makedirs(settings.output_dir, exist_ok=True)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理"""
    global carla_client
    if carla_client:
        await carla_client.disconnect()
    print("[INFO] 应用已关闭")


# ============== 主函数 ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=1
    )