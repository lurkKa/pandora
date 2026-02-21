#!/usr/bin/env python3
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
TASKS_FILE = BASE_DIR / "tasks.json"
LEGACY_FILE = BASE_DIR / "tasks_legacy.json"

ARCHIVED_TASK_ID_PREFIXES = (
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


def dedupe_resources(items):
    seen = set()
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        url = str(it.get("url") or "").strip()
        title = str(it.get("title") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({"title": title or url, "url": url})
    return out


DEFAULT_RESOURCES = {
    "python": {
        "docs": [{"title": "Python: tutorial (EN)", "url": "https://docs.python.org/3/tutorial/index.html"}],
        "videos": [{"title": "Python: основы (freeCodeCamp, EN)", "url": "https://www.youtube.com/watch?v=rfscVS0vtbw"}],
    },
    "javascript": {
        "docs": [{"title": "MDN: руководство по JavaScript (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/JavaScript/Guide"}],
        "videos": [{"title": "JavaScript: основы (freeCodeCamp, EN)", "url": "https://www.youtube.com/watch?v=PkZNo7MFNFg"}],
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
        "videos": [{"title": "Scratch Team: видео", "url": "https://www.youtube.com/@ScratchTeam/videos"}],
    },
}


def resources_for_task(task: dict) -> dict:
    category = str(task.get("category") or "").lower()
    explicit = task.get("resources") if isinstance(task.get("resources"), dict) else {}

    docs = []
    videos = []
    if isinstance(explicit.get("docs"), list):
        docs.extend(explicit.get("docs") or [])
    if isinstance(explicit.get("videos"), list):
        videos.extend(explicit.get("videos") or [])

    defaults = DEFAULT_RESOURCES.get(category) or {}
    docs.extend(defaults.get("docs") or [])
    videos.extend(defaults.get("videos") or [])

    text = " ".join(
        [
            str(task.get("title") or ""),
            str(task.get("story") or ""),
            str(task.get("description") or ""),
            str(task.get("initial_code") or ""),
        ]
    ).lower()

    # Concept-sensitive docs (best-effort).
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

    return {"docs": dedupe_resources(docs), "videos": dedupe_resources(videos)}


TITLE_OVERRIDES = {
    "fe_03_card": "Паспорт героя",
    "scr_01_move_cat": "Первые шаги кота",
    "scr_07_grow_giant": "Гигантский рост",
    "scr_21_switch_backdrop": "Переход между мирами",
    "scr_20_broadcast_msg": "Боевой сигнал",
    "scr_15_if_else": "Порог мастерства",
    "scr_22_list": "Свиток заклинаний",
}

EXT_STORY_VARIANTS = {
    "py_ext_s_": [
        "Архимаг проверяет точность ритуала: одна ошибка — и круг распадётся.",
        "Древний манускрипт требует ясной логики: перепутай шаг — и печать сорвётся.",
        "В башне магов тестируют твой разум — формула должна сойтись безупречно.",
        "Алхимический круг дрожит: закрепи вычисления, пока реагенты не вспыхнули.",
        "Врата откроются лишь при идеальной проверке — неверный ответ закрывает путь.",
        "Хранитель свитков ждёт доказательств: обработай данные аккуратно и строго.",
        "Кристалл памяти трескается от шума — оставь только верную структуру решения.",
        "Символы на рунах меняются: твоя функция должна держать форму при любых входах.",
        "Ритуал повторяется в цикле: удержи инварианты и не потеряй ни одной детали.",
        "Семь печатей требуют порядка: собери результат без лишних движений.",
        "В лаборатории времени нельзя ошибаться: вычисли точно и верни правильный итог.",
        "Совет архимагов смотрит молча: пусть логика будет железной, а код — чистым.",
    ],
    "js_ext_s_": [
        "Старшие маги проверяют логику: одно неверное условие — и заклинание сорвётся.",
        "Книга контрактов требует точности: обработай данные без двусмысленностей.",
        "Хронометр башни идёт вспять: синхронизируй вычисления и верни верный результат.",
        "В зеркальном зале истина одна: пусть функция выдержит любые входные данные.",
        "На совете гильдии ценят ясность: выражайся кодом чётко и предсказуемо.",
        "Механизм портала чувствителен: собери ответ без случайностей и побочных эффектов.",
        "Оракул просит доказательство: вычисли строго и верни структуру без искажений.",
        "Заклятие работает только при верных типах: будь внимателен к формату результата.",
        "Три печати требуют порядка: преобразуй данные без потерь и лишних шагов.",
        "Арена ошибок не прощает: проверь крайние случаи и удержи результат.",
        "Руны мерцают: составь решение так, чтобы оно было устойчивым и читаемым.",
        "Финальный экзамен мастеров: функция должна пройти проверку без компромиссов.",
    ],
    "fe_ext_s_": [
        "Панель командира должна оставаться читаемой: расставь акценты и удержи сетку.",
        "В бою интерфейс не имеет права дрожать: сделай layout устойчивым и чистым.",
        "Свет факелов меняется: обеспечь контраст и структуру с помощью переменных.",
        "На карте сражения важна сетка: выстрой блоки так, чтобы они не ломались.",
        "Склад артефактов растёт: подготовь адаптивное правило, чтобы всё влезало.",
        "Стражи требуют порядка: выровняй элементы и задай понятные отступы.",
        "Экран кристалла мал: перестрой интерфейс под узкую ширину без хаоса.",
        "Финальный щит UI: собери CSS так, чтобы он выдержал любой размер окна.",
    ],
    "scr_ext_s_": [
        "Финальная арена требует многоступенчатой логики и реакции на события.",
        "Турнир мастеров ждёт механики: события должны запускаться без задержек.",
        "Подземелье живёт таймерами: собери логику так, чтобы игра не развалилась.",
        "Страж арены проверяет условия: ветвления должны быть точными и понятными.",
        "Клонов становится больше: держи контроль над сценой и состоянием игры.",
        "Комбо-система требует ритма: события и переменные должны работать согласованно.",
        "Финальный бой: собери механику в цельный проект и проверь все сценарии.",
    ],
}


def apply_text_fixes(tasks):
    for t in tasks:
        tid = str(t.get("id") or "")
        if tid in TITLE_OVERRIDES:
            t["title"] = TITLE_OVERRIDES[tid]

    # Make ext S-pack stories less templated.
    for prefix, variants in EXT_STORY_VARIANTS.items():
        group = [t for t in tasks if str(t.get("id") or "").startswith(prefix)]
        group.sort(key=lambda x: str(x.get("id") or ""))
        for i, t in enumerate(group):
            if not variants:
                continue
            t["story"] = variants[i % len(variants)]


def assign_campaign(tasks):
    tier_to_act = {"D": 1, "C": 2, "B": 3, "A": 4, "S": 5}
    cat_to_chapter = {"python": 1, "javascript": 2, "frontend": 3, "scratch": 4}

    groups = defaultdict(list)
    for t in tasks:
        tier = str(t.get("tier") or "D").upper()
        cat = str(t.get("category") or "").lower()
        act = tier_to_act.get(tier, 1)
        chapter = cat_to_chapter.get(cat, 9)
        groups[(act, chapter)].append(t)

    for (act, chapter), items in groups.items():
        items.sort(key=lambda x: (int(x.get("xp") or 0), str(x.get("id") or "")))
        for idx, t in enumerate(items, start=1):
            cat = str(t.get("category") or "").lower()
            task_type = "side" if cat == "scratch" else "quest"
            t["campaign"] = {"act": act, "chapter": int(chapter), "order": int(idx), "type": task_type}
        # One boss per non-scratch chapter: last task.
        if chapter in (1, 2, 3) and items:
            items[-1]["campaign"]["type"] = "boss"

    # Optional: reorder tasks to follow the roadmap.
    tasks.sort(
        key=lambda t: (
            int((t.get("campaign") or {}).get("act") or 9),
            int((t.get("campaign") or {}).get("chapter") or 9),
            int((t.get("campaign") or {}).get("order") or 9999),
            str(t.get("id") or ""),
        )
    )


def main():
    if not TASKS_FILE.exists():
        raise SystemExit(f"tasks.json not found: {TASKS_FILE}")

    raw = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
    tasks = list(raw.get("tasks") or [])

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BASE_DIR / f"tasks_full_backup_{ts}.json"
    shutil.copy2(TASKS_FILE, backup_path)

    legacy_tasks = [t for t in tasks if is_archived_task_id(t.get("id"))]
    curated_tasks = [t for t in tasks if not is_archived_task_id(t.get("id"))]

    apply_text_fixes(curated_tasks)
    for t in curated_tasks:
        t["resources"] = resources_for_task(t)

    assign_campaign(curated_tasks)

    # Write curated tasks back to tasks.json
    raw["tasks"] = curated_tasks
    raw.setdefault("meta", {})
    raw["meta"]["version"] = str(raw["meta"].get("version") or "3.1")
    raw["meta"]["description"] = "PANDORA tasks (curated + roadmap + resources). Legacy packs moved to tasks_legacy.json."
    TASKS_FILE.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Preserve existing legacy archive (idempotent runs should never erase it).
    existing_legacy_tasks = []
    if LEGACY_FILE.exists():
        try:
            existing_legacy = json.loads(LEGACY_FILE.read_text(encoding="utf-8"))
            if isinstance(existing_legacy, dict):
                existing_legacy_tasks = existing_legacy.get("tasks", []) or []
        except Exception:
            existing_legacy_tasks = []

    legacy_by_id = {}
    for t in (existing_legacy_tasks if isinstance(existing_legacy_tasks, list) else []) + legacy_tasks:
        if not isinstance(t, dict):
            continue
        tid = str(t.get("id") or "")
        if not tid:
            continue
        legacy_by_id.setdefault(tid, t)
    combined_legacy_tasks = list(legacy_by_id.values())

    legacy_payload = {
        "meta": {
            "version": f"legacy-{ts}",
            "description": "Archived legacy packs extracted from tasks.json (kept for compatibility with old progress/homework).",
            "archived_prefixes": list(ARCHIVED_TASK_ID_PREFIXES),
        },
        "categories": raw.get("categories") or ["python", "javascript", "frontend", "scratch"],
        "tasks": combined_legacy_tasks,
    }
    LEGACY_FILE.write_text(json.dumps(legacy_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Backup:", backup_path.name)
    print("Curated tasks:", len(curated_tasks))
    print("Legacy tasks:", len(combined_legacy_tasks))
    print("Wrote:", TASKS_FILE.name, "and", LEGACY_FILE.name)


if __name__ == "__main__":
    main()
