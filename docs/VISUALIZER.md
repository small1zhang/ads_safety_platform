# CARLA 可视化服务说明

## 概述

CARLA 可视化服务是一个**独立的模块**，不修改任何现有代码。

## 功能

- 🗺️ **鸟瞰图渲染**：使用 OpenCV 绘制车辆、行人、交通灯
- ⚠️ **风险叠加**：在画面上显示当前风险等级、场景名称、风险指数
- 🌐 **Web 界面**：通过浏览器实时查看 CARLA 可视化

## 启动方式

```bash
cd /home/aisecurity/01_ZHB/backend
source venv/bin/activate
python carla_visualizer_server.py 8001
```

## 访问地址

- 可视化页面：http://localhost:8001/carla-viewer
- 健康检查：http://localhost:8001/api/carla/health
- 图像流：http://localhost:8001/api/carla/view

## API 接口

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/api/carla/view` | 获取一帧可视化图像 |
| GET | `/api/carla/event` | 获取当前事件 |
| POST | `/api/carla/event/update` | 更新当前事件 |
| GET | `/api/carla/health` | 健康检查 |

## 与主服务的关系

可视化服务**完全独立**于主检测 API（端口 8000），可以同时运行：

```
┌──────────────────┐     ┌──────────────────┐
│   主检测服务      │     │  可视化服务        │
│   端口: 8000     │     │  端口: 8001       │
│                  │     │                  │
│ /api/detect/*    │     │ /carla-viewer    │
│ /api/health      │     │ /api/carla/*     │
└──────────────────┘     └──────────────────┘
```

## 当前运行状态

可视化服务当前已在后台运行：
- PID: 3108814
- 端口: 8001
- 模式: 模拟模式（因为服务器无可视化环境）
