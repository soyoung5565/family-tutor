# OpenMAIC Debug Recipes（2026-07-09 实证修正版）

调试 OpenMAIC 问题时先翻这个，再问用户。**这一版纠正了之前"minimax sk-cp- 不能调 TTS/Image"的错误结论**——OAuth 路线能通。

---

## ⚠️ 第一铁律：前端配置 ≠ 服务端配置（最常踩的坑！）

**OpenMAIC 把 provider 配置拆成两层**：
- **浏览器 localStorage**：存「用哪个 provider + 启用开关」（用户在前端配置页里改）
- **服务端 .env.local**：存「API key + base URL」（Hermes 改）

**用户在前端选 minimax-tts 并开了开关 ≠ 服务端能调通**。

**诊断价值示例**（2026-07-09 实际犯过）：
- 用户报"没声音"
- 我猜："可能你生成时没打开 `enableTTS`"
- **实际**：用户前端早就开了，是服务端 `.env.local` 缺 `TTS_MINIMAX_API_KEY` → `/api/generate/tts` 返回 500
- **根因**：课件调服务端 API；配置页 TTS 按钮**前端直调** provider（绕过服务端）

**诊断步骤**（每次报"没声音/不出图/搜索没结果"先跑这套）：
1. **看启动日志**确认服务端真的加载到 provider：
   ```
   [ServerProviderConfig] [ServerProviderConfig] Loaded (server-providers.yml): N LLM, M TTS, K Image, ...
   ```
   N/M/K > 0 才是真的加载。**这是最可靠的信号，不要看到 curl 返回 0 立即结论**
2. **curl `/api/server-providers`** 看具体 provider 列表
3. **直接调服务端 API 验证 key**（minimax 慢，30-60s 不是卡死）：
   ```bash
   curl --max-time 90 -X POST http://localhost:3000/api/generate/tts \
     -H "Content-Type: application/json" \
     -d '{"text":"测试","audioId":"dbg1","ttsProviderId":"minimax-tts","ttsVoice":"Chinese (Mandarin)_Crisp_Girl"}' \
     -o /tmp/dbg.wav -w "minimax-tts: HTTP %{http_code}, size=%{size_download}\n"
   ```
   - HTTP 200 + size > 0 = 通
   - HTTP 500 + body 含 `API key required` = 服务端缺 key
   - HTTP 500 + body 含 `login fail: Please carry the API secret key` (1004) = **key 类型错**（见下节）
   - HTTP 000 = timeout（minimax 慢，加大 max-time）

---

## ⚠️ minimax key 类型的真相（2026-07-09 实证最终结论）

之前认为"minimax 一 key 不通吃，sk-cp- 不能调 TTS/Image"是错的。**真相**：

| Key 格式 | 能调什么 | 用在哪 |
|---------|---------|--------|
| `sk-cp-...` | **只** Anthropic 兼容端点（LLM） | `MINIMAX_API_KEY` → `https://api.minimaxi.com/anthropic/v1/messages` |
| `oat-...` | minimax **原生 API**（TTS/Image/Quota） | `TTS_MINIMAX_API_KEY` / `IMAGE_MINIMAX_API_KEY` → `/v1/t2a_v2`、`/v1/image_generation` |
| `dfrt-...` | OAuth refresh_token | 自动续期 `oat-`，不用直接填 |

**核心洞察**：
- 用户在 minimax 控制台看到的"订阅 Key"(`sk-cp-`) 只能调 LLM
- 调 TTS/Image 必须用 **`mmx auth login` 拿的 OAuth `oat-` access_token**
- 不是去控制台再开"按量计费 key"（那是另一种产品，要单独付费）——**OAuth access_token 是 Token Plan 套餐附带的"原生 API 调用券"**

**错误码对照**：
- `1004 "login fail: Please carry the API secret key"` = 用了 `sk-cp-` 调原生 API（错的）；或 `oat-` 已过期
- `1008` = 余额不足
- `2056 "已达到 Token Plan 用量上限"` = 套餐配额用完，等重置（每周/每月）或升级
- `2049 "无效的 API Key"` = key 错

---

## minimax 完整接入流程（2026-07-09 实证）

### Step 1: 装 minimax CLI
```bash
npm install -g mmx-cli
```

### Step 2: 设 region（**必须** cn，否则 fallback global 然后 1004）
```bash
mmx config set --key region --value cn
mmx config set --key base_url --value https://api.minimaxi.com
```

### Step 3: 用户在终端跑（必须人工操作，浏览器 OAuth 授权）
```bash
mmx auth login --region cn
```
浏览器跳出 minimax 授权页 → 同意 → CLI 把 `oat-...` + `dfrt-...` 存到 `~/.mmx/config.json` 的 `oauth` 字段。

### Step 4: 验证
```bash
mmx auth status
# 应输出: {"method":"oauth", "token_expires":"2026-07-11T12:05:47.441Z"}

mmx speech generate --text "测试" --voice female-shaonv --output-file /tmp/x.mp3
# 应输出: {"saved":"speech_xxx.mp3", "size_bytes":17268, ...}
```

### Step 5: 把 oat- 填到 .env.local
```bash
# 提取
python -c "import json; print(json.load(open(r'C:\Users\MR\.mmx\config.json'))['oauth']['access_token'])"
# 输出 oat-xxxxx
```
```bash
# TTS_MINIMAX_API_KEY=oat-xxxxx
# TTS_MINIMAX_BASE_URL=https://api.minimaxi.com
# IMAGE_MINIMAX_API_KEY=oat-xxxxx（**同一 token**）
# IMAGE_MINIMAX_BASE_URL=https://api.minimaxi.com
```

### Step 6: 重启 OpenMAIC
改完 `.env.local` 必须重启（不是热重载）：
```bash
cmd.exe /c "netstat -ano | findstr :3000 | findstr LISTENING"  # 拿 PID
cmd.exe /c "taskkill /F /PID <PID>"
cmd.exe /c "cd /d D:\projects\OpenMAIC && set PATH=C:\Users\MR\AppData\Local\nvm\v22.22.0;%PATH% && pnpm dev"
```

### Step 7: 验证服务端
```bash
curl http://localhost:3000/api/server-providers | python -m json.tool
# 应包含:
#   "providers": {"minimax": {"models": ["MiniMax-M3", ...]}}
#   "tts": {"minimax-tts": {}}
#   "image": {"minimax-image": {}}
```

### Step 8: 端到端测 TTS
```bash
curl --max-time 30 -X POST http://localhost:3000/api/generate/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"今天我们学习古诗词三首","audioId":"e2e","ttsProviderId":"minimax-tts","ttsVoice":"Chinese (Mandarin)_Crisp_Girl"}' \
  -o /tmp/t.wav -w "HTTP %{http_code}, size=%{size_download}, time=%{time_total}s\n"
# 期望: HTTP 200, size 几十KB, time 2-3s
```

### Step 9: 端到端测 Image
```bash
mmx image generate --prompt "A cute cat" --output-file /tmp/cat.png
# 期望: saved ["image_001.jpg"], < 10s
```

---

## OAuth token 续期（生成课件前必做！）

**`oat-` access_token 有效期约 48 小时**（不是 8-30 天）。过期后：
- `mmx auth status` 报 `"API key rejected (HTTP 401)"`
- OpenMAIC 调 TTS/Image 返回 500 (1004)

**续期流程**（再跑一次 `mmx auth login`，CLI 用 refresh_token 自动换 access_token，**不需要重新浏览器授权**）：
```bash
mmx auth login --region cn
# 这次会秒过（refresh_token 自动续期）
```

**生成课件前必做**：从 `~/.mmx/config.json` 读新 `oat-` token，写到 `.env.local`，重启 OpenMAIC：
```python
import json, re, datetime
d = json.load(open(r'C:\Users\MR\.mmx\config.json'))
at = d.get('oauth', {}).get('access_token')
exp = d.get('oauth', {}).get('expires_at', '')
if not at:
    print('NEED_LOGIN: 跑 mmx auth login --region cn')
    exit(1)
if exp:
    ed = datetime.datetime.fromisoformat(exp.replace('Z', '+00:00'))
    if ed < datetime.datetime.now(datetime.timezone.utc):
        print('EXPIRED: 先跑 mmx auth login --region cn 续期')
        exit(1)
fp = r'D:\projects\OpenMAIC\.env.local'
content = open(fp, encoding='utf-8').read()
content = re.sub(r'TTS_MINIMAX_API_KEY=.*', f'TTS_MINIMAX_API_KEY={at}', content)
content = re.sub(r'IMAGE_MINIMAX_API_KEY=.*', f'IMAGE_MINIMAX_API_KEY={at}', content)
open(fp, 'w', encoding='utf-8').write(content)
print(f'OK: 同步到 .env.local, 剩余 {ed - datetime.datetime.now(datetime.timezone.utc)}')
```
然后**必须重启** OpenMAIC 生效。

---

## TTS 音频资产存储路径（前端播放机制，2026-07-09 实证）

课堂生成时如果 `enableTTS: true`，OpenMAIC **预生成**音频文件：
- 存到：`D:\projects\OpenMAIC\data\classroom-media\{classroomId}\audio\tts_s{sceneIdx}_action_{actionId}.mp3`
- `actions[i].audioUrl` 字段写 `/api/classroom-media/{classroomId}/audio/{filename}`
- **前端播放直接走 audioUrl，不实时调 TTS API**

**诊断"没声音"步骤**：
1. 打开 `D:\projects\OpenMAIC\data\classrooms\{classroomId}.json`
2. grep `audioUrl`：有没有？没有 = 生成时没开 TTS（必须 `enableTTS: true` 重新生成）
3. 有 audioUrl 但浏览器 404 = 音频文件没存到对应路径
4. 有 audioUrl 且 200 但没声音 = 浏览器音频自动播放被禁（需要用户先点页面）

**`enableTTS: false` 翻车陷阱**（pitfall 28）：speech action 只有 `{id, type:'speech', text}` 三个字段，无 audioUrl。**永远用 `enableTTS: true` 一次到位**。

---

## 默认 TTS voice 配置（2026-07-09 改）

OpenMAIC 默认 voice 在 `lib/audio/constants.ts:1284` 的 `DEFAULT_TTS_VOICES`：
```ts
'minimax-tts': 'Chinese (Mandarin)_Crisp_Girl',  // 用户试听挑的
```

**改默认 voice**：
1. 修改 `lib/audio/constants.ts:1284`
2. **必须重启 OpenMAIC**（.ts 是编译的）
3. 重新生成课件生效

**前端 localStorage 的 `ttsProviderId` 覆盖默认**（如果用户前端配过，会用 localStorage 里的）。

**minimax 完整音色库**：303 个，`mmx speech voices` 列出。中文女声适合儿童的推荐（按用户试听反馈排序）：
1. `Chinese (Mandarin)_Crisp_Girl`（干脆女孩）⭐ 用户选
2. `Chinese (Mandarin)_Warm_Girl`（温暖少女）
3. `Chinese (Mandarin)_Soft_Girl`（温柔女孩）
4. `Chinese (Mandarin)_Cute_Spirit`（灵气少女）
5. `female-shaonv`（基本款少女）
6. `Chinese (Mandarin)_Lyrical_Voice`（抒情声线）

**选 voice 流程**：用 `mmx speech generate --voice <id> --output-file /tmp/x.mp3` 各生成一段对比试听。

---

## 课件内容质量审查（不靠肉眼）

**问题**：用户报 "课件好多英文 / 内容不对" — 不要假设模型 bug。

**步骤**：
1. 找课堂 ID：`/classroom/<id>` URL
2. 读 JSON：
   ```python
   import json
   d = json.load(open(r'D:/projects/OpenMAIC/data/classrooms/<id>.json','r',encoding='utf-8'))
   scenes = d['scenes']  # 7-15 个
   ```
3. 检查讲稿（`scenes[].actions[].type='speech'.text`）：
   ```python
   for s in scenes:
       speeches = [a['text'] for a in s['actions'] if a.get('type')=='speech']
       print(s.get('title',''), '|', speeches[0][:100] if speeches else '<NO SPEECH>')
   ```
4. 检查元素文字（`scenes[].content.canvas.elements[].content` 是 HTML 片段）：
   ```python
   import re
   def find_zh(obj):
       if isinstance(obj, str) and len(obj)>30 and re.search(r'[一-龥]', obj): yield obj
       elif isinstance(obj, dict):
           for v in obj.values(): yield from find_zh(v)
       elif isinstance(obj, list):
           for v in obj: yield from find_zh(v)
   ```
5. **结论判断**：
   - 讲稿都是中文 + 元素有英文 → **requirement 歧义**（"翻译"被理解成英译对照课），重写 requirement
   - 讲稿也有英文 → 模型选错（不该用英文 LLM），检查 model

---

## "每页问候语"问题（系统 prompt 不够，2026-07-09 实证）

**症状**：每页 PPT 开头都写"同学们好"（即使 system prompt 写"只有第1页问候"）。

**原因**：
- OpenMAIC 每个 scene 是**独立 LLM call**（persona 跨 call 不记忆）
- agent persona（`lib/orchestration/registry/store.ts` 的 `DEFAULT_AGENTS['default-1']`）和 system.md 都允许问候
- M3 训练数据里教师角色习惯问候

**实际解决方案**（**不要只改 prompt**——治标不治本）：
1. **改 system.md 强规则**（`lib/prompts/templates/slide-actions/system.md`）："NEVER use a greeting on ANY page"
2. **改 agent persona**（`lib/orchestration/registry/store.ts`）：同步禁止
3. **⚠️ 关键：在 `processActions` 加 post-processor 自动 strip**（`lib/generation/scene-generator.ts:1854`）：
   ```ts
   if (processedAction.type === 'speech' && typeof processedAction.text === 'string') {
     const GREETING_PATTERNS = [
       /^同学们好[，！。,!\.\s]*/,
       /^同学们大家好[，！。,!\.\s]*/,
       /^大家好[，！。,!\.\s]*/,
       /^欢迎来到[^\n，。！？,.\!?]{0,20}[，！。,!\.\s]*/,
       /^欢迎大家来到[^\n，。！？,.\!?]{0,20}[，！。,!\.\s]*/,
       /^hello\s+everyone[，！。,!\.\s]*/i,
       /^hi\s+everyone[，！。,!\.\s]*/i,
     ];
     for (const pat of GREETING_PATTERNS) {
       if (pat.test(processedAction.text)) {
         processedAction.text = processedAction.text.replace(pat, '');
         break;
       }
     }
   }
   ```
   关键：**post-processor 必须在 TTS 生成之前**（`processActions` → `generateTTSForClassroom` → `persistClassroom`）。

---

## "scene-generator 漏传 ctx" 修复（已修，2026-07-09）

`generateFullScenes` 调 `generateSingleScene` 时没传 `SceneGenerationContext`（pageIndex/totalPages/allTitles/previousSpeeches），LLLM 看不到 `Position: Page N of M`，**默认自己是第一页**每页都问候。

**修复**（`lib/generation/scene-generator.ts:139`）：
```ts
const sceneId = await generateSingleScene(
  outline, api, aiCall, languageDirective,
  {
    pageIndex: index + 1,
    totalPages: totalScenes,
    allTitles: sceneOutlines.map((o) => o.title),
    previousSpeeches: [],  // TODO: 传前几页 speech
  },
);
```

---

## Provider 加载验证

**问题**：改了 `.env.local` 重启 OpenMAIC，curl `/api/server-providers` 还返回 0 个 provider

**判断标准**：
1. **看启动日志**（不是 curl API）：
   ```
   [ServerProviderConfig] [ServerProviderConfig] Loaded (server-providers.yml): 2 LLM, 1 TTS, 0 ASR, ...
   ```
   N > 0 才是真的加载。日志不会骗人
2. **curl 第一次返回 0 是可能的** — Next.js dev 缓存 + hot-reload。再 curl 一次或重启

---

## Minimax 配置配方

最小 `.env.local`：
```bash
# LLM（Anthropic 兼容）
MINIMAX_API_KEY=sk-cp-...T_4g
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic/v1
MINIMAX_MODELS=MiniMax-M3,MiniMax-M2.7-highspeed,MiniMax-M2.7
DEFAULT_MODEL=minimax:MiniMax-M3

# TTS/Image（minimax OAuth access_token）
TTS_MINIMAX_API_KEY=oat-...
TTS_MINIMAX_BASE_URL=https://api.minimaxi.com
IMAGE_MINIMAX_API_KEY=oat-...（同 TTS）
IMAGE_MINIMAX_BASE_URL=https://api.minimaxi.com

# WebSearch 百度优先
BAIDU_API_KEY=bce-v3/ALTAK-xxx/secret
BAIDU_BASE_URL=https://qianfan.baidubce.com
# Tavily 备用
TAVILY_API_KEY=tvly-dev-xxx
```

**M3 思考深度只能是 adaptive**（minimax API 不支持 max；这个限制在 `lib/ai/model-metadata.ts:228` 的 `minimaxM3Thinking` 已写死）。

---

## 服务稳定性

**Hermes 退出/重启 = OpenMAIC 进程死亡**（除非独立服务化）。每次会话前先看服务还在不在：
```bash
cmd.exe /c "netstat -ano | findstr :3000" | head -3
# 看到 LISTENING 就有
```
没看到就重启。

**start-tutor.bat 必须包含启动顺序**：OpenTutor → TTS Proxy → OpenMAIC。
