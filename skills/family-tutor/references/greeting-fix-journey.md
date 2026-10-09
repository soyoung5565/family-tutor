# "同学们好" 问题实战记录（2026-07-09）

## 症状
每页 PPT 的 speech action 都以"同学们好"开头（12/16 页问候），用户体验差。

## 排查过程（三次尝试）

### 第一版：改 `lib/orchestration/registry/store.ts` 的 agent persona
**修改**：在 DEFAULT_AGENTS['default-1'].persona 加中文 GREETING RULE（"只有第1页能问候"）。
**结果**：❌ 无效。persona 是英文格式 + 中文规则，LLM 倾向按英文"First page: Open with greeting"生成问候（persona 跟 system.md 里"First page: Open with greeting"同时存在，互相矛盾）。

### 第二版：改 `lib/prompts/templates/slide-actions/system.md`
**修改**：把规则加强为"NEVER use a greeting on ANY page"（绝对禁止所有页面）。
**结果**：⚠️ 部分有效。12/16 问候 → 2/12 问候（75% 改善），但仍有残留。
**根因**：minimax M3 训练数据里教师角色习惯写"同学们好"，system prompt 的绝对规则对部分 scene 不生效。

### 第三版：processActions 后处理 strip 问候语（真·最终方案）
**修改**：在 `lib/generation/scene-generator.ts:processActions()` 末尾加 post-processor，对每个 speech action 检测 text 开头，如果是问候语就用正则 strip 掉。
**结果**：✅ 100% 有效。不管 LLM 怎么输出，最终 text 都被强制 strip。

## 最终代码（直接 patch 到 scene-generator.ts）

```typescript
// in processActions()，return processedAction 之前
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
      const before = processedAction.text;
      processedAction.text = processedAction.text.replace(pat, '');
      log.debug(`Stripped greeting from speech: "${before.slice(0, 30)}..." -> "${processedAction.text.slice(0, 30)}..."`);
      break;
    }
  }
}
```

## 为什么 post-processor 比改 system prompt 强

| 方案 | 可靠性 | 副作用 |
|------|--------|--------|
| 改 system prompt | LLM 注意力不够、规则被忽略 | 仍然污染 |
| 改 store.ts persona | 与 system.md 冲突 | 互相矛盾 |
| **post-processor strip** | **代码层面强制，LLM 无法绕过** | **无** |

## 执行顺序（必须理解）

```
1. generateSceneActions(aiCall)         → LLM 输出 actions（含问候）
2. processActions(actions, elements, agents)  → 【这里 strip 问候】← 关键
3. createSceneWithActions(...)           → 创建 scene 存到 stage store
4. generateTTSForClassroom(scenes, ...)  → 用 strip 后的 text 调 TTS
5. persistClassroom(...)                 → 持久化 JSON
```

**关键**：strip 在第 2 步发生，所以第 4 步的 TTS 音频和第 5 步的 JSON 都是干净版。如果只在最后 strip JSON，TTS 音频里已经有"同学们好"了。

## 备份流程（每次改 OpenMAIC 源码前必做）

```bash
# 备份核心源码
cp /d/projects/OpenMAIC/lib/generation/scene-generator.ts \
   /d/projects/OpenMAIC/lib/generation/scene-generator.ts.bak.20260709
cp /d/projects/OpenMAIC/lib/prompts/templates/slide-actions/system.md \
   /d/projects/OpenMAIC/lib/prompts/templates/slide-actions/system.md.bak.20260709
```

## 诊断"问候语没消"问题

```bash
# 看课件 JSON 里的 speech 文本
python -c "
import json
d = json.load(open(r'D:/projects/OpenMAIC/data/classrooms/{id}.json','r',encoding='utf-8'))
for i, s in enumerate(d['scenes']):
    for a in s.get('actions',[]):
        if a.get('type')=='speech':
            text = a.get('text','')
            if '同学们好' in text or '大家好' in text:
                print(f'Page {i+1}: {text[:80]}')
            break
"
```

如果还有 → post-processor 没生效或被跳过，检查 patch 是否正确应用 + OpenMAIC 是否已重启。

## 相关 Pitfall
- 父 SKILL.md pitfall #25（已更新到第三版）
- 父 SKILL.md pitfall #25a（OpenMAIC HMR 不可靠，必须重启）
- 父 SKILL.md pitfall #25b（Token Plan 2056 配额上限错误）
