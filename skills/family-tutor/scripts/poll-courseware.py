"""
轮询批量生成的课件，直到所有 job 完成
用法：把脚本里的 JOBS 列表替换为 generate-all-courseware.py 输出的 job IDs
"""
import subprocess, time, json, os

# 替换为你的 job IDs（从 courseware-jobs.json 读取或手动填写）
JOBS_FILE = r'D:\projects\family-tutor\quiz-data\courseware-jobs.json'


def load_jobs():
    if os.path.exists(JOBS_FILE):
        d = json.load(open(JOBS_FILE))
        return d.get('jobs', [])
    return []


def poll(job):
    """查询单个 job 状态"""
    try:
        r = subprocess.run(
            ['curl', '-s', '--max-time', '10', f'http://localhost:3000/api/generate-classroom/{job}'],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            return None
        d = json.loads(r.stdout)
        return {
            'status': d.get('status'),
            'progress': d.get('progress'),
            'step': d.get('step'),
            'url': d.get('result', {}).get('url'),
            'error': d.get('error'),
        }
    except Exception as e:
        return None


def main():
    jobs = load_jobs()
    if not jobs:
        print('没有找到 job IDs')
        return

    print(f'开始轮询 {len(jobs)} 个 job...')

    while jobs:
        still_running = []
        for job in jobs:
            info = poll(job)
            if info is None:
                still_running.append(job)
                continue
            s = info['status']
            p = info.get('progress', '?')
            step = info.get('step', '?')
            print(f'[{job}] {s} - {p}% - {step}')
            if s == 'succeeded':
                print(f'  ✅ URL: http://localhost:3000{info["url"]}')
            elif s == 'failed':
                print(f'  ❌ FAIL: {info.get("error", "N/A")}')
            else:
                still_running.append(job)

        jobs = still_running
        if jobs:
            print(f'\n还有 {len(jobs)} 个 job 未完成，30 秒后继续...')
            time.sleep(30)

    print('\n🎉 所有 job 完成！')


if __name__ == '__main__':
    main()