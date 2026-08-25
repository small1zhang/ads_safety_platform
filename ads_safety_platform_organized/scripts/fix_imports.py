#!/usr/bin/env python3
"""
fix_imports.py - 修复迁移后所有代码的导入路径

用法: python fix_imports.py [source_dir] [target_dir]
"""

import os
import re
from pathlib import Path


# 定义导入路径映射
IMPORT_MAPPINGS = [
    # kg_core -> ads_safety_platform.kg
    (r'from kg_core\.', 'from ads_safety_platform.kg.'),
    (r'import kg_core\.', 'import ads_safety_platform.kg.'),
    
    # 车辆相关模块
    (r'from car\.', 'from ads_safety_platform.car.'),
    (r'import car\.', 'import ads_safety_platform.car.'),
    
    # 场景验证模块
    (r'from scenarios\.builders\.', 'from ads_safety_platform.scenarios.'),
    (r'import scenarios\.builders\.', 'import ads_safety_platform.scenarios.'),
    
    # 当前目录下的本地模块
    (r'from realtime_carla_collector', 'from ads_safety_platform.realtime_carla_collector'),
    (r'from realtime_multi_anomaly_demo', 'from ads_safety_platform.realtime_multi_anomaly_demo'),
    (r'from svg_knowledge_graph', 'from ads_safety_platform.visualization.svg_knowledge_graph'),
    (r'from knowledge_graph_visualizer', 'from ads_safety_platform.visualization.knowledge_graph_visualizer'),
]


def fix_imports_in_file(file_path: Path):
    """修复单个文件的导入"""
    try:
        content = file_path.read_text(encoding='utf-8')
        original = content
        
        for pattern, replacement in IMPORT_MAPPINGS:
            content = re.sub(pattern, replacement, content)
        
        # 特定文件的额外修复
        if file_path.name == 'ads_safety_platform.py':
            content = content.replace(
                'from scenarios.builders.carla_connector import',
                'from ads_safety_platform.scenarios.carla_connector import'
            )
            content = content.replace(
                'from scenarios.builders.scenario_validator import',
                'from ads_safety_platform.scenarios.scenario_validator import'
            )
            content = content.replace(
                'from scenarios.builders.visualization3d import',
                'from ads_safety_platform.scenarios.visualization3d import'
            )
        
        if file_path.name == 'safety_judge.py':
            content = content.replace(
                'from scenic import scenic',
                '# from scenic import scenic  # 已启用'
            )
        
        if file_path.name == 'auto_drive_agent.py':
            content = content.replace(
                'import sys',
                'import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent.parent))'
            )
        
        if content != original:
            # 维护UTF-8 BOM
            if content.startswith('\ufeff'):
                content = content[1:]
            file_path.write_text(content, encoding='utf-8')
            print(f"[FIXED] {file_path.name}")
        
        return content != original
    
    except Exception as e:
        print(f"[ERROR] 修复 {file_path} 失败: {e}")
        return False


def update_project_imports(src_dir: str):
    """更新项目中所有Python文件的导入"""
    src_path = Path(src_dir)
    
    if not src_path.exists():
        print(f"[ERROR] 目录不存在: {src_dir}")
        return
    
    py_files = list(src_path.rglob("*.py"))
    print(f"[INFO] 找到 {len(py_files)} 个Python文件")
    
    fixed_count = 0
    for py_file in py_files:
        if py_file.name.startswith('__pycache__'):
            continue
        if fix_imports_in_file(py_file):
            fixed_count += 1
    
    print(f"[SUMMARY] 修复了 {fixed_count} 个文件的导入路径")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        src_dir = sys.argv[1]
    else:
        src_dir = 'ads_safety_platform_organized/src'
    
    update_project_imports(src_dir)