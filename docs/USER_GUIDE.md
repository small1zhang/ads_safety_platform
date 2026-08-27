# 📖 ADS Safety Platform - 使用说明文档

> 本文档详细介绍 ADS Safety Platform 系统的安装、配置、使用方法和常见问题解决方案。

## 📑 目录
- [一、环境要求](#一环境要求)
- [二、安装部署](#二安装部署)
- [三、使用指南](#三使用指南)
- [四、API 接口文档](#四api-接口文档)
- [五、常见问题](#五常见问题)

---

## 一、环境要求

### 1.1 硬件要求
- **CPU**: 4核以上
- **内存**: 8GB 以上
- **GPU**: 推荐 NVIDIA 显卡（CARLA 仿真需要）
- **硬盘**: 20GB 可用空间

### 1.2 软件要求
- **操作系统**: Linux Ubuntu 20.04+ (推荐) / Windows 10+
- **Python**: 3.12+
- **CARLA**: 0.9.15
- **浏览器**: Chrome / Edge / Firefox 最新版

---

## 二、安装部署

### 2.1 启动 CARLA 仿真器

```bash
# 进入 CARLA 目录
cd ~/Carla0915

# 后台启动 CARLA（无渲染模式）
nohup ./CarlaUE4.sh -RenderOffScreen -carla-host=0.0.0.0 -carla-port=2000 > /tmp/carla.log 2>&1 &

# 验证 CARLA 启动成功
netstat -tlnp | grep 2000
```

### 2.2 启动后端服务

```bash
# 进入项目目录
cd /home/aisecurity/01_ZHB

# 激活 Python 虚拟环境
cd backend
source venv/bin/activate

# 安装依赖（如未安装）
pip install -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    fastapi uvicorn pydantic pydantic-settings websockets

# 启动后端服务
python -c "
import uvicorn
import sys
sys.path.insert(0, '.')
from app.main import app
uvicorn.run(app, host='0.0.0.0', port=8000, log_level='info')
"
```

成功启动后会看到：
```
INFO:     Started server process [xxxx]
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 2.3 访问仪表盘

打开浏览器访问：**http://localhost:8000/dashboard**

或通过网络访问：**http://服务器IP:8000/dashboard**

---

## 三、使用指南

### 3.1 仪表盘界面说明

```
┌─────────────────────────────────────────────────────────┐
│  🚗 ADS Safety Platform - 实时检测仪表盘                  │
├─────────────────────────────────────────────────────────┤
│  [CARLA: 在线] [WebSocket: 已连接] [事件ID: #5]         │
├─────────────────────────────────────────────────────────┤
│  [危急: 2] [高危: 3] [中危: 0] [低危: 0] [总数: 5]     │
├─────────────────────────────────────────────────────────┤
│  [▶ 10秒] [▶ 30秒] [▶ 60秒] [▶ 启动实时] [⏹ 停止] [📊全局]│
├─────────────────────────────────────────────────────────┤
│  📋 最近检测结果                                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐     │
│  │ 事件卡片      │ │ 事件卡片      │ │ 事件卡片      │     │
│  │ [查看图谱]    │ │ [查看图谱]    │ │ [查看图谱]    │     │
│  └──────────────┘ └──────────────┘ └──────────────┘     │
├─────────────────────────────────────────────────────────┤
│  📜 检测事件时间线                                        │
└─────────────────────────────────────────────────────────┘
```

### 3.2 启动检测

#### 方式一：页面按钮
1. 打开 `http://localhost:8000/dashboard`
2. 点击 **"▶ 启动实时检测"** 按钮
3. 等待提示 **"✅ 检测已启动"**
4. 按钮变为 **"✓ 检测运行中"**（绿色）

#### 方式二：API 调用

```bash
# 启动持续检测
curl -X POST http://localhost:8000/api/detect/start

# 启动 30 秒检测
curl -X POST http://localhost:8000/api/detect/run \
  -H "Content-Type: application/json" \
  -d '{"duration": 30, "interval": 1.0}'

# 启动 60 秒检测
curl -X POST http://localhost:8000/api/detect/run \
  -H "Content-Type: application/json" \
  -d '{"duration": 60, "interval": 1.0}'
```

### 3.3 停止检测

1. 在仪表盘上点击 **"⏹ 停止检测"** 按钮
2. 等待提示 **"⏹ 检测已停止"**
3. 按钮恢复为 **"▶ 启动实时检测"** 状态

或通过 API：
```bash
curl -X POST http://localhost:8000/api/detect/stop
```

### 3.4 查看知识图谱

#### 方式一：点击事件卡片
1. 在事件卡片上点击 **"📊 查看该事件图谱"** 按钮
2. 新窗口打开 Per-event 知识图谱
3. 图谱包含：自车状态、周围环境、违规行为、关系网络

#### 方式二：直接访问 URL
```
http://localhost:8000/output/kg_event_1.html
http://localhost:8000/output/kg_event_2.html
...
```

#### 方式三：查看全局图谱
```
http://localhost:8000/output/knowledge_graph.html
```

### 3.5 知识图谱说明

Per-event 知识图谱采用三列布局：

| 位置 | 内容 |
|------|------|
| **左栏** | 自车状态：速度、位置、风险指数；周围环境：车辆数、距离、风险等级 |
| **中栏** | 知识图谱可视化：自车节点、场景节点、风险节点、属性节点 + 关系连线 |
| **右栏** | 风险评估：圆形进度图；违规行为：列表展示；场景分析：建议文本 |

---

## 四、API 接口文档

### 4.1 健康检查
```bash
GET /api/health

# 响应
{
  "status": "healthy",
  "carla_connected": true/false,
  "timestamp": "2026-08-27T10:00:00.000000"
}
```

### 4.2 启动持续检测
```bash
POST /api/detect/start

# 响应
{
  "success": true,
  "message": "持续实时检测已启动",
  "status": "running"
}
```

### 4.3 停止检测
```bash
POST /api/detect/stop

# 响应
{
  "success": true,
  "message": "检测已停止"
}
```

### 4.4 定时检测
```bash
POST /api/detect/run
Content-Type: application/json

{
  "duration": 30,        # 检测时长（秒）
  "interval": 1.0,       # 采样间隔（秒）
  "inject_anomalies": true
}

# 响应
{
  "success": true,
  "message": "已启动30.0 秒的异常检测",
  "status": "running"
}
```

### 4.5 获取历史记录
```bash
GET /api/detect/history?limit=10

# 响应
{
  "history": [
    {
      "scenario_id": 1,
      "scenario_name": "前车急刹",
      "timestamp": "2026-08-27T10:00:00",
      "ego_x": 23.5,
      "ego_y": -12.3,
      "ego_speed": 25.6,
      "vehicle_count": 5,
      "violations": [...],
      "risk_index": 0.85,
      "risk_level": "CRITICAL",
      "kg_path": "/output/kg_event_1.html"
    }
  ],
  "stats": {
    "total": 10,
    "critical": 3,
    "high": 4,
    "medium": 2,
    "low": 1
  }
}
```

### 4.6 WebSocket 实时推送
```javascript
const ws = new WebSocket('ws://localhost:8000/api/ws/detection');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'anomaly') {
    console.log('异常事件:', data.data);
  }
};
```

---

## 五、常见问题

### Q1: 仪表盘显示"CARLA: 离线"
**原因**: CARLA UE4 服务未启动，或端口被占用
**解决**:
```bash
# 检查 CARLA 进程
ps aux | grep CarlaUE4

# 启动 CARLA
cd Carla0915
./CarlaUE4.sh -RenderOffScreen
```

### Q2: 检测启动后没有事件
**原因**: 检测器使用约 15% 概率产生事件，事件间隔较长
**解决**:
- 等待 30 秒以上
- 连续触发多个检测周期
- 或调整检测器的 `random.random() < 0.15` 阈值

### Q3: WebSocket 连接失败
**原因**: uvicorn 默认不支持 WebSocket
**解决**:
```bash
pip install websockets
# 重启后端
```

### Q4: 知识图谱无法打开
**原因**: 图谱文件未生成
**解决**:
- 确认已产生至少一个异常事件
- 检查 `/home/aisecurity/01_ZHB/output/kg_event_*.html` 文件

### Q5: CARLA Python API 连接 SegFault
**原因**: CARLA 版本与 Python API 版本不匹配
**解决**: 使用 TCP Socket 方式进行连接检查，系统会自动使用模拟数据

---

## 六、最佳实践

### 6.1 演示流程
1. 启动 CARLA
2. 启动后端
3. 打开仪表盘
4. 点击 "启动实时检测"
5. 等待 30-60 秒
6. 看到事件后点击 "查看图谱"
7. 展示完整的 Per-event 知识图谱

### 6.2 报告展示要点
- **技术架构图**：前后端分离 + CARLA 集成
- **核心功能**：实时检测 + 知识图谱 + Web可视化
- **运行效果**：3 列表格布局的知识图谱（自车、场景、风险）
- **项目亮点**：Per-event 图谱、WebSocket 推送、多模式检测

---

## 七、更新日志

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| v2.0.0 | 2026-08-27 | 完善知识图谱、添加 Toast 提示 |
| v1.0.0 | 2026-08-20 | 基础异常检测功能 |
