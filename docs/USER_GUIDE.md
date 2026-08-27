# 📖 ADS Safety Platform - 使用说明文档

> 本文档详细介绍 ADS Safety Platform 系统的安装、配置、使用方法和常见问题解决方案。

## 📑 目录
- [一、环境要求](#一环境要求)
- [二、安装部署](#二安装部署)
- [三、使用指南](#三使用指南)
- [四、RSS规则详解](#四rss规则详解)
- [五、API 接口文档](#五api-接口文档)
- [六、常见问题](#六常见问题)

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

## 四、RSS规则详解

### 4.1 RSS 概述

**RSS (Responsibility-Sensitive Safety)** 是 Mobileye 于2017年提出的自动驾驶安全框架，
通过数学公式明确定义"安全驾驶"的行为边界。

**核心思想**：
- 定义明确的安全距离
- 判断"危险情形"而非仅"碰撞"
- 要求"Proper Response"（反应得当）
- 检测"Continuous Violation"（连续违规）

### 4.2 规则分类总览

| 类别 | 规则数 | 文件 | 参考文献 |
|------|--------|------|---------|
| 纵向安全 | 8 条 | `longitudinal.py` | Shalev-Shwartz 2017 §3.1 |
| 横向安全 | 7 条 | `lateral.py` | Shalev-Shwartz 2017 §3.2 |
| 交叉口 | 8 条 | `intersection.py` | Lin et al. 2024 |
| 行人保护 | 5 条 | `pedestrian.py` | Candela et al. 2022 |
| 风险指数 | 5 条 | `risk_index.py` | Candela et al. 2022 |
| **总计** | **33 条** | | |

### 4.3 纵向安全规则（Longitudinal）

**代码位置**: `ads_safety_platform/kg_core/rules/rss/longitudinal.py`

#### 核心公式

**最小安全距离**：
```
d_min_long = v_ego * rho + 0.5 * a_brake * rho² + (v_ego² - v_front²) / (2 * a_min_brake)
```

**核心参数**：
| 参数 | 值 | 说明 |
|------|-----|------|
| `rho` | 0.5s | 反应时间 |
| `a_max_accel` | 2.0 m/s² | 后车最大加速 |
| `a_min_brake` | 4.0 m/s² | 后车最小制动 |
| `a_brake` | 8.0 m/s² | 前车最大制动 |

#### 8条规则详解

| 规则 | 函数 | 说明 |
|------|------|------|
| L1 | `check_safe_distance()` | 检查实际距离是否大于 d_min |
| L2 | `check_proper_response()` | 验证后车是否适当制动 |
| L3 | `check_dangerous_situation()` | 判断是否为危险情形 |
| L4 | `check_continuous_violation()` | 检测连续违规 |
| L5 | `compute_brake_distance()` | 计算紧急制动距离 |
| L6 | `compute_comfort_brake_distance()` | 计算舒适制动距离 |
| L7 | `前车急刹检测` | Δv > 阈值时触发 |
| L8 | `跟车过近检测` | ttc < 阈值时触发 |

### 4.4 横向安全规则（Lateral）

**代码位置**: `ads_safety_platform/kg_core/rules/rss/lateral.py`

#### 核心公式

**横向最小安全距离**：
```
d_min_lat = 2 * v_lat * rho + a_min_lat_brake * rho²
```

**安全变道条件**：
```
d_lat >= d_min_lat AND ttc >= rho
```

#### 7条规则详解

| 规则 | 函数 | 说明 |
|------|------|------|
| LA1 | `check_safe_lateral_distance()` | 检查横向安全距离 |
| LA2 | `check_proper_lateral_response()` | 验证横向反应得当 |
| LA3 | `check_lane_change_safety()` | 验证变道安全 |
| LA4 | `compute_rss_safe_lane_change_zone()` | 计算安全变道区域 |
| LA5 | `违规变道检测` | 违规越过车道线 |
| LA6 | `compute_lateral_collision_time()` | 计算横向TTC |
| LA7 | `车道线感知` | 检测车道偏离 |

### 4.5 交叉口规则（Intersection）

**代码位置**: `ads_safety_platform/kg_core/rules/rss/intersection.py`

**支持的路口类型**：
- MERGE（并道）
- INTERSECTION（十字路口）
- T_JUNCTION（T型路口）
- ROUNDABOUT（环岛）
- LANE_CHANGE（变道）

**先行权规则**：
- RIGHT_BEFORE_LEFT（右侧优先）
- FIRST_COME_FIRST_SERVED（先到先行）
- SIGNAL_CONTROLLED（信号灯控制）

#### 8条规则详解

| 规则 | 函数 | 说明 |
|------|------|------|
| I1 | `check_merge_priority()` | 检查合并优先权 |
| I2 | `check_intersection_priority()` | 检查路口优先权 |
| I3 | `check_right_of_way_by_position()` | 按位置判断先行权 |
| I4 | `check_merge_safe_distance()` | 检查合并安全距离 |
| I5 | `RCPPPlanner` | 合规路径规划器 |
| I6 | `红灯闯行检测` | 红灯时通行 |
| I7 | `T型路口规则` | T型路口通行规则 |
| I8 | `环岛规则` | 环岛通行规则 |

### 4.6 行人保护规则（Pedestrian）

**代码位置**: `ads_safety_platform/kg_core/rules/rss/pedestrian.py`

#### 核心参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `d_min_pedestrian_crossing` | 5.0m | 横穿最小距离 |
| `d_min_pedestrian_nearby` | 3.0m | 附近最小距离 |
| `d_min_yield_zone` | 5.0m | 礼让区距离 |
| `rho` | 0.5s | 反应时间 |

#### 5条规则详解

| 规则 | 函数 | 说明 |
|------|------|------|
| P1 | `check_pedestrian_crossing()` | 行人横穿道路 |
| P2 | `check_pedestrian_proximity()` | 行人在附近 |
| P3 | `check_yield_to_pedestrian()` | 礼让行人 |
| P4 | `check_approaching_pedestrian()` | 接近行人 |
| P5 | `compute_pedestrian_risk_index()` | 计算行人风险指数 |

### 4.7 风险指数规则（Risk Index）

**代码位置**: `ads_safety_platform/kg_core/rules/rss/risk_index.py`

#### 风险等级

| 等级 | 范围 | 颜色 | 说明 |
|------|------|------|------|
| SAFE | 0 | 🟢 | 完全安全 |
| LOW | 0-0.2 | 🟢 | 低风险 |
| MEDIUM | 0.2-0.4 | 🟡 | 中风险 |
| HIGH | 0.4-0.7 | 🟠 | 高风险 |
| CRITICAL | 0.7-1.0 | 🔴 | 危急 |

#### 5条规则详解

| 规则 | 函数 | 说明 |
|------|------|------|
| R1 | `compute_risk_index()` | 计算基础风险指数 |
| R2 | `compute_risk_index_comprehensive()` | 综合风险评估 |
| R3 | `驾驶偏好风险` | 个性化风险评估 |
| R4 | `generate_risk_report()` | 生成风险报告 |
| R5 | `实时风险监控` | 持续监测风险 |

---

## 五、API 接口文档

### 5.1 健康检查
```bash
GET /api/health

# 响应
{
  "status": "healthy",
  "carla_connected": true,
  "timestamp": "2026-08-27T10:00:00.000000"
}
```

### 5.2 启动持续检测
```bash
POST /api/detect/start

# 响应
{
  "success": true,
  "message": "持续实时检测已启动",
  "status": "running"
}
```

### 5.3 停止检测
```bash
POST /api/detect/stop

# 响应
{
  "success": true,
  "message": "检测已停止"
}
```

### 5.4 定时检测
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

### 5.5 获取历史记录
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

### 5.6 WebSocket 实时推送
```javascript
const ws = new WebSocket('ws://localhost:8000/api/ws/detection');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'anomaly') {
    console.log('异常事件:', data.data);
    // 自动刷新页面显示新事件
    handleDetectionEvent(data);
  }
};
```

---

## 六、常见问题

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

### Q5: 页面没有自动刷新
**原因**: WebSocket 事件类型不匹配
**解决**:
- 已修复：前端兼容 `anomaly` 和 `detection` 两种事件类型
- 刷新页面重新连接

### Q6: CARLA Python API 连接 SegFault
**原因**: CARLA 版本与 Python API 版本不匹配
**解决**: 系统会自动使用 TCP Socket 方式连接，忽略 Python API

---

## 七、最佳实践

### 7.1 演示流程
1. 启动 CARLA
2. 启动后端
3. 打开仪表盘
4. 点击 "启动实时检测"
5. 等待 30-60 秒
6. 看到事件后点击 "查看图谱"
7. 展示完整的 Per-event 知识图谱

### 7.2 报告展示要点
- **技术架构图**：前后端分离 + CARLA 集成
- **RSS规则**：33条规则分类表格
- **核心功能**：实时检测 + 知识图谱 + Web可视化
- **运行效果**：3 列表格布局的知识图谱（自车、场景、风险）
- **项目亮点**：Per-event 图谱、WebSocket 推送、多模式检测

---

## 八、更新日志

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| v2.0.0 | 2026-08-27 | 完善知识图谱、添加Toast提示、33条RSS规则文档 |
| v1.0.0 | 2026-08-20 | 基础异常检测功能 |
