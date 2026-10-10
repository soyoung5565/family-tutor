# 教材PDF处理工作流

## 核心原则
**绝不能凭空生成课程内容，必须基于真实教材。**
没有原教材 = 凭空捏造 = 不可接受。

**视觉理解不只是裁切工具，它是理解课本教学要求的核心手段。**

## 视觉理解的三重作用

### 1. 裁切定位
找到每单元的PDF起止页（靠"第X单元"字样定位，不能靠目录页码）

### 2. 提取知识点（最重要！）
课本上的这些内容是AI知识库里没有的，必须视觉读取：
- **单元导语页** — 学习目标（如"阅读时能从所读的内容想开去"）
- **课后问题** — "思考与讨论""课后练习"等具体问题
- **生字表** — 每课要求掌握的生字、拼音
- **词语表** — 要求掌握的词语
- **语文园地** — 词句段运用、日积月累、交流平台
- **习作要求** — 写作主题、方法指导

### 3. 拆分知识点用于规划
- 每天学什么（精确到具体课文）
- 知识点有哪些（用于OpenTutor出题）
- 薄弱点在哪（用于次日补强）

## 完整处理流程

### Step 1: 视觉扫描目录
用 `vision_analyze` 读取目录页，获取单元/课文/页码结构

### Step 2: 视觉定位单元边界
在预期边界附近逐页用 `vision_analyze` 查找"第X单元"字样，确定PDF索引
- 书的目录页码 ≠ PDF索引（有封面、空白页等偏移，且偏移量不一致）
- 必须逐页验证，不能直接用目录页码裁切

### Step 3: 裁切PDF
```python
import fitz
doc = fitz.open('课本.pdf')
for name, start, end in units:
    new_doc = fitz.open()
    new_doc.insert_pdf(doc, from_page=start, to_page=end)
    new_doc.save(f'materials/{name}.pdf')
```

### Step 4: 视觉精读每单元关键页
对每个单元，用 `vision_analyze` 读取并提取：

| 读取内容 | 提取什么 | 给谁用 |
|---------|---------|--------|
| 单元导语页 | 学习目标、语文要素 | OpenTutor出题依据 |
| 每课课文页 | 原文、注释、生字拼音 | OpenTutor出题依据 |
| 课后问题 | 思考题、讨论题 | OpenTutor出题依据 |
| 语文园地 | 词句段运用、日积月累 | OpenTutor出题依据 |
| 习作要求 | 写作主题、方法指导 | OpenTutor出题依据 |
| 生字表/词语表 | 生字、拼音、组词 | OpenTutor出题依据 |

**注意：提取的知识点全部用于OpenTutor出题和Hermes规划，不传给OpenMAIC。OpenMAIC自己读PDF理解内容。**

### Step 5: 结构化写入learning-state.json
```json
{
  "day": 1,
  "topic": "第一单元：古诗词三首",
  "learning_goals": ["阅读时能从所读的内容想开去"],
  "lessons": [
    {
      "title": "宿建德江",
      "author": "孟浩然",
      "text": "移舟泊烟渚，日暮客愁新。野旷天低树，江清月近人。",
      "annotations": ["建德江：新安江流经建德的一段", "渚：水中间的小块陆地"],
      "new_characters": ["渚(zhǔ)", "德(dé)", "暮(mù)", "旷(kuàng)"],
      "key_questions": ["从哪些词句体会到诗人的愁绪？"]
    }
  ],
  "quiz_focus": ["三首诗词的背诵默写", "诗词情感对比分析", "课后问题"]
}
```

### Step 6: 上传裁切PDF到OpenMAIC
**正确方式：用"导入课堂"按钮上传裁切好的PDF**
不要在输入框打字生成topic链接——用户多次纠正这一点。

OpenMAIC会自己读PDF理解内容，自己决定教学重点。Hermes不需要告诉它怎么教。

### Step 7: 提取知识点给OpenTutor出题
Hermes需要知道有哪些知识点，是为了准确告诉OpenTutor出什么题：
```json
{
  "knowledge_points": [
    {"type": "生字", "content": "渚(zhǔ) - 水中小块陆地"},
    {"type": "课后问题", "content": "从哪些词句体会到诗人的愁绪？"},
    {"type": "学习目标", "content": "阅读时能从所读的内容想开去"}
  ]
}
```

### Step 8: 上传裁切PDF到OpenTutor
作为参考材料存储（扫描版可能无法自动解析，但需存储）

## 已知案例：六年级上册语文
- 总页数：136页（PDF）
- 封面：index 0（不在页码系统内）
- 目录：index 1-3
- 第一单元导语页：index 4（无印码页码）
- 单元边界通过视觉确认（"第X单元"字样 + 页码数字）
- 裁切后每单元5-14MB，可正常上传

## Pitfalls
1. **不要用目录页码直接裁切** — 书页码≠PDF索引，偏移量不一致
2. **不要OCR** — 用vision_analyze视觉理解，用户明确要求
3. **不要凭空生成内容** — 必须基于真实教材
4. **视觉理解不只是裁切** — 还要提取知识点用于出题
5. **知识点给OpenTutor出题，不传给OpenMAIC** — OpenMAIC自己读PDF
6. **扫描版PDF可能无法被OpenTutor解析** — 但仍然要上传存储
7. **http://链接在Hermes响应中被过滤** — 不要在聊天中发链接，用`cmd.exe /c "start <url>"`打开Edge
8. **Hermes浏览器是headless的** — 用户看不到。需要用户看到页面时，用`cmd.exe /c "start <url>"`
9. **OpenMAIC配置** — LLM/TTS/搜索都在.env.local配置，或通过设置页面（齿轮图标）配置


## 关联: 三方案对比 (OCR / Vision LLM / ABBYY)

2026-09-09 实证对比, 见 [`textbook-ocr-ai-extraction.md`](./textbook-ocr-ai-extraction.md):
- 智慧教育平台 `preview` 字段只返回 49 张, 实际全 130+ 张在 `transcode/image/N.jpg` 公开 URL
- PaddleOCR 汉字 100% / 公式 30% (分式几乎全废)
- ABBYY 16 保留版式但 8GB RAM 跑不动 130 张, 必须 30 张/批
- **Vision LLM 100% 公式 (LaTeX 写法), 100% 灰色框, 100% 角色对话** — AI 用途首选

**用户强偏好 (必须执行)**:
1. 任何 OCR/AI 提取结果必须做对比图 (左原图 / 右文本) 给用户看
2. 用户说"前N张" = 全部 N 张, 不能只做示例
3. 排版对 AI 用途不重要, 但内容必须齐全 (用 "完整页面报告" prompt 模板)
4. 用 Explorer 打开文件夹, 不要用 Hermes preview (太小)
5. PDF 文件 ≤16MB 才能 preview, 大课本必须拆 25 张/份

**判断方法**: 用户说"格式不重要" / "给AI用" → Vision LLM; 用户说"孩子看" / "排版" → ABBYY
