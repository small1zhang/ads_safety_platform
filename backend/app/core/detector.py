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
        """生成完整的事件知识图谱HTML"""
        risk_color = {
            "CRITICAL": "#ff4d4f",
            "HIGH": "#faad14",
            "MEDIUM": "#f39c12",
            "LOW": "#52c41a"
        }.get(risk_level, "#52c41a")
        
        risk_glow = {
            "CRITICAL": "0 0 30px #ff4d4f",
            "HIGH": "0 0 20px #faad14",
            "MEDIUM": "0 0 15px #f39c12",
            "LOW": "0 0 10px #52c41a"
        }.get(risk_level, "0 0 10px #52c41a")
        
        # 违规行为HTML
        violation_html = "".join([
            f'''<div class="v-item">
                <span class="v-badge" style="background:{risk_color}">{html.escape(v["level"])}</span>
                <span class="v-code">{html.escape(v["code"])}</span>
                <span class="v-msg">{html.escape(v["message"])}</span>
            </div>'''
            for v in violations
        ]) or '<div class="v-item">无具体违规项</div>'
        
        # 生成模拟的周围车辆信息
        nearby_vehicles = [
            {"id": f"V{i}", "distance": round(random.uniform(5, 50), 1), 
             "speed": round(random.uniform(0, 30), 1),
             "relation": random.choice(["前车", "后车", "左车", "右车"]),
             "risk": random.choice(["安全", "注意", "危险"])}
            for i in range(min(vehicle_count, 5))
        ]
        vehicles_html = "".join([
            f'''<div class="vehicle-item">
                <span class="v-id">{v["id"]}</span>
                <span class="v-rel">{v["relation"]}</span>
                <span class="v-dist">{v["distance"]}m</span>
                <span class="v-speed">{v["speed"]}m/s</span>
                <span class="v-risk {'risk-'+v['risk']}">{v["risk"]}</span>
            </div>'''
            for v in nearby_vehicles
        ]) or '<div class="vehicle-item">无周围车辆</div>'
        
        # 生成知识图谱节点
        nodes = [
            {"id": "ego", "label": "自车", "type": "ego", "x": 250, "y": 200},
            {"id": "scenario", "label": scenario_name, "type": "scenario", "x": 450, "y": 120},
            {"id": "risk", "label": risk_level, "type": "risk", "x": 450, "y": 200},
            {"id": "speed", "label": f"{ego_speed:.1f}m/s", "type": "attr", "x": 80, "y": 120},
            {"id": "position", "label": f"({ego_x:.1f},{ego_y:.1f})", "type": "attr", "x": 80, "y": 200},
            {"id": "vehicles", "label": f"{vehicle_count}辆车", "type": "attr", "x": 80, "y": 280},
        ]
        
        edges = [
            {"from": "ego", "to": "scenario", "label": "触发"},
            {"from": "ego", "to": "risk", "label": "风险等级"},
            {"from": "ego", "to": "speed", "label": "速度"},
            {"from": "ego", "to": "position", "label": "位置"},
            {"from": "ego", "to": "vehicles", "label": "感知"},
        ]
        
        nodes_html = ""
        for n in nodes:
            node_color = {
                "ego": "#667eea",
                "scenario": "#f39c12",
                "risk": risk_color,
                "attr": "#52c41a"
            }.get(n["type"], "#999")
            nodes_html += f'''
            <div class="kg-node node-{n["type"]}" 
                 style="left:{n["x"]}px;top:{n["y"]}px;background:{node_color};">
                <div class="node-label">{n["label"]}</div>
            </div>'''
        
        edges_html = ""
        for e in edges:
            edges_html += f'''
            <div class="kg-edge" data-from="{e["from"]}" data-to="{e["to"]}">
                <span class="edge-label">{e["label"]}</span>
            </div>'''
        
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
            padding: 20px;
        }}
        h1 {{
            text-align: center;
            font-size: 1.8em;
            margin-bottom: 5px;
            color: #667eea;
            text-shadow: 0 0 20px rgba(102,126,234,0.5);
        }}
        .timestamp {{
            text-align: center;
            color: #888;
            font-size: 0.9em;
            margin-bottom: 20px;
        }}
        
        /* 三列布局 */
        .container {{
            display: grid;
            grid-template-columns: 1fr 2fr 1fr;
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        /* 通用卡片 */
        .card {{
            background: rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 15px;
        }}
        .card h2 {{
            font-size: 1em;
            color: #667eea;
            margin-bottom: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 8px;
        }}
        
        /* 知识图谱区域 */
        .kg-container {{
            background: rgba(0,0,0,0.3);
            border-radius: 12px;
            padding: 20px;
            position: relative;
            min-height: 350px;
        }}
        .kg-canvas {{
            position: relative;
            width: 100%;
            height: 350px;
        }}
        .kg-node {{
            position: absolute;
            padding: 10px 15px;
            border-radius: 20px;
            color: white;
            font-weight: bold;
            transform: translate(-50%, -50%);
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            transition: all 0.3s;
            cursor: pointer;
            z-index: 10;
        }}
        .kg-node:hover {{
            transform: translate(-50%, -50%) scale(1.1);
            box-shadow: 0 6px 25px rgba(0,0,0,0.5);
        }}
        .node-ego {{
            width: 80px;
            height: 80px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.9em;
            box-shadow: {risk_glow};
        }}
        .node-scenario {{
            border: 2px solid {risk_color};
        }}
        .node-risk {{
            font-size: 0.9em;
        }}
        .node-attr {{
            font-size: 0.8em;
            padding: 8px 12px;
            background: rgba(82,196,26,0.3);
        }}
        .kg-edge {{
            position: absolute;
            background: rgba(255,255,255,0.2);
            height: 2px;
            transform-origin: left center;
            z-index: 5;
        }}
        .edge-label {{
            position: absolute;
            right: -40px;
            top: -8px;
            font-size: 0.7em;
            color: #888;
            background: rgba(0,0,0,0.5);
            padding: 2px 5px;
            border-radius: 3px;
        }}
        
        /* 自车状态 */
        .ego-status {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }}
        .status-item {{
            background: rgba(0,0,0,0.2);
            padding: 12px;
            border-radius: 8px;
            text-align: center;
        }}
        .status-label {{
            font-size: 0.75em;
            color: #888;
            margin-bottom: 5px;
        }}
        .status-value {{
            font-size: 1.2em;
            font-weight: bold;
            color: #667eea;
        }}
        .status-value.speed {{
            color: #52c41a;
        }}
        .status-value.warning {{
            color: #faad14;
        }}
        .status-value.danger {{
            color: #ff4d4f;
        }}
        
        /* 风险指标 */
        .risk-display {{
            text-align: center;
            padding: 20px;
        }}
        .risk-circle {{
            width: 100px;
            height: 100px;
            border-radius: 50%;
            background: conic-gradient({risk_color} {risk_index*360}deg, rgba(255,255,255,0.1) 0deg);
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 15px;
            box-shadow: {risk_glow};
        }}
        .risk-inner {{
            width: 80px;
            height: 80px;
            border-radius: 50%;
            background: rgba(0,0,0,0.5);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        .risk-value {{
            font-size: 1.5em;
            font-weight: bold;
            color: white;
        }}
        .risk-level {{
            font-size: 0.8em;
            color: {risk_color};
        }}
        
        /* 周围车辆 */
        .vehicle-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px;
            margin: 5px 0;
            background: rgba(0,0,0,0.2);
            border-radius: 6px;
            font-size: 0.9em;
        }}
        .v-id {{ color: #667eea; font-weight: bold; }}
        .v-rel {{ color: #888; }}
        .v-dist {{ color: #52c41a; }}
        .v-speed {{ color: #f39c12; }}
        .v-risk {{ padding: 2px 8px; border-radius: 10px; font-size: 0.8em; }}
        .risk-安全 {{ background: rgba(82,196,26,0.3); color: #52c41a; }}
        .risk-注意 {{ background: rgba(250,173,20,0.3); color: #faad14; }}
        .risk-危险 {{ background: rgba(255,77,79,0.3); color: #ff4d4f; }}
        
        /* 违规行为 */
        .v-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px;
            margin: 5px 0;
            background: rgba(0,0,0,0.2);
            border-radius: 6px;
        }}
        .v-badge {{
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.8em;
            color: white;
        }}
        .v-code {{
            color: #667eea;
            font-family: monospace;
        }}
        .v-msg {{
            color: #e0e0e0;
        }}
        
        /* 关系图例 */
        .legend {{
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 15px;
            font-size: 0.8em;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 5px;
        }}
        .legend-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }}
        
        /* 响应式 */
        @media (max-width: 1000px) {{
            .container {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <h1>🚗 事件知识图谱 #{scenario_id}</h1>
    <p class="timestamp">检测时间: {html.escape(timestamp)}</p>
    
    <div class="container">
        <!-- 左侧：自车状态 -->
        <div class="left-panel">
            <div class="card">
                <h2>🚘 自车状态</h2>
                <div class="ego-status">
                    <div class="status-item">
                        <div class="status-label">速度</div>
                        <div class="status-value {'speed' if ego_speed < 20 else 'warning' if ego_speed < 30 else 'danger'}">{ego_speed:.1f} m/s</div>
                    </div>
                    <div class="status-item">
                        <div class="status-label">风险指数</div>
                        <div class="status-value {'danger' if risk_index > 0.7 else 'warning' if risk_index > 0.4 else ''}">{risk_index:.3f}</div>
                    </div>
                    <div class="status-item">
                        <div class="status-label">X坐标</div>
                        <div class="status-value">{ego_x:.2f}</div>
                    </div>
                    <div class="status-item">
                        <div class="status-label">Y坐标</div>
                        <div class="status-value">{ego_y:.2f}</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>📊 周围环境</h2>
                <div class="vehicle-item">
                    <span class="v-id">车辆总数</span>
                    <span class="v-dist">{vehicle_count} 辆</span>
                </div>
                {vehicles_html}
            </div>
        </div>
        
        <!-- 中间：知识图谱可视化 -->
        <div class="center-panel">
            <div class="kg-container">
                <h2 style="text-align:center;margin-bottom:15px;color:#667eea;">🕸️ 知识图谱</h2>
                <div class="kg-canvas">
                    {nodes_html}
                    {edges_html}
                </div>
                <div class="legend">
                    <div class="legend-item"><div class="legend-dot" style="background:#667eea"></div>自车</div>
                    <div class="legend-item"><div class="legend-dot" style="background:#f39c12"></div>场景</div>
                    <div class="legend-item"><div class="legend-dot" style="background:{risk_color}"></div>风险</div>
                    <div class="legend-item"><div class="legend-dot" style="background:#52c41a"></div>属性</div>
                </div>
            </div>
        </div>
        
        <!-- 右侧：风险与违规 -->
        <div class="right-panel">
            <div class="card">
                <h2>⚠️ 风险评估</h2>
                <div class="risk-display">
                    <div class="risk-circle">
                        <div class="risk-inner">
                            <div class="risk-value">{risk_index:.1f}</div>
                            <div class="risk-level">{html.escape(risk_level)}</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>🚫 违规行为</h2>
                {violation_html}
            </div>
            
            <div class="card">
                <h2>📋 场景分析</h2>
                <p style="color:#888;font-size:0.9em;">
                    当前场景 <strong style="color:#f39c12">{html.escape(scenario_name)}</strong>，
                    自车以 <strong style="color:#52c41a">{ego_speed:.1f}m/s</strong> 的速度行驶，
                    周围检测到 <strong>{vehicle_count}</strong> 个交通参与者。
                    {'建议立即采取避险措施。' if risk_level == 'CRITICAL' else '建议保持警惕，注意观察。'}
                </p>
            </div>
        </div>
    </div>
    
    <script>
        // 简单的节点连接线
        document.querySelectorAll('.kg-edge').forEach(edge => {{
            const from = document.querySelector('.kg-node.node-' + edge.dataset.from);
            const to = document.querySelector('.kg-node.node-' + edge.dataset.to);
            if (from && to) {{
                const fromRect = from.getBoundingClientRect();
                const toRect = to.getBoundingClientRect();
                const canvas = document.querySelector('.kg-canvas');
                const canvasRect = canvas.getBoundingClientRect();
                
                const x1 = fromRect.left + fromRect.width/2 - canvasRect.left;
                const y1 = fromRect.top + fromRect.height/2 - canvasRect.top;
                const x2 = toRect.left + toRect.width/2 - canvasRect.left;
                const y2 = toRect.top + toRect.height/2 - canvasRect.top;
                
                const length = Math.sqrt((x2-x1)**2 + (y2-y1)**2);
                const angle = Math.atan2(y2-y1, x2-x1) * 180 / Math.PI;
                
                edge.style.width = length + 'px';
                edge.style.left = x1 + 'px';
                edge.style.top = y1 + 'px';
                edge.style.transform = `rotate(${{angle}}deg)`;
            }}
        }});
    </script>
</body>
</html>"""
