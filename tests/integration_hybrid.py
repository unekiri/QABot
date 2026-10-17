"""品番を含む質問で、正しい品番の文書だけが根拠になることを本物のChromaDB・API・Nginx経由で確認する。"""
import base64
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, '/app')
import docsImporter

authorization = 'Basic ' + base64.b64encode(b'integration:integration-password').decode()

with tempfile.TemporaryDirectory() as directory:
    docsImporter.DOC_DIR = Path(directory)
    (Path(directory) / 'inspection-a.txt').write_text(
        '検査基準書。品番110601280の検査基準は外径測定で、許容差はプラスマイナス0.02mmです。', encoding='utf-8')
    (Path(directory) / 'inspection-b.txt').write_text(
        '検査基準書。品番110601281の検査基準は硬度測定で、HRC40以上です。', encoding='utf-8')
    docsImporter.main()
print('PASS imported two documents that differ only by part number', flush=True)


def ask(question):
    request = urllib.request.Request('http://nginx/api/ask',
        data=json.dumps({'question': question}).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': authorization})
    with urllib.request.urlopen(request, timeout=180) as response:
        assert response.status == 200
        result = json.load(response)
    print(json.dumps({'question': question, 'result': result}, ensure_ascii=False), flush=True)
    return result


result = ask('110601280の検査基準は？')
assert result['evidence'], 'part-number question found no evidence'
assert all('110601280' in item['excerpt'] for item in result['evidence'])
assert all('110601281' not in item['excerpt'] for item in result['evidence'])
assert result['sources'] == ['inspection-a.txt'], result['sources']
print('PASS part number selects only the matching document', flush=True)

result = ask('品番１１０６０１２８１の検査基準は？')
assert result['evidence'] and all('110601281' in item['excerpt'] for item in result['evidence'])
assert result['sources'] == ['inspection-b.txt'], result['sources']
print('PASS full-width part number is normalized', flush=True)

result = ask('品番999999999の検査基準は？')
assert result['abstained'] and result['evidence'] == []
print('PASS unknown part number abstains without evidence', flush=True)
print('PASS hybrid search integration', flush=True)
