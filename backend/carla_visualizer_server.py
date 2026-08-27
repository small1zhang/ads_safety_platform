#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CARLA 可视化服务启动器
独立的可视化服务，不影响主API

使用方法:
    python carla_visualizer_server.py [port]
    
示例:
    python carla_visualizer_server.py 8001
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.carla_visualizer import run_visualizer_server, CarlaVisualizer


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    host = "0.0.0.0"
    
    print("=" * 60)
    print("   CARLA 可视化服务")
    print("=" * 60)
    print(f"  端口: {port}")
    print(f"  访问: http://localhost:{port}/carla-viewer")
    print(f"  API:  http://localhost:{port}/docs")
    print("=" * 60)
    print()
    print("提示: 可视化服务独立运行，不影响主API服务")
    print()
    
    run_visualizer_server(host=host, port=port)


if __name__ == "__main__":
    main()
