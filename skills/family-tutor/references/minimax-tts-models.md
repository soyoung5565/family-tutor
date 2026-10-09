# Minimax TTS 模型与音色参考

## 内置模型清单（2026-07-09 验证）

OpenMAIC 内置6个 Minimax TTS 模型，存储在 `lib/audio/constants.ts:72-77`（`MINIMAX_TTS_MODELS`）：

| 模型 ID | 名称 | 特点 | 家庭教师推荐 |
|---------|------|------|--------------|
| `speech-2.8-hd` | Speech 2.8 HD | 最新旗舰，HD音质 | ✅ **首选** |
| `speech-2.8-turbo` | Speech 2.8 Turbo | 2.8快版，音质略降但速度更快 | ✅ 备选（速度优先） |
| `speech-2.6-hd` | Speech 2.6 HD | 上一代HD | ⚠️ 备选 |
| `speech-2.6-turbo` | Speech 2.6 Turbo | 2.6快版 | 不推荐 |
| `speech-02-hd` | Speech 02 HD | 老旗舰 | ❌ 不推荐 |
| `speech-02-turbo` | Speech 02 Turbo | 02快版 | ❌ 不推荐 |

## 完整音色目录（2026-07-09 实证：303 个）

`minimax` API **支持 303 个音色**，远超 OpenMAIC 设置页内嵌的 7 个。完整列表由 `mmx speech voices` 返回，存于 `D:\projects\family-tutor\voices-all.json`（8309 字节，303 个 ID）。

### 基本款（mmx 系统音色，8 个 + 8 个高清版）

| 类别 | 音色 ID（标准） | 音色 ID（-jingpin 高清） | 特点 |
|------|-----------------|--------------------------|------|
| 男 | `male-qn-qingse` | `male-qn-qingse-jingpin` | 清新男声 |
| 男 | `male-qn-jingying` | `male-qn-jingying-jingpin` | 精英青年 |
| 男 | `male-qn-badao` | `male-qn-badao-jingpin` | 霸道男声 |
| 男 | `male-qn-daxuesheng` | `male-qn-daxuesheng-jingpin` | 大学生男声 |
| 女 | `female-shaonv` | `female-shaonv-jingpin` | 少女音色 |
| 女 | `female-yujie` | `female-yujie-jingpin` | 御姐音色 |
| 女 | `female-chengshu` | `female-chengshu-jingpin` | 成熟女性 |
| 女 | `female-tianmei` | `female-tianmei-jingpin` | 甜美 |

### 中文（Mandarin）扩展音色（24 个）

**女声（适合教小学生）**：
- `Chinese (Mandarin)_Warm_Girl` — 温暖少女（**之前默认推荐**）
- `Chinese (Mandarin)_Gentle_Youth` — 温柔青年
- `Chinese (Mandarin)_Crisp_Girl` — 干脆女孩
- `Chinese (Mandarin)_Soft_Girl` — 温柔女孩
- `Chinese (Mandarin)_Lyrical_Voice` — 抒情声线
- `Chinese (Mandarin)_Cute_Spirit` — 灵气少女
- `Chinese (Mandarin)_Sweet_Lady` — 甜美淑女
- `Chinese (Mandarin)_Warm_Bestie` — 暖心闺蜜
- `Chinese (Mandarin)_Mature_Woman` — 成熟女性
- `Chinese (Mandarin)_Kind-hearted_Antie` — 善良阿姨
- `Chinese (Mandarin)_Wise_Women` — 智慧女性
- `Chinese (Mandarin)_Kind-hearted_Elder` — 善良长辈
- `Chinese (Mandarin)_News_Anchor` — 新闻女声
- `Chinese (Mandarin)_HK_Flight_Attendant` — 港式空姐

**男声（适合男老师）**：
- `Chinese (Mandarin)_Male_Announcer` — 男主播
- `Chinese (Mandarin)_Pure-hearted_Boy` — 纯真男孩
- `Chinese (Mandarin)_Straightforward_Boy` — 直率男孩
- `Chinese (Mandarin)_Sincere_Adult` — 真诚成年
- `Chinese (Mandarin)_Gentle_Senior` — 温柔长辈
- `Chinese (Mandarin)_Reliable_Executive` — 可靠高管
- `Chinese (Mandarin)_Gentleman` — 温润男声
- `Chinese (Mandarin)_Unrestrained_Young_Man` — 奔放青年
- `Chinese (Mandarin)_Stubborn_Friend` — 倔强伙伴
- `Chinese (Mandarin)_Radio_Host` — 电台男主播
- `Chinese (Mandarin)_Southern_Young_Man` — 南方青年
- `Chinese (Mandarin)_Humorous_Elder` — 幽默老人
- `Chinese (Mandarin)_Lyrical_Voice` — 抒情声线

### 其他语种（粤语/英语/日语/韩语/法语/德语等）

303 个音色的完整列表在 `D:\projects\family-tutor\voices-all.json`。
- 粤语：`Cantonese_*`（6 个）
- 英语：`English_*`（10+ 个）
- 日语/韩语：分别 5+ 个
- 其他语种：欧亚主要语言都有覆盖

## 用户预生成的试听样本（2026-07-09）

当用户想选音色时，按以下流程生成 10 个候选样本让用户试听：

```bash
# 1. 生成候选样本到 voice-samples/ 目录
mkdir -p D:/projects/family-tutor/voice-samples
cd D:/projects/family-tutor/voice-samples

text="同学们，今天我们一起学习古诗词三首，感受古人笔下的山水之美"

# 10 个最可能适合儿童的中文女声候选
mmx speech generate --text "$text" --voice female-shaonv --model speech-2.8-hd --output-file 01_female-shaonv.mp3
mmx speech generate --text "$text" --voice female-shaonv-jingpin --model speech-2.8-hd --output-file 02_female-shaonv-jingpin.mp3
mmx speech generate --text "$text" --voice "Chinese (Mandarin)_Warm_Girl" --model speech-2.8-hd --output-file 03_Warm_Girl.mp3
mmx speech generate --text "$text" --voice "Chinese (Mandarin)_Gentle_Youth" --model speech-2.8-hd --output-file 04_Gentle_Youth.mp3
mmx speech generate --text "$text" --voice "Chinese (Mandarin)_Crisp_Girl" --model speech-2.8-hd --output-file 05_Crisp_Girl.mp3
mmx speech generate --text "$text" --voice "Chinese (Mandarin)_Soft_Girl" --model speech-2.8-hd --output-file 06_Soft_Girl.mp3
mmx speech generate --text "$text" --voice "Chinese (Mandarin)_Lyrical_Voice" --model speech-2.8-hd --output-file 07_Lyrical_Voice.mp3
mmx speech generate --text "$text" --voice "Chinese (Mandarin)_Cute_Spirit" --model speech-2.8-hd --output-file 08_Cute_Spirit.mp3
mmx speech generate --text "$text" --voice female-tianmei --model speech-2.8-hd --output-file 09_female-tianmei.mp3
mmx speech generate --text "$text" --voice female-tianmei-jingpin --model speech-2.8-hd --output-file 10_female-tianmei-jingpin.mp3

# 2. mmx 实际不识别 --output-file 路径，文件名是 speech_YYYY-MM-DD-HH-MM-SS.mp3
#    需要按生成顺序手动重命名为 01-10_xxx.mp3
```

**注意**：`mmx speech generate --output-file <path>` 实际忽略路径参数，文件生成在当前目录用时间戳命名。**重命名脚本**（让用户试听时文件名有意义）：
```python
import os
files = sorted([f for f in os.listdir('.') if f.startswith('speech_')])
voices = ['female-shaonv', 'female-shaonv-jingpin', 'Chinese (Mandarin)_Warm_Girl',
          'Chinese (Mandarin)_Gentle_Youth', 'Chinese (Mandarin)_Crisp_Girl',
          'Chinese (Mandarin)_Soft_Girl', 'Chinese (Mandarin)_Lyrical_Voice',
          'Chinese (Mandarin)_Cute_Spirit', 'female-tianmei', 'female-tianmei-jingpin']
for i, (f, v) in enumerate(zip(files, voices)):
    new = f'{i+1:02d}_{v.replace(" ", "_").replace("(", "").replace(")", "")}.mp3'
    os.rename(f, new)
```

**已生成的 10 个样本路径**（2026-07-09 实证）：
- `D:\projects\family-tutor\voice-samples\01_female-shaonv.mp3`
- `D:\projects\family-tutor\voice-samples\02_female-shaonv-jingpin.mp3`
- `D:\projects\family-tutor\voice-samples\03_Chinese_Mandarin_Warm_Girl.mp3`
- `D:\projects\family-tutor\voice-samples\04_Chinese_Mandarin_Gentle_Youth.mp3`
- `D:\projects\family-tutor\voice-samples\05_Chinese_Mandarin_Crisp_Girl.mp3`
- `D:\projects\family-tutor\voice-samples\06_Chinese_Mandarin_Soft_Girl.mp3`
- `D:\projects\family-tutor\voice-samples\07_Chinese_Mandarin_Lyrical_Voice.mp3`
- `D:\projects\family-tutor\voice-samples\08_Chinese_Mandarin_Cute_Spirit.mp3`
- `D:\projects\family-tutor\voice-samples\09_female-tianmei.mp3`
- `D:\projects\family-tutor\voice-samples\10_female-tianmei-jingpin.mp3`

**用户选完后如何应用新音色**：
1. **改服务端默认**（推荐，全局生效）：编辑 `D:\projects\OpenMAIC\lib\audio\constants.ts:1284` `'minimax-tts': '<voice_id>'`，重启 OpenMAIC
2. **改前端 localStorage**（单浏览器临时）：在 OpenMAIC 设置页面手动改 voice 字段
3. 之后再生成的课堂就用新音色

**当前默认 voice**（2026-07-10 实证）：`Chinese (Mandarin)_Crisp_Girl`（干脆女孩），用户试听后选定。**之前默认 `female-yujie`（御姐）用户觉得"太难听"**。

**重要陷阱**：`mmx speech generate --output-file <path>` 实际**忽略路径参数**，文件生成在当前目录用时间戳命名（`speech_YYYY-MM-DD-HH-MM-SS.mp3`）。**必须按生成顺序重命名**才有意义。

**试听样本清理工作流**（2026-07-10 实证）：用户选完后**及时删**未选中的样本（避免占盘），只留选中的。重命名+删除脚本：
```bash
cd D:/projects/family-tutor/voice-samples
# 只留选中的（比如 05_Crisp_Girl），删其他的
ls *.mp3 | grep -v "05_" | xargs -I {} rm -v {}
```

## 配置方式

### 服务端配置（推荐）
在 `.env.local` 写：
```bash
TTS_MINIMAX_API_KEY=<oat-xxx access_token, 见 SKILL Pitfall 38>
# Base URL 默认为 https://api.minimaxi.com，无需写
```

### 前端配置（localStorage，临时）
通过 OpenMAIC 设置页面选择 provider=`minimax-tts`，填入 voice 和 key。

### 验证
```bash
# 字段名严格：ttsProviderId/ttsVoice/audioId
curl -s -X POST http://localhost:3000/api/generate/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"测试","audioId":"test","ttsProviderId":"minimax-tts","ttsVoice":"Chinese (Mandarin)_Warm_Girl"}' \
  -o /tmp/tts.wav -w "HTTP %{http_code}, size=%{size_download}\n"
# 期望：HTTP 200, size>10KB（成功）
# 失败：500 "API key required for TTS provider: minimax-tts" → 缺 TTS_MINIMAX_API_KEY
```

## 关键注意事项
- **minimax LLM 和 minimax TTS 是两套独立的 key**：
  - LLM：`MINIMAX_API_KEY`（`sk-cp-` 静态 key，Anthropic 兼容端点）
  - TTS：`TTS_MINIMAX_API_KEY`（**OAuth `oat-` access_token**，`mmx auth login` 拿的，不是 `sk-cp-`）
  - 详见 SKILL.md Pitfall 14a/38/40
- 路径：`/api/generate/tts` 字段名严格，不要用 `provider`/`voice`/`input`（错就 MISSING_REQUIRED_FIELD）
- minimax 官方 CLI（`mmx`）能调所有模态，是验证 TTS/Image 是否真工作的最可靠工具
