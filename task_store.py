"""
task_store — on-disk (SQLite) task/quiz store for the 512MB Render tier.

WHY THIS EXISTS
---------------
tasks.json is ~40MB; parsed into Python objects it costs ~85MB of heap, and the
old design also kept a second full parse for check_logic plus 24MB+ of
serialized /api/tasks bytes.  Under memory pressure those caches were evicted,
and the NEXT request re-parsed the 40MB file — a transient spike that OOM-killed
the dyno in a loop.

NEW DESIGN
----------
A one-off BUILD step (Render buildCommand / Docker build / startup subprocess)
parses the JSON sources once and writes:

  * task_store.db            — SQLite, read-only at runtime:
        tasks(id, seq, category, tier, archived, task_json, lite_json, public_json)
        quiz(id, difficulty, question, item_json)
        kv(key, value)       — meta/categories/fingerprint/payload etag
  * cache/tasks_payload.json     — the exact /api/tasks response body
  * cache/tasks_payload.json.gz  — its gzip twin (both streamed to disk, ~O(1) RAM)

At runtime the app keeps only a slim lite-task list in heap (see
task_shapes.lite_task) and fetches heavy rows per-task with a small LRU.
The 40MB file is NEVER parsed inside the serving process.

Build is atomic (tmp files + os.replace; the .db is replaced last and gates
payload validity via the stored fingerprint).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import sqlite3
import subprocess
import sys
import threading
import time
from functools import lru_cache
from pathlib import Path

import task_shapes

try:
    import orjson as _orjson

    def _loads(s):
        return _orjson.loads(s)

    def _dumps(obj) -> bytes:
        return _orjson.dumps(obj, option=_orjson.OPT_NON_STR_KEYS)
except ImportError:  # pragma: no cover - orjson is in requirements
    _orjson = None

    def _loads(s):
        return json.loads(s)

    def _dumps(obj) -> bytes:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

logger = logging.getLogger("academy.taskstore")

_BASE_DIR = Path(__file__).resolve().parent
STORE_PATH = Path(os.getenv("PANDORA_TASK_STORE_PATH", str(_BASE_DIR / "task_store.db")))
PAYLOAD_DIR = Path(os.getenv("PANDORA_TASK_PAYLOAD_DIR", str(_BASE_DIR / "cache")))
PAYLOAD_JSON = PAYLOAD_DIR / "tasks_payload.json"
PAYLOAD_GZ = PAYLOAD_DIR / "tasks_payload.json.gz"

# Bump when the stored shape changes so old stores rebuild automatically.
SCHEMA_VERSION = "3"

_EXTERNAL_FILE = _BASE_DIR / "tasks_external_all_available.json"
_TASKS_FILE = _BASE_DIR / "tasks.json"
_LEGACY_FILE = _BASE_DIR / "tasks_legacy.json"
_QUIZ_FILE = _BASE_DIR / "kahoot_1_2.json"

# ──────────────────────────────────────────────────────────────────────────────
# Fingerprint / freshness
# ──────────────────────────────────────────────────────────────────────────────

def _stat_sig(p: Path) -> str:
    try:
        st = p.stat()
        return f"{int(st.st_mtime)}:{st.st_size}"
    except OSError:
        return "absent"

def source_fingerprint() -> str:
    parts = [
        f"v{SCHEMA_VERSION}",
        f"ext={_stat_sig(_EXTERNAL_FILE)}",
        f"tasks={_stat_sig(_TASKS_FILE)}",
        f"legacy={_stat_sig(_LEGACY_FILE)}",
        f"quiz={_stat_sig(_QUIZ_FILE)}",
    ]
    return "|".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# Runtime access (read-only, thread-local connections, tiny LRUs)
# ──────────────────────────────────────────────────────────────────────────────

_local = threading.local()
_state_lock = threading.Lock()
_state: dict = {"version": None, "checked_at": 0.0, "payload_etag": ""}


def _connect() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        return conn
    # mode=ro: the store is immutable at runtime; readers never block each other.
    conn = sqlite3.connect(
        f"file:{STORE_PATH}?mode=ro", uri=True, timeout=5.0, check_same_thread=False
    )
    conn.execute("PRAGMA query_only=1")
    _local.conn = conn
    return conn


def _close_local_conn() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _local.conn = None


def _kv(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def ready() -> bool:
    return version() is not None


def version(max_age_s: float = 5.0) -> str | None:
    """Fingerprint stored in the DB (None if the store is missing/broken).
    Cached briefly so hot paths don't touch SQLite for the version check."""
    now = time.monotonic()
    with _state_lock:
        if _state["version"] is not None and now - _state["checked_at"] < max_age_s:
            return _state["version"]
    try:
        conn = _connect()
        ver = _kv(conn, "fingerprint")
        etag = _kv(conn, "payload_etag") or ""
    except sqlite3.Error:
        _close_local_conn()
        with _state_lock:
            _state["version"] = None
            _state["checked_at"] = now
        return None
    with _state_lock:
        _state["version"] = ver
        _state["payload_etag"] = etag
        _state["checked_at"] = now
    return ver


def invalidate_runtime_state() -> None:
    """Force the next version() call to re-read the DB (used after rebuild)."""
    with _state_lock:
        _state["version"] = None
        _state["checked_at"] = 0.0
    _get_task_full_cached.cache_clear()
    _get_task_public_cached.cache_clear()


def clear_caches() -> None:
    """Drop per-task LRUs (memory-pressure hook; refetch is a single SQLite row)."""
    _get_task_full_cached.cache_clear()
    _get_task_public_cached.cache_clear()


def load_lite_bundle() -> dict | None:
    """Return {"meta","categories","tasks":[lite dicts]} from the store.
    This is the ONLY whole-dataset read at runtime and it is ~4x smaller than
    parsing tasks.json (heavy fields never enter the heap)."""
    ver = version()
    if ver is None:
        return None
    try:
        conn = _connect()
        meta = _loads(_kv(conn, "meta_json") or "{}")
        categories = _loads(_kv(conn, "categories_json") or "[]")
        tasks = [
            _loads(row[0])
            for row in conn.execute("SELECT lite_json FROM tasks ORDER BY seq")
        ]
    except sqlite3.Error as e:
        logger.warning("task_store.load_lite_bundle failed: %s", e)
        _close_local_conn()
        return None
    return {"meta": meta, "categories": categories, "tasks": tasks, "_store_version": ver}


@lru_cache(maxsize=64)
def _get_task_full_cached(task_id: str, _ver: str) -> str | None:
    row = _connect().execute(
        "SELECT task_json FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    return row[0] if row else None


def get_task_full(task_id: str) -> dict | None:
    """Full raw task (including check_logic.cases) — one small row, LRU-cached."""
    ver = version()
    if ver is None or not task_id:
        return None
    try:
        raw = _get_task_full_cached(str(task_id), ver)
    except sqlite3.Error as e:
        logger.warning("task_store.get_task_full(%s) failed: %s", task_id, e)
        _close_local_conn()
        return None
    return _loads(raw) if raw else None


@lru_cache(maxsize=64)
def _get_task_public_cached(task_id: str, _ver: str) -> str | None:
    row = _connect().execute(
        "SELECT public_json FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    return row[0] if row else None


def get_task_public(task_id: str) -> dict | None:
    """public_task() payload (resources precomputed at build time)."""
    ver = version()
    if ver is None or not task_id:
        return None
    try:
        raw = _get_task_public_cached(str(task_id), ver)
    except sqlite3.Error as e:
        logger.warning("task_store.get_task_public(%s) failed: %s", task_id, e)
        _close_local_conn()
        return None
    return _loads(raw) if raw else None


def get_task_texts(task_ids: list[str]) -> dict[str, dict]:
    """Batch {id: {"story","description"}} for list enrichment (admin/user
    completions).  json_extract avoids parsing whole task rows."""
    ids = [str(t) for t in task_ids if t]
    if not ids or version() is None:
        return {}
    out: dict[str, dict] = {}
    try:
        conn = _connect()
        for i in range(0, len(ids), 500):
            chunk = ids[i : i + 500]
            q = (
                "SELECT id, json_extract(task_json,'$.story'),"
                " json_extract(task_json,'$.description')"
                f" FROM tasks WHERE id IN ({','.join('?' * len(chunk))})"
            )
            for tid, story, desc in conn.execute(q, chunk):
                out[tid] = {"story": story or "", "description": desc or ""}
    except sqlite3.Error as e:
        logger.warning("task_store.get_task_texts failed: %s", e)
        _close_local_conn()
    return out


def filtered_public(category: str | None, tier: str | None) -> list[dict] | None:
    """public_task list for the rarely-used filtered /api/tasks path."""
    if version() is None:
        return None
    where, args = ["archived = 0"], []
    if category:
        where.append("category = ?")
        args.append(category)
    if tier:
        where.append("tier = ?")
        args.append(tier)
    try:
        conn = _connect()
        rows = conn.execute(
            f"SELECT public_json FROM tasks WHERE {' AND '.join(where)} ORDER BY seq",
            args,
        )
        return [_loads(r[0]) for r in rows]
    except sqlite3.Error as e:
        logger.warning("task_store.filtered_public failed: %s", e)
        _close_local_conn()
        return None


def payload_file(want_gzip: bool) -> tuple[Path, str] | None:
    """(path, etag) of the prebuilt /api/tasks body, or None if unavailable."""
    if version() is None:
        return None
    with _state_lock:
        etag = _state["payload_etag"]
    path = PAYLOAD_GZ if want_gzip else PAYLOAD_JSON
    if not etag or not path.exists():
        return None
    return path, etag


def check_logic_count() -> int:
    if version() is None:
        return 0
    try:
        row = _connect().execute(
            "SELECT value FROM kv WHERE key='check_logic_count'"
        ).fetchone()
        return int(row[0]) if row else 0
    except (sqlite3.Error, ValueError):
        _close_local_conn()
        return 0


def quiz_count() -> int:
    if version() is None:
        return 0
    try:
        return int(_connect().execute("SELECT COUNT(*) FROM quiz").fetchone()[0])
    except sqlite3.Error:
        _close_local_conn()
        return 0


def quiz_pool(max_items: int = 0) -> list[dict]:
    """Lightweight selection pool: [{"id","difficulty","question"}].
    ~100 bytes/item instead of the full parsed bank (was ~20MB in heap)."""
    if version() is None:
        return []
    sql = "SELECT id, difficulty, question FROM quiz"
    args: tuple = ()
    if max_items and max_items > 0:
        sql += " ORDER BY RANDOM() LIMIT ?"
        args = (int(max_items),)
    try:
        return [
            {"id": r[0], "difficulty": r[1], "question": r[2] or ""}
            for r in _connect().execute(sql, args)
        ]
    except sqlite3.Error as e:
        logger.warning("task_store.quiz_pool failed: %s", e)
        _close_local_conn()
        return []


def quiz_items(ids: list[str]) -> dict[str, dict]:
    """Full quiz items by id (fetched only for the 12-15 selected questions)."""
    ids = [str(i) for i in ids if i]
    if not ids or version() is None:
        return {}
    try:
        conn = _connect()
        q = f"SELECT id, item_json FROM quiz WHERE id IN ({','.join('?' * len(ids))})"
        return {r[0]: _loads(r[1]) for r in conn.execute(q, ids)}
    except sqlite3.Error as e:
        logger.warning("task_store.quiz_items failed: %s", e)
        _close_local_conn()
        return {}


# ──────────────────────────────────────────────────────────────────────────────
# Build
# ──────────────────────────────────────────────────────────────────────────────

def _read_json(path: Path):
    with open(path, "rb") as f:
        return _loads(f.read())


def build_store(verbose: bool = True) -> str:
    """Parse the JSON sources once and write DB + payload files atomically.
    Runs in the deploy build (or a startup subprocess) — NOT in serving threads."""
    t0 = time.time()
    fingerprint = source_fingerprint()

    primary = _EXTERNAL_FILE if _EXTERNAL_FILE.exists() else _TASKS_FILE
    curated = _read_json(primary) if primary.exists() else {"meta": {}, "categories": [], "tasks": []}
    legacy_tasks = []
    if _LEGACY_FILE.exists():
        try:
            legacy = _read_json(_LEGACY_FILE)
            legacy_tasks = legacy.get("tasks", []) if isinstance(legacy, dict) else []
        except Exception as e:
            logger.warning("build_store: failed to read %s: %s", _LEGACY_FILE.name, e)
    bundle = task_shapes.merge_task_sources(curated, legacy_tasks)
    del curated, legacy_tasks

    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    tmp_db = STORE_PATH.with_suffix(".db.tmp")
    tmp_json = PAYLOAD_JSON.with_suffix(".json.tmp")
    tmp_gz = PAYLOAD_GZ.with_suffix(".gz.tmp")
    for p in (tmp_db, tmp_json, tmp_gz):
        try:
            p.unlink()
        except OSError:
            pass

    conn = sqlite3.connect(tmp_db)
    conn.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        CREATE TABLE kv(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE tasks(
            id TEXT PRIMARY KEY,
            seq INTEGER,
            category TEXT,
            tier TEXT,
            archived INTEGER,
            task_json TEXT,
            lite_json TEXT,
            public_json TEXT
        );
        CREATE INDEX idx_tasks_cat_tier ON tasks(category, tier);
        CREATE TABLE quiz(id TEXT PRIMARY KEY, difficulty INTEGER, question TEXT, item_json TEXT);
        """
    )

    # Stream the /api/tasks payload to disk while filling the DB: at no point
    # does the whole serialized body (24MB+) exist in memory.
    meta_b = _dumps(bundle.get("meta", {}))
    cats_b = _dumps(bundle.get("categories", []))
    md5 = hashlib.md5()
    total_json = 0

    fh = open(tmp_json, "wb")
    gz_raw = open(tmp_gz, "wb")
    gz_fh = gzip.GzipFile(filename="", mode="wb", fileobj=gz_raw, compresslevel=6)

    def emit(b: bytes):
        nonlocal total_json
        fh.write(b)
        gz_fh.write(b)
        md5.update(b)
        total_json += len(b)

    emit(b'{"meta":' + meta_b + b',"categories":' + cats_b + b',"tasks":[')

    rows = []
    n_tasks = n_public = cl_count = 0
    seen_ids: set[str] = set()
    first_payload_item = True
    for seq, task in enumerate(bundle.get("tasks", [])):
        if not isinstance(task, dict):
            continue
        tid = str(task.get("id") or "")
        if not tid or tid in seen_ids:
            continue  # PK-safe: duplicates keep first occurrence (dict-cache had last; ids are unique in practice)
        seen_ids.add(tid)
        archived = 1 if task_shapes.is_archived_task_id(tid) else 0
        public = task_shapes.public_task(task)
        if task.get("check_logic"):
            cl_count += 1
        rows.append(
            (
                tid,
                seq,
                str(task.get("category") or ""),
                str(task.get("tier") or ""),
                archived,
                _dumps(task).decode("utf-8"),
                _dumps(task_shapes.lite_task(task)).decode("utf-8"),
                _dumps(public).decode("utf-8"),
            )
        )
        n_tasks += 1
        if not archived:
            if not first_payload_item:
                emit(b",")
            emit(_dumps(public))
            first_payload_item = False
            n_public += 1
        if len(rows) >= 500:
            conn.executemany("INSERT OR IGNORE INTO tasks VALUES (?,?,?,?,?,?,?,?)", rows)
            rows.clear()
    if rows:
        conn.executemany("INSERT OR IGNORE INTO tasks VALUES (?,?,?,?,?,?,?,?)", rows)
        rows.clear()

    emit(b"]}")
    fh.close()
    gz_fh.close()
    gz_raw.close()
    etag = md5.hexdigest()[:16]

    del bundle  # free the parsed tree before touching the quiz bank

    # Quiz bank → rows (id falls back to index when the bank has no ids).
    n_quiz = 0
    if _QUIZ_FILE.exists():
        try:
            bank = _read_json(_QUIZ_FILE)
            items = bank if isinstance(bank, list) else (bank.get("items") or bank.get("questions") or [])
            qrows = []
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                qid = str(item.get("id") or f"q{idx}")
                level = task_shapes.quiz_difficulty_level(
                    item.get("_difficulty_level", item.get("difficulty"))
                )
                qrows.append((qid, level, str(item.get("question") or ""), _dumps(item).decode("utf-8")))
                if len(qrows) >= 500:
                    conn.executemany("INSERT OR IGNORE INTO quiz VALUES (?,?,?,?)", qrows)
                    n_quiz += len(qrows)
                    qrows.clear()
            if qrows:
                conn.executemany("INSERT OR IGNORE INTO quiz VALUES (?,?,?,?)", qrows)
                n_quiz += len(qrows)
            del bank, items
        except Exception as e:
            logger.warning("build_store: quiz bank skipped: %s", e)

    conn.executemany(
        "INSERT INTO kv VALUES (?,?)",
        [
            ("fingerprint", fingerprint),
            ("meta_json", meta_b.decode("utf-8")),
            ("categories_json", cats_b.decode("utf-8")),
            ("payload_etag", etag),
            ("check_logic_count", str(cl_count)),
            ("built_at", str(int(time.time()))),
        ],
    )
    conn.commit()
    conn.close()

    # Payload files first, DB last: a store whose fingerprint is present always
    # references payload files that are already in place.
    os.replace(tmp_json, PAYLOAD_JSON)
    os.replace(tmp_gz, PAYLOAD_GZ)
    os.replace(tmp_db, STORE_PATH)

    msg = (
        f"task_store built in {time.time() - t0:.1f}s: {n_tasks} tasks "
        f"({n_public} public, {cl_count} with check_logic), {n_quiz} quiz items, "
        f"payload {total_json / 1e6:.1f}MB (etag {etag})"
    )
    if verbose:
        print(msg, flush=True)
    logger.info(msg)
    return fingerprint


def rebuild_subprocess(timeout_s: float = 600.0) -> bool:
    """Build in a child process so the ~120MB parse peak never lands in (and is
    fully returned to the OS instead of fragmenting) the serving process."""
    try:
        res = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--build"],
            cwd=str(_BASE_DIR),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if res.returncode != 0:
            logger.error("task_store subprocess build failed: %s", (res.stderr or res.stdout)[-2000:])
            return False
        invalidate_runtime_state()
        return True
    except Exception as e:
        logger.error("task_store subprocess build error: %s", e)
        return False


def ensure_store(allow_inprocess: bool = True) -> bool:
    """Make sure the store matches the current sources (called at startup).
    Prefers a subprocess build; falls back to in-process (dev platforms)."""
    current = source_fingerprint()
    if version(max_age_s=0.0) == current:
        return True
    logger.info("task_store stale or missing — building (fingerprint %s)", current)
    if rebuild_subprocess():
        return version(max_age_s=0.0) == current
    if not allow_inprocess:
        return False
    try:
        build_store(verbose=False)
        invalidate_runtime_state()
        return version(max_age_s=0.0) == current
    except Exception as e:
        logger.error("task_store in-process build failed: %s", e)
        return False


# Throttled source-change probe (preserves the old "edit tasks.json → live
# reload" behaviour without stat()ing 3 files on every request).
_sources_probe = {"at": 0.0, "fingerprint": None}
_sources_probe_lock = threading.Lock()


def sources_changed(min_interval_s: float = 30.0) -> bool:
    now = time.monotonic()
    with _sources_probe_lock:
        if now - _sources_probe["at"] < min_interval_s:
            return False
        _sources_probe["at"] = now
    current = source_fingerprint()
    stored = version()
    return stored is not None and current != stored


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if "--build" in sys.argv or len(sys.argv) == 1:
        build_store()
    else:
        print(f"usage: {sys.argv[0]} --build", file=sys.stderr)
        sys.exit(2)
