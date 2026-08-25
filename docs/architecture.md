# ADS Safety Platform v2 - 架构设计文档

## 🏗️ 系统架构

### 前后端分离架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户浏览器                               │
│                  (http://localhost:5173)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      React 前端                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   组件层     │  │   服务层     │  │   状态管理           │ │
│  │  - Dashboard │  │  - api.js    │  │   - Context API      │ │
│  │  - KG View   │  │  - ws.js     │  │   - Redux (可选)     │ │
│  │  - Anomalies │  │  - utils.js  │  │                       │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                                                  │
│  - React 18 + Vite 4 + Ant Design 5 + Recharts                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Nginx 反向代理                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  /api/*     → http://backend:8000                        │ │
│  │  /output/*  → http://backend:8000                        │ │
│  │  /*        → /usr/share/nginx/html/index.html            │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI 后端                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   API层      │  │   服务层     │  │   核心检测逻辑       │ │
│  │  - main.py   │  │  - detector  │  │   - CARLA连接        │ │
│  │  - routes/   │  │  - kg_gen    │  │   - RSS规则检测      │ │
│  │  - schemas/  │  │  - storage   │  │   - 异常分析         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                                                  │
│  - FastAPI 0.100+ + Uvicorn + Pydantic 2 + SQLAlchemy         │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
    │   CARLA      │   │  SQLite/     │   │   输出文件   │
    │   仿真器     │   │  PostgreSQL  │   │   目录       │
    │  :2000       │   │  (可选)      │   │  /app/output │
    └─────────────┘   └─────────────┘   └─────────────┘
```

## 📊 API 设计

### REST API 端点

#### 健康检查
```
GET /api/health
响应: {"status": "healthy", "service": "ADS Safety Platform", "version": "2.0.0"}
```

#### 配置管理
```
GET /api/config          # 获取配置
POST /api/config         # 更新配置
```

#### 检测管理
```
POST /api/detect/run     # 运行检测
GET /api/detect/history  # 获取历史
GET /api/detect/latest   # 最新结果
```

#### 知识图谱
```
GET /api/kg/latest        # 最新知识图谱
GET /api/kg/generate     # 生成知识图谱
```

#### WebSocket 实时推送
```
ws://localhost:8000/api/ws/detection
推送: 实时检测结果
```

### 数据模型

#### DetectionResult
```json
{
  "scenario_id": 1,
  "scenario_name": "前车急刹",
  "timestamp": "2026-08-25T11:20:00",
  "ego_x": 10.5,
  "ego_y": 20.3,
  "ego_speed": 15.0,
  "vehicle_count": 3,
  "violations": [
    {
      "code": "R1",
      "rule": "纵向安全距离",
      "message": "跟车过近",
      "level": "HIGH"
    }
  ],
  "risk_index": 0.85,
  "risk_level": "CRITICAL",
  "duration_ms": 100.0
}
```

#### KnowledgeGraph
```json
{
  "nodes": [
    {
      "id": "ego",
      "label": "Ego车辆",
      "type": "vehicle",
      "color": "#4CAF50"
    },
    {
      "id": "scenario_1",
      "label": "前车急刹",
      "type": "scenario",
      "risk_level": "CRITICAL",
      "color": "#F44336"
    }
  ],
  "edges": [
    {
      "source": "ego",
      "target": "scenario_1",
      "relation": "检测到",
      "weight": 0.85
    }
  ]
}
```

## 🗄️ 数据库设计

### SQLite (默认)

```sql
-- 检测结果表
CREATE TABLE detection_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER NOT NULL,
    scenario_name TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    ego_x REAL NOT NULL,
    ego_y REAL NOT NULL,
    ego_speed REAL NOT NULL,
    vehicle_count INTEGER NOT NULL,
    violations JSON NOT NULL,
    risk_index REAL NOT NULL,
    risk_level TEXT NOT NULL,
    duration_ms REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 知识图谱节点表
CREATE TABLE kg_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT UNIQUE NOT NULL,
    label TEXT NOT NULL,
    node_type TEXT NOT NULL,
    color TEXT NOT NULL,
    properties JSON,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 知识图谱关系表
CREATE TABLE kg_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    relation TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source) REFERENCES kg_nodes(node_id),
    FOREIGN KEY (target) REFERENCES kg_nodes(node_id)
);

-- 系统配置表
CREATE TABLE system_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### PostgreSQL (可选)

```sql
-- 使用PostgreSQL时，只需修改数据库URL
-- DATABASE_URL=postgresql://user:password@localhost:5432/safety_db
```

## 🚀 部署方式

### 1. 本地开发

```bash
# 启动后端
cd backend
pip install -r requirements.txt
python -m app.main

# 启动前端
cd frontend
npm install
npm run dev
```

### 2. Docker Compose

```bash
# 一键部署
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 3. 生产部署

```bash
# 构建镜像
docker-compose build

# 启动生产环境
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 📁 目录结构

```
ads_safety_platform_v2/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI主入口
│   │   ├── config.py            # 配置管理
│   │   ├── database.py          # 数据库连接
│   │   ├── models/
│   │   │   └── __init__.py
│   │   ├── schemas/
│   │   │   └── __init__.py
│   │   ├── api/
│   │   │   └── __init__.py
│   │   ├── services/
│   │   │   └── __init__.py
│   │   └── core/
│   │       ├── __init__.py
│   │       ├── detector.py      # 检测核心
│   │       └── carla_client.py # CARLA客户端
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/
│
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   └── components/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── Dockerfile
│   └── nginx.conf
│
├── docker-compose.yml
├── docker-compose.prod.yml
├── README.md
└── docs/
    ├── architecture.md
    ├── api.md
    └── deployment.md
```

## 🔧 配置说明

### 环境变量

```bash
# 后端配置
CARLA_HOST=localhost
CARLA_PORT=2000
DATABASE_URL=sqlite:///./data/safety.db
OUTPUT_DIR=/app/output

# 前端配置
VITE_API_URL=http://localhost:8000
```

### .env 文件

```bash
# backend/.env
CARLA_HOST=localhost
CARLA_PORT=2000
DATABASE_URL=sqlite:///./data/safety.db
DEBUG=true

# frontend/.env
VITE_API_URL=http://localhost:8000
```

## 📊 监控指标

### 系统指标
- 检测频率: 1次/秒 (可配置)
- 平均检测时长: < 100ms
- 并发处理能力: 100+ 请求/秒
- 内存占用: < 500MB

### 业务指标
- 异常检出率: > 95%
- 误报率: < 5%
- 知识图谱生成时间: < 500ms
- 实时推送延迟: < 100ms

## 🔒 安全考虑

### API 安全
- CORS配置: 开发模式允许所有来源
- 生产模式: 限制特定域名
- 速率限制: 100请求/分钟
- 认证: JWT Token (可选)

### 数据安全
- 敏感数据加密存储
- 定期备份
- 访问日志记录

## 📚 依赖版本

### 后端依赖
```
fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0
python-multipart>=0.0.6
sqlalchemy>=2.0.0
aiofiles>=23.0.0
```

### 前端依赖
```
react>=18.2.0
react-dom>=18.2.0
react-router-dom>=6.14.0
antd>=5.8.0
recharts>=2.8.0
axios>=1.4.0
vite>=4.3.9
```

## 🤝 贡献指南

1. Fork仓库
2. 创建特性分支
3. 提交代码
4. 推送到远程
5. 创建Pull Request

## 📜 许可证

MIT License