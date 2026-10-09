import json, urllib.request

def gen(pdf_path, requirement, job_name):
    d = json.load(open(pdf_path))
    body = json.dumps({
        'requirement': requirement,
        'pdfContent': d['data'],
        'enableWebSearch': True,
        'webSearchProviderId': 'baidu',
        'enableTTS': True,
        'enableImageGeneration': False,
        'agentMode': 'fast'
    }).encode('utf-8')
    req = urllib.request.Request('http://localhost:3000/api/generate-classroom', data=body, headers={'Content-Type': 'application/json'})
    resp = json.loads(urllib.request.urlopen(req).read())
    print(f'{job_name}: jobId={resp.get("jobId")}, status={resp.get("status")}')
    return resp.get('jobId')

j1 = gen('/tmp/parse_day1.json', '六年级上册语文第一课《古诗词三首》', 'Day1')
j2 = gen('/tmp/parse_day2.json', '六年级上册语文第六单元《古诗三首》', 'Day2')

# Save job IDs
with open('/tmp/job_ids.json', 'w') as f:
    json.dump({'day1': j1, 'day2': j2}, f)
