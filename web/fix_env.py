import re

fp = r'D:\projects\OpenMAIC\.env.local'
content = open(fp, 'r', encoding='utf-8').read()

# 1. Add XIAOMI config after MINIMAX_MODELS line
xiaomi_block = """# MIMO (xiaomi) LLM Provider
XIAOMI_API_KEY=YOUR_MIMO_API_KEY
XIAOMI_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
XIAOMI_MODELS=mimo-v2.5-pro,mimo-v2-pro,mimo-v2.5,mimo-v2-omni,mimo-v2-flash
"""

content = content.replace(
    'MINIMAX_MODELS=MiniMax-M3,MiniMax-M2.7-highspeed,MiniMax-M2.7\n',
    'MINIMAX_MODELS=MiniMax-M3,MiniMax-M2.7-highspeed,MiniMax-M2.7\n\n' + xiaomi_block
)

# 2. Switch default model to MIMO
content = content.replace(
    'DEFAULT_MODEL=minimax:MiniMax-M3',
    'DEFAULT_MODEL=xiaomi:mimo-v2.5-pro'
)

open(fp, 'w', encoding='utf-8').write(content)
print('Done')
