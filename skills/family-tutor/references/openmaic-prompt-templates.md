# OpenMAIC Prompt Templates 参考

> ⚠️ **本文件早期版本认为根因是"AI教师 persona 没有问候语限制"。** 2026-07-09 通过代码审计（`grep "pageIndex\|totalPages" lib/generation/scene-generator.ts`）发现**真正根因是 `scene-generator.ts` 漏传 `SceneGenerationContext`**，导致 `buildCourseContext` 返回空字符串，LLM 看不到 `Position: Page N of M` 这一行，**默认自己是第一页，每页都重新问候**。早期改 store.ts / slide-actions / slide-content 的 persona 规则**没有实际效果**——是治标不治本。

## 真正的根因（2026-07-09 修正）

`lib/generation/scene-generator.ts` 的调用链：

```
generateFullScenes(sceneOutlines, store, aiCall, callbacks, languageDirective)
  └─> Promise.all(sceneOutlines.map(async (outline, index) => {
        return generateSingleScene(outline, api, aiCall, languageDirective)
        // ↑ 这里没传 ctx（pageIndex/totalPages/allTitles/previousSpeeches）
      }))
       └─> generateSceneActions(outline, content, aiCall, { languageDirective })
            // ↑ 这里也没传 ctx
            └─> buildPrompt(PROMPT_IDS.SLIDE_ACTIONS, {
                   courseContext: buildCourseContext(ctx),  // ctx 是 undefined → 返回空字符串
                   ...
                 })
```

`buildCourseContext` 在 `lib/generation/prompt-formatters.ts:9-50` 定义，**核心是输出 `Position: Page N of M`** 这行。如果 `ctx` 是 undefined，整个函数返回空，LLM 看到的 user prompt 完全没有位置信息。

## 真正有效的修复

修改 `lib/generation/scene-generator.ts`：

1. **`generateFullScenes`（约 115-170 行）**：给每个 scene 计算 ctx 并传给 `generateSingleScene`
2. **`generateSingleScene`（约 179-205 行）**：加 `ctx?: SceneGenerationContext` 参数
3. **透传到 `generateSceneActions`**：让 `buildCourseContext` 能拿到 pageIndex

修改后 LLM 看到的 user prompt 会有这一段：

```
Course Outline:
  1. 单元导入与学习目标 ← current
  2. 《宿建德江》——诗人与背景
  3. 《宿建德江》诗意赏析
  ...

IMPORTANT: All pages belong to the SAME class session. Do NOT greet again after the first page. ...

Position: Page 3 of 12 (middle of the course).
Transition: Continue naturally from the previous page. Do NOT greet or re-introduce.

Previous page speech (for transition reference):
  "...上一段的最后150字..."
```

LLM 才会按位置写讲稿（中间页不会重新问候）。

## 修改前必须备份

```bash
cp lib/generation/scene-generator.ts lib/generation/scene-generator.ts.bak
```

## 改完 store.ts / slide-actions / slide-content / agent-system 的 persona 规则没用

这些是 system prompt 层的修改。Position 缺失让 LLM 每次都假设自己是第一页，再多 system 规则都没用。早期（2026-07-08）改完 store.ts 后用户报"还是每页问候"——就是这个原因。**改了没用不算修复**，这次直接改 scene-generator.ts 才有效。

## 验证方法

1. 改完 scene-generator.ts 后重启 OpenMAIC（`pnpm dev`）
2. 调用 `/api/generate-classroom` 生成新课堂
3. 检查 `D:\projects\OpenMAIC\data\classrooms\{id}.json` 里 scenes 的 speech actions
4. 验证：只有 scene[0]（第一页）的第一条 speech 含"同学们好"；scene[1+] 的第一条 speech 应该是过渡语（"接下来""然后""我们来看"）

```python
import json
d = json.load(open(r'D:/projects/OpenMAIC/data/classrooms/{id}.json','r',encoding='utf-8'))
for i, s in enumerate(d['scenes']):
    speeches = [a.get('text','') for a in s.get('actions',[]) if a.get('type')=='speech']
    if speeches:
        first = speeches[0][:50]
        has_greeting = '同学们好' in speeches[0] or '大家好' in first
        marker = '❌' if (has_greeting and i > 0) else '✅'
        print(f'{marker} Scene {i+1}: {first}')
```

## 历史记录

- 2026-07-08：改 store.ts persona → 用户报"没区别"
- 2026-07-09：审计代码发现 scene-generator.ts 漏传 ctx → 修复后正常

## 旧的（错误的）修改位置（仅供历史参考，**不要再改这些**）

#### 0. `lib/orchestration/registry/store.ts`（早期误判为最重要）
曾经在 persona 的 `Tone:` 之前添加过中文规则，但**没用**——Position 缺失让 LLM 每次都假设自己是第一页。

#### 1. `lib/prompts/templates/slide-actions/system.md`
第 144-147 行原本已有英文规则（"First page: Open with a greeting... Middle pages: Continue naturally. Do NOT greet..."），第 149-152 行加了中文规则。但同样没用。

#### 2. `lib/prompts/templates/slide-content/system.md` 和 `lib/prompts/templates/agent-system/system.md`
同样只是 system prompt 增强，没用。
