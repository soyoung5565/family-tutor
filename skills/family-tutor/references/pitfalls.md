# Pitfalls 汇总（从 SKILL.md 拆分，2026-09-24）

> 本文件由 SKILL.md 的 `## Pitfalls` 章节拆分而来（原文 39981 字符）。
> 目的：SKILL.md 超过 100K 字符限制，拆分以便继续维护。
> 内容未做任何删改。


## Pitfalls

### 教材处理
1. **不要用目录页码直接裁切** — 书页码≠PDF索引，偏移量不一致，必须用视觉定位"第X单元"字样
2. **不要OCR** — 用MIMO多模态视觉理解，用户明确要求
3. **不要凭空生成内容** — 必须基于真实教材
4. **Hermes提取知识点是为了自己出题** — 不是传给OpenMAIC，也不是传给OpenTutor
5. **上传PDF到OpenMAIC，不要手动输入主题** — 用户多次纠正。用API（/api/parse-pdf + /api/generate-classroom）
6. **OpenTutor已弃用** — 扫描版PDF无法解析、API超时、维护成本高。Hermes直接用MIMO多模态完成所有教学环节（出题、批改、分析薄弱点）
6. **裁切后必须验证页面内容（2026-07-10 实证）** — 用户说"怎么都多了一页"，原因是裁切时没验证页面边界。**裁切后立即用 MIMO 多模态（Pitfall 48）验证**：
    ```bash
    # 提取目标页为 PNG
    python -c "
    import fitz, os
    doc = fitz.open('课本.pdf')
    os.makedirs('verify_pages', exist_ok=True)
    for page_num in [6, 7]:  # 要验证的页码
        page = doc[page_num - 1]
        pix = page.get_pixmap(dpi=150)
        pix.save(f'verify_pages/page_{page_num}.png')
    "
    # 用 MIMO 多模态验证
    node "D:/mimo-multimodal/image_understand.py" \
      --type image --input "verify_pages/page_6.png" \
      --prompt "这是课本的哪一页？有什么内容？" --json
    ```
    **验证后才裁切**，不要裁切后才发现页码错。
75. **提取知识点前先确认课本年级（2026-07-10 实证）** — 用户原话：\"你知道这是小学五年级的数学课本吗？请你在知道背景是小学五年级数学课本的情况下再确定一下？\"。**症状**：我提取的 math_day4 知识点把\"身高分段统计\"写成了五年级内容，但实际 PDF 是**四年级下册**。**正确做法**：用 MIMO 多模态读课本第一页时，**第一句 prompt 必须明确询问年级**：
    ```bash
    node "D:/mimo-multimodal/image_understand.py" \
      --type image --input "verify_math_day4.png" \
      --prompt "这是小学数学课本。请问这是几年级的课本？主要讲什么内容？" --json
    ```
    **为什么要问年级**：不同年级的同一知识点深度不同（如\"分段统计\"四年级是入门，五年级是\"复式统计表\"）。**知识要点文档必须标注年级**，否则补强练习出题难度会错。

75b. **用户纠正：数学课本实际是六年级上册（2026-07-10）** — 用户原话：\"这些全部都是六年级上册的内容。切割的原pdf不是写了吗？我的意思是，这个的背景是小学数学，而不是扫描数据分析师应当学习的内容，重心不要搞错了\"。**症状**：我提取的数学 Day 3 知识点包含了"数据收集"、"数据分析师"等专业表述，把"人口老龄化研究"（小学六年级数学）当成专业数据分析课。**正确做法**：
    - **明确课本的年级**（用 MIPS 多模态询问）
    - **知识要点文档语气要符合年级**——小学生课本用简单语言（如"用分数乘法解决生活中的问题"），不要用专业术语（如"数据分析师"、"数据建模"）
    - **每次提取知识点后必须标注年级**：`## 学习目标（小学六年级上册）`
    - **用户原话**：\"重心不要搞错了\"——背景是小学数学，不是数据分析专业

75c. **minimax M3 会在 'generate' 模式下"自主发挥"生成错误内容（2026-07-10 实证）** — 用户原话：\"agentmode默认切换到支持的最高质量挡位，当前是什么挡位？\" → 用户想要 **`'default'` 模式**（最高质量）。**症状**：`'generate'` 模式下模型会"自主发挥"——你要求"数据的表示和分析（三）- 人口老龄化研究"，模型生成"统计图的选择与应用"（11 个场景全是统计图，跟人口老龄化毫无关系）。**为什么**：`'generate'` 模式倾向快速生成但质量不稳定，模型可能完全忽略 requirement 中的具体主题。**正确做法**：
    - **永远用 `'default'` 模式**（用户明确要求）
    - **生成后必须用 `knowledge-points/{subject}_day{N}.md` 核对内容**（pitfall 61/75a）
    - **如果内容不对，必须重新生成**——不要因为"跑完了"就保留错误内容

### 教材年级核对
6. **操控用户前台浏览器必须用Edge CDP** — `browser_navigate`是headless后台浏览器，用户看不到
7. **OpenMAIC设置存在浏览器localStorage里** — 不是服务端！.env.local只配provider后端，启用哪个provider存在localStorage。必须用Edge CDP操控用户前台浏览器来改设置
8. **浏览器工具无法操作原生文件对话框** — "导入课堂"按钮弹系统文件选择器，headless无法交互。用API代替

### 服务配置
9. ~~**MIMO TTS/ASR不能用OpenAI provider** — MIMO的TTS用chat completions格式~~ — **已废弃，见 Pitfall 37**
10. **Node.js版本冲突** — Open Design需Node 24，OpenMAIC需Node 22。启动脚本必须显式`set PATH=...\\v22.22.0;%PATH%`。**Open Design daemon 启动**：`cd /d/projects/open-design/apps/daemon && C:/Users/MR/AppData/Local/nvm/v24.18.0/node.exe dist/cli.js --no-open`（端口7456）
11. **OpenTutor API必须带尾部斜杠** — 否则307重定向丢body（`/api/courses/` 不是 `/api/courses`）
12. **Hermes重启=服务死亡** — 必须用桌面快捷方式启动独立服务
13. **nvm use不持久** — Windows下必须在bat脚本中显式设置PATH
14. **TTS代理必须在OpenMAIC之前启动** — MIMO TTS 代理（`mimo-tts-proxy.py` 端口 8787）是默认 TTS。**start-tutor.bat 第 2 步必须启动它**，否则 OpenMAIC 启动时 `openai-tts` provider 虽然注册了但调用会连接失败（HTTP 000）
14a. **minimax key 类型不通用（2026-07-09 实证修正）** — 用户的 `sk-cp-` 开头 key **只对 Anthropic 兼容端点** `https://api.minimaxi.com/anthropic/v1` 有效，**不能**用于 minimax 原生 API（`/v1/t2a_v2` TTS、`/v1/image/*` 图片）。错误信息固定为 `status_code: 1004, status_msg: "login fail: Please carry the API secret key in the 'Authorization' field of the request header"`。**正确接 TTS/Image 的方式是用 OAuth `oat-` token**（不是去控制台拿 `ey...` key —— `ey...` 是文档字段名占位符，不是 key 格式）。**OpenMAIC 设计上把"选 provider + 启用开关"放浏览器 localStorage，把"API key + base URL"放服务端 .env.local**：配置页 TTS 按钮能听到声音 ≠ 课件播放有声音——前者前端直接调 provider（绕过服务端 key 解析），后者课件调服务端 `/api/generate/tts`，服务端找不到 key 就 500。**最可靠的诊断信号是 OpenMAIC 启动日志**：`[ServerProviderConfig] Loaded (server-providers.yml): N LLM, M TTS, K Image, ...`，数字都 > 0 才算配齐。完整错误码表：1004=未授权, 1008=余额不足, 2013=参数错误, 2049=无效API Key, 2056=超出Token Plan限制
14b. **`/api/generate/tts` 字段名是 `ttsProviderId`/`ttsVoice`/`audioId`，不是 `provider`/`voice`** — 错误字段名会返回 `MISSING_REQUIRED_FIELD: text, audioId, ttsProviderId, ttsVoice`。curl 测试时用：`{"text":"...","audioId":"test","ttsProviderId":"minimax-tts","ttsVoice":"female-yujie"}`
14c. **重启后 `/api/server-providers` 可能首次返回 0 个 provider** — Next.js dev 缓存 + 启动日志显示 "Loaded N LLM" 才算成功。如果 curl 第一次返回 0 立刻又查 → 等待 1-2 秒或重启后再查。**判断 provider 真的加载成功的最可靠信号是 OpenMAIC 启动日志**
14d. **TTS 音频资产存储路径与前端播放机制（2026-07-09 实证）** — 课堂生成时如果 `enableTTS: true`，OpenMAIC 会为每个 speech action **预生成**音频文件并存到 `D:\projects\OpenMAIC\data\classroom-media\{classroomId}\audio\tts_s{sceneIdx}_action_{actionId}.mp3`，然后在 `actions[i].audioUrl` 字段写 `/api/classroom-media/{classroomId}/audio/{filename}`。**前端播放直接走 audioUrl，不实时调 TTS API**。这意味着：
    - **如果生成时 `enableTTS: false`**（`pitfall 28`），audioUrl 字段不存在，播放时调用 TTS API → 失败 500（除非服务端 TTS provider 已配好）
    - **如果生成时 `enableTTS: true`** + TTS key 过期/缺失，**整个课堂生成会失败**（HTTP 500 报错在 generate-classroom 阶段），不会生成部分课件
    - **诊断"课件没声音"步骤**：
      1. 打开 `D:\projects\OpenMAIC\data\classrooms\{classroomId}.json` 看每个 speech action 有没有 `audioUrl` 字段
      2. 没有 → 生成时没开 TTS，必须重新生成带 `enableTTS: true`
      3. 有 audioUrl 但浏览器请求 404 → 音频文件没存到对应路径，**检查 data/classroom-media 目录权限**或重新生成
      4. 有 audioUrl 且返回 200 但没声音 → 浏览器音频自动播放被禁（需要用户点击页面后才能播放）
    - **手动触发单条 TTS**（生成时没开，**事后补救**用）：调 `/api/generate/tts` 拿 mp3 bytes 自己存到 classroom-media 目录 + 手动改 JSON 加 audioUrl 字段。**注意**：不推荐事后补救，**永远用 `enableTTS: true` 一次到位**

### 检查课件内容质量（用 API 看 JSON，不靠肉眼）
14g. **课件数据存盘路径**：`D:\projects\OpenMAIC\data\classrooms\{课程序列号}.json`。直接打开 JSON 看质量
14e. **用户报"课件好多英文"先grep JSON** — 不要假设模型 bug，很可能是 requirement 表述有歧义
14f. **用户报"没声音"先去服务器日志查TTS调用记录** — `proc_<id>.log` 里搜 `Generating TTS: provider=X`

### MinoMax切换经验（2026-07-09）
14g. **OpenMAIC 与 Minimax 有官方集成** — 只需在 .env.local 写 `MINIMAX_API_KEY` + `MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic/v1` + `MINIMAX_MODELS=MiniMax-M3,MiniMax-M2.7-highspeed,MiniMax-M2.7`。M3 思考深度强制 adaptive（不是 max，因为 Minimax 只支持 adaptive/disabled）

### 链接与通信
15. **http://链接在Hermes响应中被过滤** — 用`cmd.exe /c "start <url>"`直接打开Edge，不要在聊天中发链接
16. **链接发不出来时直接帮用户打开** — 用户说"链接在哪"时，不要反复发链接
17. **?topic=自动提交不100%可靠** — 输入框会自动填充，但"进入课堂"按钮偶尔不触发
18. **多会话协作："另一个会话改的，你这边能看到吗"** — 当前会话看不到别的会话的修改，必须实读文件验证

### 用户偏好：备选方案红线（用户明确 pass 过的，不要再提）
36. **❌ 绝不要推荐"Edge 浏览器原生 TTS"作为 TTS 备选**（用户多次明确拒绝）— 用户原话："我都这么多次 pass 掉这个备选了，我完全不考虑这条道路作为备选"。TTS 问题**必须**走 MIMO（api.xiaomimimo.com，经 8787 代理），不要 fallback 到浏览器原生 TTS。**也不要推荐** Google TTS / Azure TTS 等其他云 TTS。**ASR 用百炼 qwen-asr**（2026-08-22 用户要求，配置 ASR_QWEN_API_KEY，不用浏览器原生）
37. **TTS 优先级（2026-07-10 用户最新指令覆盖 Pitfall 37 旧版）** — 用户原话："mimo其实还没过期，今天还可用"。**MIMO TTS 代理（`mimo-tts-proxy.py` 端口 8787）是默认 TTS**，走 `openai-tts` provider（`.env.local` 的 `TTS_OPENAI_*`）。minimax OAuth `oat-` token 是备选（`minimax-tts` provider）。**两者可以共存**（.env.local 同时配 `TTS_OPENAI_*` 和 `TTS_MINIMAX_*`），OpenMAIC 启动日志会显示 `2 TTS`。**默认 voice 是 `alloy`**（映射到 MIMO 的"冰糖"音色）。**如果 MIMO 真过期了**，删 `TTS_OPENAI_*` 切到 minimax 原生（Pitfall 38/40）。**注意：MIMO 代理必须在 OpenMAIC 之前启动**（start-tutor.bat 第 2 步）

### minimax OAuth 接入完整流程（2026-07-09 实证）
38. **minimax Token Plan 全模态调用的正确接入方式（OAuth 流程）** — `sk-cp-` 静态 key **只能**用于 Anthropic 兼容端点（LLM），调 minimax 原生 API（TTS/Image/Quota）必须用 `mmx auth login` 拿的 OAuth `access_token`（`oat-` 前缀）。完整步骤：
    ```bash
    # 1. 安装 minimax CLI（一次）
    npm install -g mmx-cli

    # 2. 设置 region 和 base_url（**必须** cn 国内，否则 fallback 到 global 然后 1004）
    mmx config set --key region --value cn
    mmx config set --key base_url --value https://api.minimaxi.com

    # 3. 浏览器登录（这一步用户必须手动操作）
    mmx auth login --region cn
    # 浏览器跳出 minimax 授权页 → 同意 → CLI 把 access_token 存到 ~/.mmx/config.json 的 oauth 字段

    # 4. 验证：mmx auth status 应该是 "method": "oauth"
    mmx auth status
    mmx speech generate --text "测试" --output-file /tmp/test.mp3  # 验证 TTS

    # 5. 提取 access_token 填 OpenMAIC .env.local
    cat ~/.mmx/config.json | python -c "import json,sys;print(json.load(sys.stdin)['oauth']['access_token'])"
    # 输出 oat-xxxx 格式，填到 TTS_MINIMAX_API_KEY 和 IMAGE_MINIMAX_API_KEY
    ```
    **完整 .env.local 配置**（含 TTS+Image 走 minimax OAuth）：
    ```bash
    # LLM: sk-cp- key（Anthropic 兼容端点用）
    MINIMAX_API_KEY=sk-cp-...T_4g
    MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic/v1
    MINIMAX_MODELS=MiniMax-M3,MiniMax-M2.7-highspeed,MiniMax-M2.7
    DEFAULT_MODEL=minimax:MiniMax-M3

    # TTS: minimax OAuth access_token（mmx auth login 拿的 oat- token）
    TTS_MINIMAX_API_KEY=oat-xxxx
    TTS_MINIMAX_BASE_URL=https://api.minimaxi.com

    # Image: minimax OAuth access_token（同上）
    IMAGE_MINIMAX_API_KEY=oat-xxxx
    IMAGE_MINIMAX_BASE_URL=https://api.minimaxi.com
    ```
    **端到端验证 TTS**：
    ```bash
    curl -X POST http://localhost:3000/api/generate/tts \
      -H "Content-Type: application/json" \
      -d '{"text":"测试","audioId":"t1","ttsProviderId":"minimax-tts","ttsVoice":"Chinese (Mandarin)_Warm_Girl"}' \
      -o /tmp/t.wav -w "HTTP %{http_code}, size=%{size_download}\n"
    # 期望 HTTP 200 + size 几十KB，2 秒内返回
    ```
    **端到端验证 Image**：
    ```bash
    mmx image generate --prompt "A cute cat" --output-file /tmp/cat.png
    # 期望 saved ["image_001.jpg"]，< 10秒返回
    ```
39. **minimax CLI mmx 命令完整参考** — `mmx text chat --message "user:xxx" --output json --quiet --non-interactive`、`mmx speech generate --text "xxx" --voice female-shaonv --output-file /tmp/x.mp3`、`mmx image generate --prompt "xxx" --output-file /tmp/x.png`、`mmx auth status`、`mmx config show`、`mmx config set --key <k> --value <v>`、`mmx speech generate --model speech-2.8-hd --voice Chinese (Mandarin)_Warm_Girl ...`（完整模型名/音色 ID 见 `references/minimax-tts-models.md`）
40. **OAuth token 有效期 + 生成课件前的强制同步**（2026-07-09 实证，1 天 23 小时过期）— minimax `oat-` token 有效期约 **48 小时**（不是 8-30 天）。过期后 `mmx auth status` 报 "API key rejected (HTTP 401)"，但 refresh_token 仍然有效。**renew 流程**：再跑一次 `mmx auth login --region cn`（CLI 用 refresh_token 自动续期，不需要重新浏览器授权）。**OpenMAIC 端的 `TTS_MINIMAX_API_KEY` 也需要重新填**（续期后 access_token 会变），所以**每次生成课件前必须先同步 access_token**：
    ```bash
    # 生成课件前的强制步骤（写入工作流 — 每天上课第一件事）
    python -c "
    import json, re, datetime
    d = json.load(open(r'C:\Users\MR\.mmx\config.json'))
    at = d.get('oauth', {}).get('access_token')
    exp = d.get('oauth', {}).get('expires_at', '')
    if not at:
        print('NEED_LOGIN: 没找到 oauth，请跑 mmx auth login --region cn')
        exit(1)
    if exp:
        ed = datetime.datetime.fromisoformat(exp.replace('Z', '+00:00'))
        if ed < datetime.datetime.now(datetime.timezone.utc):
            print('EXPIRED: token 已过期，先跑 mmx auth login --region cn 续期')
            exit(1)
    # patch .env.local
    fp = r'D:\projects\OpenMAIC\.env.local'
    content = open(fp, encoding='utf-8').read()
    content = re.sub(r'TTS_MINIMAX_API_KEY=.*', f'TTS_MINIMAX_API_KEY={at}', content)
    content = re.sub(r'IMAGE_MINIMAX_API_KEY=.*', f'IMAGE_MINIMAX_API_KEY={at}', content)
    open(fp, 'w', encoding='utf-8').write(content)
    print(f'OK: access_token 同步到 .env.local (剩余 {ed - datetime.datetime.now(datetime.timezone.utc)})')
    "
    # 然后重启 OpenMAIC 让 .env.local 生效
    ```
    **如果 .env.local 被改了，必须重启 OpenMAIC**（kill 3000 端口的进程 → 用 `start-tutor.bat` 重启）
    **快速判断是否过期（更简单的脚本）**：
    ```bash
    python -c "import json,datetime;d=json.load(open(r'C:\Users\MR\.mmx\config.json'));exp=d['oauth']['expires_at'];ed=datetime.datetime.fromisoformat(exp.replace('Z','+00:00'));left=ed-datetime.datetime.now(datetime.timezone.utc);print(f'{\"EXPIRED\" if left.total_seconds()<0 else \"OK\"}: 剩余 {left}')"
    ```

### 设计与教学
19. **不要假设设计风格** — 用户没指定风格时不要自行决定
20. **Hermes不决定教学重点** — 只提取知识点给出题用，教学重点由OpenMAIC决定
21. **扫描版PDF可能无法被OpenTutor解析** — 仍需上传存储
22. **课堂生成耗时3-5分钟** — 需要轮询直到status=completed
23. **百度搜索API Key格式** — `bce-v3/ALTAK-xxx/secret`，配置到.env.local
24. **修改OpenMAIC源码前必须备份** — 用户明确要求"每次改版前都要完整备份"
25. **答题网页使用流程** — 生成测验题后，将题目写入 `quiz-data-day{N}.json`，然后用 `cmd.exe /c "start D:\\projects\\family-tutor\\quiz.html"` 打开网页。网页会自动从 localStorage 读取题目数据。Hermes 需要先执行 JavaScript 脚本将题目写入 localStorage：
    ```bash
    # 生成加载脚本
    python -c "
    import json
    quiz = json.load(open('D:/projects/family-tutor/quiz-data-day1.json'))
    print(f'localStorage.setItem(\"current-quiz\", JSON.stringify({json.dumps(quiz, ensure_ascii=False)}));')
    " > /tmp/load-quiz.js
    # 通过 Edge CDP 执行脚本（需要先启动 Edge 调试模式）
    ```
25. **每页"同学们好"的真·最终解决方案在 `lib/generation/scene-generator.ts:processActions` 后处理**（2026-07-09 三次修正总结）— 改 system prompt / store.ts persona 都不够，**真·最终方案是 processActions 后处理 strip 问候语**。详见 `references/greeting-fix-journey.md`（含完整代码 + 执行顺序图 + 备份流程）
25a. **OpenMAIC HMR 不可靠，所有 `.ts` 源码改动必须重启 OpenMAIC**（2026-07-09 实证）— Turbopack 对 .ts/.tsx 改动会热重载（log 看到 "Compiled"），但 `scene-generator.ts` 这种跨多文件引用的核心模块**有时 HMR 不更新**。**稳妥做法**：改 .ts 文件后**总是**手动 kill + restart。**例外**：`lib/prompts/templates/*.md` 改动不需要重启（loader 用 `fs.readFileSync` 每次调用都读盘，不缓存）
25c. **改 .env.local 前必须先备份**（2026-07-09 用户偏好）— 用户原话："删除任何文件/工具/依赖前必须先确认，不要擅自删除"。改 .env.local 之前先 `cp .env.local .env.local.bak.$(date +%Y%m%d_%H%M%S)` 备份。改错了能立刻恢复
25i. **minimax TTS 速率限制 (1002) 加 retry**（2026-07-10 实战）— 大型课堂（>50 speech）调 minimax TTS 时**部分 action 会 1002 失败**（"rate limit exceeded(RPM)"）。**症状**：课件 JSON 里 86 个 speech action 只 57 个有 `audioUrl`（66% 覆盖率）。**解决**：在 `lib/server/classroom-media-generation.ts:259-287` 加 retry 循环（3s/6s/12s 指数退避，最多 3 次）。**当前实现**已经包含这段代码（如重新生成 OpenMAIC 时被覆盖，需要重新加）。**为什么串行调用还是限流**：minimax 限流是按 RPM（requests per minute）计算的，86 个请求每条 1.5s 串行执行也可能在 1 分钟内跑完 → 触发限流窗口。**验证**：grep 课件 JSON `audioUrl` 字段数 vs `type:speech` 字段数应该相等
25d. **"每页问候语"问题最终方案 — processActions post-processor**（2026-07-09 实战）— M3 即使给了"绝对禁止问候" system prompt + 改了 store.ts persona 仍会输出"同学们好"（2/12 残留）。**真正可靠方案**是 `lib/generation/scene-generator.ts` 的 `processActions` 函数内加问候语 strip：

```ts
// 在 processActions 函数内，return processedAction 之前
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

**关键**：post-processor 必须在 TTS 生成之前——`processActions` → `generateTTSForClassroom` → `persistClassroom` 的执行顺序保证了 strip 后的 text 会被 TTS 读、会被持久化。

**配套也改**（治标）：`lib/prompts/templates/slide-actions/system.md` 和 `lib/orchestration/registry/store.ts` 的 `DEFAULT_AGENTS['default-1'].persona` 都加 "NEVER use a greeting on ANY page" 规则

**验收**：生成后 `cat data/classrooms/<id>.json | python -c "import json,sys;d=json.load(sys.stdin);print(sum(1 for s in d['scenes'] for a in s['actions'] if a.get('type')=='speech' and ('同学' in a.get('text','') or '大家好' in a.get('text',''))))"` 应该输出 0

25e. **改 minimax 默认 TTS voice 后必须重启 OpenMAIC**（2026-07-09 实证）— `lib/audio/constants.ts:1284` 的 `DEFAULT_TTS_VOICES['minimax-tts']` 改完**必须重启** OpenMAIC（.ts 编译过）。用户试听挑的推荐默认：`Chinese (Mandarin)_Crisp_Girl`（干脆女孩）。**完整 303 音色列表**：`mmx speech voices`。中文女声适合儿童的 top 6: Crisp_Girl / Warm_Girl / Soft_Girl / Cute_Spirit / female-shaonv / Lyrical_Voice。**选 voice 流程**：用 `mmx speech generate --voice <id> --output-file /tmp/x.mp3` 各生成一段对比试听

25f. **看 voice 试听不要先开浏览器**（2026-07-09 用户偏好）— 试听 mp3 走 `start /d D:\projects\family-tutor\voice-samples\xx.mp3` 或资源管理器打开，**不要**用 `browser_navigate` 加载 file:// 路径（用户看不到 + headless 体验差）
25g. **"先验证再改"的硬性原则**（2026-07-09 用户纠正）— 涉及用户配置（.env.local、key、provider、skill prompt），**先**：
   1. 读现状（`cat .env.local` / `cat skill.md` / `curl /api/server-providers`）
   2. 跟用户确认理解对不对
   3. **先备份**（`cp file file.bak.$(date +%Y%m%d)`）
   4. 改完**立即**验证（重启服务、看日志、跑端到端）
   5. 报结果（不只是"改完了"，要"改完测了，XX 工作 YY 失败"）

   **不要**一上来就改、删、装。`grep` / `cat` 错了顶多浪费时间；删了用户文件或 skill 会被纠正（用户原话："删除任何文件/工具/依赖前必须先确认"）
25h. **删临时文件前明确范围**（2026-07-09 用户偏好）— 用户说"扫描并删掉这个项目的临时文件"时，**先列出要删的清单**让用户确认。不要自作主张删 `D:\projects\family-tutor\voice-samples\*.mp3`（用户可能还要回头对比），不要把 mmx CLI 装位置、npm 全局包、备份文件当临时文件删了
25b. **Token Plan 配额上限错误 2056（2026-07-09 实证）** — minimax 错误码 2056 表示"已达到 Token Plan 用量上限，请升级 Token Plan 套餐或购买积分补充用量"。**遇到 2056 不要去查端点/key/TTS 配置**，直接让用户去 https://platform.minimaxi.com → 套餐详情 → 看用量进度条 → 买积分或升级套餐。**诊断信号**：job 状态从 `running 31%` 突然跳到 `failed`，error 字段含 `2056` 错误码 + "用量上限" 字样
43. **删除旧课堂前必须备份**（2026-07-09 实证）— 重跑前用 `cp -r data/classrooms backup-classrooms-YYYYMMDD` 备份整个目录（不需要进子目录拷每个文件）。**完整清空**：`rm -rf data/classrooms/* data/classroom-jobs/*.json`（清 classrooms 目录 + 课堂任务 JSON）。备份放 `D:\projects\family-tutor\backup-classrooms-YYYYMMDD`
50. **OpenMAIC 重启 = 运行中的 job 状态丢失**（2026-07-10 实证）— 如果 OpenMAIC 在 job 运行期间被 kill/重启，job 会卡在某个 progress（如 84%）不再更新。**症状**：job 的 `updatedAt` 时间戳远早于当前时间，`status` 仍为 `running` 但 progress 不变。**修法**：删除卡住的 job JSON（`rm data/classroom-jobs/<jobId>.json`）+ 重新调用 `/api/generate-classroom` 生成。**不要**试图"恢复"卡住的 job——OpenMAIC 没有断点续传机制
51. **不要问用户"要不要改"，直接改**（2026-07-10 用户强烈纠正）— 用户原话："你还不明白吗，别搞了让我来"。当用户明确说了"切到 MIMO""用 MIMO TTS""关闭图片"等指令时，**直接执行**，不要问"要不要删旧配置""你确认吗"。用户的指令就是确认。**只在**涉及删除用户文件、修改不可逆操作时才确认
52. **页面必须自动打开，不要让用户来找**（2026-07-10 用户纠正）— 用户原话："你直接给个浏览器链接或者直接打开文件，而不是让我来找"。答题页面、加载页面等必须用 `cmd.exe /c "start <path>"` 自动打开，不要让用户自己找文件
53. **Open Design daemon 启动需要 Node 24**（2026-07-10 实证）— 启动命令：`cd /d/projects/open-design && C:/Users/MR/AppData/Local/nvm/v24.18.0/npx pnpm tools-dev start web`。端口看启动输出（每次重启可能变）。与 OpenMAIC（Node 22）不冲突，可同时运行
54. **MIMO Token Plan 也有配额上限**（2026-07-10 实证）— 类似 minimax 2056 错误，MIMO 也会在用量耗尽时报错。症状：课堂生成 job 从 running 突然 failed，error 含"Token Plan 用量上限"。**处理方式**：让用户去 MIMO 控制台充值/升级，不要去查 provider 配置
55. **OpenTutor 已完全移除**（2026-07-10 用户指令）— 用户说"删干净open tutor"，已删除 `D:\projects\OpenTutor\` 整个目录。**所有测验功能由 Hermes 直接完成**：MIMO 多模态读课本 → 出题 → quiz.html 答题 → quiz-server.py 接收结果 → Hermes 批改分析。不要再尝试启动 OpenTutor 或引用其 API
56. **Open Design 是强制要求，不要手写 CSS 替代**（2026-07-10 用户强烈纠正）— 用户原话："不要你自己优化，我指定了open design就不要用别的"。当用户说"美化页面"时，**必须**用 Open Design 生成，不要自己写 CSS 然后说"已经美化了"。如果 Open Design 生成效果不满意，**告诉用户并让用户决定**是否重新生成，不要擅自用手写版本替代
57. **browser_console 无法读取 localStorage（安全限制）**（2026-07-10 实证）— Hermes 的 browser_console(expression=...) 会被拦截：`Blocked: tried to sensitive browser JavaScript primitive (web storage)`。**读取答题结果的替代方案**：
    - **方案A（推荐）**：确保 quiz-server.py 在跑，答题网页会自动 POST 结果到 `http://localhost:8765/api/quiz-results`，Hermes 用 `curl http://localhost:8765/api/quiz-results/latest` 读取
    - **方案B**：用 MIMO 多模态截图分析（`mimo-multimodal.cjs --type image --input screenshot.png`），但需要答题网页在浏览器中可见
    - **方案C**：让用户口头告诉分数和错题
    - **不要反复尝试 browser_console** — 安全限制不会解除，浪费时间
58. **Open Design 生成新风格需要1-3分钟**（2026-07-10 实证）— 用 MIMO 模型生成 HTML 设计时，Open Design 会经过：思考(7s) → 表单确认 → 再次思考(3s) → 执行生成(2-3min)。**如果卡在"思考中"超过3分钟**，可能是模型响应慢，不要反复刷新。**生成后文件路径**在聊天界面显示（"写入 D:\...\index.html · N 行"），复制到项目目录即可
63. **可借鉴的 GitHub 开源项目**（2026-07-30 调研）:
    - **petrbui/skills — GapHunter** (10⭐, 活跃) — 自适应 AI 教师，专门找知识漏洞并填补。核心机制：定位测试 (placement test, 3 cold challenges) → 优先级排序 → 一对一教学 → 验证掌握 → SM-2 间隔重复 → 突袭薄弱点 → Boss 战。**框架可以借鉴**，但角色定义需改为"小学生"。详细可参考: https://github.com/petrbui/skills
    - **AtomerCore/Exam2Knowledge-skill** (16⭐, 活跃) — 应试考点反向工程。提供 Bloom's Taxonomy (L1-L6) 和 5类错误归因 (C1阅读/C2概念/C3方法/C4执行/C5边界) 框架。**适合中学以上**，小学生场景不直接适用。MIT 协议。
    - 其他搜索结果 (usathyan/epistract, DongyiQin/TextBookExtraction) 都是 0-6⭐ 的小众项目，stars 数太低，不是主流方案。**结论：知识点抽取是 AI 应用的小众领域，没有公认的 SOTA 开源方案**。
    - **建议**: GapHunter 的"定位测试 + 间隔重复 + 薄弱点突袭"机制值得借鉴加入家庭教师系统，但不要硬塞，应按小学生场景简化。

### OpenMAIC IndexedDB vs 文件系统
61b. **API 生成的课件不会自动出现在主页（2026-07-10 实证，最重要的 pitfall）** — OpenMAIC 主页的"最近学习"列表**从 IndexedDB 读取，不是从文件系统**。**症状**：用户看到 3 个课件（之前在浏览器手动生成的），但 API 生成的 7 个课件全在 `D:\projects\OpenMAIC\data\classrooms\` 文件系统里，主页不显示。**根因**：OpenMAIC 存储是双轨制——生成时写文件系统，展示时从 IndexedDB 读。**解决方案**（用户原话："我从始至终都是想让你做自动导入"）：
  1. **自动方案（用户偏好）**：修改 OpenMAIC 源码。详见 `references/openmaic-indexeddb-import.md`。修改 `listStages()` + `getFirstSlideByStages()` 也从文件系统读取，新增 `/api/classroom/list-filesystem` 和 `/api/classroom/get-file` 端点。
  2. **手动方案**：打包 ZIP → 手动导入。脚本 `D:\projects\family-tutor\scripts\pack-classrooms.py` 输出到 `exported-zips\`。然后在 OpenMAIC → "导入课堂" → 选择 ZIP。
  **不要假设**文件系统存储会自动同步到 IndexedDB！**重要**：服务端脚本**无法**直接写入 IndexedDB（这是浏览器端数据库），只能通过修改源码或 ZIP 导入。

### 教材内容核对
61. **生成课件后必须用知识要点文档核对内容**（2026-07-10 实证）— minimax 可能会"自由发挥"生成与需求不符的课件。例如：需求是"数据的表示和分析（三）- 人口老龄化"，minimax 生成了"统计图的选择与应用"。**核对方法**：课件生成后，读取课件 JSON，对照 `knowledge-points/{subject}_day{N}.md` 检查关键知识点是否出现。

### 教材年级核对
60. **必须用 MIMO 多模态视觉确认课本的实际年级**（2026-07-10 实证）— 用户要求"预习小学五年级数学"，但裁切的 PDF 实际包含四年级内容（如数学 Day 4 是四年级下册"身高分段统计"，不是五年级）。**裁切 PDF 后必须验证年级和内容**：用 MIMO 多模态读 PDF 第一页，问"这是几年级的课本？主要讲什么内容？"。**如果年级不符**，需要修正 `knowledge-points/{subject}_day{N}.md` 和课件生成需求。

### minimax OAuth Token 刷新
59. **minimax sk-cp- key 不能用于 minimax 原生 API 端点（2026-07-10 实证）** — sk-cp- 静态 key 只对 Anthropic 兼容端点 `https://api.minimaxi.com/anthropic/v1` 有效。错误现象：调用 minimax 原生 API（/v1/text/chatcompletion_v2、/v1/t2a_v2 TTS、/v1/image_generation Image）时报 `status_code: 1004, status_msg: login fail: Please carry the API secret key in the Authorization field of the request header`。正确接入方式：用 OAuth `oat-` token（通过 `mmx auth login` 拿的）。快速验证 key 类型：`curl /v1/token_plan/remains -H 'Authorization: Bearer <key>'`，1004 错误 = key 类型错。
59a. **minimax OAuth token 续期用 mmx auth refresh（2026-07-10 实证）** — minimax OAuth oat- token 有效期约 48 小时。过期后不要用 `mmx auth login --region cn`（非交互模式会报 --api-key is required），用 `mmx auth refresh` 续期。续期后必须同步到 .env.local 并重启服务。
59b. **Open Design 生成的页面必须手动添加后端同步代码**（2026-07-10 实证）— Open Design 生成的是独立 HTML 页面，不包含后端同步代码。**生成后必须**：①复制到项目目录 ②在 submit 事件处理函数末尾添加 sync 代码（参考 `references/quiz-sync-code-template.md`）③替换示例题目为实际测验题 ④自动打开页面（`cmd.exe /c "start <path>"`）。**不要假设生成的页面已经包含后端集成**——每次生成后都要检查并添加 sync 代码
60. **AI 批改实现（2026-07-10 实证）** — 简答题不要用关键词匹配，要用 AI 语义理解批改。**实现方式**：
    - 后端 `quiz-server.py` 增加 `/api/grade-essay` 端点，调用 MIMO API
    - 前端 `quiz-ai.html` 提交简答题时 POST 到后端，等待 AI 返回结果
    - AI 返回：`is_correct`、`error_reason`、`reference_answer`、`process_issues`（理科）、`suggestions`
    - **用户明确要求**：简答题必须给出错误原因 + 参考答案 + 改进建议；理科要指出过程问题
    - **不要用关键词匹配**（用户原话："不要用关键词审查哦，就是要让ai来看正确与否"）
61. **动态补强练习题型（2026-07-10 实证）** — 补强练习的题型应根据错题类型动态调整：
    - 运行 `python generate-remedial.py` 分析薄弱知识点
    - **只错选择题 → 全是选择题**
    - **错了简答题 → 才包含简答题**
    - 脚本自动从原题中找同类型题目生成补强练习
    - **用户明确要求**："你的题型应该不是固定的吧，加入我没有错情感差异分析这一步，则应该全是选择题才对吧"
61a. **补强练习必须生成新题，不能重复原题（2026-07-10 用户强烈纠正）** — 用户原话："你每次出的题都是一样的，这不叫查漏补缺，所以我是让你总结漏洞知识点而不是错题"。**核心逻辑**：
    - **分析漏洞知识点**（不是错题）：运行 `python analyze-weak-points.py` 提取薄弱知识点（如"渚的读音"、"见的读音"、"诗词情感对比"）
    - **用 AI 生成新题**：运行 `python generate-remedial.py` 调用 MIMO API 根据知识点生成新题
    - **每次生成的题都不同**（AI 随机变换选项、问法），但考点一致
    - **不要重复原题** — 用户明确说"这不叫查漏补缺"
    - **流程**：分析错题 → 提取知识点 → AI 生成新题 → 用户作答 → 再次批改
62. **答题系统文件清单（2026-07-10 更新）**：
    - `quiz-ai.html` — **AI 批改版答题页面**（推荐使用，支持语义理解批改）
    - `quiz.html` — Open Design 美化的深色主题答题页面（旧版，关键词匹配）
    - `load-quiz.html` — 加载页面（点击"开始测验"自动加载题目并跳转）
    - `load-quiz-remedial.html` — 补强练习加载页（显示薄弱知识点列表）
    - `quiz-server.py` — 结果接收服务 + AI 批改端点（端口 8765）
    - `analyze-weak-points.py` — 分析薄弱知识点脚本（提取知识点，不是错题）
    - `generate-remedial.py` — 用 AI 生成新题脚本（根据知识点生成新题，每次不同）
    - `quiz-results/` — 结果存储目录
    - `quiz-data-day{N}.json` — 每天的测验题数据
    - `quiz-data-remedial.json` — 补强练习题数据
    - `weak-points-analysis.json` — 薄弱知识点分析结果

70. **课件生成中途切换 LLM provider（2026-07-10 实证）** — 用户在课件生成中途说"mimo 过期了，能不能剩下的部分用 minimax 生成，还是必须重新生成"。**正确做法**：**不需要重新生成！** 修改 `.env.local` 的 `DEFAULT_MODEL` + 重启 OpenMAIC，正在运行的 job 会自动用新 provider 完成剩余步骤（包括卡在 TTS 阶段的）。**步骤**：①备份 .env.local ②修改 `DEFAULT_MODEL=minimax:MiniMax-M3` ③杀掉旧 OpenMAIC 进程（按端口 3000）④重启 OpenMAIC（`pnpm dev`）⑤验证 provider 已加载。详见 `references/provider-switching-mid-task.md`。

70a. **不要覆盖已完成的课件（2026-07-10 用户纠错）** — 用户原话：> "有一个不是已经生成完了吗还重新生成干嘛？不要覆盖已经生成好的了"。**正确做法**：批量重生成前先检查 `data/classrooms/*.json`，已成功的保留，只重新生成没成功的或内容不对的。**内容对比**：用户要求"人口老龄化"但模型生成"统计图的选择"——即使跑完了也属于内容错误，必须重新生成（不要因为"跑完了"就保留错误内容）。**何时切换 vs 重新生成决策表**：

| 场景 | 操作 |
|------|------|
| 内容正确 + 已完成 | 保留 |
| 内容错误（偏离主题） | 重新生成 |
| 卡在 TTS（provider 配额耗尽） | 切换 provider 继续 |
| Stale job（重启后卡住） | 删除 + 重新生成（pitfall 50） |
| 用户明确说"重新生成" | 全部重新生成 |

75a. **课件生成后必须核对内容（2026-07-10 实证）** — 用户原话："你等会可以拿那些知识点大致的核对一下生成的课程对不对哈"。**正确做法**：课件生成完后，**对照 `knowledge-points/{subject}_day{N}.md` 检查课件内容**。用知识要点文档当 ground truth 核对，发现内容错误立即重新生成（minimax M3 会"自主发挥"——你要求"人口老龄化"它可能生成"统计图的选择"）。

73.
    import re
    json_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', ai_response, re.DOTALL)
    if json_block_match:
        json_str = json_block_match.group(1).strip()
    else:
        json_start = ai_response.find('{')
        json_end = ai_response.rfind('}') + 1
        json_str = ai_response[json_start:json_end] if json_start != -1 else None
    ```
64. **补强练习答案必须随机分布（2026-07-10 用户强烈纠正）** — 用户原话："你自己说答案随机分布了，然后不管是你给的网页还是你第二遍给的答案都是aaaaa 你在自己反驳自己吗？"。**必须用 shuffle_options() 函数打乱选项顺序**，不能让正确答案总是在 A。实现方式：
    ```python
    def shuffle_options(item, correct_key):
        options = item['options'].copy()
        correct_answer = item[correct_key]
        correct_idx = options.index(correct_answer)
        paired = list(enumerate(options))
        random.shuffle(paired)
        new_options = [opt for _, opt in paired]
        new_correct_idx = next(i for i, (orig_idx, _) in enumerate(paired) if orig_idx == correct_idx)
        return new_options, new_correct_idx
    ```

65. **AI 批改失败时的 fallback**（2026-07-10 实证）— 当 MIMO API 返回空内容或 JSON 解析失败时，返回默认结果（`is_correct: false`）并显示参考答案。不要让用户看到空白页面。

66. **MIMO API 对中文提示词返回空内容**（2026-07-10 实证）— `mimo-v2.5-pro` 模型在收到中文批改提示词时，`content` 字段返回空字符串（长度 0），但 `reasoning_content` 有内容。**根因**：模型把所有 token 用在"推理"上，没留给实际回复。**解决方案**：用英文提示词。详见 `references/mimo-api-chinese-prompt-issue.md`。

67. **MIMO API max_tokens 需要 ≥500**（2026-07-10 实证）— `max_tokens=50` 时，模型用 49 token 做推理、1 token 回复（空）。`max_tokens=500` 时，推理用 100-200 token，剩余给回复。**批改场景推荐 `max_tokens: 500`**。

68. **重启服务前必须杀掉所有旧进程**（2026-07-10 实证）— Windows 下 `netstat -ano | findstr :端口` 可能显示多个进程监听同一端口。必须杀掉所有旧进程再重启，否则请求可能被旧进程处理（使用旧代码）。

69. **调试日志添加后必须重启服务**（2026-07-10 实证）— 修改 quiz-server.py 后，必须杀掉旧进程再重启，否则新代码不会生效。

70. **课件生成中途切换 LLM provider（2026-07-10 实证）** — 用户在课件生成中途说"mimo 过期了，能不能剩下的部分用 minimax 生成，还是必须重新生成"。**正确做法**：**不需要重新生成！** 修改 `.env.local` 的 `DEFAULT_MODEL` + 重启 OpenMAIC，正在运行的 job 会自动用新 provider 完成剩余步骤（包括卡在 TTS 阶段的）。**步骤**：①备份 .env.local ②修改 `DEFAULT_MODEL=minimax:MiniMax-M3` ③杀掉旧 OpenMAIC 进程（按端口 3000）④重启 OpenMAIC（`pnpm dev`）⑤验证 provider 已加载。详见 `references/provider-switching-mid-task.md`。

70a. **不要覆盖已完成的课件（2026-07-10 用户纠错）** — 用户原话：> "有一个不是已经生成完了吗还重新生成干嘛？不要覆盖已经生成好的了"。**正确做法**：批量重生成前先检查 `data/classrooms/*.json`，已成功的保留，只重新生成没成功的或内容不对的。**内容对比**：用户要求"人口老龄化"但模型生成"统计图的选择"——即使跑完了也属于内容错误，必须重新生成（不要因为"跑完了"就保留错误内容）。**何时切换 vs 重新生成决策表**：

| 场景 | 操作 |
|------|------|
| 内容正确 + 已完成 | 保留 |
| 内容错误（偏离主题） | 重新生成 |
| 卡在 TTS（provider 配额耗尽） | 切换 provider 继续 |
| Stale job（重启后卡住） | 删除 + 重新生成（pitfall 50） |
| 用户明确说"重新生成" | 全部重新生成 |

75a. **课件生成后必须核对内容（2026-07-10 实证）** — 用户原话："你等会可以拿那些知识点大致的核对一下生成的课程对不对哈"。**正确做法**：课件生成完后，**对照 `knowledge-points/{subject}_day{N}.md` 检查课件内容**。用知识要点文档当 ground truth 核对，发现内容错误立即重新生成（minimax M3 会"自主发挥"——你要求"人口老龄化"它可能生成"统计图的选择"）。

73.
    import re
    json_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', ai_response, re.DOTALL)
    if json_block_match:
        json_str = json_block_match.group(1).strip()
    else:
        json_start = ai_response.find('{')
        json_end = ai_response.rfind('}') + 1
        json_str = ai_response[json_start:json_end] if json_start != -1 else None
    ```
    - **不要**简单回复"还在生成中"——给出具体的 step（如"数学 Day 1 在 generating_tts 94%，数学 Day 3 已 completed"）
    ```bash
    python -c "
    import json
    jobs = ['U2QDH1pN1T', '-VKc44-_iY', 'tKBowa1R4F', 'aAyPXHdT-m', 'PSd4kUo3J0']
    for job in jobs:
        try:
            d = json.load(open(f'D:/projects/OpenMAIC/data/classroom-jobs/{job}.json'))
            print(f'{job}: {d.get(\"status\")} - {d.get(\"progress\")}% - {d.get(\"step\")}')
        except Exception as e:
            print(f'{job}: 错误 - {e}')
    "
    ```

73. **学科 PDF 裁切和知识要点提取的标准化流程（2026-07-10 实证）** — 用户要求"按工作流来"，每科都需要：
    - **裁切 PDF 为小节**（如数学 unit1 前3页+后5页 → 2个 PDF）
    - **每个小节生成独立课件**（一天一课）
    - **用 MIMO 多模态提取知识点**（写到 `knowledge-points/{subject}_day{N}.md`）
    - **knowledge-points 内容包括**：学习目标、主要概念、核心公式、例题解析、练习题、易错点、拓展知识
    - **结构化目录**：
      - `materials/{subject}/` — 按学科分文件夹
      - `knowledge-points/` — 知识要点 .md 文档
      - `quiz-data/` — 测验数据
      - `scripts/` — 所有 Python 脚本
    - **用户原话**："知识要点和学习规划安排是需要用独立world文档来记录的。需要记录进去。推进学习计划和查漏补缺的时候直接按照已经详细提炼好的知识要点文档来做就行"

74. **OpenMAIC provider 加载逻辑：两个 provider 都显示但默认用 DEFAULT_MODEL（2026-07-10 实证）** — OpenMAIC 启动日志显示 `minimax` 和 `xiaomi` 两个 provider 都加载，**不依赖** DEFAULT_MODEL。DEFAULT_MODEL 只决定默认使用哪个。**验证 provider 加载数量**：`curl http://localhost:3000/api/server-providers | python -c "import json,sys;d=json.load(sys.stdin);print('LLM:', list(d.get('providers',{}).keys()));print('TTS:', list(d.get('tts',{}).keys()));print('Image:', list(d.get('image',{}).keys()))"` 应该是 `LLM: ['minimax', 'xiaomi']`, `TTS: ['openai-tts', 'minimax-tts']`, `Image: ['minimax-image']`。

#75g. **muse-spark 在 OpenMAIC 必须走 /v1/responses，不能走 /chat/completions（2026-09-01 实证）** — opencode-go 中继上 muse 是 `codex_responses` 模型（与 `gpt-5.6-luna / grok-4.5` 同列），但 OpenMAIC `lib/ai/providers.ts` 的 `shouldUseOpenAIResponsesApi()` 默认只对 openai-native 的 `gpt-5.5 / gpt-5.x-pro / gpt-5.x-codex` 三个 pattern 返回 true，其它 openai-provider 模型（包括 muse）一律走 `openai.chat()` → `POST /v1/chat/completions` → 中继对 muse 返回 **500 Internal server error**。症状：每次课件都在 `generating_outlines 15%` 阶段 3 次重试后 AI_RetryError 失败。修复：编辑 `D:/projects/OpenMAIC/lib/ai/providers.ts` 的 `shouldUseOpenAIResponsesApi()` 加一行 `|| /^muse-spark(?:-|$)/.test(modelId)`，让 muse 走 `openai.responses()`。**`.env.local` 的 `OPENAI_BASE_URL` 必须保持 `https://opencode.ai/zen/go/v1`**——**不要加 `/responses` 后缀**，因为 `@ai-sdk/openai` 的 `.responses()` 自己会拼 `/responses`，写死 base URL 会变成 `/v1/responses/responses` → 404 Not Found（用户第一次尝试踩到的坑）。修复后症状：muse 突破 15% 失败点，正常推进 1/8 → 2/8 场景。完整诊断/修复记录见 `references/muse-ai-sdk-responses-fix-2026-09-01.md`（含 curl.exe 直连证据 + AI SDK endpoint 拼接原理）。**注意**：同类 model 后续会继续加——任何往 opencode-go 加的新模型如果只走 `/v1/responses` 必须同步更新这个函数（见 pitfall 75i）。

75h. **只使用用户指定的 LLM 模型，不要擅自切换（2026-09-01 用户红线）** — 用户原话（首条）："只按我要求来，只用 kimi 和 muse。不要用 kimi…如果双模型就不用关"。**含义**：除非用户明确说要换，否则 `DEFAULT_MODEL` 只能在用户**明确指定**的模型之间切换。**绝对禁止**擅自引入"看起来能跑"的备选（如 `deepseek-v4-flash / minimax-m3 / ox-alpha-free / gpt-5.6-luna` 等），即使它们端点正常。**也不要**因为"加速"或"备用"理由去切换非用户指定模型。**debug/对比可以临时用，但必须立刻恢复**用户指定的模型。**修复 muse 500 应优先通过修改路由（providers.ts）+ 直连诊断（curl.exe）**，而不是换模型。**反面教训（2026-09-01 当事人亲手犯）**：用户一开始说"模型换成 muse 其他不变" → muse 500，我自作主张切到 `deepseek-v4-flash` 跑（"看起来能跑"），被用户当场训斥："我从未跟你说过要用 deepseek，停下 deepseek。你为什么要自己切换模型？？？只按我的要求来！课件 skill 里面没有说吗，不要自己随意更换模型。只用我指定的模型。" —— 这次教训直接写入此 pitfall：**user 说只用某两个模型时，"能跑"不是理由，"用户指定的"才是理由**。

75h-bis. **记录用户的模型白名单时不要漏项（2026-09-01 用户纠正）** — 用户后来再次纠正："我不是还指定了 Nvidia NIM 的 Kimi K3 和 现在对话用的 Provider 的 Minimax 的 M3 吗？"——也就是说，用户指定的不是"kimi 和 muse"二选一，而是**三个 provider 的明确集合**（2026-09-01 当前白名单）：
    - `muse-spark-1.2-contributor`（opencode-go 中继，codex_responses，**主用**，写进 `OPENAI_MODELS`）
    - `kimi-k3`（opencode-go 中继 chat_completions **+ NVIDIA NIM `moonshotai/kimi-k3` 备用入口** — NIM catalog 里有该 slug，2026-09-01 直连 + 7897 代理均 90s 超时，NVIDIA 那边当时不可达；不是 opencode-go 不可用，只是 NIM 那一路不通）
    - `MiniMax-M3`（minimax / Anthropic 兼容端点 `https://api.minimaxi.com/anthropic/v1`，用 OAuth `oat-` token；**这个 provider 当前会话正在用**，不是"备选"）
    **怎么避免漏项**：① 用户每次说"用 X 和 Y"时，**主动回读整段消息**，确认没漏掉并列项（"和" / "以及" / "还有" / "minimax 的 M3 吗" 等都是提示词）；② 用 `mmx config show` + `curl -s https://opencode.ai/zen/go/v1/models -H "Authorization: Bearer ..."` 列出当前可达 provider 列表，**跟用户原话逐项核对**，发现缺一立刻问而不是自己脑补"意思是这两个"；③ 把白名单本身写进 skill 顶部"默认配置表"+ 持久 memory，每次切换前都查白名单——**不允许"用相近的"这种推理**。**反面教训（2026-09-01 当事人亲手犯）**：用户其实指定了三个（muse + kimi + minimax-m3），我漏记了 minimax M3——它不是"能跑的备选"，而是用户**明确指定**的 provider（用户在当前会话就是用这个 model 跟我聊天的），结果 minimax M3 在我眼里被归到"看起来能跑 → 不允许"清单里，被当成禁项。这是顺序错误：**用户白名单 ≠ "用户今天让我跑任务用的那个"，而是"用户明确说过的全部集合"**。一旦会话结束 → 重置前，**白名单优先于"正在用的"**。

75l. **微课堂不要重新发明轮子（2026-09-08 用户反复纠正）** — 用户原话："我希望它基于 OpenMAIC 来开发，看看哪一部分是控制它生成完整的课堂内容的，把它改成生成较为简单的简短课堂"。**正确做法是新建 outline 模板，不改架构。** 反面例子（用户已纠正）：① 我之前说"拼 requirement 字符串调 OpenMAIC API" — 用户反驳："OpenMAIC 接到 requirement 后它内部还是会自己重新生成大纲，它不会直接照着 requirement 念"；② 我提议"改 scene-generator.ts 加微课堂模式" — 用户说"我希望基于 OpenMAIC 来开发，看看哪一部分是控制它生成完整的课堂内容的，把它改成微课堂"，意思不是改架构，而是改 outline prompt 模板。**最终方案**：新建 `D:\projects\OpenMAIC\lib\prompts\templates\micro-lesson-outlines\system.md`，加 `outlineMode: 'micro-lesson'` 路由分支。**不要改 outline-generator.ts 本身，也不要在 scene-generator.ts 加 mode 判断。**

75m. **白板/手指/标注是 OpenMAIC 内建能力，不是 prompt 写出来的（2026-09-08 用户明确纠正）** — 用户原话："用白板写出来，而不是用嘴说。这本身就是 OpenMAIC 已经调好的东西啊？这不应该是你要考虑的内容"。**事实**：OpenMAIC 课堂的"白板逐步书写"、"手指指示"、"高亮强调"、"节奏停顿"全部由 `lib/generation/scene-generator.ts:processActions` 后处理 + slide-actions prompt 模板的内建动作（wb_draw_text / wb_draw_table / wb_draw_latex 等）实现，**不需要在微课堂 prompt 里手写**。**错误做法**：在 micro-lesson-outlines/system.md 里写"请用 wb_draw_text 一步步书写、用 spotlight 强调关键数字" — 这是把 OpenMAIC 已经做好的事重新描述一遍，浪费 token 而且可能反而干扰模型。**正确做法**：新模板只约束场景数、类型、时长，**完全不提白板动作**——OpenMAIC 自动用白板讲。

75n. **图片批改不需要搭接口（2026-09-08 用户纠正）** — 学生/家长拍照发到 Hermes 对话框即可，**不要新建 `/api/quiz-submit-image` 接口，也不要改 quiz-server.py**。**原因**：图片批改和答题网页批改是两件事：① 答题网页（quiz-pending.html）的批改是 Hermes 异步读 `quiz-results/latest.json`，写回 learning-state.json；② 图片批改是 Hermes 收到图片后直接调 vision 工具 + LLM 批改，全程不经过 HTTP 接口。**正确流程**：微信发图 → vision_analyze（用 `D:/mimo-multimodal/image_understand.py`）→ LLM 批改（opencode-go ox-alpha-free + 英文 prompt + max_tokens≥2000）→ 写回 quiz-results 和 learning-state.json。**不要自作主张搭接口**，用户原话："把作业拍照发到 Hermes 对话框不就可以了吗"。

75o. **文件夹按主题分，不要按文件类型分（2026-09-08 用户明确要求）** — 旧结构 `D:\projects\family-tutor\{materials, quiz-data, knowledge-points, quiz-results, scripts}/` 是按文件类型分的，**用户明确要求改为按主题分**：`D:\家教\{语文,数学,英语}\{课本,课件,知识点及掌握情况,错题集,测验}/` 加 `系统/`。**原因**：家长/老师视角找资源时按主题找更直观（"昨天的数学错题在哪"），按文件类型找要跨多个目录。**迁移注意事项**：物理移动（不要软链接）、迁移前全量备份、迁移完后逐个 grep 替换所有路径引用（skill、脚本、HTML、.env.local），**先迁移验证 3 天无问题再删旧目录**。

75i. **加新 opencode-go 模型到 OpenMAIC 的标准 Checklist（2026-09-01 实战总结）** — 复盘 muse-spark 修复流程，下次新加模型避免再踩坑：
    1. **列模型**：`curl -s https://opencode.ai/zen/go/v1/models -H "Authorization: Bearer <GO_KEY>" | python -m json.tool | grep -i <family>` —— 确认 slug 和 family
    2. **chat_completions 探测**：`curl -X POST https://opencode.ai/zen/go/v1/chat/completions -H "Authorization: Bearer <GO_KEY>" -H "Content-Type: application/json" -d '{"model":"<slug>","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'`
       - **200** → 该模型走 chat_completions 即可，**无需任何 OpenMAIC 改动**
       - **500** → 继续
    3. **responses 探测**：`curl -X POST https://opencode.ai/zen/go/v1/responses -H "Authorization: Bearer <GO_KEY>" -H "Content-Type: application/json" -d '{"model":"<slug>","input":"hi","max_output_tokens":50,"reasoning":{"effort":"xhigh"}}'`
       - **200** → 编辑 `lib/ai/providers.ts` 的 `shouldUseOpenAIResponsesApi()`，把 slug pattern 加进去（参考 `/^muse-spark(?:-|$)/`）
       - **500** → 该模型当前在 opencode-go 不可用，回退或换模型
    4. **重启 OpenMAIC dev**（`taskkill /F /PID <pid>` + `next dev --port 3000`），`/api/server-providers` 确认模型在列表
    5. **端到端验证**：提交一次最小课件任务，确认不再 15% 失败

75j. **直连 opencode.ai 优先用 `curl.exe`，不要用 Windows `urllib`（2026-09-01 实证）** — Windows `urllib` 在同 IP 上对 opencode.ai 报 `HTTP Error 401: Unauthorized, error code: 1010`（Cloudflare TLS 指纹拦截）。`curl.exe` 不受影响。**排查中继连通性 / 端点是否正确 / 模型 family 时一律用 `curl.exe`**（Windows 自带，路径 `C:\Windows\system32\curl.EXE`），不要花时间在 `urllib` 上重试。

75p. **OpenMAIC 真实 outline prompt 在 packages 包内，不在 lib/prompts/templates/（2026-09-08 实证）** — `D:/projects/OpenMAIC/lib/prompts/templates/` 是**死代码**，没有任何 TypeScript 代码引用它。真实 outline prompt 在 `D:/projects/OpenMAIC/packages/@openmaic/generation/templates/requirements-to-outlines/`，由 `packages/@openmaic/generation/src/prompts/index.ts` 的 `PROMPT_IDS` 常量加载。**判断方法**：`grep -rn "lib/prompts" D:/projects/OpenMAIC/packages D:/projects/OpenMAIC/lib` 找不到任何引用。**反面教训**：我之前（2026-09-08）分析了半天才发现这个问题，差点基于死代码去改 `outline-generator.ts` + 加路由分支。**正确做法**：先 grep 确认 prompt 模板的真正使用位置，再决定改不改源码。

75q. **`D:/projects/start-tutor.bat` 启动 OpenMAIC 的命令是错的（2026-09-08 实证）** — bat 文件第 3 阶段用 `node %CD%\node_modules\npm\bin\npm-cli.js run dev`，**但 `npm-cli.js` 在 OpenMAIC 的 node_modules 里根本不存在**（npm 不是 OpenMAIC 的直接依赖）。该命令会静默失败，OpenMAIC 起不来。**正确启动命令**：`cd /d/projects/OpenMAIC && /d/hermes-data/node/node.exe ./node_modules/next/dist/bin/next dev --port 3000 > /d/tmp/openmaic-dev.log 2>&1`。**前置**：① node 在 `D:/hermes-data/node/node.exe`（不是系统 PATH 里）；② 输出日志要重定向到 `D:/tmp/` 而不是 `/tmp/`（MSYS 路径 `/tmp/` 在 Windows Python subprocess 下不可写）；③ bash 启动用 `terminal(background=true)` + tee 重定向，进程不会退出。

75r. **`micro-lesson.py` 默认 subject 是 ASCII "math"，导致输出路径用 `D:/家教/math/课件/` 而不是 `D:/家教/数学/课件/`（2026-09-08 实证）** — `argparse` 默认值 `default="math"` 是 ASCII，传到 `out_dir = tutor_root / args.subject / "课件"` 后路径错了。**真实使用时必须传** `--subject 数学`，否则课堂 JSON 和 requirement 都会落到错误文件夹。**修复方案**（任选）：① 改 `argparse` 默认为 `default="数学"`；② 加 `--subject-alias` 选项做中英文映射；③ demo 模式强制用 `math` 但 require 用户显式传 `--subject`。**为什么用 ASCII 而不是中文做默认**：脚本里也提到 demo 是 "math"，但用户实际使用时是 "数学"，两者不一致 → bug。**模板命令**（直接复制）：
    ```bash
    # 列模型
    curl.exe -s "https://opencode.ai/zen/go/v1/models" -H "Authorization: Bearer <KEY>" | python -m json.tool

    # chat_completions 探测
    curl.exe -s -X POST "https://opencode.ai/zen/go/v1/chat/completions" \
      -H "Authorization: Bearer <KEY>" -H "Content-Type: application/json" \
      -d '{"model":"<slug>","messages":[{"role":"user","content":"hi"}],"max_tokens":10}' \
      -w "\nHTTP_STATUS=%{http_code}\n"

    # responses 探测
    curl.exe -s -X POST "https://opencode.ai/zen/go/v1/responses" \
      -H "Authorization: Bearer <KEY>" -H "Content-Type: application/json" \
      -d '{"model":"<slug>","input":"hi","max_output_tokens":50,"reasoning":{"effort":"xhigh"}}' \
      -w "\nHTTP_STATUS=%{http_code}\n"
    ```
    **不要**用 `urllib.request.urlopen()` 打 opencode.ai —— 401/1010 误判高浪费时间。

75k. **同密钥同链路多模型并行对比是定位中继故障的最快方法（2026-09-01 实战）** — 课件 500 时，先用 `curl.exe` 并行跑 4 个测试一行拍出根因：
    - 同一密钥 + 同一 baseURL + 同一 max_tokens，分别跑 `deepseek-v4-flash`/`kimi-k3`/`minimax-m3`/`muse-spark-1.2-contributor`
    - 如果 A 模型 200、B 模型 500 → **不是密钥/代理/路由问题**，是 B 模型自身的 endpoint 路由问题（chat_completions vs responses）
    - 如果全部 500 → 密钥 / 网络 / 中继故障
    - 如果 muse 单独 500、其它都 200 → 直接锁定"该模型需要走 codex_responses"，修 `providers.ts`
    **不要**因为一个模型 500 就去改密钥 / 切 provider / 加超时 —— 先用这个矩阵定根因。

75i. **OpenMAIC v1.0.0 升级流程 (2026-09-01 实证)** — v0.3.0 -> v1.0.0 有 193 个 commit / 300+ 文件变更。**步骤**：
   1. **备份 local changes**：`git checkout -b pre-vN-backup && git add -A && git commit -m backup-pre-vN`（v0.3.0 时代用户 patch 了 providers.ts 等多个文件，备份防丢）
   2. **回到 main 并 pull**：`git checkout main && git pull origin main`（v1.0.0 实际上已 merge 进 main，v1.0.0 tag 比 main 当前 HEAD 旧）
   3. **重装依赖**：`pnpm install`（v1.0.0 要求 pnpm@10.28.0，没装过要 `npm install -g pnpm@10.28.0`；耗时 ~1.5 分钟）
   4. **重新打 patch**：`shouldUseOpenAIResponsesApi()` 加 `/^muse-spark(?:-|$)/`（v1.0.0 里这个函数还在，但其他 gpt-5.x pattern 有变化）+ minimax X-Api-Key 重写
   5. **重启 OpenMAIC**：kill port 3000 + `next dev --port 3000`
   6. **验证**：`/api/server-providers` 看 providers 列表 → 跑最小课件测试

   **关键风险**：升级后 custom fetch / X-Api-Key / route 函数可能都变了，**每一个都要重新 verify**，否则可能 silent regress。

75j. **Minimax LLM 必须 sk-cp- + X-Api-Key 头（2026-09-01 实证）** — OpenMAIC 用 `minimax:MiniMax-M3` 必须：
   - `.env.local` 的 `MINIMAX_API_KEY` 填 sk-cp- 真实 key（不是过期的 oat- token）
   - `lib/ai/providers.ts` 加 custom fetch 把 Authorization 替换成 X-Api-Key
   - 否则报 "Please carry the API secret key in the 'X-Api-Key' field" 401
   - 完整诊断 / PowerShell 直写绕过 redaction 见 `opencode-provider-troubleshooting/references/minimax-x-api-key-2026-09-01.md`
