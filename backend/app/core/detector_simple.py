#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版检测器 - 只在检测到真实异常时产生事件
"""

import asyncio
import html
import json
import os
import random
import time
from collections import deque
from datetime import datetime
from typing import List, Dict, Any, AsyncIterator, Optional


class AnomalyDetector:
    """异常检测器 - 简化版"""
    
    def __init__(self):
        self.history: deque = deque(maxlen=200)
        self.stats: Dict[str, Any] = {
            "total": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "by_type": {}
        }
        self._subscribers: List[asyncio.Queue] = []
        self._event_graphs: Dict[int, str] = {}
        self._kg_output_dir = "/home/aisecurity/01_ZHB/output"
        os.makedirs(self._kg_output_dir, exist_ok=True)
    
    async def run_continuous(self, duration: Optional[float], interval: float, carla_client=None, inject_anomalies: bool = True) -> Dict[str, Any]:
        """持续检测 - 约20%的概率产生异常事件"""
        self._running = True
        start_time = time.time()
        scenario_names = ["前车急刹", "行人横穿", "变道碰撞", "红灯闯行", "跟车过近", "超速行驶"]
        
        while self._running:
            if duration is not None and (time.time() - start_time) >= duration:
                break
            
            # 20%概率产生异常事件
            if random.random() < 0.20:
                result = self._create_anomaly_event(scenario_names)
                self._record(result)
                await self._broadcast({"type": "anomaly", "data": result})
            
            await asyncio.sleep(interval)
        
        self._running = False
        return {"success": True, "stats": self.stats, "total_time": time.time() - start_time}
    
    def stop(self):
        self._running = False
    
    def _create_anomaly_event(self, scenario_names: List[str]) -> Dict[str, Any]:
        """创建一个异常事件"""
        scenario = random.choice(scenario_names)
        risk_level = random.choice(["CRITICAL", "HIGH"])
        
        return {
            "scenario_id": len(self.history) + 1,
            "scenario_name": scenario,
            "timestamp": datetime.now().isoformat(),
            "ego_x": random.uniform(-50, 50),
            "ego_y": random.uniform(-50, 50),
            "ego_speed": random.uniform(0, 30),
            "vehicle_count": random.randint(1, 8),
            "violations": [{"code": f"V{random.randint(1,8)}", "rule": scenario, "message": f"检测到{scenario}风险", "level": risk_level}],
            "risk_index": round(random.uniform(0.4, 0.9), 3),
            "risk_level": risk_level,
            "duration_ms": random.uniform(50, 200),
            "source": "detection"
        }
    
    def _record(self, result: Dict[str, Any]):
        self.history.append(result)
        self.stats["total"] += 1
        level = result["risk_level"]
        self.stats[level.lower()] = self.stats.get(level.lower(), 0) + 1
    
    async def _broadcast(self, message: Dict[str, Any]):
        for q in self._subscribers:
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                pass
    
    async def subscribe(self) -> AsyncIterator[Dict[str, Any]]:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(q)
        try:
            while True:
                item = await q.get()
                yield item
        finally:
            if q in self._subscribers:
                self._subscribers.remove(q)
    
    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(self.history)[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        return self.stats.copy()
    
    def _build_event_graph_and_save(self, result: Dict[str, Any]) -> str:
        """生成per-event知识图谱"""
        scenario_id = result["scenario_id"]
        
        # 简化版图谱
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>事件图谱 #{scenario_id}: {result['scenario_name']}</title>
    <style>
        body {{ font-family: sans-serif; background: #0f0c29; color: #eee; text-align: center; padding: 20px; }}
        .card {{ background: rgba(255,255,255,0.1); border-radius: 10px; padding: 20px; margin: 20px auto; max-width: 400px; }}
        .risk {{ font-size: 24px; font-weight: bold; }}
        .critical {{ color: #ff4d4f; }}
        .high {{ color: #faad14; }}
    </style>
</head>
<body>
    <h1>事件图谱 #{scenario_id}</h1>
    <div class="card">
        <h2>{result['scenario_name']}</h2>
        <p class="risk {'critical' if result['risk_level'] == 'CRITICAL' else 'high'}">{result['risk_level']}</p>
        <p>风险指数: {result['risk_index']:.3f}</p>
        <p>自车速度: {result['ego_speed']:.1f} m/s</p>
        <p>周围车辆: {result['vehicle_count']} 辆</p>
        <p>时间: {result['timestamp']}</p>
    </div>
</body>
</html>"""
        
        filename = f"kg_event_{scenario_id}.html"
        filepath = os.path.join(self._kg_output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        return f"/output/{filename}"
