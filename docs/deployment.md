# ADS Safety Platform 部署指南

## 📋 环境要求

### 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|-----|---------|---------|
| CPU | 4核 | 8核 |
| 内存 | 4GB | 8GB |
| 存储 | 20GB | 50GB |
| 显卡 | CUDA可选 | NVIDIA GTX 1060+ |

### 软件要求

| 软件 | 最低版本 | 推荐版本 |
|-----|---------|---------|
| Docker | 20.10+ | 24.0+ |
| Docker Compose | 1.29+ | 2.20+ |
| Python | 3.9+ | 3.11+ |
| Node.js | 18+ | 20+ |
| PostgreSQL | 14+ | 16+ |

## 🚀 快速部署

### 方式一：Docker Compose 一键部署

```bash
# 克隆仓库
git clone <repository-url>
cd ads_safety_platform_v2

# 构建并启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 检查健康状态
curl http://localhost:8000/api/health
```

### 方式二：本地Python部署

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r backend/requirements.txt

# 启动后端
python -m app.main --host 0.0.0.0 --port 8000

# 前端（另开终端）
cd frontend
npm install
npm run dev
```

## ⚙️ 配置说明

### 环境变量

#### 后端配置

创建 `backend/.env` 文件：

```bash
# CARLA配置
CARLA_HOST=localhost          # CARLA服务器地址
CARLA_PORT=2000              # CARLA端口
CARLA_TIMEOUT=5.0            # 连接超时

# 数据库配置
DATABASE_URL=sqlite:///./data/safety.db
# 或者使用PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost:5432/safety_db

# 运行时配置
DETECT_INTERVAL=1.0          # 检测间隔
MAX_SCENARIOS=1000           # 最大场景数
OUTPUT_DIR=/app/output       # 输出目录

# 风险阈值
RISK_THRESHOLD_CRITICAL=0.7
RISK_THRESHOLD_HIGH=0.4
RISK_THRESHOLD_MEDIUM=0.2

# 调试模式
DEBUG=false
```

#### 前端配置

创建 `frontend/.env` 文件：

```bash
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

### Docker Compose 配置文件

#### 开发环境 (`docker-compose.yml`)

```yaml
# 已包含在项目中
```

#### 生产环境 (`docker-compose.prod.yml`)

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: ads-safety-backend
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - DEBUG=false
      - CARLA_HOST=${CARLA_HOST:-localhost}
      - CARLA_PORT=${CARLA_PORT:-2000}
    volumes:
      - ./data:/app/data
      - ./output:/app/output
    networks:
      - ads-network
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: ads-safety-frontend
    restart: unless-stopped
    ports:
      - "80:80"
    depends_on:
      - backend
    networks:
      - ads-network
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'

networks:
  ads-network:
    driver: bridge
```

## 🐳 使用CARLA

### 启动CARLA服务器

```bash
# 方式1: 从界面启动
./CarlaUE4.sh -nopause -carlaport=2000

# 方式2: 使用Docker (如果不可用GUI)
docker run -it --gpus all \
  -p 2000:2000 \
  -e SDL_VIDEODRIVER=offscreen \
  carlasim/carla:0.9.14
```

### 检查CARLA连接

```bash
# 在浏览器中访问
http://localhost:8000/api/health

# 响应示例:
{
  "status": "healthy",
  "carla_connected": true
}
```

### 运行CARLA场景检测

```bash
# 连接CARLA并运行检测
cd backend
python -c "
import asyncio
from app.main import *

async def main():
    result = await run_detection(duration=60, carla_connected=True)
    print(result)

asyncio.run(main())
"
```

## 📊 生成报告

### 生成知识图谱

```bash
# 通过API生成
curl -X GET http://localhost:8000/api/kg/generate

# 或运行检测后自动生成
python -m app.main
```

### 查看报告

```bash
# 仪表盘
open output/html/visualization_demo.html

# 知识图谱
open output/html/knowledge_graph.html

# 异常详情
open output/alerts/*.html
```

## 🔒 安全配置

### 启用HTTPS

```bash
# 推荐使用 Nginx 反向代理 + SSL
# 1. 获取 SSL 证书
certbot certonly --standalone -d your-domain.com

# 2. 配置 Nginx
# 修改 nginx.conf 添加 SSL 配置
```

### 数据库加密

```bash
# PostgreSQL 加密
ALTER TABLE detection_results SET (encryption_algorithm = 'aes-256-cbc');
```

### 访问控制

```bash
# 添加 API 密钥
echo "API_KEY=$(openssl rand -hex 32)" >> .env

# 在请求头中添加
# Authorization: Bearer your-api-key
```

## 📈 性能优化

### 调整检测参数

```bash
# 缩短检测间隔提高检测频率
DETECT_INTERVAL=0.5

# 调整并发处理
uvicorn app.main:app --workers 4 --host 0.0.0.0 --port 8000
```

### 数据库优化

```sql
-- 为查询添加索引
CREATE INDEX idx_detection_timestamp ON detection_results(timestamp);
CREATE INDEX idx_detection_risk ON detection_results(risk_level);

-- 定期清理旧数据
DELETE FROM detection_results WHERE created_at < datetime('now', '-30 days');
```

### 前端缓存

```bash
# 构建生产包（启用压缩）
npm run build

# 设置缓存头
# 在nginx.conf中添加
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
    expires 7d;
    add_header Cache-Control "public, immutable";
}
```

## 🛠️ 故障排查

### 常见问题

#### 1. 端口被占用

```bash
# 检查端口占用
lsof -i :8000
lsof -i :80
lsof -i :5173

# 解决办法
docker-compose down
# 修改端口后重新启动
```

#### 2. CARLA 连接失败

```bash
# 检查CARLA是否运行
netstat -an | grep 2000

# 检查连接
curl http://localhost:2000

# 解决方案
# 1. 确认CARLA已启动
# 2. 检查防火墙
# 3. 使用注入模式: --inject-anomalies
```

#### 3. 内存不足

```bash
# 检查内存
free -h

# 增加Docker内存
# 在Docker Desktop设置中增加

# 或调整后端参数
MAX_SCENARIOS=100  # 减少内存使用的场景数
```

#### 4. 前端静止不动

```bash
# 重新构建前端
cd frontend
npm run build

# 检查API是否可达
curl http://localhost:8000/api/health
```

### 查看日志

```bash
# 后端日志
docker-compose logs backend -f

# 前端日志
docker-compose logs frontend -f

# 系统日志
docker compose logs -f
```

## 📋 维护任务

### 定期备份

```bash
# 数据库备份
docker exec ads-safety-backend pg_dump -U postgres safety_db > backup.sql

# 输出文件备份
tar -czf output_backup_$(date +%Y%m%d).tar.gz output/
```

### 更新升级

```bash
# 拉取最新代码
git pull origin main

# 重建镜像
docker-compose build --no-cache

# 重启服务
docker-compose up -d
```

### 清理资源

```bash
# 清理Docker卷
docker volume prune

# 清理未使用的镜像
docker image prune -a

# 清理构建缓存
docker builder prune
```

## 📞 联系支持

- 文档: `docs/` 目录
- API: `http://localhost:8000/api/docs`
- 问题提交: GitHub Issues