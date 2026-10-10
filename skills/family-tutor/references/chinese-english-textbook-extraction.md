# 语文/英语课本知识点提取（2026-09-10 实证）

## 教材定位（国家中小学智慧教育平台）

- 语文六上 = 统编版/人教社，contentId `2e3dc199-9c42-486b-bbee-7731bd0ee227`，138 页
- 英语六上 = 粤教沪外教版/广教社，contentId `093366d6-afbc-acef-ad9b-985f8827f45e`，107 页
- 数学六上 = 北师大版，contentId `45fe27cf-8cb3-4670-8397-a482731412fc`，130 页

## 找 contentId 的方法（列表页 SPA，API 有 WAF）

1. 用 playwright 启动系统 Edge（executable_path 指向 msedge.exe，headless 即可）
2. 打开 `https://basic.smartedu.cn/tchMaterial?contentType=assets_document`
3. 点 学科/版本/年级 筛选（`page.locator("text=语文").first.click()`）
4. 等列表刷新后 `page.content()` 抓 UUID，过滤旧式 tag（第 5 段 `11ed` 的是 tag 不是资源）
5. 用公开端点验证：`https://s-file-2.ykt.cbern.com.cn/zxx/ndrv2/resources/tch_material/details/{cid}.json`（无需登录，但 UA 要像浏览器）

## 全量图片下载

preview 字段只给 49 张；**实际全量在 `transcode/image/N.jpg`**：
`https://r1|r2|r3-ndr.ykt.cbern.com.cn/edu_product/esp/assets/{cid}.t/zh-CN/{ts}/transcode/image/N.jpg`
（从 preview.Slide1 提取模板，N 直接 1..300 探测到 404 止，HEAD 请求很快）
并发 12 下载，130 页只要几秒。**不需要登录、不需要 PDF**。

## OCR（纯文本路线即可，语文/英语无需 vision 公式层）

- D:/Python312/python.exe + paddleocr 2.7.0.3（CPU，use_gpu=False, use_angle_cls=False, lang=ch）
- 每张 1.7-2.5s；输出 `{y,x,conf,text}`，y-sorted
- 语文六上：138 页 / 3612 行；英语六上：107 页
- ⚠️ paddleocr import 极慢（~1 分钟+）——必须用分离进程跑，别在前台等

## 单元切分 + LLM 提炼

按单元 slide 区间聚合 OCR 文本 → 每单元调 MiniMax-M3（Anthropic 端点）提取 KP JSON。

- 语文书页 = slide - 5；英语书页 = slide - 7（用单元导语页页脚页码验证）
- 语文：8 单元 / 54 KP（课文+单元要素+习作+口语交际+语文园地+古诗文），每单元 6-8 个
- 英语：5 单元 / 26 KP（Learning goals+每 Lesson+语音规则），每单元 5-6 个

## ⚠️ Minimax-M3 生成 JSON 必踩的坑（2026-09-10 三小时教训）

M3 输出的 JSON 会：值内用 ASCII 引号（表达"蒙汉情深"）、键名用中文引号（`”common_mistakes":`）、值内含裸换行——**任何 prompt 约束都压不住**（试过 QUOTE_RULE 也失败）。

**正解：`pip install json-repair`（装到 D:/Python312），解析时 `from json_repair import repair_json`，全自动修复，6/6 完美。** 不要手写引号状态机。

## 产出结构（对齐数学 v7）

`D:/家教/{语文|英语}/知识点及掌握情况/`：每 KP 一个 json（id/name/type/unit_name/definition/key_points/common_mistakes/start_page/slide_range/publisher）+ index.json（单元+KP数）+ overview.md

## Pitfall

1. **bash 中文路径**：写文件用 execute_code 的 open()，执行用 subprocess 调 D:/Python312/python.exe
2. **execute_code 沙箱 ≠ D:/Python312**：pip 装的东西在 D:/Python312，execute_code 内核没有；都要 subprocess 跑
3. **分离进程**：Popen(DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP|CREATE_NO_WINDOW)，stdout 重定向到 ASCII 路径 log，避免内核被杀连坐（但内核被杀时子进程也可能被带走——补跑靠断点续跑）
