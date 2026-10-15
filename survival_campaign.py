"""Backend Survival contracts, public guide, and server-owned scenario generator."""
from __future__ import annotations

import json
import random
import secrets

from survival_runtime import PythonLab, LabDatabase, LabLimit, LabCodeError

VERSION = "backend-survival-v1"
VARIANTS = {
    "inventory": {"title": "Склад орбитальной станции", "path": "/stock", "id": "sku", "value": "quantity", "minimum": 0, "maximum": 10000, "story": "Грузовые дроны присылают остатки ресурсов. Повторная доставка события не должна дублировать запись."},
    "telemetry": {"title": "Телеметрия глубокого космоса", "path": "/readings", "id": "sensor", "value": "value", "minimum": -1000, "maximum": 1000, "story": "Датчики передают показания, иногда повреждённые. Приёмник должен отвечать даже при сбое хранилища."},
    "dispatch": {"title": "Диспетчер аварийных заявок", "path": "/tickets", "id": "ticket", "value": "priority", "minimum": 1, "maximum": 5, "story": "Центр управления принимает заявки. Ошибка клиента или повтор запроса не должны обрушить службу."},
}

LEVELS = [
    ("Первый запуск", 10000, "Подключись по SSH, создай и активируй venv, установи зависимости, запусти процесс. GET /health возвращает 200 и {\"status\": \"ok\"}."),
    ("JSON на входе", 15000, "POST на адрес варианта принимает JSON и отвечает 201. body содержит accepted=true и исходные поля идентификатора и значения. /health продолжает работать."),
    ("Ошибки не убивают процесс", 20000, "Повреждённый JSON → 400/error=invalid_json. Неизвестный путь → 404/error=not_found. Неподдерживаемый метод известного пути → 405/error=method_not_allowed. После ошибочного запроса следующий корректный обрабатывается."),
    ("Граница доверия", 30000, "JSON должен быть объектом с двумя обязательными полями варианта. Идентификатор: строка, после strip длина 1–32. Значение: целое в диапазоне варианта; bool не подходит. Неверные данные → 422/error=invalid_payload. Лишние поля игнорируются. В ответе и БД используй очищенный идентификатор."),
    ("Конфигурация и доступ", 40000, "Для POST требуется Authorization: Bearer <API_TOKEN из env>; иначе 401/error=unauthorized. При скрытой проверке токен меняется: читай env, не вшивай значение в код. После авторизации проверь размер UTF-8 тела: больше MAX_BODY → 413/error=payload_too_large. Не выводи токен в ответах или логах. GET /health открыт."),
    ("БД и идемпотентность", 50000, "Создай schema.sql и выполни миграцию. Храни записи в records(id, amount), используй SQL-параметры. Новая запись → 201 с accepted=true. Повтор того же id и значения → 200 с duplicate=true. Повтор id с другим значением → 409/error=conflict, исходная запись сохраняется."),
    ("Чтение и перезапуск", 65000, "GET на адрес варианта возвращает 200 и {items: [...]}, список всех записей по возрастанию id. Элементы содержат поля варианта. После перезапуска процесса записи должны сохраниться. Изменяемые счётчики процесса держи в state, данные — в db."),
    ("Служба и метрики", 80000, "Настрой pandora.service: Restart=on-failure, EnvironmentFile=.env, ExecStart=python server.py. Включи и запусти службу. GET /metrics → 200 с целыми stored (число записей) и requests (число всех запросов к текущему процессу, включая текущий запрос метрик). После перезапуска requests начинается заново."),
    ("Защита от всплесков", 100000, "Для авторизованных POST веди отдельное скользящее окно по request['client']: максимум 5 запросов за 10 секунд. Шестой → 429/error=rate_limit. Время — request['time']; запросы возрастом 10 секунд и больше удаляются из окна. Чужой IP не расходует лимит клиента; GET /health не ограничивается."),
    ("Хранилище недоступно", 125000, "GET /ready проверяет БД через SELECT 1: доступна → 200/{ready:true}, недоступна → 503/{ready:false}. При недоступной БД POST → 503/error=storage_unavailable. Перехвати sqlite3.DatabaseError. /health остаётся 200, после восстановления БД записи снова принимаются."),
    ("Survival / финальный поток", 150000, "Сохрани все предыдущие контракты. Пройди смешанный поток корректных, повреждённых, повторных и слишком больших запросов, всплески с разных IP, перезапуски и отказ БД. Ни один необработанный сбой не допустим; записи и ответы сверяются после потока. Это модель живучести, а не измерение реального RPS."),
]

STARTER = '''import json
from sqlite3 import DatabaseError


def handle(request, state, env, db):
    # request: method, path, body (строка), headers, client, time
    # Возвращай {'status': HTTP-код, 'body': JSON-значение}.
    # Начни с GET /health. Открой «Гайд и команды» над редактором.
    return {'status': 501, 'body': {'error': 'not_implemented'}}
'''

SCHEMA = "CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, amount INTEGER NOT NULL);\n"
UNIT = "[Service]\nExecStart=python server.py\nRestart=on-failure\nEnvironmentFile=.env\n"

GUIDE = """BACKEND SURVIVAL / КОМАНДЫ

1. ssh trainee@lab
2. python -m venv .venv
3. source .venv/bin/activate
4. pip install -r requirements.txt
5. nano app.py                    # откроет файл в редакторе
6. python server.py               # запустит снимок сохранённых файлов
7. curl http://localhost:8080/health
8. check                          # серверная проверка выбранного этапа

После изменения файлов: restart или systemctl restart pandora.
Сохранение не меняет уже запущенный процесс. Перезапуск очищает state,
но сохраняет записи БД. Во время проверки используется отдельная чистая БД.

С этапа 6:
  nano schema.sql
  python manage.py migrate
С этапа 8:
  nano pandora.service
  systemctl enable pandora
  systemctl start pandora
  systemctl status pandora
  journalctl -u pandora -n 20

Ещё команды: help, ls, pwd, cd, cat, touch, rm, clear, whoami,
ps, env, printenv, pip list, curl, stop, restart, exit.
Команды — учебная модель; внешнего SSH-подключения и сетевого сервера нет.

app.py — реальный синтаксис Python в ограниченном учебном интерпретаторе:
функции, условия, циклы, comprehensions, исключения, json, SQL.
Нельзя использовать произвольные импорты, процессы, сеть, файлы ОС,
классы, async, eval/exec и служебные атрибуты. Лимиты: 32 КБ кода,
1000 элементов в коллекции, 15000 инструкций на запрос. Бесконечный
цикл прерывается и считается падением твоего виртуального процесса.

Контракт: handle(request, state, env, db) -> {'status': int, 'body': JSON}.
request['body'] — исходная строка, используй json.loads.
request['headers'] содержит Authorization с таким регистром.
state — словарь процесса; env — строки из .env. int(env['MAX_BODY']).
request['time'] — монотонные секунды, request['client'] — IP клиента.

Примеры приёмов (не готовое решение):
  data = json.loads(request['body'])
  if not isinstance(data.get('value'), int): ...
  # bool — подкласс int: его нужно отклонить отдельно.
  size = len(request['body'].encode('utf-8'))
  row = db.execute('SELECT amount FROM records WHERE id = ?', [key]).fetchone()
  # row — словарь либо None; row['amount'].
  db.execute('INSERT INTO records (id, amount) VALUES (?, ?)', [key, value])
  db.commit()
  rows = db.execute('SELECT id, amount FROM records ORDER BY id').fetchall()
  try: ...
  except DatabaseError: ...

В БД доступны только records и SELECT/INSERT/UPDATE/DELETE, без внешних файлов.
Запрос SQL собирай с ? и отдельными параметрами; конкатенация пользовательских
значений в SQL не проходит проверку. Схема: id TEXT PRIMARY KEY,
amount INTEGER NOT NULL. Нужная schema.sql приведена в задании этапа 6.

Награда подтверждается PANDORA по свежим скрытым данным. Сохранение, curl
и клиентская отметка не начисляют XP. За каждый этап каждого варианта
XP выдаётся один раз; повторные прогоны доступны без повторной награды.
"""

TRANSPORT = '''"""Локальный HTTP-адаптер. В PANDORA его работу моделирует стенд.
Экспортируй проект и запускай python server.py на своём компьютере.
"""
import json
import sqlite3
import threading
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from app import handle

env = {}
for line in Path('.env').read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
db = sqlite3.connect('lab.db', check_same_thread=False)
db.row_factory = lambda cursor, row: {column[0]: row[i] for i, column in enumerate(cursor.description)}
state = {}
lock = threading.Lock()

class Handler(BaseHTTPRequestHandler):
    def dispatch(self):
        length = int(self.headers.get('Content-Length', '0'))
        raw = self.rfile.read(min(length, int(env['MAX_BODY']) + 1))
        self.close_connection = True
        request = {'method': self.command, 'path': self.path.split('?', 1)[0],
                   'body': raw.decode('utf-8', errors='replace'),
                   'headers': {'Authorization': self.headers.get('Authorization', '')},
                   'client': self.client_address[0], 'time': time.monotonic()}
        try:
            with lock:
                response = handle(request, state, env, db)
            body = json.dumps(response['body'], ensure_ascii=False).encode()
            status = response['status']
        except Exception:
            body, status = b'{"error":"internal_error"}', 500
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = dispatch

if __name__ == '__main__':
    print('Listening on http://127.0.0.1:' + env['PORT'])
    ThreadingHTTPServer(('127.0.0.1', int(env['PORT'])), Handler).serve_forever()
'''

MIGRATOR = '''import sqlite3
from pathlib import Path

if __name__ == '__main__':
    import sys
    if sys.argv[1:] != ['migrate']:
        raise SystemExit('python manage.py migrate')
    with sqlite3.connect('lab.db') as db:
        db.executescript(Path('schema.sql').read_text())
    print('Migration applied')
'''


def initial_files(variant):
    return {
        "app.py": STARTER,
        ".env": "PORT=8080\nAPI_TOKEN=lab-token-change-me\nMAX_BODY=4096\n",
        "requirements.txt": "# Учебный адаптер использует стандартную библиотеку Python.\n",
        "schema.sql": "-- С этапа 6: создай records(id TEXT PRIMARY KEY, amount INTEGER NOT NULL).\n",
        "pandora.service": "[Service]\nExecStart=python server.py\n# С этапа 8 добавь Restart и EnvironmentFile.\n",
        "GUIDE.md": GUIDE,
        "server.py": TRANSPORT,
        "manage.py": MIGRATOR,
    }


def parse_env(text):
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(".env: ожидается KEY=value")
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip("\"'")
        if key not in {"PORT", "API_TOKEN", "MAX_BODY"}:
            raise ValueError(f".env: неизвестное поле {key}")
        result[key] = value
    if not result.get("PORT", "").isdigit() or not 1024 <= int(result["PORT"]) <= 65535:
        raise ValueError("PORT: целое от 1024 до 65535")
    if not result.get("MAX_BODY", "").isdigit() or int(result["MAX_BODY"]) != 4096:
        raise ValueError("Для испытаний установи MAX_BODY=4096")
    if not 12 <= len(result.get("API_TOKEN", "")) <= 128:
        raise ValueError("API_TOKEN: 12–128 символов")
    return result


class Process:
    def __init__(self, files, *, migrated=False, rows=(), state=None, budget=450000):
        self.env = parse_env(files.get(".env", ""))
        self.runtime = PythonLab(files.get("app.py", ""), budget=budget)
        self.runtime.sensitive_values = (self.env["API_TOKEN"],)
        self.db = LabDatabase(rows, ready=migrated)
        self.state = {} if state is None else state
        self.alive = True
        self.requests = 0
        self.crashes = 0
        self.logs = []

    def request(self, request):
        self.requests += 1
        if not self.alive:
            return {"status": 0, "body": {"error": "process_stopped"}}
        try:
            response = self.runtime.handle(request, self.state, self.env, self.db)
            # Keep workspace persistence JSON-only, including state.
            json.dumps(self.state, allow_nan=False)
        except (Exception, LabLimit) as error:
            self.alive = False
            self.crashes += 1
            self.state = {}
            response = {"status": 0, "body": {"error": type(error).__name__, "detail": str(error)[:350], "line": getattr(error, "lab_line", None)}}
        self.logs.append(f"{request['method']} {request['path']} -> {response['status']}")
        self.logs[:] = self.logs[-100:]
        return response

    def close(self):
        self.db.close()


def grade(files, variant, level, *, seed=None, migrated=False):
    """Cumulative functional checks. All random values and expected answers live here."""
    rng = random.Random(secrets.randbits(128) if seed is None else seed)
    v = VARIANTS[variant]
    checks = []
    files = dict(files)
    try:
        original_env = parse_env(files.get(".env", ""))
        original_env["API_TOKEN"] = "lab-" + str(rng.getrandbits(96))
        files[".env"] = "\n".join(f"{key}={value}" for key,value in original_env.items()) + "\n"
        process = Process(files, migrated=migrated or level >= 6)
    except (Exception, LabLimit) as error:
        return {"passed": False, "score": 0, "checks": [{"name": "Запуск app.py", "passed": False, "detail": str(error)[:400]}], "requests": 0, "crashes": 1}
    token = process.env["API_TOKEN"]
    clock = [100.0]
    ip_counter = [0]
    expected_rows = {}
    metrics_count = [0]
    total_requests = [0]
    total_crashes = [0]
    unsafe_sql = [0]
    leaked = [False]
    payload_counter = [0]
    def req(method, path, body="", *, auth=True, client=None, at=None):
        ip_counter[0] += 1
        clock[0] += 11
        return {"method": method, "path": path, "body": body if isinstance(body, str) else json.dumps(body, ensure_ascii=False), "headers": {"Authorization": "Bearer " + token} if auth else {}, "client": client or f"192.0.2.{ip_counter[0] % 250 + 1}", "time": clock[0] if at is None else at}
    def check(name, request, status, expected=None):
        result = process.request(request)
        metrics_count[0] += 1
        body = result.get("body")
        matches = result.get("status") == status and (expected is None or isinstance(body, dict) and all(type(body.get(k)) is type(value) and body.get(k) == value for k, value in expected.items()))
        if level >= 5 and token in json.dumps(result, ensure_ascii=False):
            matches = False
        leaked[0] = leaked[0] or process.runtime.leaked
        checks.append({"name": name, "passed": bool(matches), "detail": "OK" if matches else f"Ожидается HTTP {status}" + (f", body содержит {json.dumps(expected, ensure_ascii=False)}" if expected else "") + f"; получено {result.get('status')}: {json.dumps(body, ensure_ascii=False)[:180]}"})
        return result
    def payload(key=None, value=None):
        payload_counter[0] += 1
        return {v["id"]: key or f"node-{rng.randrange(100000,999999)}-{payload_counter[0]}", v["value"]: rng.randint(v["minimum"], v["maximum"]) if value is None else value}
    def create(data, label="Приём JSON"):
        normalized = data[v["id"]].strip()
        result = check(label, req("POST", v["path"], data), 201, {"accepted": True, v["id"]: normalized, v["value"]: data[v["value"]]})
        expected_rows[normalized] = data[v["value"]]
        if level >= 6:
            persisted = {r["id"]: r["amount"] for r in process.db.rows()}
            checks.append({"name": "Запись действительно в БД", "passed": persisted == expected_rows, "detail": "OK" if persisted == expected_rows else "Ответ не соответствует содержимому records"})
        return result
    def restart():
        nonlocal process
        rows = process.db.rows()
        total_requests[0] += process.requests
        total_crashes[0] += process.crashes
        unsafe_sql[0] += process.db.unsafe_queries
        process.close()
        process = Process(files, migrated=True, rows=rows)
        metrics_count[0] = 0
    try:
        check("Healthcheck", req("GET", "/health"), 200, {"status": "ok"})
        if level >= 2:
            for _ in range(rng.randint(4, 9)):
                create(payload())
        if level >= 3:
            check("Повреждённый JSON", req("POST", v["path"], '{"broken":'), 400, {"error": "invalid_json"})
            check("Неизвестный путь", req("GET", "/absent-"+str(rng.randrange(99999))), 404, {"error": "not_found"})
            check("Метод", req("DELETE", v["path"]), 405, {"error": "method_not_allowed"})
            create(payload(), "Процесс жив после ошибок")
        if level >= 4:
            invalid = [[], None, {v["id"]: "", v["value"]: 1}, {v["id"]: " "*5, v["value"]: 1}, {v["id"]: "x"*33, v["value"]: 1}, {v["id"]: 7, v["value"]: 1}, {v["id"]: "x", v["value"]: True}, {v["id"]: "x", v["value"]: "2"}, {v["id"]: "x", v["value"]: v["minimum"]-1}, {v["id"]: "x", v["value"]: v["maximum"]+1}, {v["id"]: "x"}]
            for i, data in enumerate(invalid):
                check(f"Валидация / {i+1}", req("POST", v["path"], json.dumps(data)), 422, {"error": "invalid_payload"})
            create(payload("  trimmed-"+str(rng.randrange(999999))+"  ", v["minimum"]), "Пробелы и нижняя граница")
            create(payload(value=v["maximum"]), "Верхняя граница")
        if level >= 5:
            check("Без токена", req("POST", v["path"], payload(), auth=False), 401, {"error": "unauthorized"})
            wrong = req("POST", v["path"], payload())
            wrong["headers"]["Authorization"] += "-wrong"
            check("Неверный токен", wrong, 401, {"error": "unauthorized"})
            check("Лимит тела", req("POST", v["path"], " "*4097), 413, {"error": "payload_too_large"})
            check("Размер считается в UTF-8", req("POST", v["path"], "я"*2100), 413, {"error": "payload_too_large"})
            check("Открытый healthcheck", req("GET", "/health", auth=False), 200, {"status": "ok"})
        if level >= 6:
            data = payload("repeat-"+str(rng.randrange(999999)))
            create(data)
            check("Идемпотентный повтор", req("POST", v["path"], data), 200, {"duplicate": True})
            changed = dict(data)
            changed[v["value"]] = v["minimum"] if data[v["value"]] != v["minimum"] else v["maximum"]
            check("Конфликт данных", req("POST", v["path"], changed), 409, {"error": "conflict"})
            attack = payload("q' OR '1'='1")
            create(attack, "Идентификатор содержит SQL-символы")
            checks.append({"name": "Дубликат не перезаписал запись", "passed": {r["id"]: r["amount"] for r in process.db.rows()} == expected_rows, "detail": "Сверка всех записей"})
        if level >= 7:
            restart()
            expected_items = [{v["id"]: key, v["value"]: value} for key, value in sorted(expected_rows.items())]
            check("Данные пережили перезапуск", req("GET", v["path"]), 200, {"items": expected_items})
        if level >= 8:
            for _ in range(rng.randrange(5)):
                check("Запрос перед метриками", req("GET", "/health"), 200, {"status": "ok"})
            check("Метрики процесса и БД", req("GET", "/metrics"), 200, {"stored": len(expected_rows), "requests": metrics_count[0]+1})
        if level >= 9:
            same_ip = "198.51.100.77"
            at = clock[0] + 100
            for i in range(5):
                data = payload(f"burst-{rng.randrange(999999)}-{i}")
                check(f"Лимит / разрешён {i+1}", req("POST", v["path"], data, client=same_ip, at=at+i), 201, {"accepted": True})
                expected_rows[data[v["id"]]] = data[v["value"]]
            check("Лимит / шестой запрос", req("POST", v["path"], payload(), client=same_ip, at=at+5), 429, {"error": "rate_limit"})
            check("Health не расходует лимит", req("GET", "/health", client=same_ip, at=at+5), 200, {"status": "ok"})
            data = payload()
            check("Другой клиент независим", req("POST", v["path"], data, client="198.51.100.78", at=at+5), 201, {"accepted": True})
            expected_rows[data[v["id"]]] = data[v["value"]]
            data = payload()
            check("Граница окна / ровно 10 секунд", req("POST", v["path"], data, client=same_ip, at=at+10), 201, {"accepted": True})
            expected_rows[data[v["id"]]] = data[v["value"]]
            clock[0] = at + 30
        if level >= 10:
            check("Readiness доступной БД", req("GET", "/ready"), 200, {"ready": True})
            process.db.available = False
            check("Readiness отказа", req("GET", "/ready"), 503, {"ready": False})
            check("POST при отказе БД", req("POST", v["path"], payload()), 503, {"error": "storage_unavailable"})
            check("Процесс не умер с БД", req("GET", "/health"), 200, {"status": "ok"})
            process.db.available = True
            create(payload(), "Восстановление зависимости")
        if level >= 11:
            for i in range(80):
                mode = rng.randrange(5)
                if mode == 0:
                    check(f"Поток {i+1} / мусор", req("POST", v["path"], "{"), 400, {"error": "invalid_json"})
                elif mode == 1:
                    check(f"Поток {i+1} / health", req("GET", "/health"), 200, {"status": "ok"})
                elif mode == 2:
                    key = rng.choice(list(expected_rows))
                    check(f"Поток {i+1} / повтор", req("POST", v["path"], payload(key, expected_rows[key])), 200, {"duplicate": True})
                elif mode == 3:
                    create(payload(), f"Поток {i+1} / запись")
                else:
                    check(f"Поток {i+1} / метрики", req("GET", "/metrics"), 200, {"stored": len(expected_rows), "requests": metrics_count[0]+1})
            restart()
            check("Итоговая целостность", req("GET", v["path"]), 200, {"items": [{v["id"]: key, v["value"]: value} for key, value in sorted(expected_rows.items())]})
        checks.append({"name": "Ни одного падения процесса", "passed": process.crashes + total_crashes[0] == 0, "detail": "Ошибки клиента должны стать HTTP-ответами"})
        if level >= 5:
            checks.append({"name": "Токен не попал в логи", "passed": not leaked[0], "detail": "Не логируй env и Authorization"})
        if level >= 6:
            checks.append({"name": "Итоговое содержимое БД", "passed": {r["id"]: r["amount"] for r in process.db.rows()} == expected_rows, "detail": "Все записи, повторы и отклонённые запросы сверены"})
            checks.append({"name": "SQL с параметрами", "passed": process.db.unsafe_queries + unsafe_sql[0] == 0, "detail": "Используй ? и отдельный список параметров"})
        passed = sum(c["passed"] for c in checks)
        return {"passed": passed == len(checks), "score": round(100*passed/len(checks)), "checks": checks, "requests": process.requests + total_requests[0], "crashes": process.crashes + total_crashes[0]}
    finally:
        process.close()
