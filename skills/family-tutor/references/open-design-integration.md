# Open Design 集成指南（2026-07-10 实证更新）

## 概述
Open Design 是 Claude Design 的开源替代，用于生成精美的 HTML 页面。
**⚠️ 用户强制要求：所有页面美化必须用 Open Design，不要手写 CSS。**
用户原话："不要你自己优化，我指定了open design就不要用别的"

## 启动方式

### 正确启动（pnpm tools-dev）
```bash
# 先停止旧进程
cd /d/projects/open-design && C:/Users/MR/AppData/Local/nvm/v24.18.0/npx pnpm tools-dev stop web

# 启动 daemon + web
cd /d/projects/open-design && C:/Users/MR/AppData/Local/nvm/v24.18.0/npx pnpm tools-dev start web
```

启动输出示例：
```
- daemon: started · running · http://127.0.0.1:60462 · pid 8080
- web: started · running · http://127.0.0.1:60463 · pid 14016
```

**注意：端口每次启动可能不同（60462/60463 等），看启动输出。**

### 错误启动方式（不要用）
- ❌ `node dist/cli.js --no-open` — 只启动 daemon，没有 web UI
- ❌ 直接访问 `http://127.0.0.1:7456` — 默认端口可能没在用

## Web UI 使用流程（完整步骤）

### 1. 打开 Web UI
```bash
cmd.exe /c "start http://127.0.0.1:<port>"
```
或用 `browser_navigate` 打开。

### 2. 输入设计需求
在输入框输入中文描述，例如：
```
设计一个温暖明亮的课后测验答题网页，适合小学生使用。风格：圆润可爱，使用柔和的渐变色（浅蓝、浅紫、浅绿），大字体，卡通图标，友好的交互反馈。
```

点击"发送"按钮（ref 通常是页面底部的"运行"或"发送"按钮）。

### 3. 回答表单问题（Open Design 会弹出确认表单）
Open Design 会弹出确认表单，包含：
- **"我们要做什么？"** → 选 **Prototype**（单页原型）
- **"目标平台"** → 选 **响应式网页**
- **"目标用户"** → 填具体描述（如"小学六年级学生，语文课后测验"）
- **"大概需要多少内容？"** → 填具体数量（如"8道选择题 + 2道简答题，含结果页和知识点分析"）
- **"品牌背景"** → 选"帮我选一个方向"
- **"还有什么需要知道的吗？"** → 可选填

**快速跳过**：点"一键跳过"按钮可跳过所有问题直接生成（有倒计时，到时自动继续）。

### 4. 等待生成
生成时间 1-3 分钟，取决于模型速度。
状态显示："准备中…" → "思考中" → "执行中" → "已完成"

### 5. 复制生成文件
生成完成后，聊天界面会显示文件路径：
```
写入 D:\projects\open-design\.od\projects\<project-id>\index.html · 942 行
```

复制到目标位置：
```bash
cp "D:/projects/open-design/.od/projects/<project-id>/index.html" "D:/projects/family-tutor/quiz.html"
```

### 6. 更新题目数据（如用于测验）
Open Design 生成的是示例题目，需要替换为实际测验题。
用 Python 脚本替换 `QUESTIONS` 数组（参考 `quiz-data-day{N}.json`）。

## CLI 命令参考

### od 命令（bin/od.mjs）
```bash
# 启动 daemon + web（推荐）
cd /d/projects/open-design && C:/Users/MR/AppData/Local/nvm/v24.18.0/npx pnpm tools-dev start web

# 停止
cd /d/projects/open-design && C:/Users/MR/AppData/Local/nvm/v24.18.0/npx pnpm tools-dev stop web

# 查看帮助
cd /d/projects/open-design/apps/daemon && C:/Users/MR/AppData/Local/nvm/v24.18.0/node.exe bin/od.mjs --help

# 上传文件到项目（注意：只能上传，不能触发设计生成）
cd /d/projects/open-design/apps/daemon && C:/Users/MR/AppData/Local/nvm/v24.18.0/node.exe bin/od.mjs artifacts create --name "file.html" --input "path/to/file.html" --project "<project-id>"

# 创建聊天
cd /d/projects/open-design/apps/daemon && C:/Users/MR/AppData/Local/nvm/v24.18.0/node.exe bin/od.mjs chat new --project "<project-id>" --title "设计名称"
```

### MCP 服务器
```bash
# 启动 MCP 服务器（供 Hermes 等 coding agent 使用）
cd /d/projects/open-design/apps/daemon && C:/Users/MR/AppData/Local/nvm/v24.18.0/node.exe bin/od.mjs mcp --daemon-url http://127.0.0.1:<port>
```

## 设计系统
Open Design 内置 71+ 设计系统，可通过 Web UI 的"不指定设计系统"按钮选择。
常用设计系统：
- **Neutral Modern** — 中性现代风格
- **Warm Editorial** — 温暖编辑风格
- 各品牌设计系统（Apple, Stripe, Linear 等）

## 常见问题

### Q: 生成的设计不满意怎么办？
A: 重新输入不同的提示词再生成一次。可以指定更详细的风格要求（如"温暖明亮""圆润可爱""深色Linear风格"等）。

### Q: 生成时间太长？
A: 正常 1-3 分钟。如果超过 5 分钟，检查 Open Design daemon 是否正常运行。

### Q: 端口冲突？
A: 每次启动端口可能不同，看启动输出。如果冲突，先 `pnpm tools-dev stop web` 再启动。

### Q: Node 版本问题？
A: Open Design 需要 Node 24，OpenMAIC 需要 Node 22。两者不冲突，可同时运行。

### Q: CLI 命令行能直接生成设计吗？
A: 不能。`od artifacts create` 只能上传文件到已有项目，不能触发设计生成。必须通过 Web UI 交互。
