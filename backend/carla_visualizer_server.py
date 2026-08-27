#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CARLA 可视化服务启动器（支持两种渲染方式）

支持的渲染方式：
1. birdseye (OpenCV鸟瞰图) - 默认模式，可在任何环境运行
2. debug_draw (CARLA Debug Draw API) - 需要本地图形界面

使用示例:
    python carla_visualizer_server.py 8001
    python carla_visualizer_server.py 8001 --mode debug_draw
    python carla_visualizer_server.py 8001 --mode birdseye --no-debug-draw
"""

import sys
import os
import argparse

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.carla_visualizer import (
    run_visualizer_server,
    CarlaVisualizer,
    viz_app
)


def main():
    parser = argparse.ArgumentParser(description="CARLA 可视化服务")
    parser.add_argument("port", nargs="?", type=int, default=8001, help="服务端口 (默认8001)")
    parser.add_argument("--mode", choices=["birdseye", "debug_draw"], default="birdseye",
                       help="渲染模式: birdseye (OpenCV) 或 debug_draw (CARLA Debug Draw)")
    parser.add_argument("--no-debug-draw", action="store_true", help="不启动Debug Draw线程")
    args = parser.parse_args()
    
    port = args.port
    host = "0.0.0.0"
    
    print("=" * 60)
    print("   CARLA 可视化服务 v2.0")
    print("=" * 60)
    print(f"  端口: {port}")
    print(f"  模式: {args.mode}")
    print(f"  访问: http://localhost:{port}/carla-viewer")
    print(f"  API:  http://localhost:{port}/docs")
    print("=" * 60)
    print()
    
    # 创建可视化器
    global visualizer
    from app.core.carla_visualizer import visualizer
    
    # 连接CARLA
    if not visualizer.connect():
        print("⚠️ CARLA未连接 - 将使用模拟数据模式")
        print()
        print("提示:")
        print("  1. 如果服务器没有显示器，可以使用 birdseye 模式查看Web可视化")
        print("  2. 如果想看到CARLA Debug Draw效果，需要在本地启动CARLA客户端")
        print()
    else:
        print("✅ 已连接CARLA仿真环境")
        print(f"   - 找到 {len(visualizer.world.get_actors().filter('vehicle.*'))} 辆车")
        
        # 如果是debug_draw模式，启动Debug Draw线程
        if args.mode == "debug_draw" and not args.no_debug_draw:
            print("   - 启动 CARLA Debug Draw 线程...")
            visualizer.start_debug_draw()
            print("   - ✅ Debug Draw已启动（每帧更新风险信息）")
        elif args.mode == "debug_draw":
            print("   - 模式: birdseye + API调用")
    
    # 启动HTTP服务
    run_visualizer_server(host=host, port=port)


if __name__ == "__main__":
    main()
