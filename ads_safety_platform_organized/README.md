# ADS Safety Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)

## 🚗 自动驾驶安全验证平台

一个集成CARLA仿真、RSS（Responsibility-Sensitive Safety）规则检测与时空知识图谱分析的综合性安全验证平台。

## 📁 项目结构

```
ads_safety_platform_organized/
├── src/ads_safety_platform/     # 主源码目录
│   ├── kg/                       # 知识图谱核心模块
│   ├── rss/                      # RSS规则引擎
│   ├── scenarios/                # 场景构建与验证
│   ├── car/                      # 车辆动力学模型
│   ├── visualization/            # 可视化组件
│   ├── tools/                    # 工具脚本
│   ├── paths.py                  # 路径配置
│   ├── realtime_multi_anomaly_demo.py  # 实时检测演示
│   └── ...
├── tests/                        # 测试代码
├── examples/                     # 示例代码
├── tools/                        # 实用工具
├── configs/                      # 配置文件
├── docs/                         # 文档
├── scripts/                      # 脚本工具
├── output/                       # 输出文件
│   ├── html/                     # HTML报告
│   └── json/                     # JSON数据
├── results/                      # 结果数据
│   ├── kg_output/               # 知识图谱输出
│   ├── reports/                 # 报告
│   └── anomalies/               # 异常详情页
└── setup.py                     # 安装配置
```

## 🚀 快速开始

### 1. 安装依赖

```bash
# 克隆仓库
git clone <repository-url>
cd ads_safety_platform_organized

# 安装（开发模式）
pip install -e .
```

### 2. 运行实时检测

```bash
# 运行10秒实时检测（注入异常场景）
python -m ads_safety_platform.realtime_multi_anomaly_demo \
    --duration 10 --step 1

# 连接CARLA服务器
python -m ads_safety_platform.realtime_multi_anomaly_demo \
    --duration 60 --carla --host 127.0.0.1 --port 2000
```

### 3. 查看结果

```bash
# 查看仪表盘
open output/html/visualization_demo.html

# 查看知识图谱
open output/html/knowledge_graph_*.html

# 查看异常详情
open results/anomalies/anomaly_*.html
```

## 🎯 功能特性

### 1. 实时数据收集
- ✅ 支持CARLA服务器实时连接
- ✅ 断线自动重连
- ✅ 备用模式（无CARLA时注入模拟场景）

### 2. RSS规则检测
- ✅ 纵向规则（速度、距离）
- ✅ 横向规则（变道、优先权）
- ✅ 行人规则（安全出行）
- ✅ 红灯/红绿灯规则

### 3. 知识图谱构建
- ✅ 时空关系建模
- ✅ 实体关联网络
- ✅ SVG可视化
- ✅ 交互式浏览

### 4. 异常检测与可视化
- ✅ 多异常并行检测
- ✅ 风险分级（Low/Medium/High/Critical）
- ✅ 交互式Dashboard
- ✅ 个别异常详情页
- ✅ 传统SVG知识图谱

## 📊 输出格式

### Dashboard 仪表盘
- 统计数据展示
- 异常卡片列表
- 点击跳转详情页
- 知识图谱链接

### 知识图谱
- **圆形节点**：表示实体（Ego车辆、场景、违规等）
- **连线**：表示实体间的关系
- **线上标注**：关系类型标签（检测到、包含、相关等）
- **交互**：点击节点显示属性，悬停查看详情

### 单个异常页面
- 异常概览（风险等级、位置、速度）
- 违规详情列表
- 返回仪表盘按钮

## 🔧 配置说明

### 命令行参数

```bash
--duration     收集持续时间(秒), 默认: 60
--step         采样间隔(秒), 默认: 2.0
--carla        连接CARLA服务器
--host         CARLA主机, 默认: localhost
--port         CARLA端口, 默认: 2000
--timeout      连接超时秒数, 默认: 5.0
--seed         随机种子, 默认: 42
--output       输出目录, 默认: output/
```

### 环境变量

```bash
# CARLA_SERVER_HOST=127.0.0.1
# CARLA_SERVER_PORT=2000
# CARLA_TIMEOUT=10.0
```

## 📚 文档

- [项目文档](docs/Project_Summary.md)
- [实现概述](docs/Implementation_Complete.md)
- [GitHub推送指南](docs/GitHub_Push_Guide.md)
- [STKG集成设计](docs/STKG_Integration_Design.md)

## 🧪 测试

```bash
# 运行单元测试
pytest tests/

# 运行集成测试
python -m pytest tests/integration/ -v
```

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📜 许可证

MIT License