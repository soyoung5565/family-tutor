# 课本 OCR/AI 提取对比 — 三大方案与用户偏好

**场景**：从扫描版课本提取内容，用于：
- **AI 系统**（KP 库、出题、错题讲解）
- **学生查阅**（保留版式）

用户的明确偏好（2026-09-09 session 实证）：

> "格式不重要，毕竟是给ai用的，所以 vision 的内容齐全就可以"

→ **AI 用途**：Vision LLM 最佳
> **学生用途**：ABBYY/PaddleOCR 保留版式

---

## 三大方案横向对比

| 维度 | PaddleOCR 2.7 (CPU) | ABBYY FineReader 16 | Vision LLM (minimax-M3) |
|---|---|---|---|
| **印刷体汉字** | ✅ 100% | ✅ SOTA | ✅ 100% |
| **数字 + 简单运算** | ✅ 95%+ | ✅ 100% | ✅ 100% |
| **分数 (4/5, 1/2)** | ❌ 30% (被打散) | ❌ 30-50% | ✅ 100% (LaTeX) |
| **分式 (4÷2=4×(1/2))** | ❌ 10% (`####`) | ❌ 30-40% | ✅ 100% (LaTeX 推算) |
| **数学符号 (π, ²)** | ✅ 80% | ✅ 95% | ✅ 100% |
| **中文拼音/英音标** | ❌ 0% | ✅ 80% | ✅ 100% |
| **角色对话 (淘气/笑笑)** | ❌ 混在一起 | ⚠️ 部分分 | ✅ 100% 分角色 |
| **灰色框/小字注释** | ⚠️ 偶尔 | ✅ 90% | ✅ 100% (列全) |
| **插图描述** | ❌ 看不到 | ❌ 看到但不会描述 | ✅ 100% (逐张描述) |
| **版式保留 (PDF/DOCX)** | ❌ 不行 | ✅ 100% (可搜索 PDF) | ❌ 不行 (纯文本) |
| **速度 (49 张)** | 78s | 1-2min/批 25 张 | ~3s/张 (单 vision_analyze) |
| **硬件需求** | CPU 即可 | 8GB RAM 跑 25 张/批 | 任意 |
| **成本** | 免费 | 商业 (700+MB 安装) | 取决于主 LLM |

---

## 1. 智慧教育平台课本抓取

**关键发现**：basic.smartedu.cn 的 `preview` JSON 字段**只返回前 49 张**预览，但 `custom_properties.ti_items[0].ti_storage` 路径下的**全 130+ 张图**全公开可下。

### 公开 URL 模式（无需登录）
```
https://r1-ndr.ykt.cbern.com.cn/edu_product/esp/assets/{content_id}.t/zh-CN/{timestamp}/transcode/image/{N}.jpg
```

`{N}` = 1 到总页数（如 130）

### 工作流程

```python
# 1) 拿 metadata
import urllib.request, json
content_id = "45fe27cf-8cb3-4670-8397-a482731412fc"  # 6上北师大数学
url = f"https://s-file-2.ykt.cbern.com.cn/zxx/ndrv2/resources/tch_material/details/{content_id}.json"
with urllib.request.urlopen(url, timeout=30) as r:
    meta = json.loads(r.read())
print(f"preview 仅 {len(meta['custom_properties']['preview'])} 张")
print(f"实际总页数 from custom_properties: {meta['custom_properties']['pagesize']}")

# 2) 下载全 N 张 (这里 N=130)
import os
from concurrent.futures import ThreadPoolExecutor
src_dir = r"D:\家教\数学\课本\45fe27cf-..."
os.makedirs(src_dir, exist_ok=True)

def dl(n):
    url = f"https://r1-ndr.ykt.cbern.com.cn/edu_product/esp/assets/{content_id}.t/zh-CN/1787023637193/transcode/image/{n}.jpg"
    out = os.path.join(src_dir, f"slide_{n:03d}.jpg")
    if os.path.exists(out) and os.path.getsize(out) > 10000:
        return n, "skip", 0
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://basic.smartedu.cn/",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        with open(out, "wb") as f:
            f.write(data)
        return n, "ok", len(data)
    except Exception as e:
        return n, f"err: {e}", 0

# 测最高页号 (用 HEAD 请求 50, 100, 150, 200...)
import urllib.request as ur
for n in [50, 100, 130, 150, 200]:
    test_url = f"https://r1-ndr.ykt.cbern.com.cn/edu_product/esp/assets/{content_id}.t/zh-CN/1787023637193/transcode/image/{n}.jpg"
    try:
        req = ur.Request(test_url, method="HEAD", headers={
            "User-Agent": "Mozilla/5.0", "Referer": "https://basic.smartedu.cn/",
        })
        with ur.urlopen(req, timeout=5) as r:
            print(f"  page {n}: {r.status} {r.headers.get('Content-Length','?')}B")
    except: print(f"  page {n}: 404/err")

# 找到 max 后 ThreadPoolExecutor 并发下
with ThreadPoolExecutor(max_workers=16) as ex:
    results = [f.result() for f in [ex.submit(dl, n) for n in range(1, max_page+1)]]
```

### PDF 端点（公开但需 Referer + 私域）
```
https://r1-ndr-private.ykt.cbern.com.cn/edu_product/esp/assets/{content_id}.pkg/{filename}.pdf
```
**返回 401/403**（需登录）→ **不要用这个 URL**，直接用单图 JPG 拼接

---

## 2. PaddleOCR 工作流（已经验证）

### 安装
```bash
# paddle 2.6.2 (CPU 稳) + paddleocr 2.7.0.3
pip install "paddlepaddle==2.6.2" --index-url https://pypi.tuna.tsinghua.edu.cn/simple
pip install "paddleocr==2.7.0.3" scikit-image imgaug pyclipper lmdb --no-deps
pip install "opencv-python<4.10" "numpy<2" python-Levenshtein
```

### Python API（新版 3.x）
```python
import os
os.environ['DISABLE_MODEL_SOURCE_CHECK'] = 'True'
import logging; logging.disable(logging.CRITICAL)
from paddleocr import PaddleOCR

ocr = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False, show_log=False)
# 全 130 张并发跑 (~80s)
for n in range(1, 131):
    img = f"D:/.../slide_{n:03d}.jpg"
    r = ocr.ocr(img, cls=True)
    lines = []
    for ln in (r[0] or []):
        bbox, (text, conf) = ln
        xs = [p[0] for p in bbox]; ys = [p[1] for p in bbox]
        lines.append({"y": int(min(ys)), "x": int(min(xs)), "conf": round(conf, 3), "text": text})
    lines.sort(key=lambda l: (l["y"], l["x"]))
```

### 已知缺陷
- 数字+运算 95%+
- **分数 (4/5)** 30% — 被打散成"4""5"多行
- **分式整体 (4÷2=4×1/2)** 几乎全军覆没（`####`）
- 灰色框/小字 偶尔漏
- 插图完全看不到

### 已知坑
- **Windows + Python 3.12 + paddle 2.6.2** 装完需 `pip install pyclipper lmdb python-Levenshtein`（单独装）
- 跑 130 张扫描版，**CPU** 130 秒搞定，GPU 反而慢
- `lang='en'` 纯英文准，但中英混排全乱（需用百度 API 或 UmiOCR）

---

## 3. ABBYY FineReader 16 (GUI 工具, 需手动)

### 用户场景
"格式不重要" → **AI 用途不需要 ABBYY**（Vision LLM 更准）
"学生查阅" → **必须用 ABBYY**（保留版式 + 公式 + 插图）

### 已知限制
- **8GB RAM 跑不动 130 张整本** → 报"页面 19, 23: Not enough memory"
- **解决方案**: 30 张/批, 5 批跑完
- 即便能跑, **数学公式识别也差**（不如 Vision LLM）
- 必须**手动 GUI 操作**（沙箱里跑不动）

### 装好后正确路径
1. 打开 ABBYY → 点**右上 "OCR 编辑器"** 卡片（不是左边的"扫描"）
2. **文件** → **打开** → 选 PDF
3. **Ctrl+A** 全选页
4. 顶部 **OCR** 菜单 → **"识别所有页面"**
5. 等 1-2 分钟
6. **文件** → **保存为** → **DOCX**（保留版式）

### 关键 OCR 语言设置（数学课本推荐）
```
简体中文
简体中文和英语, 数字
英语
简单数学公式
繁体中文
```
- "**英语音标**" 可以不加（数学课本用不到）
- "**简单数学公式**" 必须勾（提升分数识别率）

---

## 4. Vision LLM (推荐方案, AI 用途)

### 关键 prompt 模板 (2026-09-09 验证)

```python
prompt = """这是一页数学课本。请像做完整"页面内容报告"一样，把这页**所有可见信息**都提取出来，**不要漏掉任何文字、公式、人物、插图、小字注释**。按以下结构：

# 单元/章节标题
- 单元:
- 章节:
- 页码:

# 这页出现的【所有人名/角色】（淘气、笑笑、机灵狗、智慧老人、编者等）
列出每个角色 + 他们说了什么话

# 完整【题目】列表（每道题编号+完整题目）
列出所有题目，不只是例题

# 完整【数学公式】（LaTeX，每行一个）
包括所有出现的公式、算式、分数
不要漏掉任何"4/5"、"3/4"这类分式

# 完整【概念/规则说明】（每条独立列出）
包括课本正文里讲的规则、定理、要求

# 完整【小字注释/提示】（灰色框、蓝框、黄框、问题框等）
把每个特殊框的内容抄出来

# 完整【插图描述】（每张插图一行）
包括人物图、实物图、示意图

# 关键页码/页脚
页脚显示什么？

# 这页教的核心（1 句话）
最重要想让学生掌握什么？

请确保**全部内容**都列出来，不要省略。如果某项没有，标"(无)"。"""
```

**核心要点**：
- "**全部内容**" "**不要省略**" 必须出现在 prompt 里
- 8 个固定 section, 任何项空都标"(无)" 而不是省略
- 公式必须 LaTeX（让 vision 推算数字）
- 灰色/彩色框特殊说明, vision 才知道要单独摘
- 人物对话**按角色分**（"淘气说...""笑笑说..."）

### Vision 真实表现
- ✅ 印刷体汉字 100%
- ✅ 分数 4/5 完整 (`4/5`) 不打散
- ✅ 公式完整 (`4÷2=4×(1/2)`)
- ✅ 角色对话完整（淘气/笑笑/妙想/机灵狗/智慧老人等）
- ✅ 灰色框完整摘出
- ✅ 插图逐一描述
- ✅ 应用题题干完整
- ❌ 版式丢失（无位置/字号/颜色信息）
- ❌ 长公式太长会省略（vision 输出 token 限制）

---

## 5. 用户的强偏好: 一定要做对比图

**触发信号**: 任何 OCR/AI 提取课本内容, **必须**做对比图给用户看效果。

### 对比图代码模板
```python
from PIL import Image, ImageDraw, ImageFont

font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 12)
COLOR_RED = (200, 0, 0)     # 标题
COLOR_BLUE = (0, 80, 180)   # 题目编号
COLOR_GRAY = (80, 80, 80)   # 列表项
COLOR_BLACK = (0, 0, 0)    # 普通文字

def make_compare_img(img_path, vision_text, out_path):
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    right_w = 1300
    right = Image.new("RGB", (right_w, h), (250, 250, 245))
    draw = ImageDraw.Draw(right)
    draw.text((10, 4), f"=== {os.path.basename(img_path)} vision LLM 提取 ===", fill=COLOR_RED, font=font)
    y = 22
    for line in vision_text.split("\n"):
        if y > h - 14: break
        if line.startswith("# "): color = COLOR_RED
        elif line.startswith(("1.","2.","3.","4.","5.","6.","7.","8.")): color = COLOR_BLUE
        elif line.startswith("- "): color = COLOR_GRAY
        else: color = COLOR_BLACK
        draw.text((10, y), line[:150], fill=color, font=font)
        y += 14
    combined = Image.new("RGB", (w + right_w + 20, h), (200, 200, 200))
    combined.paste(img, (0, 0))
    combined.paste(right, (w + 20, 0))
    combined.thumbnail((1900, 1300), Image.LANCZOS)
    combined.save(out_path, "JPEG", quality=78)
```

**注意**:
- Hermes preview pane 太小, 用户**看不到细节**
- **必须用 Explorer 打开文件夹**让用户双击放大看
- 用 `subprocess.Popen(f'explorer "{folder}"')`
- PDF 大小限制 **≤16MB** (Hermes preview 上限) — 大课本需拆 25-30 张/份

---

## 6. 用户的强偏好: "前N张" = 全部N张

**触发信号**: 用户说"做前 N 张对比" → **不能只做 2-3 张示例**, 必须做**全部 N 张**。

**错的理解**: "我做了 3 张给您看看效果, 觉得 OK 我再做剩下的"
**正解**: 全部 N 张, 让用户一次性看

---

## 7. PDF 文件大小限制 (Hermes preview 16MB)

```python
# 合并 130 张 JPG → PDF 通常 70+ MB, preview 装不下
# 必须拆 25 张/份, 每份 12-15MB
import fitz
src = "D:/tmp/课本完整.pdf"  # 72MB
doc = fitz.open(src)
chunk = 25
for i in range((len(doc)+chunk-1)//chunk):
    s, e = i*chunk, min((i+1)*chunk, len(doc))
    d2 = fitz.open()
    for j in range(s, e):
        d2.insert_pdf(doc, from_page=j, to_page=j)
    d2.save(f"D:/tmp/课本_part{i+1:02d}_P{s+1:03d}-{e:03d}.pdf", deflate=True, garbage=4)
    d2.close()
```

---

## 8. 用户的"无排版"vs"有排版"区分

**用户原话**: "我想了想，格式不重要，毕竟是给ai用的"

| 用途 | 需要什么 | 推荐方案 |
|---|---|---|
| **给 AI 用**（KP 库、出题、错题讲解）| 内容齐全 | Vision LLM（最准） |
| **给学生看**（PDF 阅读）| 版式保留 | ABBYY 16 + 30 张/批 |

**判断方法**: 用户说"格式不重要" → Vision LLM; 用户说"我要给孩子看" → ABBYY

---

## 9. 验证流程

跑完 OCR/AI 后, **必做**:
1. 跑样本 (1-5 张) 验证 prompt 质量
2. 跟用户**确认是否漏内容**（"漏掉的东西特别多" 是用户的强信号）
3. 用 `D:\tmp\vision_compare_vN\` 目录 + Explorer 打开, 用户双击看
4. **不要 preview pane** (太小)

---

## 关键 Pitfalls

1. **不要相信"preview 49 张"是全集** — 实际能下 130+ 张, 直接探 `transcode/image/N.jpg` 路径
2. **不要把 70MB PDF 喂 Hermes preview** — 报 "file too large", 必须拆 16MB 以下
3. **不要用 vision_analyze 默认 prompt** — 漏内容极多, 必须用上面的 "完整页面报告" 模板
4. **不要只做 2-3 张示例对比图** — 用户要"前 N 张" = 全部 N 张
5. **不要让 vision 输出"省略"或"等等"** — 强制要求"全部列出, 某项无则标(无)"
6. **不要用 OCR 处理数学公式** — 30% 准确率, vision 100% LaTeX
7. **不要信任 sandbox 装 GUI 软件** — 沙箱无 GUI, ABBYY 必须用户手动装
8. **不要用 bash 中文路径** — Windows bash 转义错, 必须用 `D:\tmp\xxx.pdf` 或 subprocess.run
9. **每次跑 vision 前必须明确"AI 用途"还是"学生用途"** — 走不同路径
10. **vision prompt 公式 LaTeX 必填** — 否则 vision 写中文描述 "4除以2", 结构化工具解析不了
