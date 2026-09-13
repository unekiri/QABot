import base64
import json
import urllib.error
import urllib.request
import re

BASE_URL = 'http://nginx'
GOOD_AUTH = 'Basic ' + base64.b64encode(b'integration:integration-password').decode()
BAD_AUTH = 'Basic ' + base64.b64encode(b'integration:wrong').decode()


def request(path='/', method='GET', data=None, authorization=None):
    headers = {}
    if authorization:
        headers['Authorization'] = authorization
    if data is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(BASE_URL + path, method=method, data=data, headers=headers)
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()
    with response:
        return response.status, dict(response.headers), response.read()


status, headers, _ = request()
assert status == 401
assert headers.get('WWW-Authenticate') == 'Basic realm="QABot"'
print('PASS anonymous access rejected', flush=True)

status, _, _ = request(authorization=BAD_AUTH)
assert status == 401
print('PASS invalid credentials rejected', flush=True)

status, headers, body = request(authorization=GOOD_AUTH)
assert status == 200
assert b'https://fonts.googleapis.com' not in body
assert "default-src 'self'" in headers.get('Content-Security-Policy', '')
script_paths = re.findall(rb'<script[^>]+src="([^"]+)"', body)
for script_path in script_paths:
    status, _, script = request(script_path.decode(), authorization=GOOD_AUTH)
    assert status == 200
    assert b'localhost:5000' not in script
print('PASS authenticated local-only UI', flush=True)

status, _, _ = request('/api/ask', method='GET', authorization=GOOD_AUTH)
assert status == 403
print('PASS non-POST API method rejected', flush=True)

oversized = json.dumps({'question': 'x' * 20000}).encode()
status, _, _ = request('/api/ask', method='POST', data=oversized, authorization=GOOD_AUTH)
assert status == 413
print('PASS oversized request rejected by Nginx', flush=True)

too_long = json.dumps({'question': 'x' * 2001}).encode()
status, _, body = request('/api/ask', method='POST', data=too_long, authorization=GOOD_AUTH)
assert status == 422
assert b'x' * 100 not in body
print('PASS question length validated without echoing input', flush=True)

limited = False
for _ in range(8):
    status, _, _ = request('/api/ask', method='POST', data=b'{}', authorization=GOOD_AUTH)
    if status == 429:
        limited = True
        break
assert limited
print('PASS API rate limit enforced', flush=True)
