# ads_safety_platform - 自动驾驶安全评测平台

基于 CARLA 0.9.16 的自动驾驶安全评测与监测平台，采用**物理规则 + 知识图谱**双引擎架构。

## 项目概述

本平台通过以下方式检测自动驾驶安全风险：

- **轨迹簇预测**：基于运动学自行车模型，生成未来 5 秒的多控制通道轨迹包
- **可达集计算**：使用 Graham Scan 凸包算法计算各时刻车辆可达区域
- **碰撞检测**：利用分离轴定理 (SAT) 检测轨迹包的多边形重叠
- **实时风险判定**：闯红灯、压线、碰撞风险的三级分类 (SAFE/UNCERTAIN/UNSAFE)

## 核心模块

| 模块 | 文件 | 功能 |
|------|------|------|
| 主程序 | `ads_safety_platform.py` | CARLA 仿真集成、GUI 渲染、NPC 生成 |
| 安全引擎 | `safety_judge.py` | 三重物理规则检测（闯红灯、压线、碰撞） |
| 控制器 | `auto_drive_agent.py` | 车道保持 PID 控制 Agent |
| 轨迹预测 | `car/trajectory_prediction.py` | 运动学自行车模型 + 四阶 RK4 积分 |
| 可达集 | `car/reachable_set.py` | 轨迹簇生成 + 凸包计算 |
| 碰撞检测 | `car/collision_prediction.py` | SAT 碰撞预测分析 |

## 依赖安装

```bash
# 安装 CARLA 0.9.16 Python API
pip install carla==0.9.16

# 安装其他依赖
pip install numpy pygame
```

## 运行方式

### 1. 启动 CARLA 服务器

```bash
./CarlaUE4.sh -carla-port=2000
```

### 2. 运行安全检测平台

```bash
python ads_safety_platform.py
```

### 3. 运行测试代码

```bash
python safety_judge.py
```

## 配置说明

在 `ads_safety_platform.py` 中可配置：

```python
WIDTH, HEIGHT = 800, 600          # 显示分辨率
NUM_NPC_VEHICLES = 10             # 障碍车数量
NORMAL_DRIVING_TEST = True        # 是否测试正常驾驶
LOCK_RED_LIGHT = False            # 是否强制保持红灯
```

## 场景证据

运行平台会自动生成场景证据到 `scene_evidence/` 目录，保存格式：

```
scene_evidence/
├── 1/
│   └── scene_data.txt
├── 2/
│   └── scene_data.txt
...
```

风险违规日志记录到 `safety_logs/risk_violations.log`。

## 知识图谱增强

项目集成 [SpatioTemporalKG](../SpatioTemporalKG) 架构，详见 [STKG_Integration_Design.md](docs/STKG_Integration_Design.md)。

## 许可证

项目仅供研究与教育用途。
