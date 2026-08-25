#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_demo_framework.py - 更新可视化演示框架

功能：
1. 保持visualization_demo.html框架不变
2. 更新知识图谱链接为新的SVG版本
3. 同步使用最新检测数据
"""

import json
import re
from pathlib import Path
from datetime import datetime


def update_knowledge_graph_link(html_path: str, new_kg_path: str) -> bool:
    """更新知识图谱链接"""
    html = Path(html_path)
    if not html.exists():
        print(f"[ERROR] 找不到文件: {html_path}")
        return False
    
    content = html.read_text(encoding='utf-8')
    
    # 更新知识图谱按钮链接
    pattern = r"location\.href='knowledge_graph_[^']+\.html'"
    replacement = f"location.href='{Path(new_kg_path).name}'"
    content = re.sub(pattern, replacement, content)
    
# 更新按钮中的文件名
    content = re.sub(
        r'onclick="[^"]*knowledge_graph[^"]*"',
        f'onclick="location.href=\'{Path(new_kg_path).name}\'"',
        content
    )
    
    # 保存
    html.write_text(content, encoding='utf-8')
    print(f"[SUCCESS] ✅ 已更新知识图谱链接: {new_kg_path}")
    return True


def update_demo_with_new_data(demo_path: str, anomalies_data: list) -> bool:
    """更新演示页面的数据"""
    demo = Path(demo_path)
    if not demo.exists():
        print(f"[ERROR] 找不到文件: {demo_path}")
        return False
    
    content = demo.read_text(encoding='utf-8')
    
    # 统计数据
    total = len(anomalies_data)
    critical = sum(1 for a in anomalies_data if a.get('risk_level') == 'CRITICAL')
    high = sum(1 for a in anomalies_data if a.get('risk_level') == 'HIGH')
    medium = sum(1 for a in anomalies_data if a.get('risk_level') == 'MEDIUM')
    low = total - critical - high - medium
    
    # 更新统计数据
    content = re.sub(
        r'<div class="stat-value">\d+</div>\s*<div class="stat-label">总异常数</div>',
        f'<div class="stat-value">{total}</div>\n            <div class="stat-label">总异常数</div>',
        content
    )
    content = re.sub(
        r'<div class="stat-value" style="color: #e74c3c;">\d+</div>\s*<div class="stat-label">危急</div>',
        f'<div class="stat-value" style="color: #e74c3c;">{critical}</div>\n            <div class="stat-label">危急</div>',
        content
    )
    content = re.sub(
        r'<div class="stat-value" style="color: #e67e22;">\d+</div>\s*<div class="stat-label">高危</div>',
        f'<div class="stat-value" style="color: #e67e22;">{high}</div>\n            <div class="stat-label">高危</div>',
        content
    )
    content = re.sub(
        r'<div class="stat-value" style="color: #f39c12;">\d+</div>\s*<div class="stat-label">中危</div>',
        f'<div class="stat-value" style="color: #f39c12;">{medium}</div>\n            <div class="stat-label">中危</div>',
        content
    )
    content = re.sub(
        r'<div class="stat-value" style="color: #2ecc71;">\d+</div>\s*<div class="stat-label">低危</div>',
        f'<div class="stat-value" style="color: #2ecc71;">{low}</div>\n            <div class="stat-label">低危</div>',
        content
    )
    
    demo.write_text(content, encoding='utf-8')
    print(f"[SUCCESS] ✅ 已更新统计数据")
    return True


if __name__ == '__main__':
    # 加载最新的知识图谱
    kg_files = sorted(Path('.').glob('knowledge_graph_svg.html'))
    if kg_files:
        latest_kg = kg_files[-1]
        print(f"发现最新知识图谱: {latest_kg}")
        
        # 更新visualization_demo.html
        update_knowledge_graph_link('visualization_demo.html', str(latest_kg))
        update_knowledge_graph_link('index.html', str(latest_kg))
    else:
        print("[WARN] 没有找到SVG知识图谱文件")