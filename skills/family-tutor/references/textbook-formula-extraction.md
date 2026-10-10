# 课本知识点提取：v7 公式层（2026-09-10 实证）

## 分工（用户拍板）

- **PaddleOCR**：跑字 + 定位坐标（文字部分 100% 准确）——已含在 v6 每页 lines
- **Vision (MiniMax-M3)**：只补"公式层"——带公式的页丢给视觉模型
- **测试题目**：完全忽略，不提取

## 产物

- `D:/家教/数学/知识库/math_grade6_v6.json` — OCR 文字+坐标+61 KP（unit 字段有 bug：全是 u1）
- `D:/家教/数学/知识库/math_grade6_v7.json` — v6 + 每页 `formulas` 列表 + unit 修正
- `D:/家教/数学/知识库/vision_formulas/slide_NNN.json` — vision 原始输出（断点续跑靠它）

## 脚本

- `D:/家教/系统/scripts/extract-formulas-vision.py` — 批量调 vision，跳过已有输出，3 次重试
- `D:/家教/系统/scripts/merge-v7.py` — 合并进 v7 + 修 unit + 统计

## API 事实（实测 2026-09-10）

- 端点：`POST https://api.minimaxi.com/anthropic/v1/messages`
  - ⚠️ **不是** `/anthropic/messages`（404）。Anthropic SDK 会对 base_url 自动拼 `/v1/messages`
- 头：`X-Api-Key: <MINIMAX_CN_API_KEY>`（sk-cp- 静态 key 可用）+ `anthropic-version: 2023-06-01`
- model：`MiniMax-M3`；body 结构：`{"model":"MiniMax-M3","max_tokens":2048,"messages":[{"role":"user","content":[{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":<b64>}},{"type":"text","text":<prompt>}]}]}`
- 响应：`data.content[].text` 拼接
- 速度：单页 ~4s，120 页 ~16 分钟；QPS 不需要节流（静态 key 无 rpm 墙）

## Prompt 要点

"只列出本页所有【公式】和【数学算式】，每行一个，保持分数/除号/乘号原样（2/5÷3/4=2/5×4/3）；1) 只抄真实内容不推断不补全 2) 横排拆行合并 3) 栏目名和题目文字不抄 4) 无公式回答'无'"

## 判定哪些页给 vision

用 v6 每页 lines 的类型统计（`formula_or_digit` / `formula_fail` / `low_conf`），无公式特征页跳过。数学六上 130 页里 9 页无公式特征（封面/扉页/附录：slide 2,3,4,121,123,125,127,129,130）→ 实际跑 121 页。

## Pitfall

1. **v6 的 `page_text[*].unit` 全是 u1**（bug）——book_page 正确；合并时用 `index.slide_to_page_map` 边界重算 unit：`for start,unit in sorted(boundaries): if start<=slide: unit=u`
2. **slide→书页号**：`unit_starts` 边界推（slide 7=P2, 16=P11, 38=P33, 49=P44, 54=P49, 62=P57, 72=P67, 78=P73, 80=P75, 91=P86, 96=P91, 108=P103, 113=P108, 121=P116）
3. **模型名大小写**：`MiniMax-M3` 正常；如 400/404 含 model 字样可兜底尝试 `minimax-m3`
4. **中文路径写文件**：Hermes write_file 工具对含中文/转义的路径会 bash 转义失败 → 用 execute_code 的 open()/shutil 写，或先写 ASCII 临时路径再复制
5. **执行含中文路径的脚本**：terminal bash 找不到带 D:/ 与中文混用的路径 → 用 execute_code subprocess.run 调 venv python 更稳
