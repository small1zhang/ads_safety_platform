#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
svg_knowledge_graph.py - SVG传统知识图谱生成器

功能：
1. 生成SVG格式的传统知识图谱
2. 实体用圆形表示
3. 关系用线连接
4. 关系类型标注在线上
5. 支持点击交互
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


def generate_svg_knowledge_graph(data: Dict[str, Any], output_path: str):
    """生成SVG知识图谱"""
    
    nodes = data.get('nodes', [])
    links = data.get('links', [])
    
    # 计算SVG尺寸
    min_x = min(n.get('x', 0) for n in nodes) - 100
    max_x = max(n.get('x', 0) for n in nodes) + 100
    min_y = min(n.get('y', 0) for n in nodes) - 100
    max_y = max(n.get('y', 0) for n in nodes) + 100
    
    width = max_x - min_x
    height = max_y - min_y
    
    # 确保最小尺寸
    width = max(width, 800)
    height = max(height, 600)
    
    # 视图框
    viewbox = f"{min_x} {min_y} {width} {height}"
    
    # 生成SVG
    svg_parts = []
    
    # SVG头
    svg_parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" 
    viewBox="{viewbox}" 
    width="100%" height="100%" 
    style="background: #1a1a2e; font-family: 'Segoe UI', sans-serif;">
    
    <defs>
        <style>
            .node-circle {{
                stroke: #fff;
                stroke-width: 2;
                cursor: pointer;
                transition: all 0.3s;
            }}
            .node-circle:hover {{
                stroke-width: 3;
                filter: drop-shadow(0 0 10px #fff);
            }}
            .node-text {{
                fill: #fff;
                font-size: 12px;
                text-anchor: middle;
                pointer-events: none;
            }}
            .node-label {{
                font-weight: bold;
                font-size: 14px;
            }}
            .link-line {{
                stroke-linecap: round;
                marker-end: url(#arrowhead);
            }}
            .link-text {{
                fill: #fff;
                font-size: 10px;
                text-anchor: middle;
                pointer-events: none;
            }}
            .link-text-bg {{
                fill: rgba(0,0,0,0.7);
                rx: 3px;
                ry: 3px;
            }}
            .tooltip {{
                visibility: hidden;
            }}
        </style>
        
        <marker id="arrowhead" markerWidth="10" markerHeight="7" 
                refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#fff"/>
        </marker>
    </defs>
    
    <rect width="100%" height="100%" fill="#1a1a2e"/>''')
    
    # 绘制关系线（先画线，后画节点，这样节点会覆盖在线上）
    for link in links:
        source = next((n for n in nodes if n['id'] == link['source']), None)
        target = next((n for n in nodes if n['id'] == link['target']), None)
        
        if source and target:
            # 线的颜色
            link_color = get_link_color(link.get('type', 'unknown'))
            link_width = link.get('width', 2)
            
            # 计算线的中点（用于标签）
            mid_x = (source['x'] + target['x']) / 2
            mid_y = (source['y'] + target['y']) / 2
            
            # 绘制线
            svg_parts.append(f'''
            <line x1="{source['x']}" y1="{source['y']}" 
                  x2="{target['x']}" y2="{target['y']}" 
                  stroke="{link_color}" 
                  stroke-width="{link_width}" 
                  class="link-line" 
                  id="link_{link.get('source', '')}_{link.get('target', '')}"/>
            
            <!-- 关系标签 -->
            <text x="{mid_x}" y="{mid_y - 10}" 
                  class="link-text" 
                  fill="{link_color}">
                {link.get('type', 'related')}
            </text>''')
    
    # 绘制节点
    for node in nodes:
        radius = node.get('radius', 25)
        color = node.get('color', get_node_color(node.get('type', 'unknown')))
        
        # 绘制圆形
        svg_parts.append(f'''
        <circle cx="{node['x']}" cy="{node['y']}" r="{radius}" 
                fill="{color}" 
                class="node-circle" 
                id="node_{node['id']}" 
                onmouseover="showTooltip(evt, {json.dumps(node, ensure_ascii=False)})" 
                onmouseout="hideTooltip()"/>''')
        
        # 绘制标签
        label = node.get('label', node.get('id', ''))
        if label:
            # 处理多行标签
            lines = label.split('\n')
            for i, line in enumerate(lines):
                svg_parts.append(f'''
                <text x="{node['x']}" y="{node['y'] - radius - 20 + i * 15}" 
                      class="node-text node-label" 
                      fill="#fff">
                    {line}
                </text>''')
    
    # 添加图例
    svg_parts.append('''
    <g transform="translate(20, 20)">
        <rect x="0" y="0" width="200" height="120" 
              fill="rgba(0,0,0,0.7)" rx="5" ry="5"/>
        <text x="10" y="20" fill="#fff" font-size="14px" font-weight="bold">图例</text>
        <g transform="translate(10, 40)">
            <circle cx="10" cy="10" r="8" fill="#27ae60"/>
            <text x="25" y="14" fill="#fff" font-size="12px">Ego车辆</text>
        </g>
        <g transform="translate(10, 60)">
            <circle cx="10" cy="10" r="8" fill="#3498db"/>
            <text x="25" y="14" fill="#fff" font-size="12px">车辆</text>
        </g>
        <g transform="translate(10, 80)">
            <circle cx="10" cy="10" r="8" fill="#f39c12"/>
            <text x="25" y="14" fill="#fff" font-size="12px">交通灯</text>
        </g>
        <g transform="translate(10, 100)">
            <circle cx="10" cy="10" r="8" fill="#e74c3c"/>
            <text x="25" y="14" fill="#fff" font-size="12px">违规</text>
        </g>
    </g>''')
    
    # 添加统计信息
    svg_parts.append(f'''
    <g transform="translate({width - 220}, 20)">
        <rect x="0" y="0" width="200" height="80" 
              fill="rgba(0,0,0,0.7)" rx="5" ry="5"/>
        <text x="10" y="20" fill="#fff" font-size="14px" font-weight="bold">统计</text>
        <text x="10" y="40" fill="#667eea" font-size="12px">实体: {len(nodes)}</text>
        <text x="10" y="60" fill="#667eea" font-size="12px">关系: {len(links)}</text>
    </g>''')
    
    # 添加JavaScript交互
    svg_parts.append('''
    <script type="text/javascript">
        // 工具提示
        const tooltip = document.createElementNS("http://www.w3.org/2000/svg", "foreignObject");
        tooltip.setAttribute("width", "300");
        tooltip.setAttribute("height", "200");
        tooltip.setAttribute("x", "0");
        tooltip.setAttribute("y", "0");
        tooltip.style.visibility = "hidden";
        tooltip.style.background = "rgba(0,0,0,0.9)";
        tooltip.style.borderRadius = "5px";
        tooltip.style.color = "#e0e0e0";
        tooltip.style.padding = "10px";
        tooltip.style.fontSize = "12px";
        document.querySelector("svg").appendChild(tooltip);
        
        function showTooltip(evt, node) {
            const svg = document.querySelector("svg");
            const pt = svg.createSVGPoint();
            pt.x = evt.clientX;
            pt.y = evt.clientY;
            const svgP = pt.matrixTransform(svg.getScreenCTM().inverse());
            
            let html = `<div style="color: #667eea; font-weight: bold; margin-bottom: 5px;">${node.label || node.id}</div>`;
            html += `<div><strong>类型:</strong> ${node.type || 'unknown'}</div>`;
            
            if (node.attributes) {
                for (const [k, v] of Object.entries(node.attributes)) {
                    html += `<div><strong>${k}:</strong> ${v}</div>`;
                }
            }
            
            if (node.x !== undefined) {
                html += `<div><strong>坐标:</strong> (${node.x.toFixed(1)}, ${node.y.toFixed(1)})</div>`;
            }
            
            tooltip.innerHTML = html;
            tooltip.setAttribute("x", svgP.x + 10);
            tooltip.setAttribute("y", svgP.y + 10);
            tooltip.style.visibility = "visible";
        }
        
        function hideTooltip() {
            const tooltip = document.querySelector("foreignObject");
            if (tooltip) {
                tooltip.style.visibility = "hidden";
            }
        }
        
        // 点击节点高亮
        document.querySelectorAll(".node-circle").forEach(circle => {
            circle.addEventListener("click", function() {
                // 移除其他高亮
                document.querySelectorAll(".node-circle").forEach(c => {
                    c.setAttribute("stroke", "#fff");
                    c.setAttribute("stroke-width", "2");
                });
                document.querySelectorAll(".link-line").forEach(l => {
                    l.setAttribute("stroke-width", l.getAttribute("data-width") || "2");
                });
                
                // 高亮当前节点
                this.setAttribute("stroke", "#ffeb3b");
                this.setAttribute("stroke-width", "4");
                
                // 高亮相关连接
                const nodeId = this.id.replace("node_", "");
                document.querySelectorAll(".link-line").forEach(l => {
                    const linkId = l.id.replace("link_", "").split("_");
                    if (linkId[0] === nodeId || linkId[1] === nodeId) {
                        l.setAttribute("stroke", "#ffeb3b");
                        l.setAttribute("stroke-width", "4");
                    }
                });
            });
        });
        
        // 保存原始线宽
        document.querySelectorAll(".link-line").forEach(l => {
            l.setAttribute("data-width", l.getAttribute("stroke-width") || "2");
        });
    </script>''')
    
    # 关闭SVG
    svg_parts.append('\n</svg>')
    
    # 组合HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADS Safety Platform - 知识图谱</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            background: #1a1a2e;
            overflow: hidden;
            height: 100vh;
        }}
        svg {{
            display: block;
            width: 100%;
            height: 100%;
        }}
    </style>
</head>
<body>
{''.join(svg_parts)}
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
            'color': get_node_color('ego'),
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
                'label': f"{anomaly.get('scenario_name', '未知场景')}\\n{anomaly.get('risk_level', 'UNKNOWN')}",
                'type': 'scenario',
                'x': (i % 5) * 150 - 300,
                'y': (i // 5) * 150 - 200,
                'radius': 25,
                'color': get_node_color('scenario'),
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
                    'label': f"{violation.get('code', 'N/A')}\\n{violation.get('level', 'unknown')}",
                    'type': 'violation',
                    'x': (i % 5) * 150 - 300 + (j + 1) * 80,
                    'y': (i // 5) * 150 - 200 + 100,
                    'radius': 20,
                    'color': get_node_color('violation'),
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
    
    # 创建示例数据
    anomalies = []
    for i in range(5):
        anomaly = {
            'scenario_id': i,
            'scenario_name': ['红灯场景', '合流场景', '人行横道场景', '交叉口场景'][i % 4],
            'timestamp': datetime.now().isoformat(),
            'ego_x': 0,
            'ego_y': 0,
            'ego_speed': 15.0,
            'vehicle_count': 2,
            'violations': [
                {'code': f'RULE_{i}_1', 'rule': '速度超限', 'message': '车速超过限速', 'level': 'high'},
                {'code': f'RULE_{i}_2', 'rule': '距离过近', 'message': '与前车距离不足', 'level': 'medium'}
            ],
            'risk_index': 0.75,
            'risk_level': 'HIGH',
            'scenario_type': 'traffic_rule',
            'duration_ms': 100.0
        }
        anomalies.append(anomaly)
    
    # 创建知识图谱数据
    kg_data = create_kg_data_from_anomalies(anomalies)
    
    # 生成HTML
    output_path = 'knowledge_graph_svg.html'
    generate_svg_knowledge_graph(kg_data, output_path)
    print(f"[SUCCESS] SVG知识图谱已生成: {output_path}")