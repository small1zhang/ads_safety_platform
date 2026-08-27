#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backend/app/core/detector.py - 异常检测核心逻辑（稳定版）

提供：
- 实时检测循环（支持持续运行或定时时长）
- 每次检测到异常事件立即生成per-event知识图谱并广播
- 历史数据管理
- WebSocket流式推送
- 10秒/30秒/60秒检测模式
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
    """异常检测器"""
    
    def __init__(self):
        # 历史记录限制最近200条
        self.history: deque = deque(maxlen=200)
        self.stats: Dict[str, Any] = {
            "total": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "by_type": {}
        }
        self._running = False
        self._latest: Optional[Dict[str, Any]] = None
        
        # ===== WebSocket多客户端订阅者 =====
        self._subscribers: List[asyncio.Queue] = []
        
        # ===== Per-event知识图谱存储 =====
        self._event_graphs: Dict[int, str] = {}
        self._kg_output_dir = "/home/aisecurity/01_ZHB/output"
        os.makedirs(self._kg_output_dir, exist_ok=True)
    
    async def run_continuous(
        self,
        duration: Optional[float],
        interval: float = 2.0,
        carla_client=None,
        inject_anomalies: bool = True
    ) -> Dict[str, Any]:
        """
        运行连续检测
        
        参数:
            duration: 检测时长（秒），None表示持续运行直到stop
            interval: 检测间隔（秒）
        """
        self._running = True
        start_time = time.time()
        
        scenario_names = [
            "前车急刹", "行人横穿", "变道碰撞", "红灯闯行",
            "跟车过近", "超速行驶", "逆向行驶", "违规变道"
        ]
        
        while self._running:
            # 检查是否超时
            if duration is not None and (time.time() - start_time) >= duration:
                break
            
            # 约15%的概率产生一个异常事件（模拟真实驾驶场景）
            if random.random() < 0.15:
                result = self._create_anomaly_event(scenario_names)
                self._record(result)
                
                # 生成per-event图谱并广播
                kg_path = self._build_event_graph_and_save(result)
                result["kg_path"] = kg_path
                self._event_graphs[result["scenario_id"]] = kg_path
                
                # 广播给所有订阅者
                await self._broadcast({
                    "type": "anomaly",
                    "data": result
                })
                
                # 更新最新状态
                self._latest = result
            
            # 等待下一个间隔
            await asyncio.sleep(interval)
        
        self._running = False
        
        return {
            "success": True,
            "stats": self.stats,
            "total_time": time.time() - start_time
        }
    
    def stop(self):
        """停止检测循环"""
        self._running = False
    
    def _create_anomaly_event(self, scenario_names: List[str]) -> Dict[str, Any]:
        """创建一个异常事件"""
        scenario_name = random.choice(scenario_names)
        risk_level = random.choice(["CRITICAL", "HIGH"])
        
        return {
            "scenario_id": self.stats["total"] + 1,
            "scenario_name": scenario_name,
            "timestamp": datetime.now().isoformat(),
            "ego_x": round(random.uniform(-50, 50), 2),
            "ego_y": round(random.uniform(-50, 50), 2),
            "ego_speed": round(random.uniform(0, 30), 1),
            "vehicle_count": random.randint(1, 8),
            "violations": [
                {
                    "code": f"V{random.randint(1, 8)}",
                    "rule": scenario_name,
                    "message": f"检测到{scenario_name}风险",
                    "level": risk_level
                }
            ],
            "risk_index": round(random.uniform(0.4, 0.95), 3),
            "risk_level": risk_level,
            "duration_ms": round(random.uniform(50, 200), 1),
            "source": "detection"
        }
    
    def _record(self, result: Dict[str, Any]):
        """记录检测结果到历史"""
        self.history.append(result)
        self.stats["total"] += 1
        level = result["risk_level"]
        self.stats[level.lower()] = self.stats.get(level.lower(), 0) + 1
        # 按类型统计
        name = result["scenario_name"]
        self.stats["by_type"][name] = self.stats["by_type"].get(name, 0) + 1
    
    async def _broadcast(self, message: Dict[str, Any]):
        """广播消息给所有订阅者"""
        for q in self._subscribers:
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                # 丢弃最老的消息
                try:
                    q.get_nowait()
                    q.put_nowait(message)
                except:
                    pass
    
    async def subscribe(self) -> AsyncIterator[Dict[str, Any]]:
        """订阅实时检测事件"""
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.append(q)
        try:
            while True:
                item = await q.get()
                yield item
        finally:
            if q in self._subscribers:
                self._subscribers.remove(q)
    
    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取历史记录"""
        return list(self.history)[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats.copy()
    
    def get_event_graph_path(self, event_id: int) -> Optional[str]:
        """获取指定event的per-event图谱"""
        return self._event_graphs.get(event_id)
    
    def _build_event_graph_and_save(self, result: Dict[str, Any]) -> str:
        """为单个事件生成细粒度知识图谱并保存"""
        scenario_id = result["scenario_id"]
        timestamp = result["timestamp"]
        scenario_name = result["scenario_name"]
        risk_level = result["risk_level"]
        risk_index = result["risk_index"]
        ego_x = result["ego_x"]
        ego_y = result["ego_y"]
        ego_speed = result["ego_speed"]
        vehicle_count = result["vehicle_count"]
        violations = result.get("violations", [])
        
        # 生成HTML知识图谱
        html_content = self._generate_kg_html(
            scenario_id, timestamp, scenario_name, risk_level, risk_index,
            ego_x, ego_y, ego_speed, vehicle_count, violations
        )
        
        # 保存
        filename = f"kg_event_{scenario_id}.html"
        filepath = os.path.join(self._kg_output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        return f"/output/{filename}"
    
    def _generate_kg_html(
        self, scenario_id, timestamp, scenario_name, risk_level,
        risk_index, ego_x, ego_y, ego_speed, vehicle_count, violations
    ) -> str:
        """生成事件图谱HTML"""
        risk_color = {
            "CRITICAL": "#ff4d4f",
            "HIGH": "#faad14",
            "MEDIUM": "#f39c12",
            "LOW": "#52c41a"
        }.get(risk_level, "#52c41a")
        
        violation_html = "".join([
            f'<div class="v-item"><span class="v-badge" style="background:{risk_color}">{html.escape(v["level"])}</span> {html.escape(v["message"])}</div>'
            for v in violations
        ]) or '<div class="v-item">无具体违规项</div>'
        
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>事件图谱 #{scenario_id}: {html.escape(scenario_name)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            min-height: 100vh;
            color: #e0e0e0;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
        }}
        h1 {{ font-size: 1.5em; margin-bottom: 10px; color: #667eea; }}
        .event-info {{
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 15px 25px;
            margin-bottom: 20px;
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
            justify-content: center;
        }}
        .info-item {{ text-align: center; }}
        .info-label {{ font-size: 0.8em; opacity: 0.7; }}
        .info-value {{ font-size: 1.2em; font-weight: bold; }}
        .risk-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: bold;
            color: white;
            background: {risk_color};
        }}
        .violation-box {{
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            padding: 20px;
            max-width: 500px;
            width: 100%;
        }}
        .v-item {{
            padding: 8px;
            margin: 5px 0;
            background: rgba(0,0,0,0.2);
            border-radius: 6px;
        }}
        .v-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.8em;
            color: white;
            margin-right: 8px;
        }}
    </style>
</head>
<body>
    <h1>事件知识图谱 #{scenario_id}</h1>
    
    <div class="event-info">
        <div class="info-item">
            <div class="info-label">场景类型</div>
            <div class="info-value">{html.escape(scenario_name)}</div>
        </div>
        <div class="info-item">
            <div class="info-label">风险等级</div>
            <div class="info-value"><span class="risk-badge">{html.escape(risk_level)}</span></div>
        </div>
        <div class="info-item">
            <div class="info-label">风险指数</div>
            <div class="info-value">{risk_index:.3f}</div>
        </div>
        <div class="info-item">
            <div class="info-label">自车速度</div>
            <div class="info-value">{ego_speed:.1f} m/s</div>
        </div>
        <div class="info-item">
            <div class="info-label">周围车辆</div>
            <div class="info-value">{vehicle_count} 辆</div>
        </div>
        <div class="info-item">
            <div class="info-label">时间</div>
            <div class="info-value" style="font-size:0.9em">{html.escape(timestamp)}</div>
        </div>
    </div>
    
    <div class="violation-box">
        <h3 style="margin-bottom:10px;color:#667eea;">检测到的违规行为</h3>
        {violation_html}
    </div>
</body>
</html>"""
