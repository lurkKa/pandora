"""Independent reference handler used only by tests, never exposed by the API."""
from survival_campaign import VARIANTS


def reference(variant, *, database=True):
    v = VARIANTS[variant]
    constants = f"PATH={v['path']!r}\nKEY={v['id']!r}\nVALUE={v['value']!r}\nLOW={v['minimum']}\nHIGH={v['maximum']}\nDATABASE={database!r}\n"
    return constants + '''
import json
from sqlite3 import DatabaseError

def reply(status, body):
    return {'status': status, 'body': body}

def handle(request, state, env, db):
    state['requests'] = state.get('requests', 0) + 1
    method = request['method']
    path = request['path']
    if method == 'GET' and path == '/health':
        return reply(200, {'status': 'ok'})
    if method == 'GET' and path == '/ready':
        try:
            db.execute('SELECT 1').fetchone()
        except DatabaseError:
            return reply(503, {'ready': False})
        return reply(200, {'ready': True})
    if method == 'GET' and path == '/metrics':
        count = db.execute('SELECT COUNT(*) AS n FROM records').fetchone()['n']
        return reply(200, {'stored': count, 'requests': state['requests']})
    if path != PATH:
        return reply(404, {'error': 'not_found'})
    if method == 'GET':
        rows = db.execute('SELECT id, amount FROM records ORDER BY id').fetchall()
        return reply(200, {'items': [{KEY: row['id'], VALUE: row['amount']} for row in rows]})
    if method != 'POST':
        return reply(405, {'error': 'method_not_allowed'})
    if request['headers'].get('Authorization') != 'Bearer ' + env['API_TOKEN']:
        return reply(401, {'error': 'unauthorized'})
    if len(request['body'].encode('utf-8')) > int(env['MAX_BODY']):
        return reply(413, {'error': 'payload_too_large'})
    limits = state.setdefault('limits', {})
    history = [t for t in limits.get(request['client'], []) if request['time'] - t < 10]
    if len(history) >= 5:
        return reply(429, {'error': 'rate_limit'})
    history.append(request['time'])
    limits[request['client']] = history
    try:
        data = json.loads(request['body'])
    except ValueError:
        return reply(400, {'error': 'invalid_json'})
    if not isinstance(data, dict):
        return reply(422, {'error': 'invalid_payload'})
    key = data.get(KEY)
    value = data.get(VALUE)
    if not isinstance(key, str) or not 1 <= len(key.strip()) <= 32:
        return reply(422, {'error': 'invalid_payload'})
    if not isinstance(value, int) or isinstance(value, bool) or not LOW <= value <= HIGH:
        return reply(422, {'error': 'invalid_payload'})
    key = key.strip()
    if DATABASE:
        try:
            row = db.execute('SELECT amount FROM records WHERE id = ?', [key]).fetchone()
            if row is not None:
                if row['amount'] == value:
                    return reply(200, {'duplicate': True})
                return reply(409, {'error': 'conflict'})
            db.execute('INSERT INTO records (id, amount) VALUES (?, ?)', [key, value])
            db.commit()
        except DatabaseError:
            return reply(503, {'error': 'storage_unavailable'})
    return reply(201, {'accepted': True, KEY: key, VALUE: value})
'''
