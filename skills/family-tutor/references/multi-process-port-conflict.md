# 多进程端口冲突问题

## 问题描述

重启服务时，杀掉旧进程后立即启动新进程，可能出现两个进程同时监听同一端口的情况。

**症状：**
- `netstat` 显示两个 PID 监听同一端口（如 8765）
- AI 批改请求超时或返回空
- 服务响应异常

## 原因

Windows 进程终止后，端口释放需要时间。如果立即启动新进程，旧进程的端口可能还未完全释放。

## 解决方案

杀掉进程后等待 2 秒再启动新进程：

```bash
# 杀掉旧进程
cmd.exe /c "taskkill /F /PID <old_pid>"

# 等待端口释放
sleep 2

# 启动新进程
cd /d/projects/family-tutor && python quiz-server.py

# 验证只有一个进程监听
cmd.exe /c "netstat -ano | findstr :8765 | findstr LISTENING"
# 应该只有一行输出
```

## 验证方法

```bash
# 检查端口监听情况
cmd.exe /c "netstat -ano | findstr :8765 | findstr LISTENING"

# 期望输出（只有一行）：
#   TCP    0.0.0.0:8765           0.0.0.0:0              LISTENING       <PID>

# 如果有两行，说明有冲突，需要杀掉所有相关进程后重新启动
```

## 相关文件

- `D:\projects\family-tutor\quiz-server.py` — 答题结果接收服务（端口 8765）
- `D:\projects\family-tutor\mimo-tts-proxy.py` — MIMO TTS 代理（端口 8787）
