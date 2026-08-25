# ADS Safety Platform - 前后端分离架构

本项目是一个基于 FastAPI + React 的前后端分离式自动驾驶安全验证平台。

## 项目架构

```
.
├── backend/                    # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py              # 主入口，FastAPI应用
│   │   ├── config.py            # 配置管理
│   │   ├── database.py          # 数据库连接
│   │   ├── models/              # SQLAlchemy数据模型
│   │   ├── schemas/             # Pydantic请求/响应模式
│   │   ├── api/                 # API路由
│   │   ├── services/            # 业务逻辑服务
│   │   └── core/                # 核心检测逻辑
│   ├── requirements.txt         # Python依赖
│   ├── Dockerfile               # 后端Docker镜像
│   └── tests/                   # 后端测试
│
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── main.jsx             # 前端主入口
│   │   ├── App.jsx              # 路由配置
│   │   ├── components/          # 组件库
│   │   ├── services/            # API服务调用
│   │   └── styles/              # 样式文件
│   ├── package.json             # Node.js依赖
│   ├── vite.config.js           # Vite配置
│   └── Dockerfile               # 前端Docker镜像
│
├── docker-compose.yml           # Docker Compose配置
├── README.md                    # 项目说明
└── docs/                        # 文档
    ├── architecture.md          # 架构设计
    ├── api.md                   # API文档
    └── deployment.md            # 部署指南
```

## 快速开始

### 1. 启动服务端

```bash
cd backend
pip install -r requirements.txt
python -m app.main
```

服务端默认运行在 `http://localhost:8000`

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`

### 3. 使用Docker一键部署

```bash
docker-compose up -d
```

## API 文档

访问 `http://localhost:8000/docs` 查看自动生成的API文档（Swagger UI）

## 主要功能

- 实时CARLA数据采集
- RSS规则异常检测
- 知识图谱生成
- 交互式可视化
- REST API
- 数据库持久化