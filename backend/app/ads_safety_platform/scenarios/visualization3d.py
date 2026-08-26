#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visualization3d.py - 3D 可视化模块

功能：
1. 创建3D视图的HTML模板
2. 使用CSS 3D变换实现离线3D效果
3. 支持车辆、路网、行人等实体可视化
4. 集成到现有可视化页面

用法：
    python scenarios/builders/visualization3d.py --input kg_output/verification_1.json --output viz_3d.html
"""

import json
import math
from pathlib import Path
from typing import Dict, Any, List, Optional

# 3D HTML 模板
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADS Safety Platform - 3D 可视化</title>
    {style_tag}
</head>
<body>
    {container_html}
    {control_panel_html}
    {info_panel_html}
    <script>
        let rotation = 0;
        let zoom = 1;
        
        function rotateView() {{
            const scene = document.getElementById('scene');
            rotation += 45;
            scene.style.transform = `translate(-50%, -50%) rotateX(30deg) rotateY(${{rotation}}deg)`;
        }}
        
        function zoomIn() {{
            zoom *= 0.9;
            document.getElementById('scene').style.transform = `translate(-50%, -50%) rotateX(30deg) scale(${{zoom}})`;
        }}
        
        function zoomOut() {{
            zoom *= 1.1;
            document.getElementById('scene').style.transform = `translate(-50%, -50%) rotateX(30deg) scale(${{zoom}})`;
        }}
        
        function showDetails() {{
            alert(`{data_json}`);
        }}
        
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'r') rotateView();
            if (e.key === '+') zoomIn();
            if (e.key === '-') zoomOut();
        }});
    </script>
</body>
</html>
'''


class Visualization3D:
    """3D 可视化生成器"""
    
    METERS_TO_PIXELS = 10  # 1米 = 10像素
    SCENE_WIDTH = 800
    SCENE_HEIGHT = 600
    SCENE_CENTER_X = SCENE_WIDTH // 2
    SCENE_CENTER_Y = SCENE_HEIGHT // 2
    
    @staticmethod
    def _pos_to_css(x: float, y: float) -> tuple:
        """转换坐标到CSS位置"""
        cx = x * Visualization3D.METERS_TO_PIXELS + Visualization3D.SCENE_CENTER_X
        cy = -y * Visualization3D.METERS_TO_PIXELS + Visualization3D.SCENE_CENTER_Y
        return f"{cx:.1f}px", f"{cy:.1f}px"
    
    @staticmethod
    def _generate_styles() -> str:
        """生成CSS样式"""
        return f'''
        <style>
            body {{
                margin: 0;
                padding: 0;
                overflow: hidden;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
                min-height: 100vh;
            }}
            
            .container {{
                width: 100vw;
                height: 100vh;
                position: relative;
                perspective: 1000px;
            }}
            
            .scene {{
                position: absolute;
                width: {Visualization3D.SCENE_WIDTH}px;
                height: {Visualization3D.SCENE_HEIGHT}px;
                left: 50%;
                top: 50%;
                transform: translate(-50%, -50%) rotateX(30deg);
                transform-style: preserve-3d;
                background: rgba(0, 0, 0, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 20px;
            }}
            
            .ground {{
                position: absolute;
                width: 1200px;
                height: 1200px;
                left: 50%;
                top: 50%;
                transform: translate(-50%, 0) rotateX(90deg);
                background: linear-gradient(135deg, #1a472a 0%, #2d5a3d 100%);
                border: 1px solid rgba(0, 255, 0, 0.3);
                border-radius: 10px;
                box-shadow: 0 0 50px rgba(0, 255, 0, 0.1);
            }}
            
            .ground::before {{
                content: "";
                position: absolute;
                width: 100%;
                height: 100%;
                background: radial-gradient(circle at 30% 30%, rgba(255,255,255,0.1) 0%, transparent 50%),
                            radial-gradient(circle at 70% 70%, rgba(255,255,255,0.05) 0%, transparent 50%);
            }}
            
            .vehicle {{
                position: absolute;
                transform-style: preserve-3d;
                transition: transform 0.3s ease, box-shadow 0.3s ease;
                cursor: pointer;
            }}
            
            .vehicle.ego {{
                width: 45px;
                height: 18px;
                background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);
                border: 2px solid #27ae60;
                border-radius: 8px;
                box-shadow: 0 0 30px rgba(39, 174, 96, 0.5);
            }}
            
            .vehicle.npc {{
                width: 40px;
                height: 18px;
                background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
                border: 2px solid #3498db;
                border-radius: 8px;
                box-shadow: 0 0 20px rgba(52, 152, 219, 0.3);
            }}
            
            .vehicle:hover {{
                box-shadow: 0 0 50px rgba(255, 255, 255, 0.8) !important;
                transform: scale(1.15);
            }}
            
            .vehicle::before {{
                content: attr(data-id);
                position: absolute;
                top: -25px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(0, 0, 0, 0.8);
                color: #fff;
                padding: 4px 12px;
                border-radius: 15px;
                font-size: 12px;
                font-weight: bold;
                white-space: nowrap;
                z-index: 10;
            }}
            
            .traffic-light {{
                position: absolute;
                width: 30px;
                height: 100px;
                background: #34495e;
                border-radius: 15px;
                box-shadow: 0 0 20px rgba(0, 0, 0, 0.5);
            }}
            
            .traffic-light .light {{
                position: absolute;
                width: 20px;
                height: 20px;
                border-radius: 50%;
                margin: 15px 0;
                transition: opacity 0.3s;
            }}
            
            .traffic-light .red {{ background: #e74c3c; box-shadow: 0 0 15px #e74c3c; }}
            .traffic-light .green {{ background: #2ecc71; box-shadow: 0 0 15px #2ecc71; }}
            .traffic-light .yellow {{ background: #f39c12; box-shadow: 0 0 15px #f39c12; }}
            
            .traffic-light.red .green, .traffic-light.red .yellow {{ opacity: 0.3; }}
            .traffic-light.green .red, .traffic-light.green .yellow {{ opacity: 0.3; }}
            .traffic-light.yellow .red, .traffic-light.yellow .green {{ opacity: 0.3; }}
            
            .risk-zone {{
                position: absolute;
                border: 3px dashed;
                border-radius: 50%;
                opacity: 0.4;
                animation: pulse 2s infinite;
            }}
            
            .risk-zone.high {{
                border-color: #e74c3c;
                background: radial-gradient(circle, rgba(231, 76, 60, 0.1) 0%, transparent 70%);
            }}
            
            .risk-zone.medium {{
                border-color: #f39c12;
                background: radial-gradient(circle, rgba(243, 156, 18, 0.1) 0%, transparent 70%);
            }}
            
            @keyframes pulse {{
                0%, 100% {{ opacity: 0.3; }}
                50% {{ opacity: 0.7; }}
            }}
            
            .axes {{
                position: absolute;
                width: 400px;
                height: 400px;
                left: 20px;
                bottom: 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                z-index: 5;
            }}
            
            .axis-x {{
                width: 350px;
                height: 3px;
                background: #e74c3c;
            }}
            
            .axis-x::before {{
                content: "X";
                position: absolute;
                right: -20px;
                top: -10px;
                color: #e74c3c;
                font-weight: bold;
            }}
            
            .axis-y {{
                position: absolute;
                width: 3px;
                height: 350px;
                background: #3498db;
                transform: rotate(90deg);
                top: -180px;
                left: 175px;
            }}
            
            .axis-y::before {{
                content: "Y";
                position: absolute;
                left: -20px;
                top: -10px;
                color: #3498db;
                font-weight: bold;
            }}
            
            .control-panel {{
                position: absolute;
                top: 20px;
                right: 20px;
                background: rgba(0, 0, 0, 0.7);
                padding: 15px;
                border-radius: 10px;
                backdrop-filter: blur(10px);
                z-index: 100;
            }}
            
            .btn {{
                display: block;
                width: 100%;
                padding: 10px;
                margin: 5px 0;
                background: #667eea;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 14px;
                transition: background 0.3s;
            }}
            
            .btn:hover {{
                background: #764ba2;
            }}
            
            .info-panel {{
                position: absolute;
                bottom: 20px;
                left: 20px;
                background: rgba(0, 0, 0, 0.7);
                padding: 15px;
                border-radius: 10px;
                backdrop-filter: blur(10px);
                max-width: 300px;
            }}
            
            .info-panel h3 {{
                margin: 0 0 10px 0;
                color: #667eea;
            }}
            
            .info-item {{
                margin: 8px 0;
                font-size: 13px;
            }}
            
            .info-label {{
                color: #a0a0a0;
            }}
            
            .info-value {{
                color: #fff;
                font-weight: bold;
            }}
            
            .risk-badge {{
                padding: 5px 15px;
                border-radius: 20px;
                font-weight: bold;
            }}
            
            .risk-badge.critical {{ background: #e74c3c; }}
            .risk-badge.high {{ background: #e67e22; }}
            .risk-badge.medium {{ background: #f39c12; }}
            .risk-badge.low {{ background: #2ecc71; }}
        </style>
        '''
    
    @staticmethod
    def _generate_vehicles_html(vehicles: list, ego: dict) -> str:
        """生成车辆HTML"""
        html_parts = []
        
        # ego车辆
        vx = ego.get('vx', 0)
        vy = ego.get('vy', 0)
        speed = math.sqrt(vx**2 + vy**2)
        yaw = math.atan2(vy, vx) if speed > 0 else 0
        
        cx, cy = Visualization3D._pos_to_css(ego['x'], ego['y'])
        html_parts.append(f'''
            <div class="vehicle ego" style="left: {cx}; top: {cy}; transform: rotate({math.degrees(yaw)}deg);"
                 data-id="🚗 Ego" title="自车 (ego)">
            </div>''')
        
        # NPC车辆
        for i, v in enumerate(vehicles[:15]):
            cx, cy = Visualization3D._pos_to_css(v['x'], v['y'])
            yaw = v.get('yaw', 0)
            
            html_parts.append(f'''
                <div class="vehicle npc" style="left: {cx}; top: {cy}; transform: rotate({math.degrees(yaw)}deg);"
                     data-id="车辆{i+1}" title="{v.get('type', '车辆')}">
                </div>''')
        
        return '\n'.join(html_parts)
    
    @staticmethod
    def _generate_traffic_lights_html(traffic_lights: list) -> str:
        """生成交通灯HTML"""
        html_parts = []
        
        for i, light in enumerate(traffic_lights[:10]):
            cx, cy = Visualization3D._pos_to_css(light['x'], light['y'])
            light_class = light.get('state', 'Red').lower()
            html_parts.append(f'''
                <div class="traffic-light" style="left: {cx}; top: {cy};">
                    <div class="light red" style="{'opacity: 1;' if light_class == 'red' else 'opacity: 0.3;'}"></div>
                    <div class="light green" style="{'opacity: 1;' if light_class == 'green' else 'opacity: 0.3;'}"></div>
                    <div class="light yellow" style="{'opacity: 1;' if light_class == 'yellow' else 'opacity: 0.3;'}"></div>
                </div>''')
        
        return '\n'.join(html_parts)
    
    @staticmethod
    def _generate_risk_zones_html(violations: list) -> str:
        """生成风险区域HTML"""
        html_parts = []
        
        # 为每个high-level违规生成一个风险区域
        for i, v in enumerate(violations[:5]):
            if v.get('level') == 'high':
                html_parts.append(f'''
                    <div class="risk-zone high" style="width: 80px; height: 80px; left: {Visualization3D.SCENE_CENTER_X}px; top: {Visualization3D.SCENE_CENTER_Y}px; border-radius: 50%;"></div>''')
        
        return '\n'.join(html_parts)
    
    @staticmethod
    def generate_html(data: dict, output_path: str) -> None:
        """生成3D可视化HTML"""
        scene = data.get('frame', {})
        ego = scene.get('ego', {})
        vehicles = scene.get('vehicles', [])
        traffic_lights = scene.get('traffic_lights', [])
        violations = data.get('violations', [])
        risk = data.get('risk', {})
        stats = data.get('stats', {})
        
        # 生成HTML片段
        vehicles_html = Visualization3D._generate_vehicles_html(vehicles, ego)
        lights_html = Visualization3D._generate_traffic_lights_html(traffic_lights)
        zones_html = Visualization3D._generate_risk_zones_html(violations)
        
        # 生成控制面板
        control_panel_html = f'''
            <div class="control-panel">
                <button class="btn" onclick="rotateView()">🔄 旋转视角</button>
                <button class="btn" onclick="zoomIn()">🔍 放大</button>
                <button class="btn" onclick="zoomOut()">🔎 缩小</button>
            </div>
        '''
        
        # 生成信息面板
        risk_badge_class = risk.get('risk_level', 'LOW').lower()
        risk_icon = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}.get(risk_badge_class, '🟢')
        
        info_panel_html = f'''
            <div class="info-panel">
                <h3>🚗 交通信息</h3>
                <div class="info-item">
                    <span class="info-label">风险指数:</span>
                    <span class="info-value"><span class="risk-badge {risk_badge_class}">{risk_icon} {risk.get("risk_index", 0.1):.2f}</span></span>
                </div>
                <div class="info-item">
                    <span class="info-label">自车位置:</span>
                    <span class="info-value">({ego.get("x", 0):.1f}m, {ego.get("y", 0):.1f}m)</span>
                </div>
                <div class="info-item">
                    <span class="info-label">自车速度:</span>
                    <span class="info-value">{ego.get("speed", 0):.1f} m/s</span>
                </div>
                <div class="info-item">
                    <span class="info-label">车辆数量:</span>
                    <span class="info-value">{len(vehicles)}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">交通灯:</span>
                    <span class="info-value">{len(traffic_lights)}</span>
                </div>
            </div>
        '''
        
        # 生成容器HTML
        container_html = f'''
            <div class="container">
                <div class="scene" id="scene">
                    <div class="ground"></div>
                    {vehicles_html}
                    {lights_html}
                    {zones_html}
                    <div class="axes"></div>
                </div>
                {control_panel_html}
                {info_panel_html}
            </div>
        '''
        
        # 组合完整HTML
        styles = Visualization3D._generate_styles()
        
        html = HTML_TEMPLATE.format(
            style_tag=styles,
            container_html=container_html,
            control_panel_html=control_panel_html,
            info_panel_html=info_panel_html,
            data_json=json.dumps(data, indent=2, ensure_ascii=False)
        )
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        print(f"✅ 3D 可视化生成: {output_path}")


if __name__ == "__main__":
    import argparse
    
    p = argparse.ArgumentParser(description="生成3D可视化")
    p.add_argument('--input', required=True, help='输入JSON文件')
    p.add_argument('--output', required=True, help='输出HTML文件')
    args = p.parse_args()
    
    with open(args.input) as f:
        data = json.load(f)
    
    Visualization3D.generate_html(data, args.output)