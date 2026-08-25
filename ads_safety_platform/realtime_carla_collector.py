#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
realtime_carla_collector.py - 实时CARLA数据收集器

功能：
1. 实时从CARLA提取数据（支持断线重连）
2. 收集10分钟或直到停止
3. 注入异常场景进行测试
4. 异步并行绘制知识图谱
5. 生成完整的异常可视化页面
6. 支持点击跳转到异常详情页
"""

import sys
import json
import math
import asyncio
import argparse
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
import threading

sys.path.insert(0, str(Path(__file__).parent))

from scenarios.builders.carla_connector import (
    CARLAClient, ScenarioExtractor, CARLAFallback, 
    CarlaActorState
)
from scenarios.builders.scenario_validator import ScenarioValidator, ValidationResult
from scenarios.builders.visualization3d import Visualization3D


@dataclass
class AnomalyResult:
    """单个异常检测结果"""
    scenario_id: int
    scenario_name: str
    timestamp: str
    ego_x: float
    ego_y: float
    ego_speed: float
    vehicle_count: int
    violations: List[Dict[str, Any]]
    risk_index: float
    risk_level: str
    scenario_type: str
    duration_ms: float


@dataclass  
class CollectedData:
    """收集的完整数据"""
    start_time: str
    end_time: str
    total_duration: float
    num_scenarios: int
    anomalies: List[AnomalyResult] = field(default_factory=list)
    vehicle_trajectories: List[Dict] = field(default_factory=list)
    traffic_light_states: List[Dict] = field(default_factory=list)
    risk_distribution: Dict[str, int] = field(default_factory=dict)


class RealTimeCollector:
    """实时数据收集器"""
    
    def __init__(self, host: str = "localhost", port: int = 2000, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.client = None
        self.validator = ScenarioValidator()
        self.collected_data = CollectedData(
            start_time=datetime.now().isoformat(),
            end_time="",
            total_duration=0.0,
            num_scenarios=0
        )
        self.running = False
        self._lock = threading.Lock()
    
    def connect(self) -> bool:
        """连接CARLA"""
        try:
            self.client = CARLAClient(self.host, self.port, self.timeout)
            return self.client.is_connected()
        except Exception as e:
            print(f"[{'WARN'}] CARLA连接失败: {e}")
            return False
    
    def get_actors_info(self) -> Dict[str, Any]:
        """获取所有实体信息"""
        if not self.client or not self.client.is_connected():
            return {'vehicles': [], 'traffic_lights': [], 'pedestrians': []}
        
        try:
            vehicles = self.client.get_all_vehicles()
            lights = self.client.get_all_traffic_lights()
            pedestrians = self.client.get_all_pedestrians()
            
            return {
                'vehicles': [asdict(v) for v in vehicles],
                'traffic_lights': lights,
                'pedestrians': [asdict(p) for p in pedestrians]
            }
        except Exception as e:
            print(f"[{'ERROR'}] 获取实体信息失败: {e}")
            return {'vehicles': [], 'traffic_lights': [], 'pedestrians': []}
    
    def collect_scenario(self, scenario_id: int, inject_anomaly: bool = False) -> Optional[AnomalyResult]:
        """收集单个场景"""
        from scenarios.builders import ScenarioBuilder, ScenarioPresets
        
        try:
            if inject_anomaly:
                # 注入异常场景
                builder = ScenarioBuilder()
                anomaly_types = [
                    ('RED_LIGHT', builder.create_red_light_scenario),
                    ('MERGE_CONFLICT', builder.create_merge_scenario),
                    ('PEDESTRIAN', builder.create_pedestrian_crossing_scenario),
                    ('INTERSECTION', builder.create_intersection_scenario),
                ]
                scenario_type, creator = anomaly_types[scenario_id % len(anomaly_types)]
                
                # 根据场景类型传递正确的参数
                if scenario_type == 'RED_LIGHT':
                    scenario = creator(
                        ego_speed=15.0 + (scenario_id % 5),
                        distance_to_light=6.0
                    )
                elif scenario_type == 'MERGE_CONFLICT':
                    scenario = creator(
                        ego_speed=15.0 + (scenario_id % 5),
                        merge_distance=12.0
                    )
                elif scenario_type == 'PEDESTRIAN':
                    scenario = creator(
                        ego_speed=15.0 + (scenario_id % 5),
                        distance_to_crossing=5.0
                    )
                else:  # INTERSECTION
                    scenario = creator(
                        ego_speed=15.0 + (scenario_id % 5),
                        distance_to_intersection=8.0
                    )
            else:
                # 从CARLA提取
                if self.client and self.client.is_connected():
                    extractor = ScenarioExtractor(self.client)
                    scenario = extractor.extract_current_scene()
                else:
                    return None
            
            # 运行检测
            start_time = time.time()
            result = self.validator.validate(scenario)
            duration_ms = (time.time() - start_time) * 1000
            
            # 构建结果
            ego = scenario.ego_vehicle
            anomaly = AnomalyResult(
                scenario_id=scenario_id,
                scenario_name=scenario.name,
                timestamp=datetime.now().isoformat(),
                ego_x=ego.x,
                ego_y=ego.y,
                ego_speed=ego.speed,
                vehicle_count=len(scenario.vehicles),
                violations=[v.to_dict() for v in result.violations],
                risk_index=result.risk_index,
                risk_level=result.risk_level,
                scenario_type=scenario.scenario_type.value,
                duration_ms=duration_ms
            )
            
            return anomaly
            
        except Exception as e:
            print(f"[{'ERROR'}] 收集场景 {scenario_id} 失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def collect_trajectory(self) -> Optional[Dict[str, Any]]:
        """收集车辆轨迹点"""
        if not self.client or not self.client.is_connected():
            return None
        
        try:
            actors_info = self.get_actors_info()
            timestamp = datetime.now().isoformat()
            
            trajectory_point = {
                'timestamp': timestamp,
                'vehicles': [
                    {
                        'id': v.get('entity_id', v.get('actor_id', 0)),
                        'type': v.get('type', 'unknown'),
                        'x': v.get('x', 0),
                        'y': v.get('y', 0),
                        'speed': v.get('speed', 0),
                        'yaw': v.get('yaw', 0)
                    }
                    for v in actors_info.get('vehicles', [])
                ],
                'traffic_lights': [
                    {
                        'actor_id': t.get('actor_id', 0),
                        'state': t.get('state', 'Red'),
                        'x': t.get('x', 0),
                        'y': t.get('y', 0)
                    }
                    for t in actors_info.get('traffic_lights', [])
                ]
            }
            
            return trajectory_point
        except Exception as e:
            print(f"[{'ERROR'}] 收集轨迹失败: {e}")
            return None

    async def collect_async(self, duration_seconds: int, interval: float = 1.0, 
                           inject_anomalies: bool = True) -> CollectedData:
        """异步收集数据"""
        self.running = True
        start = datetime.now()
        scenario_id = 0
        
        print(f"[{'INFO'}] 开始收集数据，持续 {duration_seconds} 秒...")
        
        while (datetime.now() - start).total_seconds() < duration_seconds:
            if not self.running:
                break
            
            # 收集场景结果
            anomaly = self.collect_scenario(scenario_id, inject_anomalies)
            if anomaly:
                with self._lock:
                    self.collected_data.anomalies.append(anomaly)
                    self.collected_data.num_scenarios += 1
                    
                    # 更新风险分布
                    level = anomaly.risk_level
                    self.collected_data.risk_distribution[level] = \
                        self.collected_data.risk_distribution.get(level, 0) + 1
            
            # 收集轨迹
            trajectory = self.collect_trajectory()
            if trajectory:
                with self._lock:
                    self.collected_data.vehicle_trajectories.append(trajectory)
            
            scenario_id += 1
            await asyncio.sleep(interval)
        
        self.collected_data.end_time = datetime.now().isoformat()
        self.collected_data.total_duration = (
            datetime.now() - start
        ).total_seconds()
        
        self.running = False
        return self.collected_data
    
    def stop(self):
        """停止收集"""
        self.running = False


class KnowledgeGraphGenerator:
    """知识图谱生成器"""
    
    @staticmethod
    async def generate_knowledge_graph_async(data: CollectedData, output_path: str):
        """异步生成知识图谱HTML"""
        nodes = []
        links = []
        node_styles = {
            'ego': {'color': '#27ae60', 'shape': 'ellipse'},
            'vehicle': {'color': '#3498db', 'shape': 'box'},
            'traffic_light': {'color': '#f39c12', 'shape': 'diamond'},
            'violation': {'color': '#e74c3c', 'shape': 'ellipse'}
        }
        
        # 生成节点
        ego_node = {
            'id': 'ego',
            'label': 'Ego车辆',
            'type': 'ego',
            'x': data.anomalies[0].ego_x if data.anomalies else 0,
            'y': data.anomalies[0].ego_y if data.anomalies else 0,
            'color': node_styles['ego']['color'],
            'shape': node_styles['ego']['shape'],
            'attributes': {
                '速度': f"{data.anomalies[0].ego_speed if data.anomalies else 0:.1f} m/s",
                '类型': 'Tesla Model 3',
                '状态': 'OK'
            }
        }
        nodes.append(ego_node)
        
        # 为每个异常生成节点
        for i, anomaly in enumerate(data.anomalies):
            # 违规节点
            violation_node = {
                'id': f'violation_{i}',
                'label': f'{i+1}. {anomaly.violations[0]["code"] if anomaly.violations else "NO_VIOLATION"}\n{anomaly.risk_level}',
                'type': 'violation',
                'x': anomaly.ego_x + (i % 5) * 10,
                'y': anomaly.ego_y + (i // 5) * 10,
                'color': node_styles['violation']['color'],
                'shape': node_styles['violation']['shape'],
                'attributes': {
                    '风险指数': f"{anomaly.risk_index:.2f}",
                    '违规数': len(anomaly.violations),
                    '场景': anomaly.scenario_name,
                    '检测时间': anomaly.timestamp.split('T')[1][:8] if 'T' in anomaly.timestamp else anomaly.timestamp
                }
            }
            nodes.append(violation_node)
            
            # 连接ego到违规
            links.append({
                'source': 'ego',
                'target': f'violation_{i}',
                'type': 'detected',
                'label': '检测到'
            })
            
            # 为每个具体违规生成节点
            for j, v in enumerate(anomaly.violations):
                rule_node = {
                    'id': f'rule_{i}_{j}',
                    'label': f'{v["rule"]}\n{v["code"]}',
                    'type': 'violation',
                    'x': anomaly.ego_x + (i % 5) * 10 + j * 5,
                    'y': anomaly.ego_y + (i // 5) * 10 + j * 5,
                    'color': '#e74c3c' if v['level'] == 'high' else '#f39c12' if v['level'] == 'medium' else '#2ecc71',
                    'shape': 'ellipse',
                    'attributes': {
                        '等级': v['level'],
                        '消息': v['message'][:30] + '...' if len(v['message']) > 30 else v['message']
                    }
                }
                nodes.append(rule_node)
                
                links.append({
                    'source': f'violation_{i}',
                    'target': f'rule_{i}_{j}',
                    'type': 'contains',
                    'label': '包含'
                })
        
        # 生成HTML
        html = KnowledgeGraphGenerator._generate_html(nodes, links, data)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return output_path
    
    @staticmethod
    def _generate_html(nodes: list, links: list, data: CollectedData) -> str:
        """生成知识图谱HTML"""
        nodes_json = json.dumps(nodes, ensure_ascii=False)
        links_json = json.dumps(links, ensure_ascii=False)
        summary = json.dumps({
            'total_scenarios': len(data.anomalies),
            'risk_distribution': data.risk_distribution,
            'avg_duration_ms': sum(a.duration_ms for a in data.anomalies) / max(1, len(data.anomalies))
        }, ensure_ascii=False)
        
        # 使用字符串替换避免转义问题
        js_code = """
        const nodes = NODES;
        const links = LINKS;
        const summary = SUMMARY;
        
        // 渲染节点
        nodes.forEach(node => {
            const el = document.createElement('div');
            el.className = 'node';
            el.style.left = (node.x + 400) + 'px';
            el.style.top = (node.y + 300) + 'px';
            el.style.setProperty('--color', node.color);
            
            let attrsHtml = '';
            for (const [k, v] of Object.entries(node.attributes)) {
                attrsHtml += '<div>' + k + ': ' + v + '</div>';
            }
            
            el.innerHTML = '<div class="node-label">' + node.label + '</div>' +
                           '<div class="node-attrs">' + attrsHtml + '</div>';
            
            el.onclick = () => {
                alert('ID: ' + node.id + '\\n类型: ' + node.type + '\\n属性: ' + JSON.stringify(node.attributes, null, 2));
            };
            
            document.getElementById('graphContainer').appendChild(el);
        });
        
        // 渲染链接
        links.forEach(link => {
            const el = document.createElement('div');
            el.className = 'link';
            document.getElementById('graphContainer').appendChild(el);
        });
        """
        
        js_code = js_code.replace('NODES', nodes_json)
        js_code = js_code.replace('LINKS', links_json)
        js_code = js_code.replace('SUMMARY', summary)
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>ADS Safety Platform - 知识图谱</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', sans-serif;
            background: #1a1a2e;
            color: #e0e0e0;
            overflow: hidden;
        }}
        #graphContainer {{
            width: 100vw;
            height: 100vh;
            position: relative;
        }}
        .node {{
            position: absolute;
            background: var(--color);
            border: 2px solid #fff;
            border-radius: 10px;
            padding: 10px;
            font-size: 12px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
        }}
        .node:hover {{
            transform: scale(1.2);
            box-shadow: 0 0 20px #fff;
        }}
        .link {{
            position: absolute;
            background: #666;
            height: 2px;
            transform-origin: 0 0;
        }}
        .node-label {{
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .node-attrs {{
            font-size: 10px;
            color: #aaa;
        }}
        .summary-panel {{
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(0,0,0,0.8);
            padding: 15px;
            border-radius: 10px;
        }}
        .summary-item {{
            margin: 10px 0;
        }}
    </style>
</head>
<body>
    <div id="graphContainer"></div>
    <div class="summary-panel">
        <div class="summary-item"><strong>总场景数:</strong> {len(data.anomalies)}</div>
        <div class="summary-item"><strong>高危:</strong> {data.risk_distribution.get('CRITICAL', 0)}</div>
        <div class="summary-item"><strong>中危:</strong> {data.risk_distribution.get('HIGH', 0)}</div>
        <div class="summary-item"><strong>低危:</strong> {data.risk_distribution.get('LOW', 0)}</div>
    </div>
    <script>
{js_code}
    </script>
</body>
</html>"""
        
        return html