# 补强练习答案随机分布

## 问题描述

用户强烈纠正：补强练习的答案不能全是 A，必须随机分布。

**用户原话：**
> "你自己说答案随机分布了，然后不管是你给的网页还是你第二遍给的答案都是aaaaa 你在自己反驳自己吗？"

## 解决方案

在 `generate-remedial.py` 中用 `shuffle_options()` 函数打乱选项顺序：

```python
def shuffle_options(item, correct_key):
    """随机打乱选项顺序，返回新的选项列表和正确答案索引"""
    options = item['options'].copy()
    correct_answer = item[correct_key]
    
    # 找到正确答案的原始位置
    correct_idx = options.index(correct_answer)
    
    # 创建 (选项, 是否正确) 的配对
    paired = list(enumerate(options))
    
    # 随机打乱
    random.shuffle(paired)
    
    # 提取打乱后的选项和正确答案的新位置
    new_options = [opt for _, opt in paired]
    new_correct_idx = next(i for i, (orig_idx, _) in enumerate(paired) if orig_idx == correct_idx)
    
    return new_options, new_correct_idx
```

## 使用示例

```python
# 生成选择题时
for item in selected:
    # 随机打乱选项
    new_options, new_correct_idx = shuffle_options(item, 'pinyin')
    questions.append({
        "type": "choice",
        "topic": "生字拼音",
        "text": f"「{item['char']}」的正确读音是？",
        "options": new_options,
        "answer": new_correct_idx,
        "keywords": []
    })
```

## 验证方法

```bash
# 运行生成脚本
cd /d/projects/family-tutor && python generate-remedial.py

# 检查输出中的答案分布
cat /d/projects/family-tutor/quiz-data-remedial.json | python -c "
import json, sys
d = json.load(sys.stdin)
for i, q in enumerate(d['questions']):
    if q['type'] == 'choice':
        print(f'{i+1}. 答案位置: {chr(65 + q[\"answer\"])} ({q[\"options\"][q[\"answer\"]]})')
"

# 期望输出：答案位置随机分布，如 D, C, C, B, B, D, C, C
# 不是：A, A, A, A, A, A, A, A
```

## 相关文件

- `D:\projects\family-tutor\generate-remedial.py` — 补强练习生成脚本
- `D:\projects\family-tutor\quiz-data-remedial.json` — 补强练习题数据
- `D:\projects\family-tutor\load-quiz-remedial.html` — 补强练习加载页
