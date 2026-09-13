import json
import urllib.request
import time
import base64

authorization = 'Basic ' + base64.b64encode(b'integration:integration-password').decode()

deadline = time.monotonic() + 60
while True:
    try:
        with urllib.request.urlopen('http://api:5000/health', timeout=2) as response:
            assert response.status == 200
        break
    except (OSError, AssertionError):
        if time.monotonic() >= deadline:
            raise
        time.sleep(1)

cases = [
    ('社内の貸出用ノートパソコンの返却期限は何日ですか？', False, '14', 'loan-policy.txt'),
    ('社員用駐車場の利用申請はどこに提出しますか？', False, '人事', 'parking-policy.txt'),
    ('明日の東京の天気を教えてください。', True, None, None),
    ('貸出用ノートパソコンの延滞料金はいくらですか？', True, None, None),
]
failures = []
for question, abstained, keyword, source in cases:
    request = urllib.request.Request('http://nginx/api/ask',
        data=json.dumps({'question': question}).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': authorization})
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.load(response)
        assert response.status == 200
    passed = (result['abstained'] == abstained
              and (keyword is None or keyword in result['answer'])
              and (source is None or source in result['sources'])
              and (abstained or any(item['excerpt'] for item in result['evidence'])))
    print(json.dumps({'question': question, 'passed': passed, 'result': result}, ensure_ascii=False), flush=True)
    if not passed:
        failures.append(question)
assert not failures, failures
print('PASS 4 real-LLM cases through Nginx', flush=True)
