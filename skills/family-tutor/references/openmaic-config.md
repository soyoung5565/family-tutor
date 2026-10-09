# OpenMAIC配置参考

## 当前配置（2026-07-09 切到 MiniMax）

- **LLM**: MiniMax-M3（Anthropic-compatible endpoint）
- **TTS**: 继续用 MIMO `mimo-v2.5-tts` 走本地代理（MiniMax 没 TTS）
- **ASR**: 浏览器原生（OpenMAIC 用不上 MiniMax ASR）
- **Web Search**: 百度千帆 + Tavily 备用

## MiniMax 配置（OpenMAIC官方集成）

OpenMAIC 内置 MiniMax provider，`LLM_ENV_MAP` 含 `MINIMAX → minimax`。配置 env：

```bash
MINIMAX_API_KEY=sk-cp-...
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic/v1
MINIMAX_MODELS=MiniMax-M3,MiniMax-M2.7-highspeed,MiniMax-M2.7
DEFAULT_MODEL=minimax:MiniMax-M3
ALLOW_LOCAL_NETWORKS=true
```

### 验证 provider 真的加载（必做！）

光改 `.env.local` 不算数，OpenMAIC 启动时按 `LLM_ENV_MAP` 转 env 为 provider：

```bash
# 1. 看启动日志，确认加载成功：
#    [ServerProviderConfig] Loaded (server-providers.yml): N LLM, ...
#    N>=1 且含 minimax

# 2. 查 API（最可靠）：
curl http://localhost:3000/api/server-providers | python -m json.tool
# 应看到 "providers": {"minimax": {"models": ["MiniMax-M3", ...]}}

# 3. 端到端冒烟测试（fast 模式 ~3 分钟）：
curl -X POST http://localhost:3000/api/generate-classroom \
  -H "Content-Type: application/json" \
  -d '{"requirement":"翻译《宿建德江》",
       "agentMode":"fast","enableWebSearch":false,"enableTTS":false}'
# 轮询 jobId 直到 succeeded
```

如果 `/api/server-providers` 返回 `"providers": {}` 或不含 minimax：
- 检查 `MINIMAX_API_KEY` 拼写（注意是 `MINIMAX_` 不是 `MINIMAX_`）
- 检查 `.env.local` 是否在 `process.cwd()`（即 OpenMAIC 根目录）
- 重启 OpenMAIC 才生效

### UI 一键配置（比手改 .env.local 可靠）

OpenMAIC 顶栏 → 设置（齿轮）→ Provider 选 MiniMax → 填 API Key → 一键自动配置 LLM + base URL + 默认模型。**配置存在浏览器 localStorage**（用户前台），不影响服务端 `.env.local`。其他 Hermes 会话看不到这个配置。

## TTS/ASR配置（MIMO → 本地代理）

**MIMO的TTS/ASR API格式跟OpenAI不一样，不能用OpenAI TTS/ASR provider！**

| API | OpenAI格式 | MIMO格式 |
|-----|-----------|----------|
| TTS | `POST /v1/audio/speech` | `POST /v1/chat/completions` + `modalities: ["text", "audio"]` |
| ASR | `POST /v1/audio/transcriptions` | MIMO自有格式 |

**症状**：OpenAI TTS/ASR provider配MIMO endpoint会报"Not Found"错误。

**解决方案（二选一）**：

### 方案A：浏览器原生（简单，语音质量一般）
1. 打开 localhost:3000 → 点右上角齿轮 → 语音合成
2. 左侧选"浏览器原生 TTS" → 打开开关 → 保存
3. 左侧选"语音识别" → 选"浏览器原生 ASR" → 保存

### 方案B：MIMO TTS代理（推荐，语音质量好）
1. 启动代理：`python D:/projects/family-tutor/mimo-tts-proxy.py`（端口8787）
2. 在OpenMAIC设置中选"OpenAI TTS"
3. Base URL改为 `http://127.0.0.1:8787/v1`
4. API Key填MIMO的key
5. 保存

**注意：TTS代理必须在OpenMAIC之前启动，否则TTS报连接失败。**

## 联网搜索配置

.env.local中配置搜索provider的key：
```
BAIDU_API_KEY=bce-v3/ALTAK-xxx/<secret>
BAIDU_BASE_URL=https://qianfan.baidubce.com
TAVILY_API_KEY=tvly-dev-xxx
```

浏览器设置→网络搜索→选择要用的provider→保存。
支持的provider：Tavily、博查、Brave、百度、MiniMax、豆包。

## 课堂生成API

### 创建课堂
```bash
curl -X POST http://localhost:3000/api/generate-classroom \
  -H "Content-Type: application/json" \
  -d '{
    "requirement": "教学内容描述...",
    "enableWebSearch": true,
    "enableTTS": true,
    "agentMode": "deep"
  }'
```
返回 `{jobId, status, pollUrl}`

### 轮询状态
```bash
curl http://localhost:3000/api/generate-classroom/{jobId}
```
status: queued → running (generating_outlines → generating_scenes) → succeeded

**生成时间参考**：
- fast 模式 + 不开联网/TTS: ~3 分钟
- deep 模式 + 联网 + TTS: ~5-15 分钟
- deep 模式 + 联网 + TTS + 14 页左右 PPT: 通常 7-10 分钟

## PDF解析API

```bash
curl -X POST http://localhost:3000/api/parse-pdf \
  -F "pdf=@file.pdf" \
  -F "providerId=unpdf"
```
返回 `{text, images: [base64...], fileName, fileSize}`
- 扫描版PDF：text为空，images有每页的base64图片
- 文字版PDF：text有提取的文字

## .env.local完整配置模板（MiniMax方案）
```
# LLM (MiniMax Anthropic-compatible)
MINIMAX_API_KEY=sk-cp-...
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic/v1
MINIMAX_MODELS=MiniMax-M3,MiniMax-M2.7-highspeed,MiniMax-M2.7
DEFAULT_MODEL=minimax:MiniMax-M3
ALLOW_LOCAL_NETWORKS=true

# 搜索（按优先级）
BAIDU_API_KEY=bce-v3/ALTAK-xxx/<secret>
BAIDU_BASE_URL=https://qianfan.baidubce.com
TAVILY_API_KEY=tvly-dev-xxx

# TTS（通过代理，端口8787）
TTS_OPENAI_API_KEY=tp-...
TTS_OPENAI_BASE_URL=http://127.0.0.1:8787/v1

# ASR不需要配——用浏览器原生
```

## Pitfalls
1. **OpenAI TTS/ASR不能用于MIMO** — API格式不同，会报Not Found
2. **.env.local改完要重启OpenMAIC** — 不会热更新
3. **"服务端托管"的provider不能在浏览器修改** — 需要改.env.local
4. **课堂生成需要5-15分钟（deep）或 3分钟（fast）** — 内容多时更长，需要轮询等待
5. **链接在Hermes聊天中被过滤** — 不能直接发http链接，需要用Edge CDP打开用户浏览器
6. **TTS/ASR启用状态存在浏览器localStorage** — .env.local只配provider后端（API Key/URL），但**启用哪个provider（OpenAI vs 浏览器原生）存在浏览器localStorage**。后台浏览器改设置不会同步到用户浏览器！必须用Edge CDP操控用户前台浏览器来改设置。
7. **课堂生成用API比浏览器更可靠** — "导入课堂"按钮会弹文件选择器，headless浏览器无法操作。用`/api/parse-pdf` + `/api/generate-classroom` API代替。
8. **Node.js版本冲突** — OpenMAIC需要Node 22，启动脚本必须`set PATH=...\\v22.22.0;%PATH%`
9. **TTS代理必须在OpenMAIC之前启动** — 否则TTS报连接失败
10. **课堂生成提示词优化** — 如果每页都有"同学们好"开场白，需要修改OpenMAIC提示词模板。详见 `references/openmaic-prompt-templates.md`
11. **多会话切换 provider 后必须验证"实际加载"** — `.env.local` 改完不算数，要重启 OpenMAIC → 查启动日志含 `N LLM` 和 minimax → `/api/server-providers` 返回 minimax 配置 → fast 模式冒烟测试。其他会话的修改当前会话看不到，必须实读文件验证
12. **MINIMAX_API_KEY 中的 `MINIMAX` 是 OpenMAIC 默认前缀，不能改** — LLM_ENV_MAP 写死的，env 中其他前缀都不会被识别

## 操控用户前台浏览器

**用户多次强调：必须操控前台Edge浏览器，不能用后台headless浏览器。**

### 为什么不能用 browser_navigate？
`browser_navigate` 打开的是 headless Chromium 后台浏览器，用户看不到。用户需要在自己的 Edge 浏览器中看到和操作页面。

### 正确方法：Edge CDP 连接
```bash
# 1. 关闭所有 Edge 进程
taskkill /F /IM msedge.exe

# 2. 用调试端口重启 Edge（保留用户 profile）
"/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
  --remote-debugging-port=9222 \
  --user-data-dir="D:/edge_debug_profile" \
  --no-first-run http://localhost:3000

# 3. 验证端口
netstat -an | grep 9222  # 必须显示 LISTENING
```

### Playwright CDP 连接
```python
from playwright.sync_api import sync_playwright
pw = sync_playwright().start()
browser = pw.chromium.connect_over_cdp('http://127.0.0.1:9222')
context = browser.contexts[0]
page = context.pages[0] if context.pages else context.new_page()
page.goto('http://localhost:3000')
# 操作页面...
pw.stop()
```

### 修改 localStorage 设置
```python
page.evaluate('''() => {
    const data = JSON.parse(localStorage.getItem('settings-storage'));
    data.state.ttsProvidersConfig['openai-tts'] = {
        apiKey: 'xxx',
        baseUrl: 'http://127.0.0.1:8787/v1',
        enabled: true,
        isServerConfigured: false,
        serverDisabled: false
    };
    data.state.ttsProviderId = 'openai-tts';
    data.state.ttsEnabled = true;
    localStorage.setItem('settings-storage', JSON.stringify(data));
}''')
page.reload()  # 刷新生效
```
