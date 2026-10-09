# OpenMAIC 内部架构解析（2026-09-08 关键发现）

**目的**：未来 session 改 OpenMAIC（加新模式、调 prompt、修 bug）时，能直接定位代码而不用重新读一遍源码。

## 整体生成流程（4 阶段）

```
用户输入 requirement + pdfContent
       ↓
【第 1 步】 选择 outline 模板
   ↓
【第 2 步】 调 LLM 生成 outline JSON
   ↓
【第 3 步】 每个场景调 LLM 展开成 actions（白板动作）
   ↓
【第 4 步】 processActions 后处理 + TTS 生成 + 持久化
```

## 第 1 步：outline 模板选择

**模板位置**：`D:\projects\OpenMAIC\lib\prompts\templates\`

**已有模板**：

| 模板 ID | 路径 | 用途 | 场景数 |
|---|---|---|---|
| `interactive-outlines` | `lib/prompts/templates/interactive-outlines/system.md` | 普通交互式课堂（默认） | 灵活（<10 也行，>10 也行） |
| `task-engine-outlines` | `lib/prompts/templates/task-engine-outlines/system.md` | 职业教育专用（强制混合结构） | **强制 10-14 场景** |
| `interactive-outlines` 之外还有 `agent-system*`、`director`、`web-search-query-rewrite` 等 | 各自管各自的事 | - | - |

**模板加载机制**（`lib/prompts/loader.ts`）：
- 用 `{{snippet:name}}` 语法包含 snippets
- 用 `{{#if condition}}...{{/if}}` 条件块
- 用 `{{variable}}` 变量插值
- 支持 system.md + user.md（user.md 可选）

**新增模板的标准做法**：
1. 在 `lib/prompts/templates/{新模板名}/` 下新建 `system.md`（可选 `user.md`）
2. 在 `lib/prompts/loader.ts` 的 `PromptId` 类型加新 ID
3. 在 `app/api/generate-classroom/route.ts` 加分支：
   ```ts
   if (body.outlineMode === 'micro-lesson') {
     outlinePromptId = 'micro-lesson-outlines';
   }
   ```

## 第 2 步：outline JSON 结构

**interactive-outlines 模板的输出格式**（强制的）：
```json
{
  "languageDirective": "教学语言指令（2-5 句）",
  "courseTitle": "课程名（≤30 字）",
  "outlines": [
    {
      "id": "scene_1",
      "type": "slide",          // "slide" | "interactive"
      "title": "...",
      "description": "...",
      "keyPoints": ["...", "..."],
      "order": 1,
      // interactive 才有下面两个字段：
      "widgetType": "simulation" | "diagram" | "code" | "game" | "visualization3d" | "procedural-skill",
      "widgetOutline": { ... }
    }
  ]
}
```

**关键约束**：
- 顶层必须是对象（不能是 bare array）
- `languageDirective` 和 `courseTitle` 必填
- `interactive` 类型必须同时填 `widgetType` 和 `widgetOutline`

## 第 3 步：场景展开成 actions

**模板位置**：`D:\projects\OpenMAIC\packages\@openmaic\generation\templates\`

| 路径 | 用途 |
|---|---|
| `slide-actions/` | slide 类型的 actions（白板书写） |
| `slide-content/` | slide 类型的整体内容 |
| `simulation-content/` | simulation widget 内容 |
| `diagram-content/` | diagram widget 内容 |
| `game-content/` | game widget 内容 |
| `quiz-content/` `quiz-actions/` | 测验相关 |
| `procedural-skill-content/` | 职业教育 checklist |
| `pbl-actions/` | 项目式学习 |
| `interactive-actions/` | 通用 interactive actions |
| `visualization3d-content/` | 3D 可视化 |
| `code-content/` | 代码 playground |
| `requirements-to-outlines/` | requirement → outline |

**白板动作清单**（slide-actions 用）：

| 动作 | 效果 |
|---|---|
| `wb_draw_text` | 白板写文字 |
| `wb_draw_shape` | 画形状（rectangle / circle / arrow） |
| `wb_draw_chart` | 画图表（bar / line / pie） |
| `wb_draw_latex` | 写公式 |
| `wb_draw_table` | 画表格 |
| `wb_draw_line` | 画线段（带 arrow） |
| `wb_draw_code` | 写代码块 |
| `wb_edit_code` | 编辑代码 |
| `wb_clear` | 清空白板 |
| `wb_delete` | 删除元素 |
| `wb_open` / `wb_close` | 开关白板 |

**这些是 OpenMAIC 内建能力**，微课堂不需要在 prompt 里强调，slide-actions 模板会自动用。

## 第 4 步：processActions 后处理

**文件位置**：`D:\projects\OpenMAIC\lib\generation\scene-generator.ts`

**做了什么**：
- TTS 生成（每个 speech action 生成 mp3）
- 后处理 strip 问候语（pitfall 25d）
- 持久化到 `data/classrooms/{课程序列号}.json`

**音频存储**：`D:\projects\OpenMAIC\data\classroom-media\{classroomId}\audio\tts_s{sceneIdx}_action_{actionId}.mp3`

## 微课堂模式实现（待做）

**目标**：在 OpenMAIC 加一个 `outlineMode: 'micro-lesson'` 选项。

**最小改动清单**：
1. 新建文件 `lib/prompts/templates/micro-lesson-outlines/system.md`（核心 prompt）
2. 改 `lib/prompts/index.ts` 或 `app/api/generate-classroom/route.ts` 加分支（约 10 行代码）
3. （可选）写 `D:\家教\系统\scripts\micro-lesson.py` 调 OpenMAIC 新 API

**micro-lesson-outlines/system.md 的关键约束**（草案）：
```
- 强制 3-5 个场景（不是 <10 的模糊要求）
- 强制场景结构：导入 → 概念 → 例题 → 小结
- 强制只 slide 类型（不要 widget，widget 加载慢）
- 强制每场景 keyPoints ≤ 3 个
- 强制总时长 ≤ 3 分钟（按 speech action 数估算）
- 接收外部传入的 knowledgeScope 参数作为 system prompt 的一部分
- 禁止 quiz、interactive、game 场景
- 禁止任何 widget
- 禁止超出 knowledgeScope 列表的概念
```

## 调试方法

| 想看什么 | 怎么查 |
|---|---|
| 当前加载了哪些 outline 模板 | `ls lib/prompts/templates/` |
| 看 outline JSON 长什么样 | `cat data/classrooms/{id}.json \| python -m json.tool \| head -100` |
| 看每个 speech 是否有 audioUrl | `cat data/classrooms/{id}.json \| python -c "import json,sys;d=json.load(sys.stdin);speech=[a for s in d['scenes'] for a in s['actions'] if a.get('type')=='speech'];audio=[a for a in speech if a.get('audioUrl')];print(f'{len(audio)}/{len(speech)}')"` |
| 看 prompt 实际内容 | 看 `lib/prompts/loader.ts:loadPrompt()` 返回值 |
| 看 LLM 调了哪些接口 | `proc_<id>.log` 里搜 `Generating TTS` / `Generating scene` |
