"""Persistent virtual shell and authenticated, server-verified Survival API."""
from __future__ import annotations

import configparser
import hashlib
import io
import json
from pathlib import Path
import re
import shlex
import threading
import time
from urllib.parse import urlparse
import zipfile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, StrictInt, StrictStr

from survival_campaign import VERSION, VARIANTS, LEVELS, GUIDE, SCHEMA, UNIT, initial_files, parse_env, Process, grade
from survival_runtime import LabLimit, LabCodeError, PythonLab

EDITABLE = {"app.py", ".env", "requirements.txt", "schema.sql", "pandora.service"}
READONLY = {"server.py", "manage.py", "GUIDE.md"}
GRADE_SLOTS = threading.BoundedSemaphore(2)


def ensure_schema(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS survival_workspaces (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        variant TEXT NOT NULL, version TEXT NOT NULL, files_json TEXT NOT NULL,
        shell_json TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0,
        last_grade REAL NOT NULL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, variant, version))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS survival_completions (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        variant TEXT NOT NULL, version TEXT NOT NULL, level INTEGER NOT NULL,
        code_hash TEXT NOT NULL, base_xp INTEGER NOT NULL, xp_earned INTEGER NOT NULL,
        completed_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, variant, version, level))""")
    if "ui_json" not in {row[1] for row in cursor.execute("PRAGMA table_info(survival_workspaces)").fetchall()}:
        cursor.execute("ALTER TABLE survival_workspaces ADD COLUMN ui_json TEXT NOT NULL DEFAULT '{}'")
    cursor.execute("""CREATE TABLE IF NOT EXISTS survival_preferences (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        version TEXT NOT NULL, active_variant TEXT NOT NULL,
        PRIMARY KEY(user_id, version))""")


def fresh_shell():
    return {"connected": False, "venv": False, "active": False, "dependencies": False, "deps_hash": "",
            "migrated": False, "schema_hash": "", "enabled": False, "running": False,
            "running_hash": "", "running_files": {}, "state": {}, "rows": [], "clock": 0, "logs": []}


def fingerprint(files):
    return hashlib.sha256(json.dumps({k: files.get(k, "") for k in sorted(EDITABLE)}, sort_keys=True).encode()).hexdigest()


def schema_valid(text):
    text = re.sub(r"--[^\n]*", "", text)
    return re.sub(r"\s+", "", text).lower().rstrip(";") == re.sub(r"\s+", "", SCHEMA).lower().rstrip(";")


def unit_valid(text):
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(text)
        return parser["Service"].get("Restart") == "on-failure" and parser["Service"].get("ExecStart") == "python server.py" and parser["Service"].get("EnvironmentFile") == ".env"
    except (configparser.Error, KeyError):
        return False


def validate_files(files, variant):
    canonical = initial_files(variant)
    if not isinstance(files, dict) or not EDITABLE | READONLY <= files.keys() or len(files) > 18:
        raise HTTPException(422, "Нужны все файлы стенда; максимум 18 файлов")
    for name, content in files.items():
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,48}", name) or name in {".", ".."} or not isinstance(content, str):
            raise HTTPException(422, "Некорректный файл")
        if len(content.encode()) > 32768:
            raise HTTPException(422, f"{name}: максимум 32 КБ")
        if name in READONLY and content != canonical[name]:
            raise HTTPException(422, f"{name} — файл учебного адаптера, его менять нельзя")
        if name not in EDITABLE | READONLY and not name.endswith((".md", ".txt")):
            raise HTTPException(422, "Дополнительные файлы — только .md и .txt")
    if len(json.dumps(files).encode()) > 180000:
        raise HTTPException(422, "Проект слишком большой")


class Input(BaseModel):
    variant: StrictStr = "inventory"
    revision: StrictInt
    class Config:
        extra = "forbid"


class SaveInput(Input):
    files: dict[StrictStr, StrictStr]
    ui: dict | None = None


class SessionInput(Input):
    ui: dict


def validate_ui(ui, files):
    allowed = {"selected_file", "selected_level", "cursor", "scroll", "terminal", "history", "command", "guide_open", "previous_open"}
    if set(ui) - allowed or len(json.dumps(ui, ensure_ascii=False).encode()) > 100000:
        raise HTTPException(422, "Состояние редактора слишком большое или имеет неизвестные поля")
    for key, value in ui.items():
        if key == "selected_file" and (not isinstance(value, str) or value not in files):
            raise HTTPException(422, "Неизвестный открытый файл")
        if key in {"selected_level", "cursor", "scroll"} and (type(value) is not int or not 0 <= value <= 1000000 or key == "selected_level" and not 1 <= value <= len(LEVELS)):
            raise HTTPException(422, "Неверная позиция редактора или этап")
        if key in {"guide_open", "previous_open"} and type(value) is not bool:
            raise HTTPException(422, "Неверное состояние панели")
        if key == "command" and (not isinstance(value, str) or len(value) > 5000):
            raise HTTPException(422, "Команда слишком длинная")
        if key == "history" and (not isinstance(value, list) or len(value) > 50 or any(not isinstance(text, str) or len(text) > 5000 for text in value)):
            raise HTTPException(422, "Неверная история команд")
        if key == "terminal" and (not isinstance(value, list) or len(value) > 80 or any(not isinstance(entry, dict) or set(entry) != {"text", "kind"} or not isinstance(entry["text"], str) or len(entry["text"]) > 4000 or not isinstance(entry["kind"], str) or entry["kind"] not in {"", "command", "error", "success"} for entry in value)):
            raise HTTPException(422, "Неверная история терминала")
    return ui


class CommandInput(Input):
    command: StrictStr


class GradeInput(Input):
    level: StrictInt


class SurvivalService:
    def __init__(self, db, award):
        self.db, self.award = db, award

    def variant(self, name):
        if name not in VARIANTS:
            raise HTTPException(404, "Неизвестный вариант стенда")

    def row(self, conn, uid, variant, *, create=False):
        self.variant(variant)
        if create:
            conn.execute("INSERT OR IGNORE INTO survival_workspaces(user_id,variant,version,files_json,shell_json) VALUES (?,?,?,?,?)",
                         (uid, variant, VERSION, json.dumps(initial_files(variant)), json.dumps(fresh_shell())))
        row = conn.execute("SELECT * FROM survival_workspaces WHERE user_id=? AND variant=? AND version=?", (uid, variant, VERSION)).fetchone()
        if not row:
            raise HTTPException(404, "Сначала открой стенд")
        return row

    def view(self, conn, uid, variant):
        row = self.row(conn, uid, variant)
        files, shell = json.loads(row["files_json"]), json.loads(row["shell_json"])
        completed = conn.execute("SELECT variant,level,base_xp,xp_earned FROM survival_completions WHERE user_id=? AND version=? ORDER BY level", (uid, VERSION)).fetchall()
        progress = {key: [] for key in VARIANTS}
        for item in completed:
            progress[item["variant"]].append(dict(item))
        passed = {c["level"] for c in progress[variant]}
        next_level = next((n for n in range(1, len(LEVELS)+1) if n not in passed), len(LEVELS))
        xp = conn.execute("SELECT xp,level FROM users WHERE id=?", (uid,)).fetchone()
        return {"owner_id": uid, "ui": json.loads(row["ui_json"]), "variant": variant, "variants": VARIANTS, "revision": row["revision"], "files": files, "readonly": sorted(READONLY),
                "shell": {k: shell.get(k) for k in ("connected", "venv", "active", "dependencies", "migrated", "enabled", "running", "logs")},
                "needs_restart": shell.get("running_hash") != fingerprint(files), "progress": progress,
                "next_level": next_level, "campaign_complete": len(passed) == len(LEVELS),
                "levels": [{"id": n, "title": title, "xp": xp, "contract": contract, "unlocked": n == 1 or n-1 in passed, "completed": n in passed} for n, (title,xp,contract) in enumerate(LEVELS,1)],
                "xp": xp["xp"], "user_level": xp["level"], "guide": GUIDE, "schema_example": SCHEMA, "unit_example": UNIT}

    def remember_variant(self, conn, uid, variant):
        conn.execute("INSERT INTO survival_preferences(user_id,version,active_variant) VALUES (?,?,?) ON CONFLICT(user_id,version) DO UPDATE SET active_variant=excluded.active_variant", (uid,VERSION,variant))

    def state(self, uid, variant=None):
        with self.db() as conn:
            if variant is None:
                preference = conn.execute("SELECT active_variant FROM survival_preferences WHERE user_id=? AND version=?", (uid,VERSION)).fetchone()
                latest = conn.execute("SELECT variant FROM survival_workspaces WHERE user_id=? AND version=? ORDER BY updated_at DESC, rowid DESC LIMIT 1", (uid,VERSION)).fetchone()
                variant = preference[0] if preference else latest[0] if latest else "inventory"
            self.row(conn, uid, variant, create=True)
            self.remember_variant(conn, uid, variant)
            result = self.view(conn, uid, variant)
            conn.commit()
            return result

    def check_revision(self, row, revision):
        if row["revision"] != revision:
            raise HTTPException(409, "Стенд изменился в другой вкладке. Сохрани локальный текст и обнови стенд.")

    def persist(self, conn, uid, variant, files, shell):
        # Bound both persistence and terminal output before touching the DB.
        shell["logs"] = [str(line)[:1200] for line in shell.get("logs", [])[-100:]]
        content = json.dumps(shell, allow_nan=False)
        if len(content.encode()) > 350000:
            raise HTTPException(422, "Состояние стенда слишком большое; перезапусти процесс")
        conn.execute("UPDATE survival_workspaces SET files_json=?,shell_json=?,revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE user_id=? AND variant=? AND version=?",
                     (json.dumps(files), content, uid, variant, VERSION))

    def save(self, uid, data):
        self.variant(data.variant)
        validate_files(data.files, data.variant)
        with self.db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self.row(conn, uid, data.variant)
            self.check_revision(row, data.revision)
            self.persist(conn, uid, data.variant, data.files, json.loads(row["shell_json"]))
            if data.ui is not None:
                self.persist_ui(conn, uid, data.variant, validate_ui(data.ui, data.files))
            result = self.view(conn, uid, data.variant)
            conn.commit()
            return result

    def persist_ui(self, conn, uid, variant, ui):
        # Viewing another file must not invalidate an in-flight code check.
        conn.execute("UPDATE survival_workspaces SET ui_json=? WHERE user_id=? AND variant=? AND version=?", (json.dumps(ui, ensure_ascii=False),uid,variant,VERSION))
        self.remember_variant(conn, uid, variant)

    def session(self, uid, data):
        with self.db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self.row(conn, uid, data.variant)
            self.check_revision(row, data.revision)
            self.persist_ui(conn, uid, data.variant, validate_ui(data.ui, json.loads(row["files_json"])))
            conn.commit()
            return {"revision": row["revision"]}

    def reset(self, uid, data):
        with self.db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self.row(conn, uid, data.variant)
            self.check_revision(row, data.revision)
            self.persist(conn, uid, data.variant, initial_files(data.variant), fresh_shell())
            self.persist_ui(conn, uid, data.variant, {})
            result = self.view(conn, uid, data.variant)
            conn.commit()
            return result

    def start(self, files, shell):
        if not shell["connected"] or not shell["active"] or not shell["dependencies"]:
            raise ValueError("Сначала SSH, venv, source .venv/bin/activate и pip install -r requirements.txt")
        if shell.get("deps_hash") != hashlib.sha256(files["requirements.txt"].encode()).hexdigest():
            raise ValueError("requirements.txt изменился: повтори pip install -r requirements.txt")
        parse_env(files[".env"])
        PythonLab(files["app.py"], budget=20000)
        shell.update(running=True, running_hash=fingerprint(files), running_files=dict(files), state={})
        return "Process started · http://127.0.0.1:" + parse_env(files[".env"])["PORT"]

    def curl(self, parts, files, shell):
        if not shell["running"]:
            raise ValueError("Connection refused: сервер не запущен")
        method, body, headers, url = "GET", "", {}, None
        i = 1
        while i < len(parts):
            part = parts[i]
            if part in {"-X", "--request", "-d", "--data", "--data-raw", "-H", "--header"}:
                if i+1 >= len(parts):
                    raise ValueError("curl: не хватает значения параметра")
                value = parts[i+1]
                if part in {"-X", "--request"}:
                    method = value.upper()
                elif part in {"-d", "--data", "--data-raw"}:
                    body = value
                    if method == "GET": method = "POST"
                else:
                    if ":" not in value: raise ValueError("Заголовок: Name: value")
                    key, val = value.split(":",1)
                    headers["Authorization" if key.lower() == "authorization" else key] = val.strip()
                i += 2
                continue
            if part not in {"-s", "-i", "-sS"}:
                if url is not None: raise ValueError("curl: укажи один адрес")
                url = part
            i += 1
        parsed = urlparse(url or "")
        env = parse_env(shell["running_files"][".env"])
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"} or parsed.port != int(env["PORT"]) or parsed.username:
            raise ValueError("curl доступен только к localhost и порту твоего виртуального сервера")
        shell["clock"] += 1
        process = Process(shell["running_files"], migrated=shell["migrated"], rows=shell["rows"], state=shell["state"], budget=30000)
        try:
            response = process.request({"method": method, "path": parsed.path or "/", "body": body, "headers": headers, "client": "127.0.0.1", "time": shell["clock"]})
            shell["state"], shell["rows"] = process.state, process.db.rows()
            shell["logs"].extend(process.logs + process.runtime.logs)
            if not process.alive:
                shell["running"] = False
                if shell["enabled"] and unit_valid(shell["running_files"]["pandora.service"]):
                    self.start(shell["running_files"], shell)
                    shell["logs"].append("Service restarted after failure")
            return response
        finally:
            process.close()

    def command(self, uid, data):
        if not 1 <= len(data.command) <= 5000 or "\n" in data.command or "\x00" in data.command:
            raise HTTPException(422, "Одна команда, не больше 5000 символов")
        try:
            parts = shlex.split(data.command)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        if not parts:
            raise HTTPException(422, "Пустая команда")
        action, output, response = None, "", None
        with self.db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self.row(conn, uid, data.variant)
            self.check_revision(row, data.revision)
            files, shell = json.loads(row["files_json"]), json.loads(row["shell_json"])
            try:
                cmd = parts[0]
                if cmd == "help": output = GUIDE
                elif cmd == "clear": action = {"type": "clear"}
                elif cmd == "ssh":
                    if len(parts) != 2 or parts[1] not in {"trainee@lab", f"trainee@{data.variant}.lab"}: raise ValueError("ssh trainee@lab")
                    shell["connected"] = True
                    output = "Connected to " + data.variant + ".lab · учебный SSH\nРабочая директория /srv/app"
                elif not shell["connected"]: raise ValueError("Сначала подключись: ssh trainee@lab")
                elif cmd in {"pwd", "whoami"}: output = "/srv/app" if cmd == "pwd" else "trainee"
                elif cmd == "ls": output = "\n".join(sorted(files))
                elif cmd == "cd":
                    if parts[1:] not in [["/srv/app"], ["~/app"], ["."], []]: raise ValueError("В этом стенде доступна /srv/app")
                    output = "/srv/app"
                elif cmd in {"nano", "vim", "code", "cat", "touch", "rm"}:
                    if len(parts) != 2 or not re.fullmatch(r"[A-Za-z0-9_.-]{1,48}", parts[1]) or parts[1] in {".", ".."}: raise ValueError("Укажи один файл стенда")
                    name = parts[1]
                    if cmd in {"touch", "nano", "vim", "code"} and name not in files:
                        if not name.endswith((".md", ".txt")) or len(files) >= 18: raise ValueError("Можно добавить заметку .md или .txt")
                        files[name] = ""
                    if name not in files: raise ValueError("Файл не найден")
                    if cmd == "cat": output = files[name]
                    elif cmd == "touch": output = name
                    elif cmd == "rm":
                        if name in EDITABLE | READONLY: raise ValueError("Файлы проекта сохраняются; для сброса используй кнопку «Сбросить стенд»")
                        del files[name]
                        output = "Removed " + name
                    else: action = {"type": "open", "file": name}
                elif parts == ["python", "-m", "venv", ".venv"]:
                    shell["venv"] = True
                    output = "Created virtual environment .venv"
                elif parts in [["source", ".venv/bin/activate"], [".", ".venv/bin/activate"]]:
                    if not shell["venv"]: raise ValueError("Создай .venv: python -m venv .venv")
                    shell["active"] = True
                    output = "(.venv) activated"
                elif parts == ["pip", "install", "-r", "requirements.txt"]:
                    if not shell["active"]: raise ValueError("Сначала активируй venv")
                    deps = [line.strip() for line in files["requirements.txt"].splitlines() if line.strip() and not line.lstrip().startswith("#")]
                    if deps: raise ValueError("Этот адаптер использует стандартную библиотеку. Внешние пакеты в учебном Python недоступны.")
                    shell["dependencies"] = True
                    shell["deps_hash"] = hashlib.sha256(files["requirements.txt"].encode()).hexdigest()
                    output = "Environment ready: Python stdlib / json / sqlite3 / HTTP adapter"
                elif parts == ["pip", "list"]: output = "Python stdlib · no external packages"
                elif parts == ["python", "manage.py", "migrate"]:
                    if not shell["active"]: raise ValueError("Сначала активируй venv")
                    if not schema_valid(files["schema.sql"]): raise ValueError("Схема: " + SCHEMA)
                    shell["migrated"], shell["schema_hash"] = True, hashlib.sha256(files["schema.sql"].encode()).hexdigest()
                    output = "Migration applied · records(id, amount)"
                elif parts in [["python", "server.py"], ["restart"]]: output = self.start(files, shell)
                elif parts == ["stop"]:
                    shell["running"] = False
                    output = "Process stopped"
                elif cmd == "systemctl":
                    if len(parts) != 3 or parts[2] not in {"pandora", "pandora.service"}: raise ValueError("systemctl start|restart|stop|enable|status pandora")
                    verb = parts[1]
                    if verb == "status": output = "pandora.service: " + ("active (running)" if shell["running"] else "inactive") + (" / enabled" if shell["enabled"] else " / disabled")
                    elif verb == "stop": shell["running"], output = False, "Service stopped"
                    elif verb in {"enable", "start", "restart"}:
                        if not unit_valid(files["pandora.service"]): raise ValueError("Проверь pandora.service по гайду этапа 8")
                        if verb == "enable": shell["enabled"], output = True, "Service enabled"
                        else: output = self.start(files, shell)
                    else: raise ValueError("Неизвестное действие systemctl")
                elif cmd == "ps": output = "trainee  101  python server.py" if shell["running"] else "No running app process"
                elif cmd == "journalctl": output = "\n".join(shell["logs"][-20:]) or "No logs yet"
                elif cmd in {"env", "printenv"}: output = "\n".join(f"{k}={v}" for k,v in parse_env(files[".env"]).items())
                elif cmd == "curl":
                    response = self.curl(parts, files, shell)
                    output = f"HTTP {response['status']}\n" + json.dumps(response["body"], ensure_ascii=False, indent=2)
                elif cmd in {"check", "pytest"}: action = {"type": "grade"}
                elif cmd == "exit": shell["connected"], output = False, "SSH session closed"
                else: raise ValueError("Команда не поддерживается учебным стендом. help — список команд")
            except (Exception, LabLimit) as error:
                output = "ERROR: " + str(error)[:700]
                action = None
            shell["logs"].append(output[:1200] if not data.command.startswith(("cat ", "env", "printenv", "help", "journalctl")) else "$ " + parts[0])
            self.persist(conn, uid, data.variant, files, shell)
            result = self.view(conn, uid, data.variant)
            conn.commit()
            return {"workspace": result, "output": output, "action": action, "response": response}

    def run_grade(self, uid, data):
        if not 1 <= data.level <= len(LEVELS):
            raise HTTPException(422, "Неизвестный этап")
        with self.db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self.row(conn, uid, data.variant)
            self.check_revision(row, data.revision)
            files, shell = json.loads(row["files_json"]), json.loads(row["shell_json"])
            previous = conn.execute("SELECT COUNT(*) FROM survival_completions WHERE user_id=? AND variant=? AND version=? AND level<?", (uid,data.variant,VERSION,data.level)).fetchone()[0]
            if previous != data.level-1: raise HTTPException(409, "Сначала пройди предыдущие этапы этого варианта")
            if not shell["connected"] or not shell["running"] or shell["running_hash"] != fingerprint(files): raise HTTPException(409, "Сохрани файлы и перезапусти сервер; требуется активная SSH-сессия")
            if data.level >= 6 and (not shell["migrated"] or shell["schema_hash"] != hashlib.sha256(files["schema.sql"].encode()).hexdigest() or not schema_valid(files["schema.sql"])): raise HTTPException(409, "Выполни актуальную миграцию schema.sql")
            if data.level >= 8 and (not shell["enabled"] or not unit_valid(files["pandora.service"])): raise HTTPException(409, "Настрой и включи службу pandora")
            if time.time()-row["last_grade"] < 3: raise HTTPException(429, "Подожди 3 секунды между проверками")
            if not GRADE_SLOTS.acquire(blocking=False): raise HTTPException(429, "Проверяющие стенды заняты; повтори немного позже")
            try:
                conn.execute("UPDATE survival_workspaces SET last_grade=? WHERE user_id=? AND variant=? AND version=?", (time.time(),uid,data.variant,VERSION))
                conn.commit()
            except BaseException:
                GRADE_SLOTS.release()
                raise
        try:
            result = grade(files, data.variant, data.level, migrated=shell["migrated"])
        finally:
            GRADE_SLOTS.release()
        awarded, already = 0, False
        with self.db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = self.row(conn, uid, data.variant)
            self.check_revision(current, data.revision)
            if result["passed"]:
                existing = conn.execute("SELECT 1 FROM survival_completions WHERE user_id=? AND variant=? AND version=? AND level=?", (uid,data.variant,VERSION,data.level)).fetchone()
                already = bool(existing)
                if not existing:
                    base = LEVELS[data.level-1][1]
                    reason = f"backend_survival:{data.variant}:{data.level}:{VERSION}"
                    self.award(conn.cursor(), uid, base, reason, f"survival:{data.variant}:{data.level}")
                    ledger = conn.execute("SELECT xp_change FROM xp_log WHERE user_id=? AND reason=? ORDER BY id DESC LIMIT 1", (uid,reason)).fetchone()
                    awarded = int(ledger[0]) if ledger else base
                    conn.execute("INSERT INTO survival_completions(user_id,variant,version,level,code_hash,base_xp,xp_earned) VALUES (?,?,?,?,?,?,?)", (uid,data.variant,VERSION,data.level,fingerprint(files),base,awarded))
            workspace = self.view(conn, uid, data.variant)
            conn.commit()
        return {**result, "awarded": awarded, "already_completed": already, "base_reward": LEVELS[data.level-1][1], "workspace": workspace}


def install(app, db, auth, award):
    service = SurvivalService(db, award)
    router = APIRouter(prefix="/api/survival", tags=["Backend Survival"])

    @app.get("/survival", include_in_schema=False)
    @app.get("/survival/", include_in_schema=False)
    def page():
        return FileResponse(Path(__file__).with_name("survival.html"))

    @router.get("/state")
    def state(variant: str | None = None, user: dict = Depends(auth)):
        return service.state(int(user["id"]), variant)

    @router.post("/save")
    def save(data: SaveInput, user: dict = Depends(auth)):
        return service.save(int(user["id"]), data)

    @router.post("/command")
    def command(data: CommandInput, user: dict = Depends(auth)):
        return service.command(int(user["id"]), data)

    @router.post("/session")
    def session(data: SessionInput, user: dict = Depends(auth)):
        return service.session(int(user["id"]), data)

    @router.post("/grade")
    def check(data: GradeInput, user: dict = Depends(auth)):
        return service.run_grade(int(user["id"]), data)

    @router.post("/reset")
    def reset(data: Input, user: dict = Depends(auth)):
        return service.reset(int(user["id"]), data)

    @router.get("/export")
    def export(variant: str = "inventory", user: dict = Depends(auth)):
        workspace = service.state(int(user["id"]), variant)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in workspace["files"].items():
                archive.writestr(name, content)
        return Response(stream.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="survival-{variant}.zip"'})

    app.include_router(router)
    return service
