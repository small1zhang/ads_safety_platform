#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_index_with_real_data.py - 使用真实数据更新index.html

功能：
1. 从真实场景数据中提取信息
2. 更新index.html中的动画数据
3. 更新场景可视化元素
"""

import sys
import json
import math
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from scenarios.builders.carla_connector import CARLAFallback


def generate_real_scenario(seed: int = 42) -> dict:
    """生成真实场景数据"""
    scenario = CARLAFallback.generate_random_scenario(seed=seed)
    
    # 转换为可视化数据格式
    ego = scenario.ego_vehicle
    
    # 计算车辆信息
    vehicles = []
    for i, v in enumerate(scenario.vehicles):
        vehicles.append({
            'id': f'npc{i+1}',
            'x': int(((v.x + 50) / 100) * 80 + 10),  # 转换为百分比位置
            'y': int(((v.y + 50) / 100) * 100 + 150),  # 转换为像素位置
            'color': 'linear-gradient(135deg, #3498db 0%, #2980b9 100%)',
            'isEgo': False
        })
    
    # 确保ego车在最前面
    ego_vehicle = {
        'id': 'ego',
        'x': 50,
        'y': 180,
        'color': 'linear-gradient(135deg, #e74c3c 0%, #c0392b 100%)',
        'isEgo': True
    }
    
    all_vehicles = [ego_vehicle] + vehicles[:3]  # 限制为4辆车
    
    # 计算风险等级和指数
    risk_levels = ['LOW', 'MEDIUM', 'HIGH']
    risk_colors = ['low', 'medium', 'high']
    
    # 根据违规数量确定风险等级
    validator_module = __import__('scenarios.builders.scenario_validator', fromlist=['ScenarioValidator'])
    validator = validator_module.ScenarioValidator()
    result = validator.validate(scenario)
    
    if result.risk_index >= 0.8:
        risk_level = 'HIGH'
        risk_color = 'high'
        risk_value = 0.82
    elif result.risk_index >= 0.6:
        risk_level = 'MEDIUM'
        risk_color = 'medium'
        risk_value = 0.55
    else:
        risk_level = 'LOW'
        risk_color = 'low'
        risk_value = 0.25
    
    return {
        'vehicles': all_vehicles,
        'risk_level': risk_level,
        'risk_color': risk_color,
        'risk_value': risk_value,
        'scenario_name': scenario.name,
        'violations_count': len(result.violations),
        'timestamp': datetime.now().isoformat()
    }


def update_index_html(data: dict, index_path: str) -> str:
    """更新index.html使用真实数据"""
    index_file = Path(index_path)
    if not index_file.exists():
        print(f"[ERROR] 找不到文件: {index_path}")
        return None
    
    content = index_file.read_text(encoding='utf-8')
    
    # 1. 更新风险徽章
    content = content.replace(
        '<span class="risk-badge high" id="riskBadge">HIGH</span>',
        f'<span class="risk-badge {data["risk_color"]}" id="riskBadge">{data["risk_level"]}</span>'
    )
    
    # 2. 更新风险计
    content = content.replace(
        '<div class="risk-meter-fill high" id="riskMeter"></div>',
        f'<div class="risk-meter-fill {data["risk_color"]}" id="riskMeter"></div>'
    )
    
    # 3. 更新风险指数
    content = content.replace(
        '<span id="riskIndex">0.82</span>',
        f'<span id="riskIndex">{data["risk_value"]:.2f}</span>'
    )
    
    # 4. 更新车辆数据JavaScript部分
    vehicles_json = json.dumps(data['vehicles'], ensure_ascii=False)
    
    # 替换animateScene函数中的车辆数组
    import re
    pattern = r"const vehicles = \[\s*\{[^}]+\}(?:,\s*\{[^}]+\})*\];"
    replacement = f"const vehicles = {vehicles_json};"
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # 5. 更新风险等级数组
    risk_levels_json = json.dumps([data['risk_level']])
    risk_colors_json = json.dumps([data['risk_color']])
    risk_values_json = json.dumps([data['risk_value']])
    
    content = content.replace(
        "const riskLevels = ['LOW', 'MEDIUM', 'HIGH'];",
        f"const riskLevels = ['{data['risk_level']}'];"
    )
    content = content.replace(
        "const riskColors = ['low', 'medium', 'high'];",
        f"const riskColors = ['{data['risk_color']}'];"
    )
    content = content.replace(
        "const riskValues = [0.25, 0.55, 0.82];",
        f"const riskValues = [{data['risk_value']:.2f}];"
    )
    
    # 6. 保存更新
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = index_file.parent / f"index_backup_{timestamp}.html"
    backup_path.write_text(content, encoding='utf-8')
    
    index_file.write_text(content, encoding='utf-8')
    
    print(f"[SUCCESS] ✅ index.html已更新")
    print(f"[INFO] 备份: {backup_path}")
    
    return str(index_file)


def main():
    parser = argparse.ArgumentParser(description="使用真实数据更新index.html")
    parser.add_argument('--index-path', default='index.html', help='index.html路径')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print(" 使用真实数据更新index.html".center(70))
    print("=" * 70)
    print()
    
    # 生成真实场景数据
    print("[INFO] 生成真实场景数据...")
    data = generate_real_scenario(seed=args.seed)
    
    print(f"[SUCCESS] 场景: {data['scenario_name']}")
    print(f"[SUCCESS] 车辆数: {len(data['vehicles'])}")
    print(f"[SUCCESS] 风险等级: {data['risk_level']} ({data['risk_value']:.2f})")
    print(f"[SUCCESS] 违规数: {data['violations_count']}")
    
    # 更新index.html
    print(f"\n[INFO] 更新 {args.index_path}...")
    result = update_index_html(data, args.index_path)
    
    if result:
        print(f"\n[SUCCESS] ✅ 完成! 文件已更新: {result}")
    else:
        print(f"\n[ERROR] 更新失败")
        sys.exit(1)


if __name__ == "__main__":
    main()