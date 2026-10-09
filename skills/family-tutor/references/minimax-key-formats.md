# Minimax Key 格式与 API 端点对应关系（2026-07-09 实证）

## 核心结论

**`sk-cp-` 开头的 key 和 OAuth `access_token` 是两套独立的 minimax 凭证，权限范围不同。**
**更准确地说：minimax 原生 API（`/v1/t2a_v2`、`/v1/image_generation` 等）走 OAuth access_token 鉴权，**
**`sk-cp-` 只是 anthropic 兼容层专用的"壳 key"。** 用户报的"minimax 一 key 通吃"是**误解**——
Token Plan 套餐**确实**包含全模态，但接入方式是 OAuth 登录拿 access_token，不是用 `sk-cp-` 静态 key。

## 用户的 key 实证

用户的 minimax key（`sk-cp-...T_4g`）：

| 端点 | 用途 | 协议 | 是否能用 sk-cp- key |
|------|------|------|---------------------|
| `https://api.minimaxi.com/anthropic/v1/messages` | LLM (MiniMax-M3) | Anthropic | ✅ 能用 |
| `https://api.minimaxi.com/v1/t2a_v2` | TTS (speech-2.8-hd) | HTTP 自有 | ❌ 1004 "login fail" |
| `https://api.minimaxi.com/v1/image_generation` | Image (image-01) | HTTP 自有 | ❌ 1004 / 404（端点路径错也会 404） |
| `https://api.minimaxi.com/v1/video_generation` | Video (Hailuo) | HTTP 自有 | ❌ 推测 1004 |
| `https://api.minimaxi.com/v1/token_plan/remains` | Quota 查询 | HTTP 自有 | ❌ 同样 1004 = key 类型错 |

`sk-cp-` 是 minimax 为 **Anthropic 兼容生态**单独发行的套餐 key，**只走 Anthropic 兼容端点**。原生 API（TTS/Image/Video）需要 **OAuth access_token**（不是 `ey...` 静态 key——`ey...` 是 minimax 文档示例里的"API secret key"字段名占位符，实际填的就是 OAuth access_token）。

## 诊断步骤（用户报"minimax TTS/Image 不通"时）

1. **直接 curl 测试原生端点**（不经过 OpenMAIC）：

```bash
# TTS
curl --max-time 30 -X POST "https://api.minimaxi.com/v1/t2a_v2" \
  -H "Authorization: Bearer <用户key>" \
  -H "Content-Type: application/json" \
  -d '{"model":"speech-2.8-hd","text":"测试","stream":false,"output_format":"hex","voice_setting":{"voice_id":"Chinese (Mandarin)_Warm_Girl","speed":1.0,"vol":1,"pitch":0},"audio_setting":{"sample_rate":32000,"bitrate":128000,"format":"mp3","channel":1},"language_boost":"auto"}'

# Image（注意：minimax 官方 CLI 端点是 `/v1/image_generation` 不带中间斜杠！）
curl --max-time 30 -X POST "https://api.minimaxi.com/v1/image_generation" \
  -H "Authorization: Bearer <用户key>" \
  -H "Content-Type: application/json" \
  -d '{"model":"image-01","prompt":"a cat","n":1,"response_format":"url"}'
```

2. **判断结果**：
   - 200 + 返回音频/图片数据 → key 有效
   - `{"base_resp":{"status_code":1004,"status_msg":"login fail"}}` → **key 类型错**（用户 `sk-cp-` 这种），必须 OAuth 登录拿 access_token
   - 401 / 403 → key 过期或被禁用
   - 404 → 端点路径错（参考下方"minimax 官方 CLI 端点"表）

3. **向用户解释**：
   - `sk-cp-` 是 minimax 为 Anthropic SDK 生态单独发行的特殊 key
   - Token Plan 套餐"全模态覆盖"是真的，但接入方式是 **OAuth 登录** 拿 access_token，**不是**用 `sk-cp-` 这种静态 key
   - 解决路径：① `mmx auth login` 拿 access_token ② 让用户去 minimax 控制台"Token Plan 管理"找 OAuth access_token（不是订阅 Key）
   - 不要让用户浪费时间试"再加一个 `ey...` key"——`ey...` 是文档字段名占位符，**实际填的还是 OAuth access_token**

## minimax 1004 错误码（来自 minimax 官方 docs/api-reference/api-overview）

| 错误码 | 含义 | 解决方法 |
|--------|------|---------|
| 1000 | 未知错误/系统默认错误 | 请稍后再试 |
| 1001 | 请求超时 | 请稍后再试 |
| 1002 | 请求频率超限 | 请稍后再试 |
| **1004** | **未授权/Token 不匹配/Cookie 丢失** | **请检查 API Key**（实际多见：用了 sk-cp- 而非 OAuth access_token） |
| 1008 | 余额不足 | 请检查您的账户余额 |
| 2013 | 参数错误 | 请检查请求参数 |
| 2049 | 无效的 API Key | 请检查 API Key |
| 2056 | 超出 Token Plan 资源限制 | 请等待下一个时间段资源释放后，再次尝试 |

**快速验证 1004 是 key 类型错还是其他错**：
- **`curl /v1/token_plan/remains -H "Authorization: Bearer <key>"` 同样 1004** = key 类型错（不是端点错）
- 如果 `/v1/token_plan/remains` 返回 200 但 `/v1/t2a_v2` 1004 = key 有效但该端点未开通

## 临时方案（OAuth access_token 拿到之前）

如果用户没有 OAuth access_token，TTS 用以下两种方案：
- **A. MIMO 代理**（用户之前用着没问题）：`D:\projects\family-tutor\mimo-tts-proxy.py`（端口8787），OpenMAIC 配 `TTS_OPENAI_API_KEY=<mimo-tp-key>` + `TTS_OPENAI_BASE_URL=http://127.0.0.1:8787/v1`
- **B. 浏览器原生 TTS**：OpenMAIC 设置页里选 `browser-native-tts`，无需 API，但语音质量一般

图片生成没有好的 fallback（minimax 是主流选），建议：
- 等 OAuth access_token
- 或换 provider：Doubao Seedream / 阿里 DashScope 万相 / Stability AI

## minimax TTS API 文档要点（来自 platform.minimaxi.com/docs/api-reference/speech-t2a-http）

- 端点：`https://api.minimaxi.com/v1/t2a_v2`
- Auth：`Authorization: Bearer <access_token>`（Bearer 前缀**必须**有；Bearer 加不加不是 1004 的原因——是 key 类型）
- 模型：speech-2.8-hd（推荐，默认）、speech-2.8-turbo、speech-2.6-hd、speech-2.6-turbo、speech-02-hd、speech-02-turbo
- 音色（中文推荐）：`Chinese (Mandarin)_Warm_Girl`（温暖少女，给孩子听最合适）、`female-shaonv`（少女）、`female-yujie`（御姐）
- 必填 body 字段：`model`、`text`、`stream`（必须 false，否则要 WebSocket）、`output_format`（hex/base64/url）、`voice_setting.voice_id`、`audio_setting`（含 sample_rate/bitrate/format/channel）
- 可选 body 字段：`language_boost`（auto/chinese/english 等）、`subtitle_enable`、`timber_weights`、`voice_modify`、`pronunciation_dict`、`audio_setting` 完整

## minimax 官方 CLI 端点（2026-07-09 源码证实）

minimax 官方 CLI（`github.com/MiniMax-AI/cli`，命令 `mmx`）`src/client/endpoints.ts` 暴露的**真实端点**和官方 API 文档示例**不完全一致**：

| 模态 | CLI 真实端点 | 文档示例 | 备注 |
|------|--------------|----------|------|
| LLM | `${baseUrl}/anthropic/v1/messages` | 同左 | CLI 调 LLM 也走 anthropic 路径 |
| TTS | `${baseUrl}/v1/t2a_v2` | 同左 | ✅ |
| Image | `${baseUrl}/v1/image_generation` | `/v1/image/generation` | **没有中间斜杠**，文档示例错 |
| Video | `${baseUrl}/v1/video_generation` | 类似 | |
| Music | `${baseUrl}/v1/music_generation` | | |
| Voices | `${baseUrl}/v1/get_voice` | | 查可用音色 |
| Quota | `${baseUrl}/v1/token_plan/remains` | | **调试用**——查套餐剩余额度 |
| Search | `${baseUrl}/v1/coding_plan/search` | | minimax 联网搜索 |
| VLM | `${baseUrl}/v1/coding_plan/vlm` | | |

`baseUrl` 按区域：
- `global`: `https://api.minimax.io`
- `cn`: `https://api.minimaxi.com`

**OAuth 而非静态 key（最关键发现）**：minimax CLI **不是**用 `sk-cp-` 静态 key 调 API，而是用 **OAuth Device Authorization Grant**（`mmx auth login` → 浏览器授权）拿到 `access_token` + `resource_url`（动态 API gateway 主机名），再用 `Authorization: Bearer ${access_token}` 调 API。

**`sk-cp-` 是 minimax 为 Anthropic 兼容生态单独发行的 key**，**和 OAuth access_token 是两套独立凭证**——这解释了为什么 `sk-cp-` 在 `/v1/t2a_v2` 等原生端点 1004 拒绝：原生端点只认 OAuth access_token，**`sk-cp-` 是 anthropic 兼容层专用**。

诊断步骤（**不绕弯**）：
- **`curl /v1/token_plan/remains -H "Authorization: Bearer <key>"` 同样 1004 必然是 key 类型错**（不是端点错），不要去查端点路径
- `sk-cp-` 只能用 `/anthropic/v1/messages`（LLM），**其他原生端点都用不了**
- 想用 TTS/Image：要么 `mmx auth login` 拿 OAuth access_token，要么去控制台开"按量付费"key（也是走 OAuth）

OAuth 实现细节（来自 `src/auth/oauth.ts` + `src/auth/refresh.ts`）：
- CLIENT_ID: `659cf4c1-615c-45f6-a5f6-4bf15eb476e5`
- Token URL: `${OAUTH_HOSTS[region]}/oauth2/token`，`global` → `https://account.minimax.io`，`cn` → `https://account.minimaxi.com`
- Grant: `grant_type=refresh_token` 续期，`device_code` 首次授权
- 响应字段：`access_token`、`refresh_token`、`expired_in`（绝对 Unix ms）、`resource_url`（API gateway 主机名）
- 配置存到 `~/.mmx/config.json` 的 `oauth` 子键

**用户拿不到 OAuth access_token 时的 fallback**：
- TTS: MIMO 代理（端口 8787）或浏览器原生 TTS
- Image: 暂时关掉，或换 Doubao Seedream / 阿里 DashScope / Stability AI

## 用户常见误解（避免反复解释）

1. **"minimax 套餐一 key 通吃"** — ❌ 错。Token Plan 套餐**确实**全模态覆盖，但接入方式是 **OAuth 登录拿 access_token**，不是用 `sk-cp-` 静态 key。`sk-cp-` 是 anthropic 兼容层专用。
2. **"minimax 文档里写 `ey...` 开头的 key"** — ❌ 错。`ey...` 是文档示例里的**字段名占位符**（"your api key"），**不是**一种 key 格式。实际填的是 OAuth access_token。
3. **"客服说 anthropic 路径是 TTS 也能用"** — ❌ 错。客服说"国内服务填 `https://api.minimaxi.com/anthropic`"是回答 **LLM** 端点的问题。TTS/Image 没有 anthropic 兼容路径。**别把客服关于 LLM 的回复扩展到 TTS/Image**。
