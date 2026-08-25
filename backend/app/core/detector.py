#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backend/app/core/detector.py - 异常检测核心逻辑

提供：
- 实时检测循环
- 历史数据管理
- 知识图谱生成
- WebSocket流式推送
"""

import asyncio
import json
import random
import time
import os
from datetime import datetime
from typing import List, Dict, Any, AsyncIterator, Optional


class AnomalyDetector:
    """异常检测器"""
    
    def __init__(self):
        self.history: List[Dict[str, Any]] = []
        self.stats: Dict[str, Any] = {
            "total": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "by_type": {}
        }
        self._latest: Optional[Dict[str, Any]] = None
        self._knowledge_graph: Optional[Dict[str, Any]] = None
        self._running = False
        self._event = asyncio.Event()
    
    async def run_continuous(
        self,
        duration: float,
        interval: float,
        carla_client=None,
        inject_anomalies: bool = True
    ) -> Dict[str, Any]:
        """运行连续检测"""
        self._running = True
        start_time = time.time()
        results = []
        
        scenario_names = [
            "前车急刹", "行人横穿", "变道碰撞", "红灯闯行",
            "跟车过近", "超速行驶", "逆向行驶", "违规变道"
        ]
        
        while time.time() - start_time < duration:
            # 检测一轮
            result = self._detect_one(carla_client, inject_anomalies, scenario_names)
            results.append(result)
            self._record(result)
            
            # 发送事件
            self._latest = result
            self._event.set()
            
            # 等待下一个间隔
            await asyncio.sleep(interval)
        
        self._running = False
        
        # 生成知识图谱
        self._generate_knowledge_graph(results)
        
        return {
            "success": True,
            "results": results,
            "stats": self.stats,
            "total_time": time.time() - start_time
        }
    
    def _detect_one(self, carla_client, inject_anomalies: bool, scenario_names: List[str]) -> Dict[str, Any]:
        """检测一个场景"""
        # 生成随机场景数据
        risk = random.random()
        
        if risk > 0.7:
            risk_level = "CRITICAL"
        elif risk > 0.4:
            risk_level = "HIGH"
        elif risk > 0.2:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        scenario_name = random.choice(scenario_names)
        
        result = {
            "scenario_id": len(self.history) + 1,
            "scenario_name": scenario_name,
            "timestamp": datetime.now().isoformat(),
            "ego_x": random.uniform(-50, 50),
            "ego_y": random.uniform(-50, 50),
            "ego_speed": random.uniform(0, 30),
            "vehicle_count": random.randint(0, 8),
            "violations": [
                {
                    "code": f"V{random.randint(1, 8)}",
                    "rule": scenario_name,
                    "message": f"检测到{scenario_name}风险",
                    "level": risk_level
                }
            ],
            "risk_index": round(risk, 3),
            "risk_level": risk_level,
            "duration_ms": random.uniform(50, 500)
        }
        
        return result
    
    def _record(self, result: Dict[str, Any]):
        """记录检测结果"""
        self.history.append(result)
        self.stats["total"] += 1
        level = result["risk_level"]
        if level == "CRITICAL":
            self.stats["critical"] += 1
        elif level == "HIGH":
            self.stats["high"] += 1
        elif level == "MEDIUM":
            self.stats["medium"] += 1
        else:
            self.stats["low"] += 1
        
        # 按类型统计
        scenario_name = result["scenario_name"]
        self.stats["by_type"][scenario_name] = self.stats["by_type"].get(scenario_name, 0) + 1
    
    def _generate_knowledge_graph(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成知识图谱数据"""
        nodes = []
        edges = []
        
        # 自车节点
        nodes.append({
            "id": "ego",
            "label": "Ego车辆",
            "type": "vehicle",
            "color": "#4CAF50"
        })
        
        # 场景节点
        for i, result in enumerate(results):
            node_id = f"scenario_{result['scenario_id']}"
            nodes.append({
                "id": node_id,
                "label": result["scenario_name"],
                "type": "scenario",
                "risk_level": result["risk_level"],
                "color": self._get_risk_color(result["risk_level"])
            })
            
            edges.append({
                "source": "ego",
                "target": node_id,
                "relation": "检测到",
                "weight": result["risk_index"]
            })
        
        self._knowledge_graph = {
            "nodes": nodes,
            "edges": edges,
            "generated_at": datetime.now().isoformat(),
            "node_count": len(nodes),
            "edge_count": len(edges)
        }
        
        return self._knowledge_graph
    
    def _get_risk_color(self, level: str) -> str:
        """获取风险等级颜色"""
        colors = {
            "CRITICAL": "#F44336",
            "HIGH": "#FF9800",
            "MEDIUM": "#FFEB3B",
            "LOW": "#4CAF50"
        }
        return colors.get(level, "#9E9E9E")
    
    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取历史记录"""
        return self.history[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats
    
    def get_latest(self) -> Optional[Dict[str, Any]]:
        """获取最新结果"""
        return self._latest
    
    def get_knowledge_graph(self) -> Optional[Dict[str, Any]]:
        """获取知识图谱"""
        return self._knowledge_graph
    
    def generate_knowledge_graph_html(self) -> str:
        """生成知识图谱HTML"""
        if not self._knowledge_graph:
            return ""
        
        # 生成SVG
        svg_parts = []
        width, height = 1200, 800
        
        # 放置节点
        positions = {}
        for i, node in enumerate(self._knowledge_graph["nodes"]):
            x = 100 + (i % 5) * 220 + random.uniform(-30, 30)
            y = 100 + (i // 5) * 150 + random.uniform(-30, 30)
            positions[node["id"]] = (x, y)
        
        # 绘制边
        for edge in self._knowledge_graph["edges"]:
            sx, sy = positions.get(edge["source"], (width/2, height/2))
            tx, ty = positions.get(edge["target"], (width/2, height/2))
            svg_parts.append(
                f'<line x1="{sx}" y1="{sy}" x2="{tx}" y2="{ty}" '
                f'stroke="#888" stroke-width="2" stroke-dasharray="5,5"/>'
            )
            # 标签
            mx, my = (sx + tx) / 2, (sy + ty) / 2
            svg_parts.append(
                f'<text x="{mx}" y="{my}" fill="#666" font-size="12" '
                f'text-anchor="middle">{edge["relation"]}</text>'
            )
        
        # 绘制节点
        for node in self._knowledge_graph["nodes"]:
            x, y = positions.get(node["id"], (width/2, height/2))
            svg_parts.append(
                f'<circle cx="{x}" cy="{y}" r="25" fill="{node["color"]}" '
                f'opacity="0.8" stroke="#fff" stroke-width="2"/>'
            )
            svg_parts.append(
                f'<text x="{x}" y="{y+5}" fill="white" font-size="10" '
                f'text-anchor="middle">{node["label"]}</text>'
            )
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>知识图谱</title>
    <style>
        body {{ font-family: sans-serif; background: #1a1a2e; color: #eee; }}
        h2 {{ text-align: center; color: #4CAF50; }}
        .kg-container {{ text-align: center; }}
        svg {{ background: #16213e; border-radius: 10px; }}
    </style>
</head>
<body>
    <h2>时空知识图谱</h2>
    <div class="kg-container">
        <svg width="{width}" height="{height}">
            {''.join(svg_parts)}
        </svg>
    </div>
    <p style="text-align:center;color:#888">
        生成时间: {datetime.now().isoformat()} | 节点数: {self._knowledge_graph["node_count"]} | 关系数: {self._knowledge_graph["edge_count"]}
    </p>
</body>
</html>"""
        
        # 保存文件
        os.makedirs("/app/output", exist_ok=True)
        path = "/app/output/knowledge_graph.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        
        return path
    
    async def stream_results(self) -> AsyncIterator[Dict[str, Any]]:
        """流式推送检测结果"""
        while True:
            if self._latest:
                yield self._latest
            await asyncio.sleep(1.0)