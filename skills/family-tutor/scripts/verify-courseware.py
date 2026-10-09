"""
验证生成的课件内容是否与需求匹配
用法：python verify-courseware.py <classroom_id> <keyword1> <keyword2> ...

例：python verify-courseware.py RMe3GvnJeX 人口老龄化 普查 年龄段
"""
import json, sys


def main():
    if len(sys.argv) < 3:
        print('用法: python verify-courseware.py <classroom_id> <keyword1> ...')
        sys.exit(1)

    classroom_id = sys.argv[1]
    keywords = sys.argv[2:]

    path = f'D:/projects/OpenMAIC/data/classrooms/{classroom_id}.json'
    if not __import__('os').path.exists(path):
        print(f'❌ 课件不存在: {path}')
        sys.exit(1)

    d = json.load(open(path, encoding='utf-8'))
    name = d.get('stage', {}).get('name', '')

    # 提取所有场景标题和 speech 内容
    content = []
    for s in d.get('scenes', []):
        content.append(s.get('title', ''))
        for a in s.get('actions', []):
            if a.get('type') == 'speech':
                content.append(a.get('text', ''))
    full_text = ' '.join(content)

    # 显示基本信息
    print(f'课件名称: {name}')
    print(f'场景数: {len(d.get("scenes", []))}')
    print(f'内容长度: {len(full_text)} 字符')
    print()

    # 检查关键知识点
    print('=== 知识点核对 ===')
    missing = []
    for kw in keywords:
        if kw in full_text:
            print(f'  ✅ "{kw}" — 找到')
        else:
            print(f'  ❌ "{kw}" — 未找到')
            missing.append(kw)

    if missing:
        print(f'\n❌ 课件缺少 {len(missing)} 个关键知识点: {missing}')
        print('建议：删除并重新生成')
    else:
        print(f'\n✅ 课件包含所有 {len(keywords)} 个关键知识点')


if __name__ == '__main__':
    main()