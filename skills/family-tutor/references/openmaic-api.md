# OpenMAIC API 参考

## PDF解析
```
POST /api/parse-pdf
Content-Type: multipart/form-data

Fields:
- pdf: File (required)
- providerId: string (default: "unpdf")
- apiKey: string (optional)
- baseUrl: string (optional)

Response:
{
  "success": true,
  "data": {
    "text": " ",           // 扫描版PDF无文字层
    "images": ["data:image/png;base64,...", ...],  // 每页一张图片
    "processingTime": 6396,
    "fileName": "unit1.pdf",
    "fileSize": 5314928
  }
}
```

**关键**：`data` 字段就是 generate-classroom 的 `pdfContent` 入参——直接把 `parse.json['data']` 整个 JSON 序列化塞给 `pdfContent` 即可。

## 课堂生成
```
POST /api/generate-classroom
Content-Type: application/json

Body:
{
  "requirement": "课程描述（简洁！只写"今天学哪课"）",  // 1-2句话
  "pdfContent": { ... },           // parse-pdf 的 data 字段（可选但强烈建议传）
  "enableWebSearch": true,
  "webSearchProviderId": "baidu",
  "enableTTS": true,
  "agentMode": "deep"              // deep=质量高, fast=快速（约3分钟）
}

Response:
{
  "success": true,
  "jobId": "u45qLYGHtD",
  "status": "queued",
  "pollUrl": "http://localhost:3000/api/generate-classroom/u45qLYGHtD",
  "pollIntervalMs": 5000
}
```

**requirement 的反例（2026-07-09 用户纠正）**：
- ❌ 把原文+注释+课后题+学习目标全塞进 requirement（"备课"行为，污染OpenMAIC自主发挥）
- ❌ 在 requirement 里指定课时数、页数、教学顺序（应该让 OpenMAIC 自己规划）
- ✅ `"六年级上册语文第一单元第1课《古诗词三首》"` 这种1-2句话足矣

## 端到端脚本（生成课堂）
```bash
# 1. 解析PDF
curl -s -X POST http://localhost:3000/api/parse-pdf \
  -F "pdf=@D:/projects/family-tutor/materials/unit1_古诗词三首_草原_丁香结.pdf" \
  -F "providerId=unpdf" > /tmp/parse.json

# 2. 提取 data 字段
PDF_DATA=$(python -c "import json;d=json.load(open('/tmp/parse.json'));print(json.dumps(d['data']))")

# 3. 提交生成
JOB=$(curl -s -X POST http://localhost:3000/api/generate-classroom \
  -H "Content-Type: application/json" \
  -d "{\"requirement\":\"六年级上册语文第一单元第1课《古诗词三首》\",
       \"pdfContent\": $PDF_DATA,
       \"agentMode\":\"fast\",\"enableWebSearch\":false,\"enableTTS\":false}" \
  | python -c "import json,sys;print(json.load(sys.stdin)['jobId'])")

echo "Job: $JOB"

# 4. 轮询（5-10s/次）
for i in {1..60}; do
  sleep 10
  R=$(curl -s http://localhost:3000/api/generate-classroom/$JOB)
  S=$(echo "$R" | python -c "import json,sys;print(json.load(sys.stdin).get('status','?'))")
  P=$(echo "$R" | python -c "import json,sys;print(json.load(sys.stdin).get('progress','?'))")
  echo "[$i] $S - $P%"
  [ "$S" = "succeeded" ] && {
    echo "$R" | python -c "import json,sys;print('URL:', json.load(sys.stdin).get('result',{}).get('url','N/A'))"
    break
  }
  [ "$S" = "failed" ] && { echo "FAIL"; break; }
done
```

## 轮询课堂状态
```
GET /api/generate-classroom/{jobId}

Response:
{
  "status": "running",  // queued → running → succeeded/failed
  "step": "generating_scenes",  // generating_outlines → generating_scenes
  "progress": 75,
  "result": { "url": "/classroom/85u7AJHi8S" }  // succeeded时返回
}
```

## 课件数据读盘
- **存盘路径**：`D:\projects\OpenMAIC\data\classrooms\{id}.json`
- **直接 `cat` 看质量**（讲稿在 `actions[].type='speech'.text`、元素文字在 `content.canvas.elements[].content` HTML 片段）
- `/api/classroom/{id}` 路由404是正常的，直接读盘文件

## TTS 试听
```
POST /api/generate/tts
Content-Type: application/json
Body: {"text":"测试","audioId":"test","ttsProviderId":"minimax-tts","ttsVoice":"female-yujie"}
```

字段名**严格**：是 `ttsProviderId`/`ttsVoice`/`audioId`，不是 `provider`/`voice`/`input`（错就返回 MISSING_REQUIRED_FIELD）

## 配置验证
`curl http://localhost:3000/api/server-providers` 应该返回：
- `providers.minimax.models`：`["MiniMax-M3", "MiniMax-M2.7-highspeed", "MiniMax-M2.7"]`
- `tts`：含 `openai-tts`（MIMO代理）和 `minimax-tts`
- `webSearch`：含 `baidu` 和 `tavily`

## 注意事项
- 课堂生成耗时3-5分钟（fast模式约3分钟）
- 扫描版PDF无文字层，但 parse-pdf 会提取每页为 base64 PNG
- 重启OpenMAIC后配置才生效
- **requirement 越简短越好**，真正的内容通过 `pdfContent` 传入
