#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_knowledge_graph.py - 更新传统知识图谱

功能：
1. 从最新数据生成传统知识图谱
2. 实体用圆形表示
3. 关系用线连接
4. 关系类型标注在线上
5. 更新index.html链接
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from knowledge_graph_visualizer import generate_knowledge_graph_html, create_kg_data_from_anomalies


def load_latest_anomalies():
    """加载最新的异常数据"""
    # 尝试从live_test_results加载
    results_dir = Path(__file__).parent / 'live_test_results'
    json_files = sorted(results_dir.glob('live_test_*.json'))
    
    anomalies = []
    if json_files:
        latest = json_files[-1]
        data = json.loads(latest.read_text(encoding='utf-8'))
        if 'anomalies' in data:
            anomalies = data['anomalies']
        else:
            # 单个检测结果
            anomaly = {
                'scenario_id': data.get('frame', {}).get('id', 1),
                'scenario_name': data.get('metadata', {}).get('scenario_name', '未知场景'),
                'timestamp': data.get('frame', {}).get('timestamp', ''),
                'ego_x': data.get('frame', {}).get('ego', {}).get('x', 0),
                'ego_y': data.get('frame', {}).get('ego', {}).get('y', 0),
                'ego_speed': data.get('frame', {}).get('ego', {}).get('speed', 0),
                'vehicle_count': len(data.get('frame', {}).get('vehicles', [])),
                'violations': data.get('violations', []),
                'risk_index': data.get('risk', {}).get('risk_index', 0),
                'risk_level': data.get('risk', {}).get('risk_level', 'LOW'),
                'scenario_type': data.get('metadata', {}).get('scenario_type', 'unknown'),
                'duration_ms': data.get('stats', {}).get('avg_latency_ms', 0)
            }
            anomalies.append(anomaly)
    
    return anomalies


def generate_knowledge_graph(anomalies):
    """生成知识图谱"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = Path(__file__).parent / f'knowledge_graph_{timestamp}.html'
    
    # 创建知识图谱数据
    kg_data = create_kg_data_from_anomalies(anomalies)
    
    # 生成HTML
    generate_knowledge_graph_html(kg_data, str(output_path))
    
    return output_path


if __name__ == '__main__':
    anomalies = load_latest_anomalies()
    
    if not anomalies:
        print("[WARN] 没有找到异常数据，使用示例数据")
        # 使用示例数据
        anomalies = [
            {
                'scenario_id': 1,
                'scenario_name': '红灯场景',
                'timestamp': datetime.now().isoformat(),
                'ego_x': 0, 'ego_y': 0, 'ego_speed': 15.0,
                'vehicle_count': 2,
                'violations': [
                    {'code': 'RED_LIGHT_VIOLATION', 'rule': '红灯停', 'message': '车辆闯红灯', 'level': 'high'}
                ],
                'risk_index': 0.9, 'risk_level': 'CRITICAL',
                'scenario_type': 'traffic_rule', 'duration_ms': 100.0
            },
            {
                'scenario_id': 2,
                'scenario_name': '合流场景',
                'timestamp': datetime.now().isoformat(),
                'ego_x': 0, 'ego_y': 0, 'ego_speed': 12.0,
                'vehicle_count': 3,
                'violations': [
                    {'code': 'MERGE_CONFLICT', 'rule': '合流让行', 'message': '合流时未让行', 'level': 'medium'}
                ],
                'risk_index': 0.5, 'risk_level': 'MEDIUM',
                'scenario_type': 'merge', 'duration_ms': 100.0
            }
        ]
    
    output = generate_knowledge_graph(anomalies)
    print(f"[SUCCESS] 知识图谱已生成: {output}")