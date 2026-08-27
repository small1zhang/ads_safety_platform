# 📖 ADS Safety Platform - 系统使用文档

> 本文档详细介绍 ADS Safety Platform 系统的安装、配置、使用方法和常见问题解决方案。

## 📑 目录

- [一、系统要求](#一系统要求)
- [二、安装指南](#二安装指南)
- [三、配置说明](#三配置说明)
- [四、使用指南](#四使用指南)
- [五、检测脚本说明](#五检测脚本说明)
- [六、API 接口使用](#六api-接口使用)
- [七、常见问题](#七常见问题)
- [八、故障排除](#八故障排除)

---

## 一、系统要求

### 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 4 核 | 8 核及以上 |
| 内存 | 8GB | 16GB |
| GPU | 不必需 | NVIDIA GTX 1060+ |
| 硬盘 | 20GB | 50GB |

### 软件要求

- **操作系统**: Linux (Ubuntu 20.04+) / macOS / Windows 10+ (WSL2)
- **Python**: 3.8+
- **Node.js**: 16+ (前端)
- **CARLA**: 0.9.13+
- **Docker**: 20.10+ (可选)

### 网络要求

- CARLA 仿真器默认端口: `2000` (TCP) + `2001` (UE4)
- 后端服务: `8000` (HTTP)
- 前端服务: `5173` (HTTP)

---

## 二、安装指南

### 方式一：本地安装（推荐开发使用）

#### 1. 克隆项目

```bash
git clone https://github.com/small1zhang/ads_safety_platform.git
cd 01_ZHB
```

#### 2. 安装 Python 依赖

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r backend/requirements.txt
```

#### 3. 安装 CARLA Python API

```bash
# 方式 1: pip 安装
pip install carla==0.9.13

# 方式 2: 从 CARLA 解压目录安装
cd ~/CARLA_0.9.13/PythonAPI/carla/dist
pip install carla-0.9.13-*.whl
```

#### 4. 安装前端依赖

```bash
cd frontend
npm install
```

#### 5. 启动 CARLA 仿真器

```bash
# 单独启动
cd ~/CARLA_0.9.13
./CarlaUE4.sh -windowed -ResX=1280 -ResY=720

# 启动并加载地图
./CarlaUE4.sh /Game/Carla/Maps/Town03 -windowed
```

### 方式二：Docker 部署（推荐生产使用）

```bash
# 一键启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

---

## 三、配置说明

### 环境变量

#### 后端配置 (`backend/.env`)

```bash
# CARLA 连接配置
CARLA_HOST=localhost
CARLA_PORT=2000
CARLA_TIMEOUT=10.0

# 数据库配置
DATABASE_URL=sqlite:///./data/safety.db
# 可选: postgresql://user:password@localhost:5432/safety_db

# 检测配置
DETECTION_INTERVAL=1.0     # 检测间隔 (秒)
RISK_THRESHOLD=0.5         # 风险阈值
ALERT_COOLDOWN=3.0         # 告警冷却时间 (秒)

# 输出配置
OUTPUT_DIR=./output

# 开发模式
DEBUG=true
LOG_LEVEL=INFO
```

#### 前端配置 (`frontend/.env`)

```bash
# API 地址
VITE_API_URL=http://localhost:8000

# WebSocket 地址
VITE_WS_URL=ws://localhost:8000/api/ws
```

### RSS 规则参数

可以在代码中调整 RSS 参数：

```python
# longitudinal.py
@dataclass
class RSSLongitudinalParams:
    rho: float = 0.5              # 反应时间 (s)
    a_max_accel: float = 2.0      # 后车最大加速 (m/s²)
    a_min_brake: float = 4.0      # 后车最小制动 (m/s²)
    a_brake: float = 8.0          # 前车最大制动 (m/s²)

# lateral.py
@dataclass
class RSSLateralParams:
    rho: float = 0.5              # 反应时间 (s)
    a_max_lat: float = 3.0        # 最大横向加速度 (m/s²)
    a_min_lat_brake: float = 5.0  # 最小横向制动减速度 (m/s²)
    vehicle_width: float = 2.0    # 标准车宽 (m)
    lane_width: float = 3.7       # 车道宽度 (m)
```

---

## 四、使用指南

### 4.1 启动顺序

**重要：请按顺序启动**

1. **启动 CARLA 仿真器**（必须先启动）
2. **运行检测脚本**（会自动连接 CARLA）
3. **可选：启动前端界面**

### 4.2 快速开始（5分钟体验）

#### 步骤 1: 启动 CARLA

```bash
# 终端 1
cd ~/CARLA_0.9.13
./CarlaUE4.sh -windowed
```

#### 步骤 2: 运行实时检测

```bash
# 终端 2
cd /home/aisecurity/01_ZHB
python3 run_realtime_alert.py
```

#### 步骤 3: 观察输出

终端会显示：
- 🚗 车辆位置和速度信息
- 📊 实时风险评估
- ⚠️ 违规预警信息
- 🔴 车辆颜色变化

#### 步骤 4: 停止检测

按 `Ctrl+C` 停止。系统会保存检测报告到 `output_realtime_alert/` 目录。

### 4.3 启动前端界面（可选）

```bash
# 终端 3
cd backend
python -m app.main

# 终端 4
cd frontend
npm run dev
```

浏览器打开 `http://localhost:5173` 访问。

---

## 五、检测脚本说明

本项目提供多个检测脚本，根据不同需求选择：

### 5.1 `run_realtime_alert.py` - 实时预警检测（推荐）

**功能**：连接 CARLA，对所有车辆进行实时 RSS 规则检测，触发终端预警和车辆颜色变化。

```bash
python3 run_realtime_alert.py
```

**特点**：
- ✅ 实时检测（每秒1次）
- ✅ 终端颜色预警（红/黄/绿）
- ✅ CARLA 车辆颜色变化
- ✅ 违规原因详细输出
- ✅ 30分钟检测时长
- ✅ 输出 JSON 报告

**输出示例**：
```
🚗 检测循环 #42
  车辆 0: pos=(10.5, 20.3) speed=15.0 m/s
  车辆 1: pos=(12.0, 22.1) speed=12.0 m/s
  ⚠️ 与车辆横向距离 0.5m 低于安全距离
  🚨 风险等级: MEDIUM

📊 统计: 违规 29/600 (4.8%)
```

### 5.2 `run_real_carla_detection.py` - 真实 CARLA 检测

**功能**：使用 CARLA 仿真器中现有的车辆进行 RSS 检测。

```bash
python3 run_real_carla_detection.py
```

**特点**：
- ✅ 使用 CARLA 自动驾驶模式
- ✅ 包含 Traffic Manager
- ✅ 30分钟长时间检测
- ✅ 真实车辆动力学

### 5.3 `run_anomaly_simple.py` - 简化异常检测

**功能**：注入异常场景并检测（适合测试和验证）。

```bash
python3 run_anomaly_simple.py
```

**注入的异常类型**：
- `sudden_brake`: 急刹车
- `tailgating`: 尾随过近
- `close_call`: 横向近距离
- `rapid_approach`: 快速接近

**特点**：
- ✅ 自动注入异常（每 5-8 秒 40% 概率）
- ✅ 验证 RSS 规则有效性
- ✅ 测试结果可视化

### 5.4 `run_anomaly_injection_detection.py` - 高级异常注入

**功能**：完整的异常场景注入与检测。

```bash
python3 run_anomaly_injection_detection.py
```

**特点**：
- ✅ 6 种异常场景（急刹、变道、交叉口冲突、尾随、超速、行人横穿）
- ✅ 可配置异常频率
- ✅ 详细违规原因分析

---

## 六、API 接口使用

### 6.1 健康检查

```bash
curl http://localhost:8000/api/health
```

**响应**：
```json
{
  "status": "healthy",
  "service": "ADS Safety Platform",
  "version": "2.0.0"
}
```

### 6.2 触发检测

```bash
curl -X POST http://localhost:8000/api/detect/run \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_id": 1,
    "duration": 60
  }'
```

**响应**：
```json
{
  "status": "started",
  "task_id": "task-123",
  "scenario": "前车急刹"
}
```

### 6.3 获取历史检测

```bash
curl http://localhost:8000/api/detect/history?limit=10
```

**响应**：
```json
[
  {
    "scenario_id": 1,
    "scenario_name": "前车急刹",
    "timestamp": "2026-08-26T10:00:00",
    "ego_speed": 15.0,
    "violations": [...],
    "risk_level": "MEDIUM"
  }
]
```

### 6.4 WebSocket 实时推送

```javascript
const ws = new WebSocket('ws://localhost:8000/api/ws/detection');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('检测结果:', data);
};
```

---

## 七、常见问题

### Q1: CARLA 连接失败

**问题**：`RuntimeError: connection to localhost:2000 failed`

**解决方案**：
1. 确认 CARLA 仿真器已启动
2. 检查端口 `2000` 是否被占用：`netstat -an | grep 2000`
3. 检查防火墙设置
4. 重启 CARLA 仿真器

### Q2: 没有任何违规检出

**问题**：运行 10 分钟，违规数为 0

**解决方案**：
1. 确认 CARLA 中有多个车辆（至少 2-3 辆）
2. 使用 `run_anomaly_simple.py` 注入异常场景
3. 检查 NPC 车辆位置是否与 ego 车辆足够接近
4. 调整 RSS 参数阈值

### Q3: 检测速度太慢

**问题**：检测一帧需要超过 1 秒

**解决方案**：
1. 减少 CARLA 中的车辆数量
2. 降低检测频率（修改 `DETECTION_INTERVAL`）
3. 使用更简单的异常注入模式

### Q4: 终端颜色不显示

**问题**：终端输出没有颜色

**解决方案**：
- 终端需要支持 ANSI 颜色（大多数现代终端支持）
- Linux/macOS: 使用默认终端即可
- Windows: 使用 Windows Terminal 或 WSL2

### Q5: 大量误报

**问题**：检出大量非真实违规

**解决方案**：
1. 调整 RSS 参数（增加 `rho` 反应时间）
2. 提高 `RISK_THRESHOLD` 阈值
3. 检查车辆位置数据是否准确

---

## 八、故障排除

### 8.1 错误代码对照表

| 错误代码 | 含义 | 解决方案 |
|---------|------|---------|
| `CONN_REFUSED` | CARLA 未启动 | 启动 CARLA 仿真器 |
| `TIMEOUT` | 连接超时 | 检查网络和防火墙 |
| `VEHICLE_NONE` | 场景中无车辆 | 生成 NPC 车辆 |
| `INVALID_STATE` | 无效车辆状态 | 重启 CARLA |
| `PORT_BUSY` | 端口被占用 | 修改端口配置 |

### 8.2 日志查看

```bash
# 查看检测日志
tail -f output/logs/detection.log

# 查看错误日志
grep "ERROR" output/logs/*.log
```

### 8.3 性能调优

#### 检测性能优化

```python
# 减少检测频率
DETECTION_INTERVAL = 2.0  # 从 1.0 改为 2.0 秒

# 减少同时检测的车辆数量
MAX_VEHICLES = 5
```

#### CARLA 性能优化

```bash
# 启动时降低渲染质量
./CarlaUE4.sh -quality-level=Low

# 减少 NPC 车辆
# 在脚本中设置 traffic_manager.distance_to_leading_vehicle
```

### 8.4 重置系统

如果系统出现异常状态，可以完全重置：

```bash
# 1. 停止所有服务
pkill -f carla
pkill -f "python3 run_"
pkill -f "uvicorn"

# 2. 清理输出
rm -rf output_*/
rm -rf data/safety.db

# 3. 重启 CARLA
cd ~/CARLA_0.9.13
./CarlaUE4.sh

# 4. 重新运行检测
cd /home/aisecurity/01_ZHB
python3 run_realtime_alert.py
```

---

## 九、最佳实践

### 9.1 测试流程建议

1. **第一次测试**: 使用 `run_anomaly_simple.py` 验证系统能正常工作
2. **第二次测试**: 使用 `run_realtime_alert.py` 测试真实场景检测
3. **长时间测试**: 使用 `run_real_carla_detection.py` 进行 30 分钟压力测试
4. **生产部署**: 使用 Docker Compose 部署到生产环境

### 9.2 参数调优建议

| 场景 | 推荐参数调整 |
|------|-------------|
| 高速公路 | `rho=0.7, a_min_brake=5.0` |
| 城市道路 | `rho=0.5, a_min_brake=4.0`（默认）|
| 拥堵路段 | `rho=0.3, a_min_brake=3.5` |
| 雨天环境 | `rho=0.6, a_min_brake=5.0` |

### 9.3 数据备份

```bash
# 备份检测数据
tar -czf backup_$(date +%Y%m%d).tar.gz output_*/ data/

# 备份数据库
cp data/safety.db backup/safety_$(date +%Y%m%d).db
```

---

## 📞 技术支持

- **项目地址**: [github.com/small1zhang/ads_safety_platform](https://github.com/small1zhang/ads_safety_platform)
- **问题反馈**: GitHub Issues
- **文档版本**: v2.0.0
- **最后更新**: 2026-08-26

---

*本文档将持续更新以反映系统最新功能。*
