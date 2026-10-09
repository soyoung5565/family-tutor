# 2026-07-10 晚间会话学习记录

## 用户偏好总结（重要！）

### 1. 配置参数偏好（用户明确要求）
- **agentMode**: 用户原话"那应该就是default就可以。不要快速模式" → **永远用 `'default'` 模式**（最高质量）
- **TTS**: MIMO TTS 代理（端口 8787），minimax TTS 备选
- **LLM**: MIMO mimo-v2.5-pro 主力，minimax M3 备选
- **WebSearch**: 百度搜索
- **Image**: 关闭（效果差）

### 2. PDF 裁切规范（按学科）
- **数学**：大单元再分小节（如 unit1 前3页+后5页 → 2个 PDF），每天一课
- **英语**：按语法板块裁切（如 unit1 第4-10页 → 1个 PDF）
- **语文**：按古诗三首裁切（如 第6-7页、94-95页）

### 3. 知识要点文档规范（重要！）
- **每个课程一个独立 .md 文件**：`knowledge-points/{subject}_day{N}.md`
- **必须标注年级**：在标题里写"（小学六年级上册）"
- **语气符合年级**：小学生用简单语言，不要专业术语
- **用户原话**："知识要点和学习规划安排是需要用独立world文档来记录的"
- **用途**：推进学习计划和查漏补缺时直接参考，不需要重新提取

### 4. 课件生成工作流
1. 裁切 PDF 为小节
2. 用 MIMO 多模态提取知识点 → knowledge-points/{subject}_day{N}.md
3. 调用 OpenMAIC 生成课件（`agentMode: 'default'`）
4. **生成后必须核对内容**（pitfall 61/75a）
5. **内容不对就重新生成**（minimax M3 会自主发挥）

### 5. 多进程端口冲突（必须记！）
**症状**：重启服务后，`netstat` 可能显示多个 PID 监听同一端口
**修法**：必须杀掉所有旧进程再重启，否则请求走旧代码
**脚本**：
```bash
for pid in $(cmd.exe /c "netstat -ano | findstr :PORT | findstr LISTENING" 2>&1 | awk '{print $NF}' | sort -u | tr -d '\r'); do
  cmd.exe /c "taskkill /F /PID $pid"
done
```

### 6. 课件内容核对流程（必做！）
用户原话："你等会可以拿那些知识点大致的核对一下生成的课程对不对哈"
```python
# 读取课件 JSON
import json
d = json.load(open(f'D:/projects/OpenMAIC/data/classrooms/<id>.json'))
name = d.get('stage', {}).get('name', '')
scenes = [s.get('title', '') for s in d.get('scenes', [])]

# 对照 knowledge-points 文档检查
# 例如：math_day3 的 knowledge-points 包含"人口老龄化"、"人口普查"
# 检查课件场景是否包含这些关键词
```

### 7. 决策表：何时切换 vs 重新生成
| 场景 | 操作 |
|------|------|
| 内容正确 + 已完成 | 保留 |
| 内容错误（偏离主题） | 重新生成 |
| 卡在 TTS（provider 配额耗尽） | 切换 provider 继续 |
| Stale job（重启后卡住） | 删除 + 重新生成 |
| 用户明确说"重新生成" | 全部重新生成 |

**用户原话**："有一个不是已经生成完了吗还重新生成干嘛？不要覆盖已经生成好的了" → 已完成的保留，内容不对的重新生成。

### 8. 批量生成课件工作流（一次 5 个）
**脚本**：`scripts/generate-all-courseware.py`
**步骤**：
1. 解析所有 PDF（保存到 `quiz-data/parse_*.json`）
2. 批量生成课件（每个对应一个 requirement）
3. Job IDs 保存到 `quiz-data/courseware-jobs.json`
4. 后台轮询直到完成
5. 用 knowledge-points 文档核对内容

### 9. minimax LLM Key 过期处理
**症状**：`AI_APICallError: login fail: Please carry the API secret key in the 'X-Api-Key' field`
**修法**：把 `MINIMAX_API_KEY` 从 `sk-cp-...` 替换为 OAuth `oat-...` token
**OAuth token 来源**：`mmx auth login --region cn` → 存到 `~/.mmx/config.json`

### 10. 标准化文件结构（2026-07-10 整理）
```
D:\projects\family-tutor\
├── materials/                  # 课本材料（按学科分文件夹）
│   ├── chinese/
│   ├── math/
│   └── english/
├── knowledge-points/           # 知识要点文档（独立 .md）
├── quiz-data/                  # 测验数据
│   ├── parse_*.json           # PDF 解析结果
│   ├── quiz-data-day{N}.json  # 每天的测验题
│   ├── quiz-data-remedial.json
│   ├── weak-points-analysis.json
│   └── courseware-jobs.json   # 课件生成任务
├── quiz-results/               # 答题结果
├── scripts/                    # 脚本
│   ├── analyze-weak-points.py
│   ├── generate-remedial.py
│   ├── quiz-server.py
│   ├── generate-all-courseware.py
│   └── switch-provider.py
├── backup/                     # 备份
└── *.html                      # 页面文件
```

## 重要 pitfall 总结

- **Pitfall 70**: 课件生成中途切换 LLM provider（不需要重新生成，切换后重启 OpenMAIC 继续）
- **Pitfall 70a**: 不要覆盖已完成的课件（先检查已成功的，只重新生成失败的或内容不对的）
- **Pitfall 75a**: 课件生成后必须核对内容（用 knowledge-points 文档）
- **Pitfall 75b**: 课本年级必须正确标注（用 MIMO 多模态询问年级）
- **Pitfall 75c**: minimax M3 在 'generate' 模式会"自主发挥"——永远用 'default' 模式
- **Pitfall 62**: agentMode 只有 'default' 和 'generate' 两种值，'fast' 不存在
- **Pitfall 61b**: OpenMAIC IndexedDB vs 文件系统（API 生成的课件不会自动出现在主页，必须打包 ZIP 手动导入或修改源码让 listStages 从文件系统读取）。详见 `references/openmaic-indexeddb-import.md`
- **Pitfall 75d**: 答案必须真随机分布（用 `shuffle_options()` 函数打乱选项顺序，不能让正确答案总是在 A 位置）
- **Pitfall 75e**: 补强练习必须生成新题，不能重复原题（根据薄弱知识点用 AI 生成新题）
- **Pitfall 75f**: 课件类型应动态调整（只错选择题 → 全是选择题，错了简答题 → 才包含简答题）
- **Pitfall 75g**: AI 批改不要用关键词匹配（用 AI 语义理解批改，英文提示词，max_tokens ≥500）

## 用户验证的关键决策
1. **不要半途而废**（用户原话："你还不明白吗，别搞了让我来"）——用户的指令就是确认
2. **页面必须自动打开**（用户原话："你直接给个浏览器链接或者直接打开文件，而不是让我来找"）
3. **删除文件前先确认**（用户原话："删除任何文件/工具/依赖前必须先确认"）
4. **不要自己决定风格**（用户原话："你知道这是小学数学课本吗？"——语气要符合年级）

## 下次会话启动检查清单

1. **服务状态**：
   ```bash
   cmd.exe /c "netstat -ano | findstr :3000 | findstr LISTENING"  # OpenMAIC
   cmd.exe /c "netstat -ano | findstr :8765 | findstr LISTENING"  # Quiz server
   cmd.exe /c "netstat -ano | findstr :8787 | findstr LISTENING"  # MIMO TTS proxy
   ```

2. **Provider 加载确认**：
   ```bash
   curl -s http://localhost:3000/api/server-providers | python -c "import json,sys;d=json.load(sys.stdin);print('LLM:', list(d.get('providers',{}).keys()));print('TTS:', list(d.get('tts',{}).keys()))"
   ```

3. **OAuth token 状态**：
   ```bash
   python -c "import json,datetime;d=json.load(open(r'C:\Users\MR\.mmx\config.json'));exp=d['oauth']['expires_at'];ed=datetime.datetime.fromisoformat(exp.replace('Z','+00:00'));left=ed-datetime.datetime.now(datetime.timezone.utc);print('OK' if left.total_seconds()>0 else 'EXPIRED', left)"
   ```

4. **当前 DEFAULT_MODEL**：应该是 `minimax:MiniMax-M3` 或 `xiaomi:mimo-v2.5-pro`

5. **knowledge-points 文档**：检查 `D:\projects\family-tutor\knowledge-points\` 是否有所有课程的文档