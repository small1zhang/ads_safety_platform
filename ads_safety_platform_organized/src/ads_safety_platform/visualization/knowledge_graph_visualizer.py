#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
knowledge_graph_visualizer.py - 传统知识图谱可视化生成器

功能：
1. 从异常数据生成传统知识图谱
2. 实体用圆形表示
3. 关系用线连接
4. 关系类型标注在线上
5. 支持点击交互
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


def generate_knowledge_graph_html(data: Dict[str, Any], output_path: str):
    """生成传统知识图谱HTML"""
    
    # 提取节点和关系
    nodes = data.get('nodes', [])
    links = data.get('links', [])
    
    # 为节点添加可视化属性
    for node in nodes:
        if 'color' not in node:
            node['color'] = get_node_color(node.get('type', 'unknown'))
        if 'radius' not in node:
            node['radius'] = 25
    
    # 为关系添加可视化属性
    for link in links:
        if 'color' not in link:
            link['color'] = get_link_color(link.get('type', 'unknown'))
        if 'width' not in link:
            link['width'] = 2
    
    # 生成HTML
    nodes_json = json.dumps(nodes, ensure_ascii=False)
    links_json = json.dumps(links, ensure_ascii=False)
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADS Safety Platform - 知识图谱</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1a1a2e;
            color: #e0e0e0;
            overflow: hidden;
            height: 100vh;
        }}
        
        #header {{
            position: absolute;
            top: 20px;
            left: 20px;
            right: 20px;
            z-index: 100;
            background: rgba(0,0,0,0.7);
            padding: 15px 20px;
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        #header h1 {{
            font-size: 20px;
            color: #667eea;
        }}
        
        #stats {{
            display: flex;
            gap: 20px;
        }}
        
        .stat-item {{
            background: rgba(255,255,255,0.1);
            padding: 8px 15px;
            border-radius: 5px;
            font-size: 12px;
        }}
        
        .stat-value {{
            font-weight: bold;
            color: #667eea;
        }}
        
        #graph-container {{
            width: 100%;
            height: 100%;
        }}
        
        #canvas {{
            width: 100%;
            height: 100%;
            display: block;
        }}
        
        .node-tooltip {{
            position: absolute;
            background: rgba(0,0,0,0.9);
            padding: 10px 15px;
            border-radius: 5px;
            font-size: 12px;
            pointer-events: none;
            z-index: 1000;
            display: none;
            max-width: 300px;
            border: 1px solid #667eea;
        }}
        
        .node-tooltip h4 {{
            color: #667eea;
            margin-bottom: 5px;
        }}
        
        .node-tooltip .attr {{
            color: #aaa;
            margin: 3px 0;
        }}
        
        .link-label {{
            position: absolute;
            background: rgba(0,0,0,0.7);
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 10px;
            color: #fff;
            pointer-events: none;
            z-index: 50;
            transform: translate(-50%, -50%);
        }}
        
        #controls {{
            position: absolute;
            bottom: 20px;
            left: 20px;
            z-index: 100;
            background: rgba(0,0,0,0.7);
            padding: 15px;
            border-radius: 10px;
        }}
        
        .control-btn {{
            background: #667eea;
            color: white;
            border: none;
            padding: 8px 15px;
            margin: 5px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 12px;
        }}
        
        .control-btn:hover {{
            background: #764ba2;
        }}
        
        .legend {{
            position: absolute;
            bottom: 20px;
            right: 20px;
            z-index: 100;
            background: rgba(0,0,0,0.7);
            padding: 15px;
            border-radius: 10px;
            font-size: 12px;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 8px 0;
        }}
        
        .legend-color {{
            width: 15px;
            height: 15px;
            border-radius: 50%;
            margin-right: 8px;
        }}
    </style>
</head>
<body>
    <div id="header">
        <h1>📊 ADS Safety Platform - 知识图谱</h1>
        <div id="stats">
            <div class="stat-item">
                <span class="stat-value">{len(nodes)}</span> 个实体
            </div>
            <div class="stat-item">
                <span class="stat-value">{len(links)}</span> 个关系
            </div>
        </div>
    </div>
    
    <div id="graph-container">
        <canvas id="canvas"></canvas>
    </div>
    
    <div class="node-tooltip" id="tooltip">
        <h4 id="tooltip-title"></h4>
        <div id="tooltip-attrs"></div>
    </div>
    
    <div id="controls">
        <button class="control-btn" onclick="resetView()">重置视图</button>
        <button class="control-btn" onclick="toggleLabels()">切换标签</button>
    </div>
    
    <div class="legend">
        <h4>图例</h4>
        <div class="legend-item">
            <div class="legend-color" style="background: #27ae60;"></div>
            <span>自车 (Ego)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #3498db;"></div>
            <span>车辆 (Vehicle)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #f39c12;"></div>
            <span>交通灯 (Traffic Light)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #e74c3c;"></div>
            <span>违规 (Violation)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #9b59b6;"></div>
            <span>场景 (Scenario)</span>
        </div>
    </div>
    
    <script>
        // 数据
        const nodes = {nodes_json};
        const links = {links_json};
        
        // 画布设置
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const tooltip = document.getElementById('tooltip');
        
        // 视图参数
        let offsetX = 0;
        let offsetY = 0;
        let scale = 1;
        let isDragging = false;
        let lastX, lastY;
        let showLabels = true;
        let hoveredNode = null;
        let hoveredLink = null;
        
        // 颜色映射
        const nodeColors = {{
            'ego': '#27ae60',
            'vehicle': '#3498db',
            'traffic_light': '#f39c12',
            'violation': '#e74c3c',
            'scenario': '#9b59b6',
            'pedestrian': '#1abc9c',
            'unknown': '#95a5a6'
        }};
        
        const linkColors = {{
            'detected': '#e74c3c',
            'contains': '#3498db',
            'causes': '#e67e22',
            'related': '#9b59b6',
            'unknown': '#7f8c8d'
        }};
        
        // 调整画布大小
        function resizeCanvas() {{
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            draw();
        }}
        
        // 将屏幕坐标转换为图形坐标
        function screenToGraph(x, y) {{
            return {{
                x: (x - canvas.width / 2 - offsetX) / scale,
                y: (y - canvas.height / 2 - offsetY) / scale
            }};
        }}
        
        // 将图形坐标转换为屏幕坐标
        function graphToScreen(x, y) {{
            return {{
                x: x * scale + canvas.width / 2 + offsetX,
                y: y * scale + canvas.height / 2 + offsetY
            }};
        }}
        
        // 绘制节点
        function drawNode(node) {{
            const pos = graphToScreen(node.x, node.y);
            const radius = node.radius * scale;
            
            // 绘制外发光效果
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, radius + 5, 0, Math.PI * 2);
            ctx.fillStyle = node.color + '40';
            ctx.fill();
            
            // 绘制节点圆形
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
            ctx.fillStyle = node.color;
            ctx.fill();
            
            // 绘制边框
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 2;
            ctx.stroke();
            
            // 绘制标签
            if (showLabels) {{
                ctx.fillStyle = '#fff';
                ctx.font = `${{12 * scale}}px Arial`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                
                const lines = node.label.split('\\n');
                lines.forEach((line, i) => {{
                    ctx.fillText(line, pos.x, pos.y - radius - 15 + i * 15);
                }});
            }}
            
            return pos;
        }}
        
        // 绘制关系线
        function drawLink(link) {{
            const source = nodes.find(n => n.id === link.source);
            const target = nodes.find(n => n.id === link.target);
            
            if (!source || !target) return null;
            
            const start = graphToScreen(source.x, source.y);
            const end = graphToScreen(target.x, target.y);
            
            // 绘制线
            ctx.beginPath();
            ctx.moveTo(start.x, start.y);
            ctx.lineTo(end.x, end.y);
            ctx.strokeStyle = link.color || linkColors[link.type] || '#7f8c8d';
            ctx.lineWidth = link.width * scale;
            ctx.stroke();
            
            // 计算标签位置（线的中点）
            const midX = (start.x + end.x) / 2;
            const midY = (start.y + end.y) / 2;
            
            return {{ x: midX, y: midY, link: link }};
        }}
        
        // 主绘制函数
        function draw() {{
            // 清空画布
            ctx.fillStyle = '#1a1a2e';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            // 绘制关系线
            const linkPositions = [];
            links.forEach(link => {{
                const pos = drawLink(link);
                if (pos) linkPositions.push(pos);
            }});
            
            // 绘制节点
            nodes.forEach(node => {{
                drawNode(node);
            }});
            
            // 绘制关系标签
            if (showLabels) {{
                linkPositions.forEach(pos => {{
                    ctx.fillStyle = '#fff';
                    ctx.font = `${{10 * scale}}px Arial`;
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(pos.link.type, pos.x, pos.y - 10);
                }});
            }}
        }}
        
        // 检测节点悬停
        function checkNodeHover(x, y) {{
            const graphPos = screenToGraph(x, y);
            
            for (const node of nodes) {{
                const dx = graphPos.x - node.x;
                const dy = graphPos.y - node.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance <= node.radius + 5) {{
                    return node;
                }}
            }}
            return null;
        }}
        
        // 检测关系悬停
        function checkLinkHover(x, y) {{
            const graphPos = screenToGraph(x, y);
            
            for (const link of links) {{
                const source = nodes.find(n => n.id === link.source);
                const target = nodes.find(n => n.id === link.target);
                
                if (!source || !target) continue;
                
                // 计算点到线段的距离
                const dx = target.x - source.x;
                const dy = target.y - source.y;
                const lineLength = Math.sqrt(dx * dx + dy * dy);
                
                if (lineLength === 0) continue;
                
                const t = ((graphPos.x - source.x) * dx + (graphPos.y - source.y) * dy) / (lineLength * lineLength);
                const closestX = source.x + t * dx;
                const closestY = source.y + t * dy;
                
                const distance = Math.sqrt(
                    Math.pow(graphPos.x - closestX, 2) + 
                    Math.pow(graphPos.y - closestY, 2)
                );
                
                if (distance <= 5 && t >= 0 && t <= 1) {{
                    return link;
                }}
            }}
            return null;
        }}
        
        // 显示工具提示
        function showTooltip(node, x, y) {{
            tooltip.style.display = 'block';
            tooltip.style.left = (x + 10) + 'px';
            tooltip.style.top = (y + 10) + 'px';
            
            document.getElementById('tooltip-title').textContent = node.label || node.id;
            
            let attrsHtml = '<div class="attr"><strong>ID:</strong> ' + node.id + '</div>';
            attrsHtml += '<div class="attr"><strong>类型:</strong> ' + (node.type || 'unknown') + '</div>';
            
            if (node.attributes) {{
                for (const [key, value] of Object.entries(node.attributes)) {{
                    attrsHtml += '<div class="attr"><strong>' + key + ':</strong> ' + value + '</div>';
                }}
            }}
            
            if (node.x !== undefined) {{
                attrsHtml += '<div class="attr"><strong>坐标:</strong> (' + node.x.toFixed(1) + ', ' + node.y.toFixed(1) + ')</div>';
            }}
            
            document.getElementById('tooltip-attrs').innerHTML = attrsHtml;
        }}
        
        // 隐藏工具提示
        function hideTooltip() {{
            tooltip.style.display = 'none';
        }}
        
        // 重置视图
        function resetView() {{
            offsetX = 0;
            offsetY = 0;
            scale = 1;
            draw();
        }}
        
        // 切换标签显示
        function toggleLabels() {{
            showLabels = !showLabels;
            draw();
        }}
        
        // 鼠标事件
        canvas.addEventListener('mousedown', (e) => {{
            isDragging = true;
            lastX = e.clientX;
            lastY = e.clientY;
        }});
        
        canvas.addEventListener('mousemove', (e) => {{
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            if (isDragging) {{
                offsetX += e.clientX - lastX;
                offsetY += e.clientY - lastY;
                lastX = e.clientX;
                lastY = e.clientY;
                draw();
            }}
            
            // 检测悬停
            const node = checkNodeHover(e.clientX, e.clientY);
            const link = checkLinkHover(e.clientX, e.clientY);
            
            if (node) {{
                hoveredNode = node;
                hoveredLink = null;
                showTooltip(node, e.clientX + 10, e.clientY + 10);
                canvas.style.cursor = 'pointer';
            }} else if (link) {{
                hoveredNode = null;
                hoveredLink = link;
                hideTooltip();
                canvas.style.cursor = 'pointer';
            }} else {{
                hoveredNode = null;
                hoveredLink = null;
                hideTooltip();
                canvas.style.cursor = 'grab';
            }}
        }});
        
        canvas.addEventListener('mouseup', () => {{
            isDragging = false;
            canvas.style.cursor = 'default';
        }});
        
        canvas.addEventListener('mouseleave', () => {{
            hideTooltip();
            canvas.style.cursor = 'default';
        }});
        
        // 鼠标滚轮缩放
        canvas.addEventListener('wheel', (e) => {{
            e.preventDefault();
            const delta = e.deltaY > 0 ? 0.9 : 1.1;
            scale *= delta;
            scale = Math.max(0.1, Math.min(3, scale));
            draw();
        }});
        
        // 双击重置
        canvas.addEventListener('dblclick', resetView);
        
        // 初始化
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();
        draw();
    </script>
</body>
</html>"""
    
    Path(output_path).write_text(html, encoding='utf-8')
    return output_path


def get_node_color(node_type: str) -> str:
    """获取节点颜色"""
    colors = {
        'ego': '#27ae60',
        'vehicle': '#3498db',
        'traffic_light': '#f39c12',
        'violation': '#e74c3c',
        'scenario': '#9b59b6',
        'pedestrian': '#1abc9c',
        'unknown': '#95a5a6'
    }
    return colors.get(node_type.lower(), '#95a5a6')


def get_link_color(link_type: str) -> str:
    """获取关系颜色"""
    colors = {
        'detected': '#e74c3c',
        'contains': '#3498db',
        'causes': '#e67e22',
        'related': '#9b59b6',
        'unknown': '#7f8c8d'
    }
    return colors.get(link_type.lower(), '#7f8c8d')


def create_kg_data_from_anomalies(anomalies: List[Dict]) -> Dict[str, Any]:
    """从异常数据创建知识图谱数据"""
    nodes = []
    links = []
    
    # 添加Ego车辆节点
    if anomalies:
        ego_node = {
            'id': 'ego',
            'label': 'Ego车辆',
            'type': 'ego',
            'x': 0,
            'y': 0,
            'radius': 30,
            'attributes': {
                '类型': '自动驾驶车辆',
                '状态': '运行中'
            }
        }
        nodes.append(ego_node)
        
        # 为每个异常创建节点
        for i, anomaly in enumerate(anomalies):
            scenario_node = {
                'id': f'scenario_{i}',
                'label': f'{anomaly.get("scenario_name", "未知场景")}\n{anomaly.get("risk_level", "UNKNOWN")}',
                'type': 'scenario',
                'x': (i % 5) * 150 - 300,
                'y': (i // 5) * 150 - 200,
                'radius': 25,
                'attributes': {
                    '风险指数': f"{anomaly.get('risk_index', 0):.2f}",
                    '违规数': len(anomaly.get('violations', [])),
                    '检测时间': anomaly.get('timestamp', '')[:19]
                }
            }
            nodes.append(scenario_node)
            
            # 连接Ego到场景
            links.append({
                'source': 'ego',
                'target': f'scenario_{i}',
                'type': 'detected',
                'color': get_link_color('detected'),
                'width': 2
            })
            
            # 为每个违规创建节点
            for j, violation in enumerate(anomaly.get('violations', [])):
                violation_node = {
                    'id': f'violation_{i}_{j}',
                    'label': f"{violation.get('code', 'N/A')}\n{violation.get('level', 'unknown')}",
                    'type': 'violation',
                    'x': (i % 5) * 150 - 300 + (j + 1) * 80,
                    'y': (i // 5) * 150 - 200 + 100,
                    'radius': 20,
                    'attributes': {
                        '规则': violation.get('rule', 'N/A'),
                        '消息': violation.get('message', '')[:50] + '...'
                    }
                }
                nodes.append(violation_node)
                
                # 连接场景到违规
                links.append({
                    'source': f'scenario_{i}',
                    'target': f'violation_{i}_{j}',
                    'type': 'contains',
                    'color': get_link_color('contains'),
                    'width': 1.5
                })
    
    return {'nodes': nodes, 'links': links}


if __name__ == '__main__':
    # 示例：从异常数据生成知识图谱
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    
    from ads_safety_platform.realtime_carla_collector import CollectedData, AnomalyResult
    from dataclasses import asdict
    
    # 创建示例数据
    anomalies = []
    for i in range(5):
        anomaly = AnomalyResult(
            scenario_id=i,
            scenario_name=['红灯场景', '合流场景', '人行横道场景', '交叉口场景'][i % 4],
            timestamp=datetime.now().isoformat(),
            ego_x=0,
            ego_y=0,
            ego_speed=15.0,
            vehicle_count=2,
            violations=[
                {'code': f'RULE_{i}_1', 'rule': '速度超限', 'message': '车速超过限速', 'level': 'high'},
                {'code': f'RULE_{i}_2', 'rule': '距离过近', 'message': '与前车距离不足', 'level': 'medium'}
            ],
            risk_index=0.75,
            risk_level='HIGH',
            scenario_type='traffic_rule',
            duration_ms=100.0
        )
        anomalies.append(asdict(anomaly))
    
    # 创建知识图谱数据
    kg_data = create_kg_data_from_anomalies(anomalies)
    
    # 生成HTML
    output_path = 'knowledge_graph_traditional.html'
    generate_knowledge_graph_html(kg_data, output_path)
    print(f"[SUCCESS] 知识图谱已生成: {output_path}")
