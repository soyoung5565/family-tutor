# 题库搜索源与抓取 SOP（2026-09-12 实测）

## 搜题入口：multi-search-engine 优先

**硬性规则**：题库搜索必须用 `multi-search-engine` skill（百度千帆 + Tavily 双 API），不要用 Hermes 自带的 `web_search`。百度千帆 `references[].content` 字段含题面预览（Tavily `results[].content` 同），命中后直接入库文本即可，省去二次抓取。

调用方式见 `multi-search-engine` skill 的 SKILL.md：
- 中文查询 → 百度千帆 AI Search `web_search` 子渠道
- 英文/国际查询 → Tavily

**坑**：百度千帆 key 路径是 `D:\hermes-data\skills\multi-search-engine\api-keys.json` 的 `channels.baidu_qianfan.api_key`，不是顶层 key。读这个文件时要注意结构是 `{"note": "...", "channels": {"tavily": {...}, "baidu_qianfan": {...}}}`。

## 实测可达的免费题源（按可用性排序）

### A 类：详情页直接显示完整题面（无需登录，可直接入库）
- `xw.5156edu.com`（无忧无虑中学语文网）：浙江站免费，部编版六年级上 200+ 语文测试卷列表。详情页常含完整题目 + 答案。
- `renrendoc.com/paper/<id>.html`（人人 doc）：部分页面含完整题面，含 36+ 计算式。**坑**：多数要登录或 VIP，但搜索结果里 `content` 字段直接带题面文本。
- `wenku.docs.qq.com/detail?docId=...`（腾讯文库）：部分预览。
- `easylearn.baidu.com`（百度题库）：题型片段。

### B 类：列表页能看，详情页要"提取码"
- `appsj.szxuexiao.com`（城市学校网，深圳本地）：**深圳金矿**——深圳罗湖/光明/宝安/南山区 2025 年六年级数学期末试卷，部分人教 PEP 英语期中试卷详情页直接显示完整题目。下载 .doc 文件需要页面提取码（写在页面里，如 `b394`/`u35d`），用户登录后可见。
- `szxuexiao.com/Examination/`：同上主站。

**坑**：下载 .doc 文件需要"提取码"，不是免费直接的。需要用户在浏览器登录后告诉提取码，或由 user 帮爬取 doc 文件内容。

### C 类：被反爬挡
- `zxxk.com`（学科网）：搜索结果有，但详情页返回空壳或触发验证码。
- `21cnjy.com`（21 世纪教育网）：登录墙 + VIP 墙。
- `mp.weixin.qq.com`（微信公众号）：搜索结果 content 有，但 curl 触发 `wappass.baidu.com` 验证码。

**应对**：从聚合搜索的 `content` 字段直接拿题面文本入库（不要试图打开原文）。

### D 类：结构化列表 + playwright 可抓
- `shijuan.org`：59,298+ 免费试卷，分类清晰。按年级/学科/版本筛。
- `xiaoxuewang.cn`（小学网）：按年级/版本分类的试卷库，playwright 可打开列表页。

## Playwright fallback（当 browser_exec 失败时）

Hermes 的 `browser_exec` 工具依赖它自己的 Chromium，常报 "Chromium browser is missing"。

**备用方案**：直接用 npx playwright 跑 Node 脚本。已验证工作：
1. 在 `D:\hermes-data\_tools\` 下 `npm install playwright @playwright/test`
2. `npx playwright install chromium`
3. 写 Node 脚本：`const { chromium } = require('playwright'); ...`

完整模板：
```javascript
const { chromium } = require('playwright');
(async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    await page.setExtraHTTPHeaders({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    });
    await page.goto(url, { timeout: 30000, waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    const text = await page.evaluate(() => document.body.innerText);
    await browser.close();
})();
```

**坑**：Python 子进程里 `subprocess.run(['npx', ...])` 在 WSL bash 下找不到 npx。必须用 `cwd=r'D:\\hermes-data\\_tools'` 直接调 node。

## 已入库流程（端到端实测通过）

1. **搜索候选**：百度千帆搜 "深圳 六年级 数学 上册 第一单元 测试卷" → 6 条 references，每条含 content 题面预览。
2. **文本入库**：从 content 提取题目文本 → 构造 candidates JSON。
3. **3 模型投票**：调 `vote-judge.py`，串行调用 MiniMax-M3 + muse-spark-1.3-contributor + deepseek-v4-pro。
4. **入库**：通过投票的题目写入 `{科目}/测验/{unit}/{kp_id}.json`，更新 `index.json` + `extraction-log.md`。

**实测规模**：21 个查询 × 6 条 = 126 候选 URL，其中 124 条带题面预览。覆盖三科全单元。

## 后续真实题源扩展清单（待跑）

- `appsj.szxuexiao.com` 全站六年级上/下各区试卷（罗湖/福田/南山/宝安/光明/龙岗/坪山/盐田）
- `shijuan.org` 按年级 + 学科 + 版本筛选
- `xiaoxuewang.cn` 三年级到六年级全版本
- 用户提供提取码后批量下载 .doc → vision_analyze 读图入库
