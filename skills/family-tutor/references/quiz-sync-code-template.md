# 答题结果同步代码模板

## 背景
Open Design 生成的 quiz.html 是独立页面，不包含后端同步代码。生成后必须手动添加以下 sync 代码。

## 添加位置
在 `btnSubmit.addEventListener('click', function() { ... })` 的末尾、`});` 之前插入。

## 同步代码（JavaScript）

```javascript
// ---- Sync results to backend ----
var weakAreasList = [];
Object.keys(TOPIC_WEIGHTS).forEach(function(topic) {
  var info = TOPIC_WEIGHTS[topic];
  var rate = info.total > 0 ? Math.round((info.correct / info.total) * 100) : 0;
  if (rate < 80) {
    weakAreasList.push({ topic: topic, rate: rate });
  }
});

var syncData = {
  title: document.title || '测验',
  date: new Date().toISOString(),
  score: accuracy,
  correctCount: correctCount,
  totalQuestions: state.total,
  weakAreas: weakAreasList,
  details: QUESTIONS.map(function(q) {
    var userAns = state.answers[q.id];
    var isCorrect = false;
    if (q.type === 'choice') {
      if (q.multi) {
        if (Array.isArray(userAns) && Array.isArray(q.answer) && userAns.length === q.answer.length) {
          var sortedUser = userAns.slice().sort();
          var sortedAns = q.answer.slice().sort();
          isCorrect = sortedUser.every(function(v, i) { return v === sortedAns[i]; });
        }
      } else {
        isCorrect = userAns === q.answer;
      }
    } else {
      if (userAns && userAns.trim().length > 0) {
        var lower = userAns.toLowerCase();
        var matchCount = 0;
        q.keywords.forEach(function(kw) {
          if (lower.indexOf(kw.toLowerCase()) !== -1) matchCount++;
        });
        isCorrect = matchCount >= Math.ceil(q.keywords.length * 0.5);
      }
    }
    return {
      question: q.text,
      type: q.type,
      userAnswer: userAns,
      isCorrect: isCorrect
    };
  })
};

// Save to localStorage
var history = JSON.parse(localStorage.getItem('quiz-history') || '[]');
history.push(syncData);
localStorage.setItem('quiz-history', JSON.stringify(history));

// Sync to backend
fetch('http://localhost:8765/api/quiz-results', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(syncData)
}).then(function(response) {
  if (response.ok) {
    console.log('✅ Results synced to backend');
  } else {
    console.log('⚠️ Backend sync failed:', response.status);
  }
}).catch(function(err) {
  console.log('⚠️ Backend sync error:', err);
});
```

## 后端读取结果

```bash
# 读取最新答题结果
curl -s http://localhost:8765/api/quiz-results/latest | python -m json.tool

# 返回格式
{
  "title": "六年级上册语文 - 古诗词三首（Day 1）",
  "date": "2026-07-10T...",
  "score": 80,
  "correctCount": 8,
  "totalQuestions": 10,
  "weakAreas": [
    {"topic": "诗词赏析", "rate": 0},
    {"topic": "诗词对比", "rate": 50}
  ],
  "details": [...]
}
```

## 注意事项
- quiz-server.py 必须在端口 8765 运行
- 浏览器安全限制无法用 browser_console 读取 localStorage（pitfall 57）
- 必须通过后端 API 读取结果，不要尝试 browser_console
