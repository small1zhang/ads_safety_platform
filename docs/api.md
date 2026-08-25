# ADS Safety Platform API 文档

## 📖 介绍

本API文档覆盖ADS Safety Platform v2的全部REST API和WebSocket接口。

## 🔐 认证

当前版本使用免费访问模式。后续版本将支持JWT认证。

## 🏥 健康检查

### GET /api/health

获取系统健康状态

**响应示例:**
```json
{
  "status": "healthy",
  "service": "ADS Safety Platform",
  "version": "2.0.0",
  "timestamp": "2026-08-25T11:00:00",
  "carla_connected": true
}
```

**状态码:**
- 200 OK - 系统健康
- 503 Service Unavailable - 系统异常

---

## ⚙️ 配置管理

### GET /api/config

获取系统配置

**响应示例:**
```json
{
  "carla_host": "localhost",
  "carla_port": 2000,
  "detect_interval": 1.0,
  "max_scenarios": 1000,
  "risk_thresholds": {
    "critical": 0.7,
    "high": 0.4,
    "medium": 0.2,
    "low": 0.0
  }
}
```

### POST /api/config

更新系统配置

**请求体:**
```json
{
  "carla_host": "192.168.1.100",
  "carla_port": 2000,
  "detect_interval": 0.5
}
```

**响应示例:**
```json
{
  "success": true,
  "message": "配置已更新"
}
```

---

## 🔍 检测管理

### POST /api/detect/run

运行异常检测

**请求体:**
```json
{
  "duration": 60,
  "interval": 1.0,
  "inject_anomalies": true
}
```

**参数说明:**
- `duration` (required): 检测时长，单位秒，范围 [1, 3600]
- `interval` (optional): 采样间隔，单位秒，范围 [0.1, 10]，默认1.0
- `inject_anomalies` (optional): 是否注入异常场景，默认true

**响应示例:**
```json
{
  "success": true,
  "results": [
    {
      "scenario_id": 1,
      "scenario_name": "前车急刹",
      "timestamp": "2026-08-25T11:00:00",
      "ego_x": 10.5,
      "ego_y": 20.3,
      "ego_speed": 15.0,
      "vehicle_count": 3,
      "violations": [
        {
          "code": "RSS-001",
          "rule": "纵向安全距离",
          "message": "紧急制动",
          "level": "CRITICAL"
        }
      ],
      "risk_index": 0.85,
      "risk_level": "CRITICAL",
      "duration_ms": 50.2
    }
  ],
  "stats": {
    "total": 5,
    "critical": 2,
    "high": 1,
    "medium": 2,
    "low": 0
  },
  "total_time": 5.12
}
```

### GET /api/detect/history

获取检测历史

**查询参数:**
- `limit` (optional): 返回记录数，默认50

**响应示例:**
```json
{
  "history": [...],
  "stats": {
    "total": 50,
    "critical": 10,
    "high": 15,
    "medium": 20,
    "low": 5
  },
  "total": 50
}
```

### GET /api/detect/latest

获取最新的检测结果

**响应示例:**
```json
{
  "scenario_id": 10,
  "scenario_name": "行人横穿",
  "timestamp": "2026-08-25T11:05:00",
  "ego_x": 0,
  "ego_y": 0,
  "ego_speed": 15.0,
  "vehicle_count": 2,
  "violations": [...],
  "risk_index": 0.92,
  "risk_level": "CRITICAL",
  "duration_ms": 45.3
}
```

---

## 📊 知识图谱

### GET /api/kg/latest

获取最新的知识图谱数据

**响应示例:**
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
  ],
  "generated_at": "2026-08-25T11:00:00",
  "node_count": 2,
  "edge_count": 1
}
```

### GET /api/kg/generate

生成知识图谱HTML

**响应示例:**
```json
{
  "success": true,
  "html_path": "/output/knowledge_graph.html",
  "timestamp": "2026-08-25T11:00:00"
}
```

---

## 🔥 WebSocket 推送

### WebSocket: /api/ws/detection

实时推送检测结果

**连接示例:**
```javascript
const ws = new WebSocket('ws://localhost:8000/api/ws/detection');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('检测结果:', data);
};
```

**推送消息:**
```json
{
  "type": "detection",
  "data": {
    "scenario_id": 1,
    "scenario_name": "前车急刹",
    "risk_level": "CRITICAL",
    "risk_index": 0.85,
    "timestamp": "2026-08-25T11:00:00"
  }
}
```

**心跳消息:**
```json
{
  "type": "heartbeat",
  "timestamp": "2026-08-25T11:00:00"
}
```

---

## 📂 文件下载

### GET /output/{filename}

下载输出文件

**示例:**
```
GET /output/knowledge_graph.html
GET /output/report_20260825.html
```

**响应:** 文件二进制流

---

## 🚨 错误代码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未授权 |
| 404 | 资源未找到 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用 |

### 错误响应示例:
```json
{
  "success": false,
  "error": "CARLA服务器未连接",
  "code": "CARLA_CONNECTION_FAILED"
}
```

## 📈 错误处理

### 常见错误

1. **CARLA_SERVER_NOT_CONNECTED**
   - 原因: CARLA服务器未启动或不可达
   - 解决: 启动CARLA或启用注入模式

2. **DETECTION_TIMEOUT**
   - 原因: 检测超时
   - 解决: 增加timeout参数或检查网络

3. **INVALID_SCENARIO**
   - 原因: 无效的场景配置
   - 解决: 检查scenario参数

## 📊 响应时间

| 端点 | 平均响应时间 | P95响应时间 |
|-----|-------------|------------|
| /api/health | < 10ms | < 50ms |
| /api/config | < 20ms | < 100ms |
| /api/detect/run | 50-500ms | < 1000ms |
| /api/detect/latest | < 30ms | < 100ms |
| /api/kg/latest | < 100ms | < 300ms |
| /api/kg/generate | 100-300ms | < 500ms |

## 🔄 版本历史

| 版本 | 日期 | 更改 |
|-----|------|------|
| 2.0.0 | 2026-08-25 | 初始版本，前后端分离 |
| 1.0.0 | 2026-08-19 | 初始版本，单体架构 |