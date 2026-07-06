"""
Pure task-shaping helpers shared by main.py (runtime) and task_store.py (build).

Extracted from main.py so the task-store build step can produce the exact same
public/lite payloads WITHOUT importing the FastAPI app (13k lines, side effects).
No imports beyond stdlib; no state.
"""

ARCHIVED_TASK_ID_PREFIXES: tuple[str, ...] = (
    # Legacy packs: generic/duplicate content and (historically) mixed schemas.
    "py_nova_",
    "js_nova_",
    "fe_nova_",
    "sc_nova_",
    "py_v3_",
    "js_v3_",
    "fe_v3_",
    "sc_v3_",
)

def is_archived_task_id(task_id: str) -> bool:
    tid = str(task_id or "")
    return any(tid.startswith(p) for p in ARCHIVED_TASK_ID_PREFIXES)

def _dedupe_resources(items: list[dict]) -> list[dict]:
    """Deduplicate resources by URL, preserving order."""
    seen: set[str] = set()
    out: list[dict] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        url = str(it.get("url") or "").strip()
        title = str(it.get("title") or "").strip()
        if not url:
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append({"title": title or url, "url": url})
    return out

_DEFAULT_RESOURCES: dict[str, dict[str, list[dict]]] = {
    "python": {
        "docs": [
            {"title": "Python: tutorial (EN)", "url": "https://docs.python.org/3/tutorial/index.html"},
        ],
        "videos": [
            {"title": "Python: основы (freeCodeCamp, EN)", "url": "https://www.youtube.com/watch?v=rfscVS0vtbw"},
        ],
    },
    "javascript": {
        "docs": [
            {"title": "MDN: руководство по JavaScript (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/JavaScript/Guide"},
        ],
        "videos": [
            {"title": "JavaScript: основы (freeCodeCamp, EN)", "url": "https://www.youtube.com/watch?v=PkZNo7MFNFg"},
        ],
    },
    "frontend": {
        "docs": [
            {"title": "MDN: HTML основы (RU)", "url": "https://developer.mozilla.org/ru/docs/Learn/Getting_started_with_the_web/HTML_basics"},
            {"title": "MDN: CSS основы (RU)", "url": "https://developer.mozilla.org/ru/docs/Learn/Getting_started_with_the_web/CSS_basics"},
        ],
        "videos": [
            {"title": "HTML: полный курс (freeCodeCamp, EN)", "url": "https://www.youtube.com/watch?v=pQN-pnXPaVg"},
            {"title": "CSS: crash course (Traversy Media, EN)", "url": "https://www.youtube.com/watch?v=yfoY53QXEnI"},
        ],
    },
    "scratch": {
        "docs": [
            {"title": "Scratch: идеи и туториалы", "url": "https://scratch.mit.edu/ideas"},
            {"title": "Scratch Wiki: блоки", "url": "https://en.scratch-wiki.info/wiki/Blocks"},
        ],
        "videos": [
            {"title": "Scratch Team: видео", "url": "https://www.youtube.com/@ScratchTeam/videos"},
        ],
    },
}

def resources_for_task(task: dict) -> dict:
    """
    Build per-task learning resources (docs + videos).
    Stored server-side so the client stays dumb and tasks.json stays schema-compatible.
    """
    category = str(task.get("category") or "").lower()
    explicit = task.get("resources") if isinstance(task.get("resources"), dict) else {}
    explicit_docs = explicit.get("docs") if isinstance(explicit.get("docs"), list) else []
    explicit_videos = explicit.get("videos") if isinstance(explicit.get("videos"), list) else []

    # If tasks.json provides resources explicitly (and both groups are non-empty),
    # treat them as authoritative.
    if explicit_docs and explicit_videos:
        return {"docs": _dedupe_resources(explicit_docs), "videos": _dedupe_resources(explicit_videos)}

    text = " ".join(
        [
            str(task.get("title") or ""),
            str(task.get("story") or ""),
            str(task.get("description") or ""),
            str(task.get("initial_code") or ""),
        ]
    ).lower()

    docs: list[dict] = []
    videos: list[dict] = []

    if explicit_docs:
        docs.extend(explicit_docs)
    if explicit_videos:
        videos.extend(explicit_videos)

    defaults = _DEFAULT_RESOURCES.get(category) or {}
    docs.extend(defaults.get("docs") or [])
    videos.extend(defaults.get("videos") or [])

    # Concept-sensitive docs (best-effort keyword matching; falls back to defaults).
    if category == "python":
        if any(k in text for k in ("регуляр", "regex", "re.")):
            docs.insert(0, {"title": "Python: re module (EN)", "url": "https://docs.python.org/3/library/re.html"})
        elif any(k in text for k in ("словар", "dict", "ключ", "{")):
            docs.insert(0, {"title": "Python: dictionaries (EN)", "url": "https://docs.python.org/3/tutorial/datastructures.html#dictionaries"})
        elif any(k in text for k in ("спис", "list", "[")):
            docs.insert(0, {"title": "Python: lists (EN)", "url": "https://docs.python.org/3/tutorial/introduction.html#lists"})
        elif any(k in text for k in ("цикл", "for ", "while ")):
            docs.insert(0, {"title": "Python: control flow (EN)", "url": "https://docs.python.org/3/tutorial/controlflow.html"})
        elif "функц" in text or "def " in text:
            docs.insert(0, {"title": "Python: defining functions (EN)", "url": "https://docs.python.org/3/tutorial/controlflow.html#defining-functions"})
        elif any(k in text for k in ("строк", "string", "split", "join")):
            docs.insert(0, {"title": "Python: strings (EN)", "url": "https://docs.python.org/3/tutorial/introduction.html#strings"})
        elif any(k in text for k in ("random", "случайн")):
            docs.insert(0, {"title": "Python: random module (EN)", "url": "https://docs.python.org/3/library/random.html"})
        elif any(k in text for k in ("множ", "set(")):
            docs.insert(0, {"title": "Python: sets (EN)", "url": "https://docs.python.org/3/tutorial/datastructures.html#sets"})

    elif category == "javascript":
        if any(k in text for k in ("регуляр", "regex", "/g", "regexp")):
            docs.insert(0, {"title": "MDN: регулярные выражения (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/JavaScript/Guide/Regular_Expressions"})
        elif any(k in text for k in ("массив", "array", "[")):
            docs.insert(0, {"title": "MDN: Array (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/JavaScript/Reference/Global_Objects/Array"})
        elif any(k in text for k in ("объект", "object", "{")):
            docs.insert(0, {"title": "MDN: объекты (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/JavaScript/Guide/Working_with_objects"})
        elif "функц" in text or "function" in text or "=>" in text:
            docs.insert(0, {"title": "MDN: функции (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/JavaScript/Guide/Functions"})
        elif any(k in text for k in ("строк", "string", ".split", ".join")):
            docs.insert(0, {"title": "MDN: String (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/JavaScript/Reference/Global_Objects/String"})
        elif any(k in text for k in ("math", "случайн", "random")):
            docs.insert(0, {"title": "MDN: Math (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/JavaScript/Reference/Global_Objects/Math"})
        elif "date" in text or "время" in text:
            docs.insert(0, {"title": "MDN: Date (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/JavaScript/Reference/Global_Objects/Date"})

    elif category == "frontend":
        if "grid" in text:
            docs.insert(0, {"title": "MDN: CSS Grid (RU)", "url": "https://developer.mozilla.org/ru/docs/Learn/CSS/CSS_layout/Grids"})
        if "flex" in text:
            docs.insert(0, {"title": "MDN: Flexbox (RU)", "url": "https://developer.mozilla.org/ru/docs/Learn/CSS/CSS_layout/Flexbox"})
        if any(k in text for k in ("@media", "адаптив", "responsive", "768px")):
            docs.insert(0, {"title": "MDN: media queries (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/CSS/Media_Queries/Using_media_queries"})
        if any(k in text for k in ("--", ":root", "переменн")):
            docs.insert(0, {"title": "MDN: CSS-переменные (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/CSS/Using_CSS_custom_properties"})
        if any(k in text for k in ("position", "absolute", "relative", "fixed", "sticky")):
            docs.insert(0, {"title": "MDN: position (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/CSS/position"})
        if any(k in text for k in ("margin", "padding", "border", "box")):
            docs.insert(0, {"title": "MDN: блочная модель (RU)", "url": "https://developer.mozilla.org/ru/docs/Learn/CSS/Building_blocks/The_box_model"})

    elif category == "scratch":
        if any(k in text for k in ("движ", "шаг", "поверн", "координат")):
            docs.insert(0, {"title": "Scratch Wiki: Motion Blocks", "url": "https://en.scratch-wiki.info/wiki/Motion_Blocks"})
        elif any(k in text for k in ("костюм", "сказать", "говор", "внешн")):
            docs.insert(0, {"title": "Scratch Wiki: Looks Blocks", "url": "https://en.scratch-wiki.info/wiki/Looks_Blocks"})
        elif any(k in text for k in ("звук", "громк")):
            docs.insert(0, {"title": "Scratch Wiki: Sound Blocks", "url": "https://en.scratch-wiki.info/wiki/Sound_Blocks"})
        elif any(k in text for k in ("флаж", "клик", "клавиш", "сообщен", "broadcast")):
            docs.insert(0, {"title": "Scratch Wiki: Events Blocks", "url": "https://en.scratch-wiki.info/wiki/Events_Blocks"})
        elif any(k in text for k in ("всегда", "повтор", "если", "таймер", "клон")):
            docs.insert(0, {"title": "Scratch Wiki: Control Blocks", "url": "https://en.scratch-wiki.info/wiki/Control_Blocks"})
        elif any(k in text for k in ("спрос", "касается", "сенсор")):
            docs.insert(0, {"title": "Scratch Wiki: Sensing Blocks", "url": "https://en.scratch-wiki.info/wiki/Sensing_Blocks"})
        elif any(k in text for k in ("переменн", "score", "level")):
            docs.insert(0, {"title": "Scratch Wiki: Variables Blocks", "url": "https://en.scratch-wiki.info/wiki/Variables_Blocks"})
        elif any(k in text for k in (">", "<", "=", "оператор")):
            docs.insert(0, {"title": "Scratch Wiki: Operators Blocks", "url": "https://en.scratch-wiki.info/wiki/Operators_Blocks"})

    return {"docs": _dedupe_resources(docs), "videos": _dedupe_resources(videos)}

def public_task(task: dict) -> dict:
    """Return a safe task payload for students (no expected answers)."""
    logic = task.get("check_logic") or {}
    return {
        "id": task.get("id"),
        "category": task.get("category"),
        "tier": task.get("tier"),
        "xp": task.get("xp"),
        "title": task.get("title"),
        "story": task.get("story"),
        "description": task.get("description"),
        "initial_code": task.get("initial_code"),
        "topic": task.get("topic", ""),
        "task_type": task.get("task_type", "code"),
        "video_url": task.get("video_url", ""),
        "resources": resources_for_task(task),
        "prerequisites": task.get("prerequisites") or [],
        "source_platform": task.get("source_platform", ""),
        "tags": task.get("tags") or [],
        "check": {
            "engine": logic.get("engine"),
            "case_count": logic.get("case_count", len(logic.get("cases") or [])),
        },
    }


def public_task_lite(task: dict) -> dict:
    """Lightweight task payload for board/card rendering (no heavy fields).
    Heavy fields (initial_code, resources, video_url, description, story) are loaded
    on-demand via /api/tasks/{task_id}/detail to reduce initial payload and memory."""
    logic = task.get("check_logic") or {}
    return {
        "id": task.get("id"),
        "category": task.get("category"),
        "tier": task.get("tier"),
        "xp": task.get("xp"),
        "title": task.get("title"),
        "topic": task.get("topic", ""),
        "task_type": task.get("task_type", "code"),
        "prerequisites": task.get("prerequisites") or [],
        "source_platform": task.get("source_platform", ""),
        "check": {
            "engine": logic.get("engine"),
            "case_count": logic.get("case_count", len(logic.get("cases") or [])),
        },
    }


# ── Lite (in-heap) representation used by the task store ──────────────────────
#
# The runtime keeps ONLY these slimmed dicts in memory for all ~12k tasks; the
# heavy fields live in task_store.db and are fetched per-task on demand.
# Semantics match the old stripped _TASKS_CACHE (cases/hidden_cases removed,
# counts preserved) so every metadata call site keeps working unchanged.

# Heavy per-task fields never read on lite code paths (verified against main.py).
LITE_DROP_FIELDS: tuple[str, ...] = (
    "description",      # 7.6MB — served via /detail and the prebuilt payload
    "story",            # 1.3MB — completions enrichment falls back to the store
    "initial_code",     # 1.5MB — served via /detail; attempt paths use the full row
    "resources",        # 4.4MB — precomputed into public_json at build time
    "manual_criteria",  # 0.6MB — review paths fetch the full row
    "review_rubric",    # 0.4MB
    "video_url",
    "source_path",
    "source_repository",
    "source_pack",
    "source_slug",
    "solution",
    "solutions",
)

def lite_task(task: dict) -> dict:
    """Return the slim in-heap copy of a task (metadata + stripped check_logic)."""
    out = {k: v for k, v in task.items() if k not in LITE_DROP_FIELDS}
    cl = out.get("check_logic")
    if isinstance(cl, dict) and ("cases" in cl or "hidden_cases" in cl):
        cl = dict(cl)
        if "cases" in cl:
            cl["case_count"] = len(cl["cases"] or [])
            del cl["cases"]
        if "hidden_cases" in cl:
            cl["hidden_case_count"] = len(cl["hidden_cases"] or [])
            del cl["hidden_cases"]
        out["check_logic"] = cl
    return out


def quiz_difficulty_level(raw, default: int = 2) -> int:
    """Normalize quiz difficulty from old numeric banks and newer labeled banks."""
    if raw is None:
        return default
    if isinstance(raw, bool):
        return default
    if isinstance(raw, (int, float)):
        return max(1, min(5, int(raw)))

    text = str(raw).strip().lower()
    if not text:
        return default
    try:
        return max(1, min(5, int(float(text))))
    except ValueError:
        pass

    label_map = {
        "beginner": 1,
        "easy": 2,
        "medium": 3,
        "hard": 4,
        "expert": 5,
        "d": 1,
        "c": 2,
        "b": 3,
        "a": 4,
        "s": 5,
    }
    if text in label_map:
        return label_map[text]
    for label, level in label_map.items():
        if len(label) > 1 and text.startswith(label):
            return level
    prefix_map = {
        "beg": 1,
        "eas": 2,
        "med": 3,
        "har": 4,
        "exp": 5,
    }
    for prefix, level in prefix_map.items():
        if text.startswith(prefix):
            return level
    return default


def merge_task_sources(curated: dict, legacy_tasks: list) -> dict:
    """Combine primary + legacy task files into the canonical bundle shape.
    Mirrors the merge previously done inline in main.load_tasks()."""
    curated_tasks = curated.get("tasks", []) if isinstance(curated, dict) else []
    return {
        "meta": curated.get("meta", {}) if isinstance(curated, dict) else {},
        "categories": curated.get("categories", []) if isinstance(curated, dict) else [],
        "tasks": (curated_tasks if isinstance(curated_tasks, list) else [])
        + (legacy_tasks if isinstance(legacy_tasks, list) else []),
    }
