#!/bin/bash
# minimax-oauth-refresh.sh
# 1. 确保 mmx 仍登录（refresh token 续期 access_token）
mmx auth status > /dev/null 2>&1 || mmx auth login --region cn

# 2. 读新 access_token
ACCESS_TOKEN=$(python -c "import json; print(json.load(open(r'C:\Users\24378\.mmx\config.json'))['oauth']['access_token'])")
if [ -z "$ACCESS_TOKEN" ]; then
  echo "ERROR: 无法获取 access_token，需要手动 mmx auth login"
  exit 1
fi

# 3. patch .env.local
ENV_FILE="D:/projects/OpenMAIC/.env.local"
# 用 sed 替换原值（python 安全做法）
python -c "
import re
fp = r'$ENV_FILE'
content = open(fp, 'r', encoding='utf-8').read()
content = re.sub(r'TTS_MINIMAX_API_KEY=.*', 'TTS_MINIMAX_API_KEY=$ACCESS_TOKEN', content)
content = re.sub(r'IMAGE_MINIMAX_API_KEY=.*', 'IMAGE_MINIMAX_API_KEY=$ACCESS_TOKEN', content)
open(fp, 'w', encoding='utf-8').write(content)
print('Updated .env.local with new access_token')
"

# 4. 重启 OpenMAIC
PID=$(netstat -ano 2>/dev/null | grep ":3000 " | grep LISTENING | head -1 | awk '{print $NF}' | tr -d '\r')
if [ -n "$PID" ]; then
  taskkill //F //PID "$PID" > /dev/null 2>&1
  echo "Killed OpenMAIC PID $PID"
fi
sleep 2

# 5. 启动 OpenMAIC
cmd.exe /c "cd /d D:\\projects\\OpenMAIC && set PATH=C:\\Users\\24378\\AppData\\Local\\nvm\\v22.22.0;%PATH% && pnpm dev" &
echo "OpenMAIC restarting..."
