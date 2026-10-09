# Open Design 安装与配置

## 项目信息
- GitHub: nexu-io/open-design (75K★)
- 类型: 桌面应用 + CLI + MCP服务器（Figma替代品）
- 源码: D:\projects\open-design\
- 版本: 0.12.1

## 环境要求
- Node.js 24+（系统默认v22不够，需nvm切换）
- Windows需要VS Build Tools（better-sqlite3 node-gyp编译）
- OD_API_TOKEN（daemon认证token）

## 安装步骤

### 1. 安装Node.js 24
```bash
nvm install 24
nvm use 24.18.0
```
**注意**: bash下PATH不生效，必须用cmd.exe执行所有Node.js命令

### 2. 克隆并安装依赖
```bash
cd D:\projects
git clone --depth 1 https://github.com/nexu-io/open-design.git
cd open-design
cmd.exe /c "cd /d D:\projects\open-design && set PATH=C:\Users\MR\AppData\Local\nvm\v24.18.0;%PATH% && corepack enable && pnpm install --ignore-scripts"
```

### 3. 编译原生模块
```bash
cmd.exe /c "cd /d D:\projects\open-design\node_modules\.pnpm\better-sqlite3@12.10.0\node_modules\better-sqlite3 && set PATH=C:\Users\MR\AppData\Local\nvm\v24.18.0;%PATH% && npm run build-release"
```

### 4. 编译Daemon
```bash
cmd.exe /c "cd /d D:\projects\open-design\apps\daemon && set PATH=C:\Users\MR\AppData\Local\nvm\v24.18.0;%PATH% && pnpm exec tsc -p tsconfig.json"
```

### 5. 生成API Token
```bash
openssl rand -hex 32
```

### 6. 启动Daemon
```bash
cmd.exe /c "cd /d D:\projects\open-design\apps\daemon && set PATH=C:\Users\MR\AppData\Local\nvm\v24.18.0;%PATH% && set OD_API_TOKEN=<token> && node dist/cli.js --no-open --port 7456"
```

### 7. 启动Web UI（端口3010避免和OpenMAIC冲突）
```bash
cmd.exe /c "cd /d D:\projects\open-design\apps\web && set PATH=C:\Users\MR\AppData\Local\nvm\v24.18.0;%PATH% && pnpm exec next dev --turbopack -p 3010"
```

## Daemon API（推荐使用方式）

### 跳过引导（关键！）
MIMO不支持`/v1/models`端点，浏览器引导流程会卡在"继续"按钮。用API跳过：
```bash
curl -X PUT http://127.0.0.1:7456/api/app-config \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"onboardingCompleted":true}'
```

### 设置BYOK配置（MIMO）
```bash
curl -X PUT http://127.0.0.1:7456/api/app-config \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"mode":"byok","apiProtocol":"openai","apiKey":"<mimo-key>","baseUrl":"https://token-plan-cn.xiaomimimo.com/v1","model":"mimo-v2.5-pro","onboardingCompleted":true}'
```

### 创建项目
```bash
PROJECT_ID=$(python -c "import uuid; print(uuid.uuid4())")
curl -X POST http://127.0.0.1:7456/api/projects \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d "{\"id\":\"$PROJECT_ID\",\"name\":\"项目名\",\"skillId\":null,\"designSystemId\":null}"
```
返回: `{"project":{...},"conversationId":"<cid>"}`

### 发送设计指令
```bash
curl -X POST http://127.0.0.1:7456/api/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d "{\"projectId\":\"<pid>\",\"conversationId\":\"<cid>\",\"message\":\"设计描述\",\"agentId\":\"opencode\"}"
```

**可用agentId**: `opencode`（已验证可用）、`hermes`

**返回**: SSE流，包含start/agent(text_delta/status)/diagnostic/end事件

### 产出文件位置
```
D:\projects\open-design\.od\projects\<project-id>\
  ├── index.html
  └── index.html.artifact.json
```

## 浏览器自动化问题

### 引导流程
- "继续"按钮需要连接测试通过（不只是选模型）→ 用API跳过
- "拉取模型"无效（MIMO不支持/v1/models）→ 用API设置
- React/Lexical组件：browser_type不触发onChange → 用API代替
- 目录选择器弹出系统对话框 → 无法自动化

### 推荐工作流
1. daemon API跳过引导 + 设置BYOK
2. daemon API创建项目 + 发送设计指令
3. 产出在.od/projects/目录
4. 可选：打开Web UI查看（localhost:3010）

## Pitfalls
1. Node.js必须v24，bash下PATH不生效用cmd.exe
2. better-sqlite3需手动编译（npm run build-release）
3. MIMO不支持/v1/models→用API跳过引导
4. Web UI端口3000和OpenMAIC冲突→用3010
5. OD_API_TOKEN必须设，否则CLI返回401
6. 浏览器自动化无法触发React组件→用daemon API
7. 产出文件在.od/projects/目录
8. **⚠️ Node 24会污染PATH导致OpenMAIC的pnpm dev失败** — 用完Open Design后必须切回Node 22，或在启动脚本中显式set PATH
