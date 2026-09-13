import base64
import json
import urllib.error
import urllib.request

authorization = 'Basic ' + base64.b64encode(b'integration:integration-password').decode()
request = urllib.request.Request(
    'http://nginx/api/ask',
    data=json.dumps({'question': 'test'}).encode(),
    headers={'Content-Type': 'application/json', 'Authorization': authorization},
)
try:
    urllib.request.urlopen(request, timeout=15)
except urllib.error.HTTPError as error:
    body = json.load(error)
    assert error.code == 500
    assert body == {'detail': 'Internal server error'}
else:
    raise AssertionError('Expected dependency failure')
print('PASS internal error details are hidden', flush=True)
