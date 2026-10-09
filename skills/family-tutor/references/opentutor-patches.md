# Patch: OpenTutor Custom Provider Health Check

## 文件: D:\projects\OpenTutor\apps\api\services\llm\providers\openai_client.py

### 问题
"custom" provider 在 `_NO_STREAM_OPTIONS` 集合中，导致 ping() 走本地 backend 探测路径（GET /models 不带 auth header），MIMO 等云 API 返回 401。

### 修复
在 ping() 方法中，找到：
```python
async with httpx.AsyncClient(timeout=5.0) as http:
    resp = await http.get(f"{base}/models")
```

替换为：
```python
headers = {}
if self.provider_name == "custom" and self.client.api_key:
    headers["Authorization"] = f"Bearer {self.client.api_key}"
async with httpx.AsyncClient(timeout=5.0, headers=headers) as http:
    resp = await http.get(f"{base}/models")
```

# OpenTutor Bridge API

## 文件: D:\projects\OpenTutor\apps\api\routers\bridge.py (新建)

提供两个端点：
- `GET /api/bridge/review-topic` — 分析未掌握的错题，生成OpenMAIC强化主题字符串
- `GET /api/bridge/progress-summary` — 学习进度概览（课程数、测验题数、正确率、薄弱知识点数）

## 注册路由
在 `D:\projects\OpenTutor\apps\api\services\router_registry.py` 中：
1. 添加 `bridge` 到 import 列表
2. 添加 `(bridge.router, "/api/bridge", ["bridge"])` 到 CORE_ROUTERS
