# 课件生成中途切换 LLM Provider

## 场景
用户在 OpenMAIC 正在生成课件的过程中，发现使用的 LLM provider（如 MIMO）配额耗尽或过期，希望切换到备用 provider（如 minimax），但不想重新生成。

## 核心结论
**不需要重新生成！** 只需修改 `.env.local` 的 `DEFAULT_MODEL` + 重启 OpenMAIC，正在运行的 job 会自动用新配置完成剩余步骤。

## 完整步骤

### 1. 备份 .env.local
```bash
cp /d/projects/OpenMAIC/.env.local /d/projects/OpenMAIC/.env.local.bak.$(date +%Y%m%d_%H%M%S)
```

### 2. 切换 DEFAULT_MODEL
```bash
# 从 MIMO 切到 minimax
sed -i 's/DEFAULT_MODEL=xiaomi:mimo-v2.5-pro/DEFAULT_MODEL=minimax:MiniMax-M3/' /d/projects/OpenMAIC/.env.local

# 或从 minimax 切回 MIMO
sed -i 's/DEFAULT_MODEL=minimax:MiniMax-M3/DEFAULT_MODEL=xiaomi:mimo-v2.5-pro/' /d/projects/OpenMAIC/.env.local
```

### 3. 杀掉旧 OpenMAIC 进程
```bash
# 查找端口 3000 的 PID
PID=$(cmd.exe /c "netstat -ano | findstr :3000 | findstr LISTENING" 2>&1 | head -1 | awk '{print $NF}' | tr -d '\r')
cmd.exe /c "taskkill /F /PID $PID"
```

### 4. 重启 OpenMAIC
```bash
cd /d/projects/OpenMAIC && pnpm dev
```

### 5. 验证 provider 切换成功
```bash
curl -s http://localhost:3000/api/server-providers | python -c "
import json, sys
d = json.load(sys.stdin)
print('LLM:', list(d.get('providers',{}).keys()))
print('TTS:', list(d.get('tts',{}).keys()))
"
```

期望输出：
```
LLM: ['minimax', 'xiaomi']
TTS: ['openai-tts', 'minimax-tts']
```

### 6. 检查正在运行的 job
```bash
# 用 Python 读 job JSON 文件（更可靠）
python -c "
import json
import os
for f in os.listdir('D:/projects/OpenMAIC/data/classroom-jobs/'):
    if f.endswith('.json'):
        d = json.load(open(f'D:/projects/OpenMAIC/data/classroom-jobs/{f}'))
        print(f'{f}: {d.get(\"status\")} - {d.get(\"progress\")}% - {d.get(\"step\")}')
"
```

## 原理
- OpenMAIC 的 provider 是从 `.env.local` 启动时加载的
- 一旦加载，所有 TTS 调用都使用已配置的 provider
- 正在运行的 job 在每个步骤（scenes、tts）都会重新读取 provider 配置
- 重启后，新 job 用新配置；但**已有的 job 状态保留**，继续处理剩余步骤

## TTS 阶段的特殊处理
如果 job 卡在 `generating_tts` 94%（MIMO 限流或配额耗尽），切换到 minimax 后：
- `generateTTSForClassroom` 函数会用 `minimax-tts` provider（不再用 `openai-tts`）
- minimax 的 TTS 走 `TTS_MINIMAX_API_KEY`（OAuth oat- token）
- 不需要重新生成 scenes，只需完成 TTS

## 验证清单
- [ ] .env.local 已备份
- [ ] DEFAULT_MODEL 已修改
- [ ] 旧 OpenMAIC 进程已杀掉
- [ ] OpenMAIC 已重启并启动日志显示 Loaded N LLM
- [ ] curl /api/server-providers 确认 provider 已加载
- [ ] 正在运行的 job 状态保留
- [ ] job 的 updatedAt 时间戳在更新（说明还在跑）
- [ ] TTS 阶段的 job 切换后能用 minimax 完成