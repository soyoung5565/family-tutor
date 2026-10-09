import re

fp = r'D:\projects\OpenMAIC\.env.local'
content = open(fp, encoding='utf-8').read()

# 备份
import shutil
shutil.copy(fp, fp + '.bak.mimo_backup')
print('已备份 .env.local')

# 切换 DEFAULT_MODEL 到 minimax
new_content = re.sub(
    r'DEFAULT_MODEL=.*',
    'DEFAULT_MODEL=minimax:MiniMax-M3',
    content
)

with open(fp, 'w', encoding='utf-8') as f:
    f.write(new_content)

print('✅ DEFAULT_MODEL 已切换到 minimax:MiniMax-M3')
print('新配置:')
for line in new_content.split('\n'):
    if line.startswith('DEFAULT_MODEL=') or line.startswith('MINIMAX_') or line.startswith('TTS_MINIMAX_'):
        print(f'  {line}')