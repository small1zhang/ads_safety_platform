#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
realtime_multi_anomaly_demo.py - 多异常实时检测演示

功能：
1. 收集CARLA数据或注入异常场景
2. 生成完整的异常可视化页面
3. 同步更新visualization_demo.html
4. 创建点击跳转到异常详情页
5. 异步绘制知识图谱

用法：
    python realtime_multi_anomaly_demo.py --duration 60 --step 5
    python realtime_multi_anomaly_demo.py --carla --host 127.0.0.1 --port 2000
"""

import sys
import json
import math
import asyncio
import argparse
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent))

from realtime_carla_collector import (
    RealTimeCollector, 
    AnomalyResult, 
    CollectedData
)
from svg_knowledge_graph import generate_svg_knowledge_graph, create_kg_data_from_anomalies


class MultiAnomalyRenderer:
    """多异常可视化渲染器"""
    
    def __init__(self, output_path: str = "visualization_demo.html"):
        self.output_path = Path(output_path)
    
    async def generate_dashboard_async(self, data: CollectedData, output_path: Optional[str] = None) -> str:
        """生成包含所有异常的Dashboard页面"""
        out_path = Path(output_path) if output_path else self.output_path
        
        # 生成每个异常的详情页
        detail_pages = []
        for i, anomaly in enumerate(data.anomalies):
            detail_path = out_path.parent / f"anomaly_{i+1:03d}_{anomaly.timestamp.replace(':', '-')[:14]}.html"
            self._generate_detail_page(anomaly, str(detail_path))
            detail_pages.append({
                'id': i,
                'title': anomaly.scenario_name,
                'risk': anomaly.risk_level,
                'risk_index': anomaly.risk_index,
                'path': detail_path.name,
                'timestamp': anomaly.timestamp
            })
        
        # 生成知识图谱（使用SVG版本）
        kg_path = out_path.parent / f"knowledge_graph_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        # 转换异常数据为字典列表
        anomalies_data = []
        for anomaly in data.anomalies:
            anomalies_data.append({
                'scenario_id': anomaly.scenario_id,
                'scenario_name': anomaly.scenario_name,
                'timestamp': anomaly.timestamp,
                'ego_x': anomaly.ego_x,
                'ego_y': anomaly.ego_y,
                'ego_speed': anomaly.ego_speed,
                'vehicle_count': anomaly.vehicle_count,
                'violations': [
                    {
                        'code': v.get('code', 'N/A'),
                        'rule': v.get('rule', 'N/A'),
                        'message': v.get('message', ''),
                        'level': v.get('level', 'medium')
                    }
                    for v in anomaly.violations
                ],
                'risk_index': anomaly.risk_index,
                'risk_level': anomaly.risk_level,
                'scenario_type': anomaly.scenario_type,
                'duration_ms': anomaly.duration_ms
            })
        
        # 创建SVG知识图谱数据
        kg_data = create_kg_data_from_anomalies(anomalies_data)
        
        # 生成SVG HTML
        generate_svg_knowledge_graph(kg_data, str(kg_path))
        
        # 生成Dashboard
        html = self._generate_dashboard_html(data, detail_pages, str(kg_path))
        
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return str(out_path)
    
    def generate_dashboard(self, data: CollectedData, output_path: Optional[str] = None) -> str:
        """同步生成Dashboard（在无事件循环时使用）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 已在事件循环中，使用新线程
                import threading
                result = {}
                def _run():
                    result['path'] = asyncio.run(
                        self.generate_dashboard_async(data, output_path)
                    )
                t = threading.Thread(target=_run)
                t.start()
                t.join()
                return result.get('path')
        except RuntimeError:
            pass
        return asyncio.run(self.generate_dashboard_async(data, output_path))
    
    def _generate_dashboard_html(self, data: CollectedData, detail_pages: list, kg_path: str) -> str:
        """生成Dashboard HTML"""
        anomalies_html = "".join([
            f'''
            <div class="anomaly-card" onclick="location.href='{page["path"]}'">
                <h3>异常 #{page["id"]+1}</h3>
                <p class="scenario-name">{page["title"]}</p>
                <div class="risk-badge {page["risk"].lower()}">{page["risk"]} ({page["risk_index"]:.2f})</div>
                <p class="timestamp">检测时间: {page["timestamp"]}</p>
            </div>
            '''
            for page in detail_pages[:10]  # 最多显示10个
        ])
        
        if len(detail_pages) > 10:
            anomalies_html += f'''
            <div class="more-anomalies">
                <p>显示前 10 个异常... 共 {len(detail_pages)} 个</p>
            </div>
            '''
        
        risk_dist = data.risk_distribution
        
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADS Safety Platform - 异常仪表盘</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            color: #e0e0e0;
            margin: 0;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            padding: 20px;
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .stats-bar {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-bottom: 30px;
        }}
        .stat-item {{
            background: rgba(255,255,255,0.1);
            padding: 15px 25px;
            border-radius: 10px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            font-size: 12px;
            color: #aaa;
        }}
        .anomalies-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .anomaly-card {{
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 20px;
            cursor: pointer;
            transition: all 0.3s;
            backdrop-filter: blur(10px);
        }}
        .anomaly-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            border-color: #667eea;
        }}
        .anomaly-card h3 {{
            margin: 0 0 10px 0;
            color: #fff;
        }}
        .scenario-name {{
            color: #667eea;
            font-size: 14px;
            margin: 5px 0;
        }}
        .risk-badge {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .risk-badge.critical {{ background: #e74c3c; }}
        .risk-badge.high {{ background: #e67e22; }}
        .risk-badge.medium {{ background: #f39c12; }}
        .risk-badge.low {{ background: #2ecc71; }}
        .timestamp {{
            color: #666;
            font-size: 12px;
        }}
        .nav-bar {{
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-bottom: 20px;
        }}
        .nav-btn {{
            padding: 10px 20px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: background 0.3s;
        }}
        .nav-btn:hover {{
            background: #764ba2;
        }}
        .more-anomalies {{
            text-align: center;
            grid-column: 1 / -1;
            padding: 20px;
            color: #666;
        }}
        .knowledge-graph-btn {{
            display: block;
            margin: 20px auto;
            padding: 10px 30px;
            background: #27ae60;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }}
        .knowledge-graph-btn:hover {{
            background: #2ecc71;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚗 ADS Safety Platform</h1>
        <h2>实时异常检测仪表盘</h2>
        <p>收集时间: {data.end_time[:10]} | 总时长: {data.total_duration:.1f}秒 | 场景数: {len(data.anomalies)}</p>
    </div>
    
    <div class="stats-bar">
        <div class="stat-item">
            <div class="stat-value">{len(data.anomalies)}</div>
            <div class="stat-label">总异常数</div>
        </div>
        <div class="stat-item">
            <div class="stat-value" style="color: #e74c3c;">{risk_dist.get('CRITICAL', 0)}</div>
            <div class="stat-label">危急</div>
        </div>
        <div class="stat-item">
            <div class="stat-value" style="color: #e67e22;">{risk_dist.get('HIGH', 0)}</div>
            <div class="stat-label">高危</div>
        </div>
        <div class="stat-item">
            <div class="stat-value" style="color: #f39c12;">{risk_dist.get('MEDIUM', 0)}</div>
            <div class="stat-label">中危</div>
        </div>
        <div class="stat-item">
            <div class="stat-value" style="color: #2ecc71;">{risk_dist.get('LOW', 0)}</div>
            <div class="stat-label">低危</div>
        </div>
    </div>
    
    <button class="knowledge-graph-btn" onclick="location.href='{Path(kg_path).name}'">
        📊 查看知识图谱
    </button>
    
    <div class="anomalies-grid" id="anomaliesGrid">
        {anomalies_html}
    </div>
    
    <script>
        // 支持返回
        history.pushState(null, null, location.href);
        window.addEventListener('popstate', function(event) {{
            window.location.reload();
        }});
    </script>
</body>
</html>'''
    
    def _generate_detail_page(self, anomaly: AnomalyResult, output_path: str):
        """生成单个异常详情页"""
        violations_html = "".join([
            f'''
            <div class="violation high">
                <strong>[{v["code"]}] {v["rule"]}</strong><br>
                {v["message"]}
            </div>
            '''
            for v in anomaly.violations if v.get('level') == 'high'
        ]) or "".join([
            f'''
            <div class="violation medium">
                <strong>[{v["code"]}] {v["rule"]}</strong><br>
                {v["message"]}
            </div>
            '''
            for v in anomaly.violations if v.get('level') == 'medium'
        ]) or "".join([
            f'''
            <div class="violation low">
                <strong>[{v["code"]}] {v["rule"]}</strong><br>
                {v["message"]}
            </div>
            '''
            for v in anomaly.violations
        ])
        
        violations_count = len(anomaly.violations)
        risk_class = anomaly.risk_level.lower()
        
        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>异常详情 #{anomaly.timestamp[:10]} - {anomaly.scenario_name}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            color: #e0e0e0;
            padding: 20px;
        }}
        .header {{
            background: rgba(0,0,0,0.3);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .risk-badge.{{
            padding: 10px 25px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 18px;
            display: inline-block;
        }}
        .risk-badge.critical {{ background: #e74c3c; }}
        .risk-badge.high {{ background: #e67e22; }}
        .risk-badge.medium {{ background: #f39c12; }}
        .risk-badge.low {{ background: #2ecc71; }}
        .violation {{
            background: rgba(255,255,255,0.05);
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            border-left: 4px solid #e74c3c;
        }}
        .violation.medium {{ border-left-color: #f39c12; }}
        .violation.low {{ border-left-color: #2ecc71; }}
        .back-btn {{
            display: inline-block;
            padding: 10px 20px;
            background: #667eea;
            color: white;
            border-radius: 5px;
            cursor: pointer;
            margin-top: 20px;
        }}
        .back-btn:hover {{ background: #764ba2; }}
        .info {{
            margin-top: 20px;
            padding: 15px;
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
        }}
        .info p {{ margin: 5px 0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 异常详情</h1>
        <h2>{anomaly.scenario_name}</h2>
        <span class="risk-badge {risk_class}">{anomaly.risk_level} ({anomaly.risk_index})</span>
    </div>
    
    <div class="info">
        <p><strong>时间戳:</strong> {anomaly.timestamp}</p>
        <p><strong>场景类型:</strong> {anomaly.scenario_type}</p>
        <p><strong>自车位置:</strong> ({anomaly.ego_x:.1f}, {anomaly.ego_y:.1f})m</p>
        <p><strong>自车速度:</strong> {anomaly.ego_speed:.1f} m/s</p>
        <p><strong>车辆数量:</strong> {anomaly.vehicle_count}</p>
        <p><strong>检测耗时:</strong> {anomaly.duration_ms:.2f}ms</p>
    </div>
    
    <h2>⚠️ 检测到的违规 ({violations_count} 个)</h2>
    {violations_html}
    
    <div style="margin-top: 30px;">
        <button class="back-btn" onclick="history.back()">← 返回仪表盘</button>
    </div>
</body>
</html>'''
        
        Path(output_path).write_text(html, encoding='utf-8')


async def main_async():
    """异步主函数"""
    parser = argparse.ArgumentParser(description="实时多异常检测演示")
    parser.add_argument('--duration', type=int, default=60, help='收集持续时间(秒)')
    parser.add_argument('--step', type=float, default=2.0, help='采样间隔(秒)')
    parser.add_argument('--carla', action='store_true', help='连接CARLA')
    parser.add_argument('--host', default='localhost', help='CARLA主机')
    parser.add_argument('--port', type=int, default=2000, help='CARLA端口')
    parser.add_argument('--output', default='visualization_demo.html', help='输出文件')
    parser.add_argument('--timeout', type=float, default=5.0, help='连接超时时间')
    parser.add_argument('--inject-anomalies', action='store_true', default=True, help='注入异常场景')
    parser.add_argument('--no-inject-anomalies', dest='inject_anomalies', action='store_false', help='不注入异常场景')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print(" ADS Safety Platform - 实时多异常检测".center(80))
    print("=" * 80)
    print()
    
    # 1. 创建收集器
    collector = RealTimeCollector(
        host=args.host,
        port=args.port,
        timeout=args.timeout if hasattr(args, 'timeout') else 5.0
    )
    
    # 2. 尝试连接CARLA
    if args.carla:
        connected = collector.connect()
        if connected:
            print(f"[SUCCESS] ✅ 已连接到CARLA服务器 {args.host}:{args.port}")
        else:
            print(f"[WARN] ⚠️ CARLA不可用，使用备用模式")
    
    # 3. 收集数据
    print(f"\n[INFO] 开始收集数据...")
    print(f"  持续时间: {args.duration}秒")
    print(f"  采样间隔: {args.step}秒")
    print(f"  注入异常: {args.inject_anomalies}")
    
    data = await collector.collect_async(
        duration_seconds=args.duration,
        interval=args.step,
        inject_anomalies=args.inject_anomalies
    )
    
    print(f"\n[SUCCESS] ✅ 收集完成!")
    print(f"  场景数: {len(data.anomalies)}")
    print(f"  持续时间: {data.total_duration:.2f}秒")
    print(f"  轨迹点: {len(data.vehicle_trajectories)}")
    
    # 4. 生成可视化
    print(f"\n[INFO] 生成可视化...")
    renderer = MultiAnomalyRenderer(args.output)
    
    # 生成Dashboard
    dashboard_path = renderer.generate_dashboard(data, args.output)
    print(f"  Dashboard: {dashboard_path}")
    
    # 5. 显示统计
    print(f"\n{'='*80}")
    print("检测结果统计:")
    print(f"{'='*80}")
    print(f"  总异常数: {len(data.anomalies)}")
    for level, count in sorted(data.risk_distribution.items()):
        print(f"  {level}: {count}")
    print(f"\n风险分布:")
    for level, count in data.risk_distribution.items():
        pct = count / max(1, len(data.anomalies)) * 100
        print(f"  {level}: {pct:.1f}% ({count})")
    print(f"{'='*80}")


def main():
    """同步入口点"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n[INFO] 收集中止")
    except Exception as e:
        print(f"\n[ERROR] 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()