# OCR 课本流程 Pitfalls（自 SKILL.md 迁出，2026-09-29 瘦身）

### Pitfalls — OCR 课本流程

1. **execute_code sandbox Python ≠ terminal Python** — sandbox 没装 paddleocr 也没装 torch，**所有 OCR/Python 库调用必须用 `terminal()` + `D:/Python312/python.exe`**，不要用 execute_code
2. **`/d/...` 路径在 Python 中不工作** — Python 拒绝 `/d/tmp/foo.json`，必须用 `D:\tmp\foo.json` Windows 风格
3. **bash 中文路径会炸** — `cd /d/家教/...` 在 bash 转义下失败。改用 execute_code + Python
4. **PaddleOCR 3.x + Paddle 3.3 在 Windows CPU 报 `ConvertPirAttribute2RuntimeAttribute`** — **降 Paddle 到 2.6.2**（CPU 稳），paddleocr 2.7.0.3
5. **paddleocr 2.7 缺 skimage/LMDB/levenshtein** — 装 `scikit-image lmdb python-Levenshtein "opencv-python<4.10" "numpy<2"`
6. **transformers 4.57.1 + tokenizers 0.23.2 不兼容**（"0.22 ≤ x ≤ 0.23"）— 升 transformers 到 4.57.6
7. **torch 2.10+cu126 wheel 文件名要 cp312-cp312-win_amd64 后缀** — curl 下载下来手动重命名，否则 pip 不认
8. **pip 装大包会卡死**（4 个 UserRequest 线程、CPU 0、IO 0）— 改用 `curl` 直下 + `pip install --no-deps <local.whl>` 绕过
9. **GitHub release 资源走 `objects.githubusercontent.com`，国内常被墙** — 用 sourceforge / 蓝奏云 / 夸克网盘镜像
10. **Unlimited-OCR 6.36GB safetensors 加载报 `OSError 1455 页面文件太小`** — C 盘 pagefile 不足时必出。**8GB RAM 物理上装不下 6GB 模型**，别再尝试
11. **directory listing 时 `slide_004` 不一定是目录页** — 必须用 vision_analyze 看图确认每张的真实内容，**不要用文件名推断**
12. **OpenMAIC `jobId` → `classroomId` 在 `job["result"]["classroomId"]` 字段**，不是 `classroomId` 顶层 — poll_job 完成后要从 `data/classroom-jobs/{id}.json` 拿 `result.classroomId`，再去 `data/classrooms/{classroomId}.json` 读
