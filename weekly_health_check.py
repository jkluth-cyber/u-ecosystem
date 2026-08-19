import os, json, hmac, hashlib, time, uuid, urllib.request, urllib.error

BASE = os.environ.get('U_BRAIN_API_URL', 'https://u-jarvis-api.ashytree-79de396a.eastus.azurecontainerapps.io').rstrip('/')
SECRET = os.environ.get('U_SHARED_SECRET', '')
TEST_USER = 'weekly-health-check'


def request(path, body=None):
    method = 'GET' if body is None else 'POST'
    headers = {'Content-Type': 'application/json'}
    data = None
    if body is not None:
        data = json.dumps(body, separators=(',', ':')).encode()
        rid = str(uuid.uuid4())
        ts = str(int(time.time()))
        sig = hmac.new(SECRET.encode(), f'{ts}.{rid}.{data.decode()}'.encode(), hashlib.sha256).hexdigest()
        headers.update({'x-u-request-id': rid, 'x-u-timestamp': ts, 'x-u-signature': sig})
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try: payload = json.loads(raw) if raw else {}
        except Exception: payload = {'error': 'non-json error'}
        return e.code, payload
    except Exception as e:
        return 0, {'error': type(e).__name__}

results = {}
for path in ['/api/health', '/api/psi', '/api/psi/dimensions', '/api/engines']:
    results[path] = request(path)

payload = {
  'title': 'Weekly system health verification',
  'situation': 'Verify the decision pipeline is operational.',
  'desired_outcome': 'Confirm a structured decision response.',
  'pillars': ['career', 'finance'],
  'facts': ['Synthetic health-check request only'],
  'unknowns': ['None supplied'],
  'constraints': ['No external action'],
  'values': ['stability', 'clarity'],
  'horizon_days': 30,
  'consent': {'analyze': True, 'memory': False, 'research': False, 'external_actions': False, 'sensitive_data': False},
  'user_id': TEST_USER,
  'command': 'decide'
}
results['/api/jarvis'] = request('/api/jarvis', payload)

# Sanitize to operational metrics only; do not print raw response bodies.
def summarize(path, pair):
    status, body = pair
    out = {'http_status': status, 'ok': status == 200}
    if path == '/api/health':
        out.update({'status': body.get('status'), 'version': body.get('version'), 'signing': body.get('signing')})
    elif path == '/api/psi':
        out.update({'status': body.get('status'), 'version': body.get('version'), 'dimensions': body.get('dimensions') or body.get('dimension_count')})
    elif path == '/api/psi/dimensions':
        dims = body.get('dimensions', body)
        out.update({'dimension_count': len(dims) if isinstance(dims, (list, dict)) else None, 'dimension_names': list(dims.keys()) if isinstance(dims, dict) else [d.get('name') for d in dims if isinstance(d, dict)]})
    elif path == '/api/engines':
        engines = body.get('engines', body if isinstance(body, list) else [])
        out.update({'engine_count': len(engines) if isinstance(engines, list) else body.get('count'), 'governance': body.get('multi_agent_governance') or body.get('governance')})
    else:
        out.update({'status': body.get('status'), 'decision_present': bool(body.get('recommendation') or body.get('decision') or body.get('recommendation_status')), 'structured_keys_present': all(k in body for k in ['status', 'recommendation', 'audit']) if isinstance(body, dict) else False, 'pipeline_ok': status == 200})
    return out

summary = {path: summarize(path, pair) for path, pair in results.items()}
summary['test_user_used'] = TEST_USER
summary['base_url'] = BASE
print(json.dumps(summary, sort_keys=True))
