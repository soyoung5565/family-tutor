#!/usr/bin/env python3
"""
打包课件为 ZIP 文件，用于 OpenMAIC 导入
"""

import json
import os
import zipfile
from datetime import datetime

CLASSROOMS_DIR = r'D:\projects\OpenMAIC\data\classrooms'
OUTPUT_DIR = r'D:\projects\family-tutor\exported-zips'


def create_manifest(classroom_data):
    """创建 OpenMAIC 导入格式的 manifest"""
    stage = classroom_data.get('stage', {})
    scenes = classroom_data.get('scenes', [])

    # 转换 scenes 为 ManifestScene 格式
    manifest_scenes = []
    for scene in scenes:
        manifest_scene = {
            'id': scene.get('id', f'scene_{len(manifest_scenes)}'),
            'title': scene.get('title', ''),
            'content': scene.get('content', {}),
            'actions': scene.get('actions', []),
            'agentIds': scene.get('agentIds', []),
            'createdAt': scene.get('createdAt', 0),
            'updatedAt': scene.get('updatedAt', 0),
        }
        manifest_scenes.append(manifest_scene)

    manifest = {
        'version': 1,
        'stage': stage,
        'scenes': manifest_scenes,
        'agents': [],
        'mediaIndex': {},
        'exportedAt': datetime.now().isoformat(),
    }
    return manifest


def pack_classroom(json_path, output_path):
    """打包单个课件为 ZIP"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    manifest = create_manifest(data)

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 写入 manifest.json
        zf.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))

    return True


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    json_files = [f for f in os.listdir(CLASSROOMS_DIR) if f.endswith('.json')]
    print(f'找到 {len(json_files)} 个课件\n')

    for json_file in sorted(json_files):
        classroom_id = json_file.replace('.json', '')
        json_path = os.path.join(CLASSROOMS_DIR, json_file)
        output_path = os.path.join(OUTPUT_DIR, f'{classroom_id}.zip')

        try:
            pack_classroom(json_path, output_path)
            name = json.load(open(json_path)).get('stage', {}).get('name', 'N/A')
            print(f'✅ {classroom_id}: {name}')
            print(f'   → {output_path}\n')
        except Exception as e:
            print(f'❌ {classroom_id}: {e}\n')

    print(f'=== 打包完成 ===')
    print(f'输出目录: {OUTPUT_DIR}')
    print(f'\n下一步：在 OpenMAIC 主页点击"导入课堂"按钮，')
    print(f'然后选择这些 ZIP 文件即可导入到 IndexedDB。')


if __name__ == '__main__':
    main()