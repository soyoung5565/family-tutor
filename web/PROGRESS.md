# 家庭教师系统 - 开发进度

## 当前状态（2026-07-10）

### ✅ 已完成

#### 1. 语文课件
- ✅ Day 1 课件：古诗词三首（宿建德江、望湖楼醉书、西江月）
- ✅ Day 2 课件：第六单元古诗三首（浪淘沙、江南春、书湖阴先生壁）
- ✅ 两个课件都已生成完成（100%）

#### 2. PDF 裁切
- ✅ 语文课本：已裁切为单元 PDF
- ✅ 英语课本：第4-10页（语法复习板块）
- ✅ 数学课本 1：第53-60页（分数的应用）
- ✅ 数学课本 2：第95-104页（数据的表示和分析）

#### 3. 答题系统
- ✅ 答题网页：`D:\projects\family-tutor\quiz-ai.html`（AI 批改版）
- ✅ 补强练习页面：`D:\projects\family-tutor\load-quiz-remedial.html`
- ✅ 答题结果接收服务：`D:\projects\family-tutor\quiz-server.py`（端口 8765）
- ✅ AI 批改功能：调用 MIMO API 进行语义理解
- ✅ 结果同步：答题结果自动保存到后端

#### 4. 薄弱知识点分析
- ✅ 分析脚本：`D:\projects\family-tutor\analyze-weak-points.py`
- ✅ 补强练习生成：`D:\projects\family-tutor\generate-remedial.py`
- ✅ 动态题目生成：根据薄弱知识点从课本知识点库中随机选择题目
- ✅ 答案随机分布：不会全是 A

### 🔄 进行中

#### 1. 答题系统测试
- 🔄 AI 批改功能测试（已修复格式问题）
- 🔄 补强练习流程测试
- 🔄 结果同步测试

### ⏳ 待完成

#### 1. 英语和数学学习
- ⏳ 英语学习计划制定
- ⏳ 数学学习计划制定
- ⏳ 英语和数学课件生成

#### 2. 系统优化
- ⏳ Open Design 页面美化（需 Node 24）
- ⏳ 答题页面 UI 优化
- ⏳ 结果统计和可视化

## 技术架构

### 前端
- 答题网页：`quiz-ai.html`（AI 批改版）
- 补强练习页面：`load-quiz-remedial.html`
- 学习中心页面：`index.html`

### 后端
- 答题结果接收服务：`quiz-server.py`（端口 8765）
- AI 批改：调用 MIMO API（英文提示词）
- 结果存储：`D:\projects\family-tutor\quiz-results\`

### 数据
- 学习计划：`learning-state.json`
- 测验题数据：`quiz-data-day{N}.json`
- 补强练习数据：`quiz-data-remedial.json`
- 薄弱知识点分析：`weak-points-analysis.json`

### 工具
- MIMO 多模态：`mimo-multimodal.cjs`（图片/音频/视频分析）
- PDF 裁切：`pymupdf`（fitz）
- 课件生成：OpenMAIC（localhost:3000）

## 工作流

### 1. 开始学习
1. 上传课本 PDF
2. 用 MIMO 多模态视觉精读课本
3. 提取知识点写入 `learning-state.json`
4. 制定学习计划

### 2. 每天上课
1. 读取 `learning-state.json` 看当前进度
2. 用 OpenMAIC 生成当天课件
3. 用户学习课件

### 3. 课后测验
1. 用 MIMO 多模态读课本页面，提取知识点
2. 根据知识点生成测验题
3. 用户在网页上作答
4. AI 批改简答题（调用 MIMO API）
5. 结果同步到后端

### 4. 分析漏洞 + 查漏补缺
1. 分析薄弱知识点
2. 动态生成补强练习（每次题目不同）
3. 用户作答后再次批改
4. 如果仍有漏洞→继续补强
5. 如果已掌握→进入下一课

## 关键文件

### 项目目录
- 学习中心：`D:\projects\family-tutor\`
- 课本目录：`D:\projects\family-tutor\materials\`
- 答题结果：`D:\projects\family-tutor\quiz-results\`

### 配置文件
- 学习计划：`D:\projects\family-tutor\learning-state.json`
- 测验题数据：`D:\projects\family-tutor\quiz-data-day{N}.json`
- 补强练习数据：`D:\projects\family-tutor\quiz-data-remedial.json`

### 脚本文件
- 薄弱知识点分析：`D:\projects\family-tutor\analyze-weak-points.py`
- 补强练习生成：`D:\projects\family-tutor\generate-remedial.py`
- 答题结果接收：`D:\projects\family-tutor\quiz-server.py`

### 页面文件
- 答题网页：`D:\projects\family-tutor\quiz-ai.html`
- 补强练习页面：`D:\projects\family-tutor\load-quiz-remedial.html`
- 学习中心页面：`D:\projects\family-tutor\index.html`

## 下一步计划

### 短期（今天）
1. 完成答题系统测试
2. 验证 AI 批改功能
3. 测试补强练习流程

### 中期（明天）
1. 制定英语和数学学习计划
2. 生成英语和数学课件
3. 继续语文学习

### 长期（暑假）
1. 完成语文、英语、数学三科学习
2. 优化答题系统 UI
3. 添加结果统计和可视化

## 注意事项

### 技术要点
1. MIMO API 对英文提示词更稳定
2. 答案需要随机分布，不能全是 A
3. 补强练习需要根据薄弱知识点动态生成
4. 结果需要同步到后端供分析使用

### 用户偏好
1. 页面需要自动打开，不要让用户找文件
2. 答案需要随机分布
3. AI 批改需要给出详细解析
4. 补强练习需要每次题目不同

## 更新记录

### 2026-07-10
- 完成语文课件生成（Day 1 和 Day 2）
- 完成英语和数学 PDF 裁切
- 修复 AI 批改格式问题（改用英文提示词）
- 实现动态补强练习生成
- 记录开发进度
