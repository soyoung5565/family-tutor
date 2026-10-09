#!/usr/bin/env python3
"""
导入文件系统中的课件到 OpenMAIC IndexedDB
通过 HTTP API 调用 /api/classroom 接口
"""

import json
import os
import sys
import urllib.request

CLASSROOMS_DIR = r'D:\projects\OpenMAIC\data\classrooms'
API_URL = 'http://localhost:3000/api/classroom'


def import_classroom(json_path):
    """导入单个课件到 IndexedDB"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 准备 POST body
        body = json.dumps({
            'stage': data.get('stage', {}),
            'scenes': data.get('scenes', [])
        }).encode('utf-8')
        
        req = urllib.request.Request(
            API_URL,
            data=body,
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            classroom_id = data.get('stage', {}).get('id', 'N/A')
            classroom_name = data.get('stage', {}).get('name', 'N/A')
            print(f'✅ {classroom_id}: {classroom_name}')
            return True
            
    except Exception as e:
        classroom_id = os.path.basename(json_path).replace('.json', '')
        print(f'❌ {classroom_id}: {str(e)[:80]}')
        return False


def main():
    print('=== 开始导入课件到 OpenMAIC IndexedDB ===\n')
    
    # 检查 API 是否可用
    try:
        req = urllib.request.Request(API_URL.replace('/classroom', '/health'))
        with urllib.request.urlopen(req, timeout=10) as r:
            print('✅ OpenMAIC API 可访问\n')
    except Exception as e:
        print(f'❌ OpenMAIC API 不可访问: {e}')
        sys.exit(1)
    
    # 扫描 classrooms 目录
    json_files = [f for f in os.listdir(CLASSROOMS_DIR) if f.endswith('.json')]
    print(f'找到 {len(json_files)} 个课件文件\n')
    
    success_count = 0
    fail_count = 0
    
    for json_file in sorted(json_files):
        json_path = os.path.join(CLASSROOMS_DIR, json_file)
        if import_classroom(json_path):
            success_count += 1
        else:
            fail_count += 1
    
    print(f'\n=== 导入完成 ===')
    print(f'成功: {success_count}')
    print(f'失败: {fail_count}')


if __name__ == '__main__':
    main()