#!/usr/bin/env python3
"""
Generate an additional curated pack: +200 tasks per category:
  - python
  - javascript
  - frontend
  - scratch

Deterministic & safe to re-run:
  - Removes previously generated tasks with prefixes:
      py_cur_, js_cur_, fe_cur_, scr_cur_
  - Re-generates exactly 200 per category.

Then run:
  python3 scripts/curate_tasks.py
to refresh `resources` and `campaign` ordering for all curated tasks.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

BASE_DIR = Path(__file__).resolve().parents[1]
TASKS_FILE = BASE_DIR / "tasks.json"
LEGACY_FILE = BASE_DIR / "tasks_legacy.json"

CUR_PREFIX = {
    "python": "py_cur_",
    "javascript": "js_cur_",
    "frontend": "fe_cur_",
    "scratch": "scr_cur_",
}

TIER_COUNTS = {"D": 40, "C": 60, "B": 60, "A": 30, "S": 10}

XP_RANGES: dict[str, dict[str, tuple[int, int]]] = {
    "python": {"D": (20, 25), "C": (55, 80), "B": (135, 180), "A": (245, 325), "S": (425, 550)},
    "javascript": {"D": (20, 25), "C": (55, 80), "B": (140, 175), "A": (245, 290), "S": (430, 490)},
    "frontend": {"D": (15, 20), "C": (45, 70), "B": (120, 165), "A": (225, 265), "S": (420, 475)},
    "scratch": {"D": (15, 20), "C": (50, 75), "B": (125, 160), "A": (215, 310), "S": (405, 485)},
}

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

TITLE_PREFIXES = ["Руна", "Свиток", "Кристалл", "Печать", "Карта", "Талисман", "Ключ", "Эликсир", "Знак", "Протокол"]
STORY_POOL = {
    "D": [
        "Первый шаг на пути героя — точность важнее скорости.",
        "Гильдия новичков выдаёт простое испытание, чтобы заклинание не сорвалось.",
        "Страж ворот проверяет основы: ответ должен быть прямым и ясным.",
        "Алхимик просит простую формулу, пока котёл не остыл.",
    ],
    "C": [
        "На развилке важен выбор: верни правильный результат для каждого случая.",
        "Страж арены проверяет ветвления — ошибся раз, и бой начнётся заново.",
        "Писарь каравана просит обработать записи и вернуть точный ответ.",
        "Механизм портала чувствителен к границам — проверь условия.",
    ],
    "B": [
        "Инвентарь растёт: нужна надёжная логика учёта и группировки.",
        "Разведчики принесли данные — отфильтруй и упорядочь аккуратно.",
        "Склад гильдии требует дисциплины: коллекции должны сходиться.",
        "На рынке всё решают данные — собери сводку без потерь.",
    ],
    "A": [
        "Совет магов требует алгоритм: крайние случаи решают исход ритуала.",
        "Кристалл памяти дрожит: обработай входные данные строго и точно.",
        "Портал защищён правилами: одна ошибка — и печать закрыта.",
        "В башне магов ценят эффективность: лишние шаги — риск провала.",
    ],
    "S": [
        "Финальное испытание: собери несколько правил в одну безупречную функцию.",
        "Архимаги проверяют мастерство: результат должен выдержать разные входы.",
        "Большая сводка для гильдии: обработай данные как настоящий мастер.",
        "В логове босса всё связано: одна ошибка рушит цепочку.",
    ],
}


def snake_to_camel(name: str) -> str:
    parts = [p for p in (name or "").split("_") if p]
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:]) if parts else "task"


def xp_for(category: str, tier: str, idx0: int, total: int) -> int:
    lo, hi = XP_RANGES[category][tier]
    if total <= 1:
        return hi
    frac = idx0 / (total - 1)
    return int(round(lo + (hi - lo) * frac))


def title_for(concept: str, i: int) -> str:
    return f"{TITLE_PREFIXES[i % len(TITLE_PREFIXES)]} {concept}"[:40]


def story_for(tier: str, i: int) -> str:
    pool = STORY_POOL.get(tier) or STORY_POOL["C"]
    return pool[i % len(pool)]


def py_lit(v: Any) -> str:
    return repr(v)


def js_lit(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False)


def py_placeholder(kind: str) -> str:
    return {"number": "0", "string": "''", "boolean": "False", "array": "[]", "object": "{}", "maybe": "None"}.get(kind, "None")


def js_placeholder(kind: str) -> str:
    return {"number": "0", "string": "''", "boolean": "false", "array": "[]", "object": "{}", "maybe": "null"}.get(kind, "null")


def py_initial(fn: str, params: list[str], kind: str, hint: str, imports: list[str] | None) -> str:
    head = ""
    if imports:
        head = "\n".join(imports).rstrip() + "\n\n"
    return f"{head}def {fn}({', '.join(params)}):\n    # {hint}\n    return {py_placeholder(kind)}\n"


def js_initial(fn: str, params: list[str], kind: str, hint: str) -> str:
    return f"function {fn}({', '.join(params)}) {{\n  // {hint}\n  return {js_placeholder(kind)};\n}}\n"


def build_cases(lang: str, fn: str, args_list: list[tuple[Any, ...]], solver: Callable[..., Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for args in args_list:
        args_s = ", ".join(py_lit(a) for a in args) if lang == "python" else ", ".join(js_lit(a) for a in args)
        out.append({"code": f"{fn}({args_s})", "expected": solver(*args)})
    return out


@dataclass(frozen=True)
class CodePattern:
    tier: str
    slug: str
    concept: str
    return_kind: str  # number|string|boolean|array|object|maybe
    params: list[str]
    rule_ru: str
    cases_args: list[tuple[Any, ...]]
    solve: Callable[..., Any]
    hidden_args: list[tuple[Any, ...]] | None = None
    py_imports: list[str] | None = None


def code_patterns() -> list[CodePattern]:
    """Returns exactly 200 patterns with tier distribution from TIER_COUNTS."""
    patterns: list[CodePattern] = []

    def add(p: CodePattern) -> None:
        patterns.append(p)

    # ===================== Tier D (40) =====================
    # 11 numeric
    add(CodePattern("D", "double_xp", "Двойной опыт", "number", ["x"], "верни x * 2", [(0,), (7,), (-3,)], lambda x: x * 2))
    add(CodePattern("D", "triple_ration", "Тройной паёк", "number", ["x"], "верни x * 3", [(1,), (5,), (-2,)], lambda x: x * 3))
    add(CodePattern("D", "square_power", "Квадрат силы", "number", ["p"], "верни p * p", [(0,), (6,), (-5,)], lambda p: p * p))
    add(CodePattern("D", "sum_two", "Сумма монет", "number", ["a", "b"], "верни a + b", [(2, 3), (-1, 1), (0, 0)], lambda a, b: a + b))
    add(CodePattern("D", "diff_damage", "Урон и броня", "number", ["attack", "armor"], "верни attack - armor", [(10, 4), (5, 9), (0, 0)], lambda attack, armor: attack - armor))
    add(CodePattern("D", "area_rect", "Площадь знамени", "number", ["w", "h"], "верни w * h", [(3, 5), (0, 10), (7, 7)], lambda w, h: w * h))
    add(CodePattern("D", "max_two", "Выбор большего", "number", ["a", "b"], "верни большее из a и b", [(3, 7), (-1, -5), (4, 4)], lambda a, b: a if a >= b else b))
    add(CodePattern("D", "min_two", "Выбор меньшего", "number", ["a", "b"], "верни меньшее из a и b", [(3, 7), (-1, -5), (4, 4)], lambda a, b: a if a <= b else b))
    add(CodePattern("D", "is_even", "Чётный знак", "boolean", ["n"], "верни True/true, если n чётное", [(4,), (7,), (0,)], lambda n: n % 2 == 0))
    add(CodePattern("D", "to_minutes", "Песок часов", "number", ["hours"], "переведи часы в минуты", [(0,), (1,), (3,)], lambda hours: hours * 60))
    add(CodePattern("D", "sum_three", "Три руны", "number", ["a", "b", "c"], "верни a + b + c", [(1, 2, 3), (-1, 0, 1), (10, 20, 30)], lambda a, b, c: a + b + c))

    # 12 strings
    add(CodePattern("D", "welcome_hero", "Приветствие героя", "string", ["name"], "верни строку: Приветствую, <name>!", [("Артур",), ("Мерлин",), ("",)], lambda name: f"Приветствую, {name}!"))
    add(CodePattern("D", "shout_spell", "Громкое заклинание", "string", ["s"], "верни s в верхнем регистре", [("hello",), ("Мир",), ("",)], lambda s: str(s).upper()))
    add(CodePattern("D", "whisper_spell", "Тихий шёпот", "string", ["s"], "верни s в нижнем регистре", [("HELLO",), ("МиР",), ("",)], lambda s: str(s).lower()))
    add(CodePattern("D", "first_rune", "Первая руна", "string", ["s"], "верни первый символ, иначе ''", [("abc",), ("Z",), ("",)], lambda s: s[0] if s else ""))
    add(CodePattern("D", "last_rune", "Последняя руна", "string", ["s"], "верни последний символ, иначе ''", [("abc",), ("Z",), ("",)], lambda s: s[-1] if s else ""))
    add(CodePattern("D", "wrap_brackets", "Скобочная печать", "string", ["s"], "верни '[' + s + ']'", [("руна",), ("",), ("OK",)], lambda s: f"[{s}]"))
    add(CodePattern("D", "add_exclaim", "Знак восклицания", "string", ["s"], "добавь '!' в конец", [("ура",), ("OK",), ("",)], lambda s: f"{s}!"))
    add(CodePattern("D", "repeat_chant", "Повтор гимна", "string", ["s", "n"], "повтори строку s n раз (n<=0→'')", [("ab", 3), ("x", 0), ("", 5)], lambda s, n: str(s) * max(0, int(n))))
    add(CodePattern("D", "join_words", "Сцепление слов", "string", ["a", "b"], "верни a + ' ' + b", [("Север", "ветер"), ("один", "два"), ("", "x")], lambda a, b: f"{a} {b}"))
    add(CodePattern("D", "replace_spaces", "Тропа без пробелов", "string", ["s"], "замени пробелы на '_'", [("a b",), (" no  way ",), ("",)], lambda s: str(s).replace(" ", "_")))
    add(CodePattern("D", "len_string", "Длина строки", "number", ["s"], "верни длину строки s", [("",), ("abc",), ("hello world",)], lambda s: len(str(s))))
    add(CodePattern("D", "is_empty", "Пустой свиток", "boolean", ["s"], "верни True/true, если s == ''", [("",), (" ",), ("abc",)], lambda s: s == ""))

    # 17 lists/misc
    add(CodePattern("D", "list_len", "Счёт предметов", "number", ["items"], "верни количество элементов", [([],), ([1, 2, 3],), (["a"],)], lambda items: len(items)))
    add(CodePattern("D", "first_item", "Первый трофей", "maybe", ["items"], "верни первый элемент, иначе null/None", [([],), ([7],), (["x", "y"],)], lambda items: items[0] if items else None))
    add(CodePattern("D", "last_item", "Последний трофей", "maybe", ["items"], "верни последний элемент, иначе null/None", [([],), ([7],), (["x", "y"],)], lambda items: items[-1] if items else None))
    add(CodePattern("D", "sum_list", "Сумма припасов", "number", ["nums"], "верни сумму списка (пустой→0)", [([],), ([1, 2, 3],), ([-1, 5, -4],)], lambda nums: sum(nums)))
    add(CodePattern("D", "max_list", "Самый ценный трофей", "maybe", ["nums"], "верни максимум или null/None", [([],), ([1, 5, 3],), ([-10, -2],)], lambda nums: max(nums) if nums else None))
    add(CodePattern("D", "min_list", "Самая низкая цена", "maybe", ["nums"], "верни минимум или null/None", [([],), ([1, 5, 3],), ([-10, -2],)], lambda nums: min(nums) if nums else None))
    add(CodePattern("D", "contains_item", "Проверка артефакта", "boolean", ["items", "item"], "верни True/true, если item есть в items", [(["a", "b"], "b"), ([1, 2, 3], 9), ([], "x")], lambda items, item: item in items))
    add(CodePattern("D", "take_first_n", "Снять вершину стопки", "array", ["items", "n"], "верни первые n элементов (n<=0→[])", [([], 3), ([1, 2, 3, 4], 2), ([7], 5)], lambda items, n: list(items[: max(0, int(n))])))
    add(CodePattern("D", "take_last_n", "Хвост каравана", "array", ["items", "n"], "верни последние n элементов (n<=0→[])", [([], 2), ([1, 2, 3, 4], 2), ([7], 5)], lambda items, n: list(items[-max(0, int(n)) :]) if int(n) > 0 else []))
    add(CodePattern("D", "merge_two_lists", "Сшивка свитков", "array", ["a", "b"], "верни новый список: a затем b", [([], []), ([1, 2], [3]), (["a"], [])], lambda a, b: list(a) + list(b)))
    add(CodePattern("D", "reverse_two", "Перестановка пары", "array", ["a", "b"], "верни [b, a]", [(1, 2), ("x", "y"), (None, 7)], lambda a, b: [b, a]))
    add(CodePattern("D", "sum_first_two", "Два первых зелья", "number", ["nums"], "верни сумму первых двух (если меньше — сумму имеющихся)", [([],), ([5],), ([5, 7, 9],)], lambda nums: sum(nums[:2])))
    add(CodePattern("D", "drop_first", "Сброс первого", "array", ["items"], "верни список без первого элемента", [([],), ([1],), ([1, 2, 3],)], lambda items: list(items[1:])))
    add(CodePattern("D", "drop_last", "Сброс последнего", "array", ["items"], "верни список без последнего элемента", [([],), ([1],), ([1, 2, 3],)], lambda items: list(items[:-1])))
    add(CodePattern("D", "count_true", "Счёт сигналов", "number", ["flags"], "посчитай истинные значения", [([],), ([True, False, True],), ([False, False],)], lambda flags: sum(1 for f in flags if bool(f))))
    add(CodePattern("D", "repeat_item", "Стопка камней", "array", ["item", "n"], "верни список из n одинаковых элементов (n<=0→[])", [("x", 3), (1, 0), (None, 2)], lambda item, n: [item] * max(0, int(n))))
    add(CodePattern("D", "bool_to_int", "Перевод флага", "number", ["flag"], "True→1 иначе 0", [(True,), (False,), (0,)], lambda flag: 1 if bool(flag) else 0))

    # ===================== Tier C (60) =====================
    # Conditionals (20)
    add(CodePattern("C", "clamp_hp", "Предел здоровья", "number", ["hp"], "ограничи hp диапазоном 0..100", [(-5,), (50,), (120,)], lambda hp: 0 if hp < 0 else 100 if hp > 100 else hp))
    add(CodePattern("C", "rarity_label", "Редкость трофея", "string", ["score"], "верни common (<10), rare (10..29) или epic (>=30)", [(0,), (10,), (35,)], lambda score: "common" if score < 10 else "rare" if score < 30 else "epic"))
    add(CodePattern("C", "is_between", "Страж границ", "boolean", ["x", "a", "b"], "верни True/true, если x в [a,b] (включая границы)", [(5, 1, 10), (1, 1, 10), (0, 1, 10)], lambda x, a, b: a <= x <= b))
    add(CodePattern("C", "apply_discount", "Скидка торговца", "number", ["price", "percent"], "цена после скидки percent (округляй вниз)", [(100, 15), (99, 50), (10, 0)], lambda price, percent: int(price * (100 - percent) // 100)))
    add(CodePattern("C", "choose_path", "Развилка", "string", ["is_raining"], "верни cave если дождь, иначе road", [(True,), (False,), (0,)], lambda is_raining: "cave" if bool(is_raining) else "road"))
    add(CodePattern("C", "spell_cost", "Цена заклинания", "number", ["level"], "5 если <=1; 10 если 2..4; иначе 20", [(1,), (3,), (7,)], lambda level: 5 if level <= 1 else 10 if level <= 4 else 20))
    add(CodePattern("C", "safe_subtract", "Безопасный вычет", "number", ["a", "b"], "верни a-b, но не меньше 0", [(10, 3), (5, 9), (0, 0)], lambda a, b: max(0, a - b)))
    add(CodePattern("C", "compare_levels", "Сравнение уровней", "string", ["a", "b"], "верни '<', '>' или '=' по сравнению a и b", [(1, 2), (2, 1), (5, 5)], lambda a, b: "<" if a < b else ">" if a > b else "="))
    add(CodePattern("C", "day_or_night", "День и ночь", "string", ["hour"], "night для 0..5 и 22..23, иначе day", [(0,), (12,), (23,)], lambda hour: "night" if (0 <= hour <= 5 or 22 <= hour <= 23) else "day"))
    add(CodePattern("C", "hp_status", "Статус героя", "string", ["hp"], "down если <=0; wounded если 1..30; иначе ok", [(0,), (10,), (31,)], lambda hp: "down" if hp <= 0 else "wounded" if hp <= 30 else "ok"))
    add(CodePattern("C", "mana_after_cast", "Остаток маны", "number", ["mana", "cost"], "верни mana-cost, но не меньше 0", [(10, 3), (5, 9), (0, 1)], lambda mana, cost: max(0, mana - cost)))
    add(CodePattern("C", "bonus_xp", "Бонус опыта", "number", ["streak"], "0 если 0; 10 если 1..2; 30 если 3..5; иначе 50", [(0,), (2,), (4,), (10,)], lambda streak: 0 if streak == 0 else 10 if streak <= 2 else 30 if streak <= 5 else 50))
    add(CodePattern("C", "can_enter_gate", "Пропуск у ворот", "boolean", ["level", "has_pass"], "войти можно, если level>=5 или есть пропуск", [(1, False), (5, False), (1, True)], lambda level, has_pass: level >= 5 or bool(has_pass)))
    add(CodePattern("C", "max_three", "Тройной выбор", "number", ["a", "b", "c"], "верни максимум из трёх", [(1, 2, 3), (3, 2, 1), (-1, -2, -3)], lambda a, b, c: max(a, b, c)))
    add(CodePattern("C", "min_three", "Тройной минимум", "number", ["a", "b", "c"], "верни минимум из трёх", [(1, 2, 3), (3, 2, 1), (-1, -2, -3)], lambda a, b, c: min(a, b, c)))
    add(CodePattern("C", "is_leap_year", "Високосный год", "boolean", ["year"], "високосный: делится на 400 или (на 4 и не на 100)", [(2000,), (1900,), (2024,)], lambda year: (year % 400 == 0) or (year % 4 == 0 and year % 100 != 0)))
    add(CodePattern("C", "triangle_possible", "Треугольная печать", "boolean", ["a", "b", "c"], "проверь, можно ли составить треугольник (a,b,c>0)", [(3, 4, 5), (1, 2, 3), (2, 2, 3)], lambda a, b, c: a > 0 and b > 0 and c > 0 and a + b > c and a + c > b and b + c > a))
    add(CodePattern("C", "sign_label", "Знак числа", "string", ["n"], "верни neg/zero/pos", [(-1,), (0,), (5,)], lambda n: "neg" if n < 0 else "pos" if n > 0 else "zero"))
    add(CodePattern("C", "cap_words_2", "Две заглавные", "string", ["s"], "сделай первые две буквы заглавными", [("",), ("a",), ("ab",), ("abc",)], lambda s: str(s).upper() if len(str(s)) < 2 else str(s)[:2].upper() + str(s)[2:]))
    add(CodePattern("C", "longer_word", "Длиннее слово", "string", ["a", "b"], "верни более длинную строку (если равны — a)", [("a", "bb"), ("xx", "y"), ("", "")], lambda a, b: a if len(str(a)) >= len(str(b)) else b))

    # Loops/counters (20)
    def _sum_1_to_n(n: int) -> int:
        return sum(range(1, n + 1)) if n > 0 else 0

    def _sum_until_zero(nums: list[int]) -> int:
        s = 0
        for x in nums:
            if x == 0:
                break
            s += x
        return s

    def _product_nonzero(nums: list[int]) -> int:
        prod = 1
        seen = False
        for x in nums:
            if x == 0:
                continue
            prod *= x
            seen = True
        return prod if seen else 1

    add(CodePattern("C", "sum_1_to_n", "Сумма до N", "number", ["n"], "верни сумму 1..n (n<=0→0)", [(0,), (1,), (5,)], lambda n: _sum_1_to_n(int(n))))
    add(CodePattern("C", "count_vowels", "Гласные руны", "number", ["s"], "посчитай a,e,i,o,u (регистр не важен)", [("aeiou",), ("HELLO",), ("",)], lambda s: sum(1 for ch in str(s).lower() if ch in "aeiou")))
    add(CodePattern("C", "count_ge", "Порог силы", "number", ["nums", "threshold"], "сколько чисел >= threshold", [([], 10), ([1, 10, 11], 10), ([-5, -1, 0], 0)], lambda nums, threshold: sum(1 for x in nums if x >= threshold)))
    add(CodePattern("C", "sum_positive", "Светлые кристаллы", "number", ["nums"], "сумма только положительных (>0)", [([],), ([1, -2, 3],), ([-1, -2],)], lambda nums: sum(x for x in nums if x > 0)))
    add(CodePattern("C", "find_first_even", "Первый чётный ключ", "maybe", ["nums"], "верни первое чётное или null/None", [([],), ([1, 3, 5],), ([1, 4, 6],)], lambda nums: next((x for x in nums if x % 2 == 0), None)))
    add(CodePattern("C", "count_word", "Слово в хрониках", "number", ["words", "target"], "сколько раз target встречается в words", [([], "a"), (["a", "b", "a"], "a"), (["A"], "a")], lambda words, target: sum(1 for w in words if w == target)))
    add(CodePattern("C", "range_list", "Шаги по тропе", "array", ["n"], "верни [1..n] (n<=0→[])", [(0,), (1,), (4,)], lambda n: list(range(1, int(n) + 1)) if int(n) > 0 else []))
    add(CodePattern("C", "countdown", "Обратный отсчёт", "array", ["n"], "верни [n..0] (n<0→[])", [(-1,), (0,), (3,)], lambda n: list(range(int(n), -1, -1)) if int(n) >= 0 else []))
    add(CodePattern("C", "sum_digits", "Печать цифр", "number", ["n"], "верни сумму цифр |n|", [(0,), (123,), (-405,)], lambda n: sum(int(ch) for ch in str(abs(int(n))))))
    add(CodePattern("C", "count_char", "Символ в руне", "number", ["s", "ch"], "сколько раз ch встречается в s", [("aaab", "a"), ("AaA", "a"), ("", "x")], lambda s, ch: str(s).count(str(ch))))
    add(CodePattern("C", "sum_until_zero", "Путь до камня", "number", ["nums"], "суммируй элементы до первого 0", [([],), ([1, 2, 0, 5],), ([0, 10],)], lambda nums: _sum_until_zero(nums)))
    add(CodePattern("C", "product_nonzero", "Умножение оберегов", "number", ["nums"], "произведение ненулевых (если нет — 1)", [([],), ([2, 0, 3],), ([0, 0],)], lambda nums: _product_nonzero(nums)))
    add(CodePattern("C", "count_changes", "Смена погоды", "number", ["items"], "сколько раз соседние элементы отличаются", [([],), ([1],), ([1, 1, 2, 2, 3],)], lambda items: sum(1 for i in range(1, len(items)) if items[i] != items[i - 1])))
    add(CodePattern("C", "sum_indexed", "Сумма по индексам", "number", ["nums"], "сумма элементов с чётными индексами", [([],), ([5],), ([1, 2, 3, 4, 5],)], lambda nums: sum(nums[::2])))
    add(CodePattern("C", "count_even", "Чётные камни", "number", ["nums"], "сколько чётных чисел в списке", [([],), ([1, 2, 3, 4],), ([7, 9],)], lambda nums: sum(1 for x in nums if x % 2 == 0)))
    add(CodePattern("C", "find_max", "Страж максимума", "maybe", ["nums"], "верни максимум или null/None", [([],), ([1, 2, 3],), ([-5, -2],)], lambda nums: max(nums) if nums else None))
    add(CodePattern("C", "find_min", "Страж минимума", "maybe", ["nums"], "верни минимум или null/None", [([],), ([1, 2, 3],), ([-5, -2],)], lambda nums: min(nums) if nums else None))
    add(CodePattern("C", "average_floor", "Среднее разведки", "number", ["nums"], "среднее вниз (пустой→0)", [([],), ([1, 2, 3],), ([1, 2],)], lambda nums: (sum(nums) // len(nums) if nums else 0)))
    add(CodePattern("C", "count_prefix", "Счёт префикса", "number", ["words", "prefix"], "сколько слов начинается с prefix", [([], "a"), (["axe", "apple", "box"], "a"), (["A"], "a")], lambda words, prefix: sum(1 for w in words if str(w).startswith(str(prefix)))))
    add(CodePattern("C", "sum_if", "Сумма по условию", "number", ["nums", "d"], "сумма чисел, делящихся на d (d!=0)", [([], 2), ([1, 2, 3, 4, 6], 2), ([9, 10, 12], 3)], lambda nums, d: sum(x for x in nums if x % int(d) == 0)))

    # Strings (10)
    add(CodePattern("C", "trim_edges", "Края свитка", "string", ["s"], "убери пробелы по краям", [("  hi  ",), ("nope",), ("   ",)], lambda s: str(s).strip()))
    add(CodePattern("C", "reverse_string", "Зеркало строки", "string", ["s"], "разверни строку наоборот", [("abc",), ("",), ("a",)], lambda s: str(s)[::-1]))
    add(CodePattern("C", "starts_with", "Начало пути", "boolean", ["s", "prefix"], "True/true если s начинается с prefix", [("hello", "he"), ("hello", "ha"), ("", "")], lambda s, prefix: str(s).startswith(str(prefix))))
    add(CodePattern("C", "ends_with", "Конец пути", "boolean", ["s", "suffix"], "True/true если s заканчивается на suffix", [("hello", "lo"), ("hello", "lO"), ("", "")], lambda s, suffix: str(s).endswith(str(suffix))))
    add(CodePattern("C", "repeat_words", "Эхо фразы", "string", ["word", "n"], "повтори word n раз через пробел (n<=0→'')", [("go", 3), ("x", 1), ("x", 0)], lambda word, n: " ".join([str(word)] * max(0, int(n)))))
    add(CodePattern("C", "swap_case_simple", "Смена регистра", "string", ["s"], "поменяй регистр латинских букв", [("aA!",), ("Hello",), ("",)], lambda s: "".join((ch.lower() if "A" <= ch <= "Z" else ch.upper() if "a" <= ch <= "z" else ch) for ch in str(s))))
    add(CodePattern("C", "count_words", "Счёт слов", "number", ["s"], "посчитай слова по пробелам (лишние пробелы игнорируй)", [("",), ("one two",), ("  a   b  ",)], lambda s: len([w for w in str(s).strip().split(" ") if w])))
    add(CodePattern("C", "initials", "Инициалы", "string", ["first", "last"], "верни строку вида F.L.", [("Ada", "Lovelace"), ("", "King"), ("A", "")], lambda first, last: f"{(str(first)[:1] or '')}.{(str(last)[:1] or '')}."))
    add(CodePattern("C", "pad_left", "Выравнивание слева", "string", ["s", "width", "ch"], "дополни слева символом ch до длины width", [("7", 3, "0"), ("abc", 2, "x"), ("", 2, "_")], lambda s, width, ch: (str(s) if len(str(s)) >= int(width) else str(ch) * (int(width) - len(str(s))) + str(s))))
    add(CodePattern("C", "strip_chars", "Снятие печатей", "string", ["s", "ch"], "удали ch по краям строки", [("___a__", "_"), ("xxhellox", "x"), ("abc", "x")], lambda s, ch: str(s).lstrip(str(ch)).rstrip(str(ch))))

    # Lists (10)
    add(CodePattern("C", "filter_even", "Чётные камни", "array", ["nums"], "верни только чётные числа", [([],), ([1, 2, 3, 4],), ([7, 9],)], lambda nums: [x for x in nums if x % 2 == 0]))
    add(CodePattern("C", "filter_ge", "Отбор по порогу", "array", ["nums", "threshold"], "верни числа >= threshold", [([], 3), ([1, 3, 2, 5], 3), ([10], 11)], lambda nums, threshold: [x for x in nums if x >= threshold]))
    add(CodePattern("C", "map_square", "Квадраты рун", "array", ["nums"], "возведи все числа в квадрат", [([],), ([1, 2, 3],), ([-2],)], lambda nums: [x * x for x in nums]))
    add(CodePattern("C", "drop_zeros", "Убрать пустые камни", "array", ["nums"], "удали все нули", [([],), ([0, 1, 0, 2],), ([0, 0],)], lambda nums: [x for x in nums if x != 0]))
    add(CodePattern("C", "take_until", "Остановиться у знака", "array", ["items", "stop"], "верни элементы до первого stop (stop не включай)", [([], 0), ([1, 2, 0, 3], 0), ([1, 2, 3], 9)], lambda items, stop: list(items[: items.index(stop)]) if stop in items else list(items)))
    add(CodePattern("C", "count_eq", "Сколько одинаковых", "number", ["items", "value"], "сколько элементов == value", [([], 1), ([1, 2, 1, 1], 1), (["1", 1], 1)], lambda items, value: sum(1 for x in items if x == value)))
    add(CodePattern("C", "sum_abs", "Сумма модулей", "number", ["nums"], "сумма |x| для всех x", [([],), ([1, -2, 3],), ([-5],)], lambda nums: sum(abs(x) for x in nums)))
    add(CodePattern("C", "all_positive", "Светлая колонна", "boolean", ["nums"], "True/true если все числа > 0 (пустой→True)", [([],), ([1, 2, 3],), ([1, 0],)], lambda nums: all(x > 0 for x in nums)))
    add(CodePattern("C", "any_negative", "Тень в ряду", "boolean", ["nums"], "True/true если есть отрицательное", [([],), ([1, 2],), ([0, -1, 5],)], lambda nums: any(x < 0 for x in nums)))
    add(CodePattern("C", "sum_pairs", "Сложить попарно", "array", ["nums"], "верни суммы пар (последний без пары — как есть)", [([],), ([1, 2, 3, 4],), ([5, 6, 7],)], lambda nums: [sum(nums[i : i + 2]) for i in range(0, len(nums), 2)]))

    # ===================== Tier B (60) =====================
    def _dedupe_keep_order(items):
        seen = set()
        out = []
        for x in items:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    def _chunk_list(items, size):
        size = int(size)
        return [list(items[i : i + size]) for i in range(0, len(items), size)] if size > 0 else []

    def _rotate_k(items, k):
        if not items:
            return []
        k = int(k) % len(items)
        return list(items[-k:] + items[:-k]) if k else list(items)

    def _flatten_one(items):
        out = []
        for sub in items:
            out.extend(list(sub))
        return out

    def _intersect_unique(a, b):
        return sorted(set(a) & set(b))

    def _difference_unique(a, b):
        return sorted(set(a) - set(b))

    def _count_runs(items):
        if not items:
            return 0
        runs = 1
        for i in range(1, len(items)):
            if items[i] != items[i - 1]:
                runs += 1
        return runs

    def _compress_runs(items):
        if not items:
            return []
        out = []
        cur = items[0]
        n = 1
        for x in items[1:]:
            if x == cur:
                n += 1
            else:
                out.append([cur, n])
                cur = x
                n = 1
        out.append([cur, n])
        return out

    def _expand_runs(pairs):
        out = []
        for v, n in pairs:
            out.extend([v] * int(n))
        return out

    def _sliding_sum_3(nums):
        return [nums[i] + nums[i + 1] + nums[i + 2] for i in range(len(nums) - 2)] if len(nums) >= 3 else []

    def _pairwise_max(nums):
        out = []
        i = 0
        while i < len(nums):
            if i + 1 < len(nums):
                out.append(nums[i] if nums[i] >= nums[i + 1] else nums[i + 1])
                i += 2
            else:
                out.append(nums[i])
                i += 1
        return out

    def _prefix_sums(nums):
        out = []
        s = 0
        for x in nums:
            s += x
            out.append(s)
        return out

    def _suffix_sums(nums):
        out = [0] * len(nums)
        s = 0
        for i in range(len(nums) - 1, -1, -1):
            s += nums[i]
            out[i] = s
        return out

    def _stable_partition_even(nums):
        ev = [x for x in nums if x % 2 == 0]
        od = [x for x in nums if x % 2 != 0]
        return ev + od

    def _unique_by_lower(words):
        seen = set()
        out = []
        for w in words:
            key = str(w).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(w)
        return out

    def _argsort(nums):
        return [i for i, _ in sorted(enumerate(nums), key=lambda p2: (p2[1], p2[0]))]

    def _median_int(nums):
        if not nums:
            return None
        s = sorted(nums)
        return s[(len(s) - 1) // 2]

    # B list/array (20)
    add(CodePattern("B", "dedupe_keep_order", "Снятие дубликатов", "array", ["items"], "удали дубликаты, сохрани порядок", [([],), ([1, 2, 1, 3, 2],), (["a", "a", "b"],)], _dedupe_keep_order))
    add(CodePattern("B", "chunk_list", "Партии груза", "array", ["items", "size"], "разбей список на чанки size (size>0)", [([], 2), ([1, 2, 3, 4, 5], 2), ([1, 2, 3], 3)], _chunk_list))
    add(CodePattern("B", "rotate_k", "Круговой марш", "array", ["items", "k"], "циклически сдвинь вправо на k", [([], 3), ([1, 2, 3, 4], 1), ([1, 2, 3, 4], 6)], _rotate_k))
    add(CodePattern("B", "flatten_one", "Развернуть свёртки", "array", ["items"], "разверни список списков на один уровень", [([],), ([[1, 2], [3], [4, 5]],), ([[], [1]],)], _flatten_one))
    add(CodePattern("B", "unique_sorted", "Уникальные по порядку", "array", ["nums"], "верни уникальные числа по возрастанию", [([],), ([3, 1, 3, 2],), ([-1, -1, 0],)], lambda nums: sorted(set(nums))))
    add(CodePattern("B", "intersect_unique", "Пересечение отрядов", "array", ["a", "b"], "уникальные общие элементы (по возрастанию)", [([], [1]), ([1, 2, 2, 3], [2, 3, 3, 4]), ([5], [5, 5])], _intersect_unique))
    add(CodePattern("B", "difference_unique", "Разность списков", "array", ["a", "b"], "уникальные элементы a, которых нет в b (по возрастанию)", [([], []), ([1, 2, 2, 3], [2]), ([5], [5, 6])], _difference_unique))
    add(CodePattern("B", "count_runs", "Серии в журнале", "number", ["items"], "количество серий одинаковых подряд элементов", [([],), ([1],), ([1, 1, 2, 2, 3],)], _count_runs))
    add(CodePattern("B", "compress_runs", "Сжатие серий", "array", ["items"], "сожми серии как [value,count]", [([],), (["a", "a", "b"],), ([1, 2, 2, 2],)], _compress_runs))
    add(CodePattern("B", "expand_runs", "Раскрыть серии", "array", ["pairs"], "разверни [value,count] обратно в список", [([],), ([["a", 2], ["b", 1]],), ([[1, 1], [2, 3]],)], _expand_runs))
    add(CodePattern("B", "sliding_sum_3", "Три шага подряд", "array", ["nums"], "суммы окон длины 3 (если <3 → [])", [([],), ([1, 2],), ([1, 2, 3, 4],)], _sliding_sum_3))
    add(CodePattern("B", "pairwise_max", "Попарный максимум", "array", ["nums"], "максимум попарно (последний без пары — как есть)", [([],), ([1, 9, 2, 3],), ([5],)], _pairwise_max))
    add(CodePattern("B", "prefix_sums", "Накопленные суммы", "array", ["nums"], "верни префиксные суммы", [([],), ([1, 2, 3],), ([-1, 1],)], _prefix_sums))
    add(CodePattern("B", "suffix_sums", "Хвостовые суммы", "array", ["nums"], "верни суффиксные суммы", [([],), ([1, 2, 3],), ([-1, 1],)], _suffix_sums))
    add(CodePattern("B", "stable_partition_even", "Сначала чётные", "array", ["nums"], "чётные вперёд, порядок сохрани", [([],), ([1, 2, 3, 4],), ([2, 2, 1],)], _stable_partition_even))
    add(CodePattern("B", "unique_by_lower", "Уникальность без регистра", "array", ["words"], "удали повторы, сравнивая lower()", [([],), (["A", "a", "B"],), (["Hi", "HI", "hi"],)], _unique_by_lower))
    add(CodePattern("B", "argsort", "Порядок индексов", "array", ["nums"], "индексы в порядке сортировки (при равенстве — меньший индекс раньше)", [([],), ([3, 1, 2],), ([5, 5, 1],)], _argsort))
    add(CodePattern("B", "top_k", "Лучшие K", "array", ["nums", "k"], "верни k наибольших по убыванию (k<=0→[])", [([], 3), ([5, 1, 9, 2], 2), ([1, 2, 3], 0)], lambda nums, k: sorted(nums, reverse=True)[: max(0, int(k))]))
    add(CodePattern("B", "bottom_k", "Нижние K", "array", ["nums", "k"], "верни k наименьших по возрастанию (k<=0→[])", [([], 3), ([5, 1, 9, 2], 2), ([1, 2, 3], 0)], lambda nums, k: sorted(nums)[: max(0, int(k))]))
    add(CodePattern("B", "median_int", "Медиана разведки", "maybe", ["nums"], "медиана: для чётной длины — левый из двух средних; пусто→null/None", [([],), ([2, 1, 3],), ([4, 1, 2, 3],)], _median_int))

    # B objects (20)
    def _count_items(items):
        out: dict[str, int] = {}
        for x in items:
            k = str(x)
            out[k] = out.get(k, 0) + 1
        return out

    def _merge_counts(a, b):
        out = dict(a)
        for k, v in b.items():
            out[k] = int(out.get(k, 0)) + int(v)
        return out

    def _invert_map(d):
        out = {}
        for k, v in d.items():
            out[str(v)] = str(k)
        return out

    def _group_by_first(words):
        out: dict[str, list[str]] = {}
        for w in words:
            w = str(w)
            if not w:
                continue
            out.setdefault(w[0], []).append(w)
        return out

    def _group_by_length(words):
        out: dict[str, list[str]] = {}
        for w in words:
            w = str(w)
            out.setdefault(str(len(w)), []).append(w)
        return out

    def _sum_by_key(items, key):
        s = 0
        for it in items:
            if isinstance(it, dict) and key in it and isinstance(it[key], (int, float)):
                s += it[key]
        return s

    def _pick_keys(obj, keys):
        return {k: obj[k] for k in keys if k in obj}

    def _omit_keys(obj, keys):
        ks = set(keys)
        return {k: v for k, v in obj.items() if k not in ks}

    def _rename_key(obj, old_key, new_key):
        out = dict(obj)
        if old_key in out:
            out[new_key] = out.pop(old_key)
        return out

    def _values_sorted(obj):
        return [obj[k] for k in sorted(obj.keys())]

    def _key_with_max(obj):
        if not obj:
            return None
        return max(obj.items(), key=lambda kv: kv[1])[0]

    def _normalize_counts(obj, cap):
        cap = int(cap)
        return {k: (v if int(v) <= cap else cap) for k, v in obj.items()}

    def _histogram_bins(nums):
        out = {"neg": 0, "zero": 0, "pos": 0}
        for x in nums:
            if x < 0:
                out["neg"] += 1
            elif x == 0:
                out["zero"] += 1
            else:
                out["pos"] += 1
        return out

    def _index_by(items, key):
        out = {}
        for it in items:
            if isinstance(it, dict) and key in it:
                out[str(it[key])] = it
        return out

    def _group_sum_by(items, key, value_key):
        out: dict[str, int] = {}
        for it in items:
            if not isinstance(it, dict) or key not in it:
                continue
            k = str(it[key])
            v = it.get(value_key, 0)
            out[k] = out.get(k, 0) + (int(v) if isinstance(v, (int, float)) else 0)
        return out

    def _pluck(items, key):
        return [it[key] for it in items if isinstance(it, dict) and key in it]

    def _object_from_pairs(pairs):
        out = {}
        for k, v in pairs:
            out[str(k)] = v
        return out

    def _pairs_from_object(obj):
        return [f"{k}={obj[k]}" for k in sorted(obj.keys())]

    def _merge_objects(a, b):
        out = dict(a)
        out.update(b)
        return out

    def _filter_object_gt(obj, threshold):
        threshold = int(threshold)
        return {k: v for k, v in obj.items() if isinstance(v, (int, float)) and v > threshold}

    add(CodePattern("B", "count_items", "Счёт добычи", "object", ["items"], "объект частот (ключи — строки)", [([],), (["a", "b", "a"],), (["x", "x", "x"],)], _count_items))
    add(CodePattern("B", "merge_counts", "Слияние отчётов", "object", ["a", "b"], "объедини частоты и сложи значения", [({}, {"x": 1}), ({"a": 2}, {"a": 3, "b": 1}), ({"k": 1}, {})], _merge_counts))
    add(CodePattern("B", "invert_map", "Обратная печать", "object", ["d"], "поменяй местами ключи и значения (повторы — последнее)", [({},), ({"a": "x", "b": "y"},), ({"a": "x", "b": "x"},)], _invert_map))
    add(CodePattern("B", "group_by_first", "Группы по первой руне", "object", ["words"], "сгруппируй слова по первой букве (пустые игнорируй)", [([],), (["apple", "axe", "book"],), (["", "a"],)], _group_by_first))
    add(CodePattern("B", "group_by_length", "Группы по длине", "object", ["words"], "сгруппируй слова по длине (ключ — строка)", [([],), (["a", "bb", "c"],), ([""],)], _group_by_length))
    add(CodePattern("B", "sum_by_key", "Сумма по ключу", "number", ["items", "key"], "сумма числовых значений key (нет ключа → пропусти)", [([], "v"), ([{"v": 2}, {"v": 3}, {}], "v"), ([{"x": 1}], "v")], _sum_by_key))
    add(CodePattern("B", "pick_keys", "Выбор ключей", "object", ["obj", "keys"], "оставь только ключи из keys, которые есть в obj", [({}, []), ({"a": 1, "b": 2}, ["b", "c"]), ({"x": 0}, ["x"])], _pick_keys))
    add(CodePattern("B", "omit_keys", "Скрыть ключи", "object", ["obj", "keys"], "удали ключи из keys", [({}, ["a"]), ({"a": 1, "b": 2}, ["a"]), ({"x": 0}, [])], _omit_keys))
    add(CodePattern("B", "rename_key", "Переименование ключа", "object", ["obj", "old_key", "new_key"], "переименуй old_key в new_key, если он есть", [({}, "a", "b"), ({"a": 1, "x": 2}, "a", "b"), ({"a": 1}, "z", "b")], _rename_key))
    add(CodePattern("B", "values_sorted", "Список значений", "array", ["obj"], "значения по ключам в алфавитном порядке", [({},), ({"b": 2, "a": 1},), ({"z": 0},)], _values_sorted))
    add(CodePattern("B", "key_with_max", "Главный ключ", "maybe", ["obj"], "ключ с максимальным числом (пусто→null/None)", [({},), ({"a": 1, "b": 3, "c": 2},), ({"x": 0},)], _key_with_max))
    add(CodePattern("B", "normalize_counts", "Нормализация счёта", "object", ["obj", "cap"], "ограничи значения сверху cap", [({}, 2), ({"a": 1, "b": 5}, 3), ({"x": 0}, 0)], _normalize_counts))
    add(CodePattern("B", "histogram_bins", "Корзины частот", "object", ["nums"], "верни {neg,zero,pos} по списку", [([],), ([-1, 0, 1, 2],), ([0, 0],)], _histogram_bins))
    add(CodePattern("B", "index_by", "Индекс по ключу", "object", ["items", "key"], "построй {valueOfKey: item} (value приводится к строке)", [([], "id"), ([{"id": "a", "v": 1}, {"id": "b", "v": 2}], "id"), ([{"v": 1}, {"id": "a", "v": 9}], "id")], _index_by))
    add(CodePattern("B", "group_sum_by", "Суммы по группе", "object", ["items", "key", "value_key"], "группируй по key и суммируй value_key", [([], "t", "v"), ([{"t": "a", "v": 2}, {"t": "a", "v": 3}], "t", "v"), ([{"t": "b", "v": 1}, {"t": "a"}], "t", "v")], _group_sum_by))
    add(CodePattern("B", "pluck", "Извлечь значения", "array", ["items", "key"], "верни список значений key для объектов, где ключ есть", [([], "x"), ([{"x": 1}, {"x": 2}, {}], "x"), ([{"y": 1}], "x")], _pluck))
    add(CodePattern("B", "object_from_pairs", "Собрать из пар", "object", ["pairs"], "преврати [[k,v],...] в объект (ключи — строки)", [([],), ([["a", 1], ["b", 2]],), ([[1, "x"]],)], _object_from_pairs))
    add(CodePattern("B", "pairs_from_object", "Пары из объекта", "array", ["obj"], "верни строки k=v по алфавиту ключей", [({},), ({"b": 2, "a": 1},), ({"x": 0},)], _pairs_from_object))
    add(CodePattern("B", "merge_objects", "Слияние объектов", "object", ["a", "b"], "ключи из b переопределяют a", [({}, {}), ({"a": 1}, {"a": 2, "b": 1}), ({"x": 0}, {})], _merge_objects))
    add(CodePattern("B", "filter_object_gt", "Фильтр значений", "object", ["obj", "threshold"], "оставь только числовые значения > threshold", [({}, 1), ({"a": 1, "b": 2}, 1), ({"x": 0}, 0)], _filter_object_gt))

    # B parsing/sorting (20)
    def _parse_kv(s):
        s = str(s)
        if not s:
            return {}
        out = {}
        for part in s.split(";"):
            if not part:
                continue
            k, v = part.split("=", 1)
            out[k] = int(v)
        return out

    def _parse_csv_line(s):
        s = str(s)
        return [] if s == "" else [p.strip() for p in s.split(",")]

    def _parse_coords(s):
        a, b = [p.strip() for p in str(s).split(",", 1)]
        return {"x": int(a), "y": int(b)}

    def _parse_bool(s):
        s = str(s).strip().lower()
        return s in ("true", "1")

    def _format_coords(x, y):
        return f"x={int(x)};y={int(y)}"

    def _parse_int_list(s):
        s = str(s).strip()
        return [] if not s else [int(x) for x in s.split()]

    def _join_int_list(nums):
        return ",".join(str(int(x)) for x in nums)

    def _parse_query(s):
        s = str(s)
        if not s:
            return {}
        out = {}
        for part in s.split("&"):
            k, v = part.split("=", 1)
            out[k] = v
        return out

    def _format_table(obj):
        return "" if not obj else "\n".join(f"{k}:{obj[k]}" for k in sorted(obj.keys()))

    def _parse_lines(s):
        out = []
        for line in str(s).split("\n"):
            if line.strip() == "":
                continue
            out.append(line)
        return out

    def _normalize_newlines(s):
        return str(s).replace("\r\n", "\n")

    def _split_path(path):
        return [p for p in str(path).split("/") if p]

    def _join_path(parts):
        return "/".join([p for p in (str(x) for x in parts) if p])

    def _parse_scoreboard(lines):
        out = {}
        for line in lines:
            name, score = str(line).split("=", 1)
            out[name] = int(score)
        return out

    def _format_scoreboard(obj):
        return [f"{k}={obj[k]}" for k in sorted(obj.keys())]

    def _sort_numbers_text(s):
        return sorted(_parse_int_list(s))

    def _sorted_by_len(words):
        return sorted([str(w) for w in words], key=lambda w: (len(w), w))

    def _nth_largest(nums, n):
        n = int(n)
        if n <= 0 or n > len(nums):
            return None
        return sorted(nums, reverse=True)[n - 1]

    def _kth_smallest(nums, k):
        k = int(k)
        if k <= 0 or k > len(nums):
            return None
        return sorted(nums)[k - 1]

    def _sort_by_two_keys(items):
        return sorted(items, key=lambda it: (-int(it.get("level", 0)), str(it.get("name", ""))))

    add(CodePattern("B", "parse_kv", "Ключ=значение", "object", ["s"], "разбери a=1;b=2 в объект (значения — int)", [("",), ("a=1;b=2",), ("x=0",)], _parse_kv))
    add(CodePattern("B", "parse_csv_line", "CSV-строка", "array", ["s"], "раздели по ',' и обрежь пробелы (пусто→[])", [("",), ("a, b, c",), ("  x  ,y",)], _parse_csv_line))
    add(CodePattern("B", "parse_coords", "Координаты карты", "object", ["s"], "разбери 'x,y' в {x:int,y:int}", [("0,0",), ("10,-2",), (" 3 , 4 ",)], _parse_coords))
    add(CodePattern("B", "parse_bool", "Истина и ложь", "boolean", ["s"], "True/true для 'true' и '1' (регистр игнорируй)", [("true",), ("1",), ("False",), ("yes",)], _parse_bool))
    add(CodePattern("B", "format_coords", "Печать координат", "string", ["x", "y"], "верни строку x=<x>;y=<y>", [(0, 0), (10, -2), (3, 4)], _format_coords))
    add(CodePattern("B", "parse_int_list", "Список чисел", "array", ["s"], "разбери числа из строки через пробел (пусто→[])", [("",), ("1 2 3",), ("  -1   0  5 ",)], _parse_int_list))
    add(CodePattern("B", "join_int_list", "Склей числа", "string", ["nums"], "соедини числа через запятую без пробелов", [([],), ([1, 2, 3],), ([-1, 0, 5],)], _join_int_list))
    add(CodePattern("B", "parse_query", "Параметры портала", "object", ["s"], "разбери a=1&b=2 в объект (значения — строки)", [("",), ("a=1&b=2",), ("x=",)], _parse_query))
    add(CodePattern("B", "format_table", "Таблица отчёта", "string", ["obj"], "верни строки key:value по алфавиту ключей через \\n", [({},), ({"b": 2, "a": 1},), ({"x": 0},)], _format_table))
    add(CodePattern("B", "parse_lines", "Строки журнала", "array", ["s"], "разбей по \\n и убери пустые строки", [("",), ("a\\n\\n b\\n",), ("x\\ny",)], _parse_lines))
    add(CodePattern("B", "normalize_newlines", "Единый перенос", "string", ["s"], "замени \\r\\n на \\n", [("a\\r\\nb",), ("x\\n",), ("\\r\\n",)], _normalize_newlines))
    add(CodePattern("B", "split_path", "Путь каравана", "array", ["path"], "раздели по '/' и убери пустые сегменты", [("",), ("/a/b/",), ("a//b",)], _split_path))
    add(CodePattern("B", "join_path", "Собрать путь", "string", ["parts"], "склей непустые сегменты через '/'", [([],), (["a", "b"],), (["a", "", "b"],)], _join_path))
    add(CodePattern("B", "parse_scoreboard", "Табло арены", "object", ["lines"], "разбери строки Name=10 в объект", [([],), (["Ada=10", "Bob=7"],), (["X=0"],)], _parse_scoreboard))
    add(CodePattern("B", "format_scoreboard", "Печать табло", "array", ["obj"], "верни строки name=score по алфавиту", [({},), ({"Bob": 7, "Ada": 10},), ({"X": 0},)], _format_scoreboard))
    add(CodePattern("B", "sort_numbers_text", "Сортировка чисел", "array", ["s"], "вытащи числа (через пробел) и отсортируй", [("",), ("3 1 2",), ("-1 0 5",)], _sort_numbers_text))
    add(CodePattern("B", "sorted_by_len", "Слова по длине", "array", ["words"], "сортируй по длине, при равенстве — по алфавиту", [([],), (["bb", "a", "aa"],), (["b", "a"],)], _sorted_by_len))
    add(CodePattern("B", "nth_largest", "N-й трофей", "maybe", ["nums", "n"], "n-й по величине (1→максимум), иначе null/None", [([], 1), ([5, 1, 9, 2], 1), ([5, 1, 9, 2], 3), ([5], 2)], _nth_largest))
    add(CodePattern("B", "kth_smallest", "K-й по малости", "maybe", ["nums", "k"], "k-й по возрастанию (1→минимум), иначе null/None", [([], 1), ([5, 1, 9, 2], 1), ([5, 1, 9, 2], 4), ([5], 2)], _kth_smallest))
    add(CodePattern("B", "sort_by_two_keys", "Сортировка записей", "array", ["items"], "отсортируй {name,level}: level по убыванию, name по возрастанию", [([],), ([{"name": "Bob", "level": 2}, {"name": "Ann", "level": 3}, {"name": "Ada", "level": 3}],)], _sort_by_two_keys))

    # ===================== Tier A (30) =====================
    # Regex (10)
    add(CodePattern("A", "extract_numbers", "Числа в тексте", "array", ["s"], "вытащи все целые числа (включая отрицательные)", [("no numbers",), ("a12 b-3 c0",), ("-1-2",)], lambda s: [int(x) for x in re.findall(r"-?\\d+", str(s))], py_imports=["import re"]))
    add(CodePattern("A", "is_valid_hex", "Hex-печать", "boolean", ["s"], "True/true если строка — hex (0-9 a-f) и не пустая", [("",), ("0F",), ("xz",)], lambda s: bool(re.fullmatch(r"[0-9a-fA-F]+", str(s) or "")), py_imports=["import re"]))
    add(CodePattern("A", "extract_tags", "Метки хроник", "array", ["s"], "верни список #тегов вида #word (латиница/цифры/_)", [("no tags",), ("#one and #two",), ("mix#bad #ok_1",)], lambda s: re.findall(r"#[A-Za-z0-9_]+", str(s)), py_imports=["import re"]))
    add(CodePattern("A", "normalize_phone", "Номер связного", "string", ["s"], "удали всё кроме цифр", [("",), ("+1 (234) 567-89",), ("00-11",)], lambda s: "".join(re.findall(r"\\d", str(s))), py_imports=["import re"]))
    add(CodePattern("A", "count_words_regex", "Слова по рунам", "number", ["s"], "посчитай слова (\\w+)", [("",), ("one two",), ("a_b,c",)], lambda s: len(re.findall(r"\\w+", str(s))), py_imports=["import re"]))
    add(CodePattern("A", "mask_digits", "Маска цифр", "string", ["s"], "замени все цифры на '#'", [("a1b2",), ("123",), ("",)], lambda s: re.sub(r"\\d", "#", str(s)), py_imports=["import re"]))
    add(CodePattern("A", "extract_domain", "Домен письма", "string", ["email"], "часть строки после '@' (если нет — '')", [("a@b.com",), ("nope",), ("x@y",)], lambda email: (str(email).split("@", 1)[1] if "@" in str(email) else "")))
    add(CodePattern("A", "is_strong_password", "Страж пароля", "boolean", ["pw"], "len>=8 и есть буква и цифра", [("abc",), ("abcd1234",), ("abcdefgh",), ("12345678",)], lambda pw: (len(str(pw)) >= 8 and bool(re.search(r"[A-Za-z]", str(pw))) and bool(re.search(r"\\d", str(pw)))), py_imports=["import re"]))
    add(CodePattern("A", "split_camel", "Распад камеля", "string", ["s"], "mySpellPower → my spell power", [("mySpellPower",), ("ABC",), ("",)], lambda s: re.sub(r"(?<!^)([A-Z])", r" \\1", str(s)).lower(), py_imports=["import re"]))
    add(CodePattern("A", "slugify_simple", "Путь-слизняк", "string", ["s"], "lower; пробелы→-; убрать всё кроме a-z0-9-", [("Hello World!",), ("  A  B  ",), ("",)], lambda s: re.sub(r"[^a-z0-9-]", "", re.sub(r"\\s", "-", str(s).strip().lower())), py_imports=["import re"]))

    # Algorithms (10)
    def _valid_brackets(s: str) -> bool:
        st = []
        pairs = {")": "(", "]": "[", "}": "{"}
        for ch in str(s):
            if ch in "([{":
                st.append(ch)
            elif ch in ")]}":
                if not st or st[-1] != pairs[ch]:
                    return False
                st.pop()
        return not st

    def _rle_encode(s: str) -> str:
        s = str(s)
        if not s:
            return ""
        out = []
        cur = s[0]
        n = 1
        for ch in s[1:]:
            if ch == cur:
                n += 1
            else:
                out.append(f"{cur}{n}")
                cur = ch
                n = 1
        out.append(f"{cur}{n}")
        return "".join(out)

    def _rle_decode(s: str) -> str:
        s = str(s)
        if not s:
            return ""
        out = []
        i = 0
        while i < len(s):
            ch = s[i]
            i += 1
            j = i
            while j < len(s) and s[j].isdigit():
                j += 1
            n = int(s[i:j] or "1")
            out.append(ch * n)
            i = j
        return "".join(out)

    def _longest_unique_len(s: str) -> int:
        s = str(s)
        last = {}
        best = 0
        start = 0
        for i, ch in enumerate(s):
            if ch in last and last[ch] >= start:
                start = last[ch] + 1
            last[ch] = i
            best = max(best, i - start + 1)
        return best

    def _two_sum_indices(nums, target):
        seen = {}
        for i, x in enumerate(nums):
            need = target - x
            if need in seen:
                return [seen[need], i]
            if x not in seen:
                seen[x] = i
        return []

    def _binary_search(nums, x):
        lo, hi = 0, len(nums) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if nums[mid] == x:
                return mid
            if nums[mid] < x:
                lo = mid + 1
            else:
                hi = mid - 1
        return -1

    def _is_anagram(a, b):
        def norm(s):
            return sorted([ch.lower() for ch in str(s) if ch != " "])
        return norm(a) == norm(b)

    def _palindrome_clean(s):
        s2 = re.sub(r"[^A-Za-z0-9]+", "", str(s)).lower()
        return s2 == s2[::-1]

    def _min_window_sum_3(nums):
        if len(nums) < 3:
            return None
        best = None
        for i in range(len(nums) - 2):
            s = nums[i] + nums[i + 1] + nums[i + 2]
            best = s if best is None else min(best, s)
        return best

    def _balanced_parentheses_only(s):
        bal = 0
        for ch in str(s):
            if ch == "(":
                bal += 1
            elif ch == ")":
                bal -= 1
                if bal < 0:
                    return False
        return bal == 0

    add(CodePattern("A", "valid_brackets", "Скобочный страж", "boolean", ["s"], "проверь корректность скобок ()[]{}", [("",), ("([{}])",), ("([)]",), ("((",)], _valid_brackets))
    add(CodePattern("A", "rle_encode", "Рунное сжатие", "string", ["s"], "RLE: aaabbc → a3b2c1", [("",), ("aaabbc",), ("abc",)], _rle_encode))
    add(CodePattern("A", "rle_decode", "Распаковка рун", "string", ["s"], "RLE-decode: a3b2c1 → aaabbc", [("",), ("a3b2c1",), ("x1",)], _rle_decode))
    add(CodePattern("A", "longest_unique_len", "Самая чистая тропа", "number", ["s"], "длина подстроки без повторов", [("abcabcbb",), ("bbbbb",), ("pwwkew",), ("",)], _longest_unique_len))
    add(CodePattern("A", "two_sum_indices", "Два ключа", "array", ["nums", "target"], "индексы пары с суммой target (если нет — [])", [([], 9), ([2, 7, 11, 15], 9), ([3, 2, 4], 6), ([1, 2, 3], 7)], _two_sum_indices))
    add(CodePattern("A", "binary_search", "Бинарный поиск", "number", ["nums", "x"], "индекс x в отсортированном списке или -1", [([], 1), ([1, 3, 5, 7, 9], 5), ([1, 3, 5, 7, 9], 4)], _binary_search))
    add(CodePattern("A", "is_anagram", "Анаграммная печать", "boolean", ["a", "b"], "анаграммы: игнорируй пробелы и регистр", [("listen", "silent"), ("A b", "ba"), ("ab", "a")], _is_anagram))
    add(CodePattern("A", "palindrome_clean", "Чистый палиндром", "boolean", ["s"], "проверь палиндром: игнорируй пробелы/знаки и регистр", [("A man, a plan, a canal: Panama",), ("race a car",), ("",)], _palindrome_clean, py_imports=["import re"]))
    add(CodePattern("A", "min_window_sum_3", "Три шага и минимум", "maybe", ["nums"], "минимальная сумма подряд идущих троек (если <3 — null/None)", [([],), ([1, 2],), ([1, 2, 3, 4],), ([5, -1, 2, 0],)], _min_window_sum_3))
    add(CodePattern("A", "balanced_parentheses_only", "Круглая печать", "boolean", ["s"], "баланс круглых скобок () (прочее игнорируй)", [("",), ("(a)(b)",), ("(()",), (")(",)], _balanced_parentheses_only))

    # Recursion/math (10)
    def _factorial(n):
        n = int(n)
        out = 1
        for i in range(2, n + 1):
            out *= i
        return out

    def _fibonacci(n):
        n = int(n)
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        return a

    def _sum_nested(items):
        if isinstance(items, (int, float)):
            return int(items)
        s = 0
        for x in items:
            s += _sum_nested(x)
        return s

    def _depth_nested(items):
        if isinstance(items, (int, float)):
            return 0
        if not items:
            return 1
        return 1 + max(_depth_nested(x) for x in items)

    def _flatten_nested(items):
        if isinstance(items, (int, float)):
            return [int(items)]
        out = []
        for x in items:
            out.extend(_flatten_nested(x))
        return out

    def _pow_fast(a, n):
        a = int(a)
        n = int(n)
        res = 1
        base = a
        exp = n
        while exp > 0:
            if exp & 1:
                res *= base
            base *= base
            exp >>= 1
        return res

    def _gcd(a, b):
        a, b = abs(int(a)), abs(int(b))
        while b:
            a, b = b, a % b
        return a

    def _lcm(a, b):
        a, b = abs(int(a)), abs(int(b))
        if a == 0 or b == 0:
            return 0
        return a // _gcd(a, b) * b

    def _is_prime(n):
        n = int(n)
        if n < 2:
            return False
        if n % 2 == 0:
            return n == 2
        d = 3
        while d * d <= n:
            if n % d == 0:
                return False
            d += 2
        return True

    add(CodePattern("A", "factorial", "Факториал стража", "number", ["n"], "верни n! для n>=0", [(0,), (1,), (5,)], _factorial))
    add(CodePattern("A", "fibonacci", "Фибоначчи руин", "number", ["n"], "fib(0)=0 fib(1)=1", [(0,), (1,), (10,)], _fibonacci))
    add(CodePattern("A", "sum_nested", "Сумма вложений", "number", ["items"], "сумма всех чисел во вложенных списках", [([],), ([1, [2, [3]], 4],), ([[[]]],)], _sum_nested))
    add(CodePattern("A", "depth_nested", "Глубина пещеры", "number", ["items"], "максимальная глубина: число→0, пустой список→1", [([],), ([1, 2],), ([1, [2, [3]]],)], _depth_nested))
    add(CodePattern("A", "flatten_nested", "Плоская карта", "array", ["items"], "разверни вложенные списки любой глубины", [([],), ([1, [2, [3, 4], 5], 6],), ([[[]]],)], _flatten_nested))
    add(CodePattern("A", "pow_fast", "Быстрое возведение", "number", ["a", "n"], "верни a**n для n>=0 (быстро)", [(2, 0), (2, 10), (3, 5)], _pow_fast))
    add(CodePattern("A", "gcd", "НОД печатей", "number", ["a", "b"], "НОД двух целых (неотрицательный)", [(54, 24), (0, 7), (7, 0)], _gcd))
    add(CodePattern("A", "lcm", "НОК каравана", "number", ["a", "b"], "НОК двух целых (если одно 0 — 0)", [(4, 6), (0, 7), (21, 6)], _lcm))
    add(CodePattern("A", "is_prime", "Простое число", "boolean", ["n"], "True/true если n — простое (n>=0)", [(0,), (1,), (2,), (17,), (18,)], _is_prime))
    add(CodePattern("A", "count_paths_grid_2x2", "Тропы решётки", "number", [], "количество путей на сетке 2x2 вправо/вниз", [tuple()], lambda: 6))

    # ===================== Tier S (10) =====================
    def _loot_report(items):
        total = 0
        rare = 0
        for it in items:
            total += int(it.get("value", 0))
            if it.get("rarity") in ("rare", "epic"):
                rare += 1
        return {"total_value": total, "rare_count": rare}

    def _spell_log_stats(lines):
        damages = []
        for line in lines:
            try:
                _, dmg = str(line).split(":", 1)
                damages.append(int(dmg))
            except Exception:
                continue
        return {"count": len(damages), "total_damage": sum(damages), "max_damage": (max(damages) if damages else 0)}

    def _craftable_recipes(recipes, inv):
        out = []
        for name, reqs in recipes.items():
            ok = True
            for item, need in reqs.items():
                if int(inv.get(item, 0)) < int(need):
                    ok = False
                    break
            if ok:
                out.append(name)
        return sorted(out)

    def _travel_budget(gold, costs):
        spent = sum(int(x) for x in costs)
        left = max(0, int(gold) - spent)
        return {"spent": spent, "left": left}

    def _normalize_inventory(items):
        out: dict[str, int] = {}
        for s in items:
            key = str(s).strip().lower()
            if not key:
                continue
            out[key] = out.get(key, 0) + 1
        return out

    def _parse_and_filter_scores(s, threshold):
        nums = _parse_int_list(s)
        threshold = int(threshold)
        return sorted([x for x in nums if x >= threshold], reverse=True)

    def _quest_chain(next_map, start):
        seen = set()
        path = []
        cur = start
        while True:
            path.append(cur)
            if cur in seen:
                break
            seen.add(cur)
            nxt = next_map.get(cur, None) if isinstance(next_map, dict) else None
            if nxt is None:
                break
            cur = nxt
        return path

    def _merge_sorted(a, b):
        i = j = 0
        out = []
        while i < len(a) and j < len(b):
            if a[i] <= b[j]:
                out.append(a[i])
                i += 1
            else:
                out.append(b[j])
                j += 1
        out.extend(a[i:])
        out.extend(b[j:])
        return out

    def _compress_text_report(lines):
        return _rle_encode("\n".join(str(x) for x in lines))

    def _schedule_potions(orders):
        out: dict[str, list[str]] = {}
        for o in orders:
            day = str(o.get("day"))
            out.setdefault(day, []).append(str(o.get("potion")))
        return out

    add(CodePattern("S", "loot_report", "Отчёт о добыче", "object", ["items"], "верни {total_value, rare_count} для списка {value,rarity}", [([],), ([{"name": "potion", "value": 5, "rarity": "common"}],), ([{"name": "ring", "value": 50, "rarity": "rare"}, {"name": "gem", "value": 100, "rarity": "epic"}],)], _loot_report, hidden_args=[([{"name": "x", "value": 0, "rarity": "rare"}],)]))
    add(CodePattern("S", "spell_log_stats", "Статистика заклинаний", "object", ["lines"], "верни {count,total_damage,max_damage} для строк name:damage", [([],), (["fire:10"],), (["ice:3", "fire:10", "ice:7"],)], _spell_log_stats, hidden_args=[(["x:0"],)]))
    add(CodePattern("S", "craftable_recipes", "Книга ремесла", "array", ["recipes", "inv"], "верни крафтабельные рецепты (по алфавиту)", [({}, {}), ({"potion": {"herb": 2}}, {"herb": 2}), ({"potion": {"herb": 2}, "bomb": {"herb": 1, "ore": 1}}, {"herb": 2, "ore": 0})], _craftable_recipes, hidden_args=[({"x": {"a": 1}}, {"a": 2})]))
    add(CodePattern("S", "travel_budget", "Бюджет похода", "object", ["gold", "costs"], "верни {spent,left}, left>=0", [(10, []), (10, [3, 4]), (5, [10])], _travel_budget, hidden_args=[(0, [1, 2, 3])]))
    add(CodePattern("S", "normalize_inventory", "Нормализация инвентаря", "object", ["items"], "частоты: lower+trim, пустые игнорируй", [([],), (["", "Sword", "sword", "shield"],), (["POTION"],)], _normalize_inventory, hidden_args=[(["  "],)]))
    add(CodePattern("S", "parse_and_filter_scores", "Судейский протокол", "array", ["s", "threshold"], "парс чисел, >=threshold, сортировка по убыванию", [("", 10), ("5 10 15 10", 10), ("-1 0 1", 0)], _parse_and_filter_scores, hidden_args=[("9 9 9", 10)]))
    add(CodePattern("S", "quest_chain", "Цепочка квестов", "array", ["next_map", "start"], "иди по next_map до null/None или повторения (включая повтор)", [({}, "a"), ({"a": "b", "b": None}, "a"), ({"a": "b", "b": "a"}, "a")], _quest_chain, hidden_args=[({"x": "x"}, "x")]))
    add(CodePattern("S", "merge_sorted", "Слияние караванов", "array", ["a", "b"], "слей два отсортированных списка", [([], []), ([1, 3, 5], [2, 4, 6]), ([1, 1], [1])], _merge_sorted, hidden_args=[([0], [])]))
    add(CodePattern("S", "compress_text_report", "Сжатый отчёт", "string", ["lines"], "склей через \\n и сделай RLE (символ+счётчик)", [([],), (["aa", "bb"],), (["a"],)], _compress_text_report, hidden_args=[([""],)]))
    add(CodePattern("S", "schedule_potions", "Расписание зелий", "object", ["orders"], "сгруппируй {day,potion} → {day:[...]}", [([],), ([{"day": 1, "potion": "heal"}, {"day": 1, "potion": "mana"}, {"day": 2, "potion": "heal"}],)], _schedule_potions, hidden_args=[([{"day": 0, "potion": "x"}],)]))

    # ===================== Validation =====================
    seen = set()
    by_tier = {t: 0 for t in TIER_COUNTS}
    for pat in patterns:
        if pat.slug in seen:
            raise SystemExit(f"Duplicate slug: {pat.slug}")
        seen.add(pat.slug)
        by_tier[pat.tier] = by_tier.get(pat.tier, 0) + 1
    if sum(by_tier.values()) != sum(TIER_COUNTS.values()):
        raise SystemExit(f"Code patterns total {sum(by_tier.values())} != {sum(TIER_COUNTS.values())}")
    for tier, need in TIER_COUNTS.items():
        if by_tier.get(tier, 0) != need:
            raise SystemExit(f"Code patterns tier {tier} has {by_tier.get(tier,0)} != {need}")
    return patterns


def frontend_specs() -> list[dict[str, Any]]:
    """Returns 200 frontend specs (tier distribution from TIER_COUNTS)."""
    specs: list[dict[str, Any]] = []

    def add(tier: str, slug: str, concept: str, description: str, initial_code: str, cases: list[dict[str, Any]]) -> None:
        specs.append({"tier": tier, "slug": slug, "concept": concept, "description": description, "initial_code": initial_code, "cases": cases})

    def page(html: str, css: str = "") -> str:
        return (
            "<!-- Работай только в этом файле -->\n"
            "<style>\n"
            f"{css.rstrip()}\n"
            "</style>\n\n"
            f"{html.rstrip()}\n"
        )

    # ---- D (40) ----
    d_templates = [
        ("title", "Заголовок", "Добавь `h1#title` с текстом `Гильдия`.", [{"type": "selector_exists", "expected": "#title"}, {"type": "text_contains", "expected": "Гильдия"}]),
        ("btn", "Кнопка", "Добавь `button#start` с текстом `В путь`.", [{"type": "selector_exists", "expected": "#start"}, {"type": "text_contains", "expected": "В путь"}]),
        ("card", "Карточка", "Добавь `div.card`.", [{"type": "selector_exists", "expected": ".card"}]),
        ("nav", "Навигация", "Добавь `nav#nav`.", [{"type": "selector_exists", "expected": "#nav"}, {"type": "selector_exists", "expected": "nav"}]),
        ("list", "Список", "Добавь `ul.inventory` и хотя бы один `li`.", [{"type": "selector_exists", "expected": ".inventory"}, {"type": "selector_exists", "expected": "li"}]),
        ("img", "Изображение", "Добавь `img` с `alt`.", [{"type": "selector_exists", "expected": "img"}, {"type": "content_regex", "expected": r"alt\\s*=\\s*['\\\"]"}]),
        ("form", "Форма", "Добавь `form#apply` и `input`.", [{"type": "selector_exists", "expected": "#apply"}, {"type": "selector_exists", "expected": "input"}]),
        ("footer", "Подпись", "Добавь `footer` с символом `©`.", [{"type": "selector_exists", "expected": "footer"}, {"type": "text_contains", "expected": "©"}]),
        ("badge", "Бейдж", "Добавь `span.badge` с текстом `Rare`.", [{"type": "selector_exists", "expected": ".badge"}, {"type": "text_contains", "expected": "Rare"}]),
        ("section", "Секция", "Добавь `section#lore` и внутри `p`.", [{"type": "selector_exists", "expected": "#lore"}, {"type": "selector_exists", "expected": "p"}]),
        ("article", "Статья", "Добавь `article.news`.", [{"type": "selector_exists", "expected": ".news"}, {"type": "selector_exists", "expected": "article"}]),
        ("aside", "Подсказка", "Добавь `aside.tip`.", [{"type": "selector_exists", "expected": ".tip"}, {"type": "selector_exists", "expected": "aside"}]),
        ("hr", "Разделитель", "Добавь `hr`.", [{"type": "selector_exists", "expected": "hr"}]),
        ("code", "Тег code", "Добавь `code` с текстом `HP`.", [{"type": "selector_exists", "expected": "code"}, {"type": "text_contains", "expected": "HP"}]),
        ("strong", "Акцент", "Добавь `strong`.", [{"type": "selector_exists", "expected": "strong"}]),
        ("em", "Эмфаза", "Добавь `em`.", [{"type": "selector_exists", "expected": "em"}]),
        ("table", "Таблица", "Добавь `table#stats`.", [{"type": "selector_exists", "expected": "#stats"}, {"type": "selector_exists", "expected": "table"}]),
        ("blockquote", "Цитата", "Добавь `blockquote`.", [{"type": "selector_exists", "expected": "blockquote"}]),
        ("progress", "Прогресс", "Добавь `div#progress` и `div#bar` внутри.", [{"type": "selector_exists", "expected": "#progress"}, {"type": "selector_exists", "expected": "#bar"}]),
        ("dialog", "Диалог", "Добавь `div.dialog`.", [{"type": "selector_exists", "expected": ".dialog"}]),
    ]
    base_d = page("<div class=\"app\">\n  <!-- TODO -->\n</div>")
    for i in range(TIER_COUNTS["D"]):
        base, concept, desc, cases = d_templates[i % len(d_templates)]
        add("D", f"d_{i+1:03d}_{base}", concept, desc, base_d, cases)

    # ---- C (60): CSS basics ----
    c_rules = [
        (".card", "padding", "16px", "Отступы", "Сделай `.card { padding: 16px; }`."),
        (".card", "border-radius", "12px", "Скругление", "Сделай `.card { border-radius: 12px; }`."),
        (".card", "border", "1px solid", "Рамка", "Сделай `.card { border: 1px solid ... }`."),
        (".title", "font-size", "24px", "Размер текста", "Сделай `.title { font-size: 24px; }`."),
        (".muted", "opacity", "0.7", "Прозрачность", "Сделай `.muted { opacity: 0.7; }`."),
        (".btn", "cursor", "pointer", "Курсор", "Сделай `.btn { cursor: pointer; }`."),
        (".btn", "padding", "10px 16px", "Отступы кнопки", "Сделай `.btn { padding: 10px 16px; }`."),
        (".badge", "background", "#222", "Фон бейджа", "Сделай `.badge { background: #222; }`."),
        (".badge", "color", "#fff", "Цвет бейджа", "Сделай `.badge { color: #fff; }`."),
        (".panel", "box-shadow", "0 2px 10px", "Тень", "Сделай `.panel { box-shadow: 0 2px 10px ... }`."),
        (".panel", "background", "#f5f5f5", "Фон панели", "Сделай `.panel { background: #f5f5f5; }`."),
        (".container", "max-width", "720px", "Ширина", "Сделай `.container { max-width: 720px; }`."),
        (".container", "margin", "24px auto", "Центрирование", "Сделай `.container { margin: 24px auto; }`."),
        (".pill", "border-radius", "999px", "Капсула", "Сделай `.pill { border-radius: 999px; }`."),
        (".pill", "display", "inline-block", "Inline-block", "Сделай `.pill { display: inline-block; }`."),
        (".card", "background", "#fff", "Белый фон", "Сделай `.card { background: #fff; }`."),
        (".title", "letter-spacing", "1px", "Интервал", "Сделай `.title { letter-spacing: 1px; }`."),
        (".list", "list-style", "none", "Без маркеров", "Сделай `.list { list-style: none; }`."),
        (".list", "padding", "0", "Без padding", "Сделай `.list { padding: 0; }`."),
        (".card", "box-shadow", "0 8px 24px", "Тень карточки", "Сделай `.card { box-shadow: 0 8px 24px ... }`."),
    ]
    base_c = page(
        "<div class=\"container\">\n"
        "  <div class=\"panel\">\n"
        "    <div class=\"card\">\n"
        "      <span class=\"badge\">Rare</span>\n"
        "      <h2 class=\"title\">Паспорт</h2>\n"
        "      <p class=\"muted\">...</p>\n"
        "      <button class=\"btn\">OK</button>\n"
        "      <ul class=\"list\"><li>1</li></ul>\n"
        "      <span class=\"pill\">pill</span>\n"
        "    </div>\n"
        "  </div>\n"
        "</div>\n",
        ".container{ }\n.panel{ }\n.card{ }\n.badge{ }\n.title{ }\n.muted{ }\n.btn{ }\n.list{ }\n.pill{ }\n",
    )
    for i in range(TIER_COUNTS["C"]):
        sel, prop, val, concept, instruction = c_rules[i % len(c_rules)]
        add(
            "C",
            f"c_{i+1:03d}_{prop.replace('-', '_')}",
            concept,
            instruction,
            base_c,
            [{"type": "selector_exists", "expected": sel}, {"type": "css_property", "expected": {"selector": sel, "property": prop, "value": val}}],
        )

    # ---- B (60): layout ----
    b_rules = [
        (".row", "display", "flex", "Flex", "Сделай `.row { display: flex; }`."),
        (".row", "gap", "12px", "Gap", "Сделай `.row { gap: 12px; }`."),
        (".row", "justify-content", "space-between", "Разнести", "Сделай `.row { justify-content: space-between; }`."),
        (".row", "align-items", "center", "Центр", "Сделай `.row { align-items: center; }`."),
        (".grid", "display", "grid", "Grid", "Сделай `.grid { display: grid; }`."),
        (".grid", "grid-template-columns", "repeat(3, 1fr)", "3 колонки", "Сделай `.grid { grid-template-columns: repeat(3, 1fr); }`."),
        (".grid", "gap", "16px", "Grid gap", "Сделай `.grid { gap: 16px; }`."),
        (".center", "display", "flex", "Центрирование", "Сделай `.center { display: flex; }`."),
        (".center", "justify-content", "center", "Центр X", "Сделай `.center { justify-content: center; }`."),
        (".center", "align-items", "center", "Центр Y", "Сделай `.center { align-items: center; }`."),
        (".wrap", "display", "flex", "Wrap flex", "Сделай `.wrap { display: flex; }`."),
        (".wrap", "flex-wrap", "wrap", "Flex wrap", "Сделай `.wrap { flex-wrap: wrap; }`."),
        (".card", "display", "grid", "Card grid", "Сделай `.card { display: grid; }`."),
        (".card", "grid-template-columns", "80px 1fr", "2 колонки", "Сделай `.card { grid-template-columns: 80px 1fr; }`."),
        (".stack", "display", "grid", "Stack", "Сделай `.stack { display: grid; }`."),
        (".stack", "gap", "10px", "Stack gap", "Сделай `.stack { gap: 10px; }`."),
        (".grid", "place-items", "center", "Place", "Сделай `.grid { place-items: center; }`."),
        (".row", "flex-direction", "column", "Колонка", "Сделай `.row { flex-direction: column; }`."),
        (".row", "align-items", "stretch", "Stretch", "Сделай `.row { align-items: stretch; }`."),
        (".grid", "grid-auto-rows", "minmax(60px, auto)", "Авто-строки", "Добавь `.grid { grid-auto-rows: minmax(60px, auto); }`."),
    ]
    base_b = page(
        "<div class=\"row\"><div class=\"chip\">A</div><div class=\"chip\">B</div><div class=\"chip\">C</div></div>\n"
        "<div class=\"grid\"><div class=\"tile\">1</div><div class=\"tile\">2</div><div class=\"tile\">3</div></div>\n"
        "<div class=\"center\"><div class=\"orb\">●</div></div>\n"
        "<div class=\"wrap\"><div class=\"chip\">X</div><div class=\"chip\">Y</div><div class=\"chip\">Z</div></div>\n"
        "<div class=\"stack\"><div class=\"tile\">one</div><div class=\"tile\">two</div></div>\n"
        "<div class=\"card\"><div class=\"avatar\"></div><div class=\"meta\">Hero</div></div>\n",
        ".row{ }\n.grid{ }\n.center{ }\n.wrap{ }\n.stack{ }\n.card{ }\n"
        ".chip{padding:8px 12px;border:1px solid #ccc;border-radius:999px;}\n"
        ".tile{padding:16px;border:1px dashed #bbb;}\n"
        ".avatar{width:64px;height:64px;border-radius:12px;background:#ddd;}\n"
        ".meta{opacity:.7;}\n",
    )
    for i in range(TIER_COUNTS["B"]):
        sel, prop, val, concept, instruction = b_rules[i % len(b_rules)]
        add(
            "B",
            f"b_{i+1:03d}_{prop.replace('-', '_')}",
            concept,
            instruction,
            base_b,
            [{"type": "selector_exists", "expected": sel}, {"type": "css_property", "expected": {"selector": sel, "property": prop, "value": val}}],
        )

    # ---- A (30): advanced ----
    a_templates = [
        ("vars", "Переменные", "Объяви `--primary` в `:root` со значением `#6a5acd`.", page("<div class=\"card\">var</div>", ":root{ /* TODO */ }\n.card{ color: var(--primary); }\n"), [{"type": "css_property", "expected": {"selector": ":root", "property": "--primary", "value": "#6a5acd"}}]),
        ("media", "Медиа", "Добавь `@media (max-width: 600px)` (любой стиль внутри).", page("<div class=\"panel\">panel</div>", "/* TODO */\n"), [{"type": "content_regex", "expected": r"@media\\s*\\(\\s*max-width\\s*:\\s*600px\\s*\\)"}]),
        ("keyframes", "Анимация", "Добавь `@keyframes float`.", page("<div class=\"orb\">●</div>", "/* TODO */\n.orb{animation:float 2s infinite;}\n"), [{"type": "content_regex", "expected": r"@keyframes\\s+float"}]),
        ("hover", "Hover", "Добавь правило `.btn:hover { ... }`.", page("<button class=\"btn\">H</button>", "/* TODO */\n"), [{"type": "content_regex", "expected": r"\\.btn\\s*:\\s*hover\\s*\\{"}]),
        ("focus", "Focus", "Добавь правило `input:focus { ... }`.", page("<input />", "/* TODO */\n"), [{"type": "content_regex", "expected": r"input\\s*:\\s*focus\\s*\\{"}]),
        ("sticky", "Sticky", "Сделай `.header { position: sticky; top: 0; }`.", page("<div class=\"header\">H</div><p>...</p>", ".header{ }\n"), [{"type": "css_property", "expected": {"selector": ".header", "property": "position", "value": "sticky"}}, {"type": "css_property", "expected": {"selector": ".header", "property": "top", "value": "0"}}]),
        ("transition", "Transition", "Добавь `transition:` в CSS.", page("<button class=\"btn\">T</button>", ".btn{ /* TODO */ }\n"), [{"type": "content_regex", "expected": r"transition\\s*:"}]),
        ("calc", "Calc", "Используй `calc(` в CSS.", page("<div class=\"panel\">C</div>", ".panel{ /* TODO */ }\n"), [{"type": "content_regex", "expected": r"calc\\("}]),
        ("clamp", "Clamp", "Используй `clamp(` в CSS.", page("<h2 class=\"title\">X</h2>", ".title{ /* TODO */ }\n"), [{"type": "content_regex", "expected": r"clamp\\("}]),
        ("aspect", "Aspect-ratio", "Установи `.avatar { aspect-ratio: 1 / 1; }`.", page("<div class=\"avatar\"></div>", ".avatar{ }\n"), [{"type": "css_property", "expected": {"selector": ".avatar", "property": "aspect-ratio", "value": "1 / 1"}}]),
        ("rem", "rem", "Установи `.title { font-size: 1.5rem; }`.", page("<h2 class=\"title\">R</h2>", ".title{ }\n"), [{"type": "css_property", "expected": {"selector": ".title", "property": "font-size", "value": "1.5rem"}}]),
        ("font", "font-family", "Установи `.card { font-family: sans-serif; }`.", page("<div class=\"card\">F</div>", ".card{ }\n"), [{"type": "css_property", "expected": {"selector": ".card", "property": "font-family", "value": "sans-serif"}}]),
        ("prefers", "prefers-reduced-motion", "Добавь media `prefers-reduced-motion`.", page("<div>m</div>", "/* TODO */\n"), [{"type": "content_regex", "expected": r"prefers-reduced-motion"}]),
        ("areas", "grid-template-areas", "Добавь `grid-template-areas`.", page("<div class=\"layout\"></div>", ".layout{display:grid;/* TODO */}\n"), [{"type": "content_regex", "expected": r"grid-template-areas"}]),
        ("place", "place-items", "Установи `.grid { place-items: center; }`.", page("<div class=\"grid\"><div>1</div></div>", ".grid{display:grid;}\n"), [{"type": "css_property", "expected": {"selector": ".grid", "property": "place-items", "value": "center"}}]),
    ]
    for i in range(TIER_COUNTS["A"]):
        base, concept, desc, init, cases = a_templates[i % len(a_templates)]
        add("A", f"a_{i+1:03d}_{base}", concept, desc, init, cases)

    # ---- S (10): boss ----
    boss_html = (
        "<div class=\"card\">\n"
        "  <h2 class=\"title\">Паспорт героя</h2>\n"
        "  <div class=\"stats\">\n"
        "    <div class=\"chip\">HP</div>\n"
        "    <div class=\"chip\">MP</div>\n"
        "    <div class=\"chip\">XP</div>\n"
        "  </div>\n"
        "  <button class=\"btn\">В путь</button>\n"
        "</div>\n"
    )
    boss_css = ".card{padding:16px;border:1px solid #ccc;border-radius:12px;}\n.stats{ }\n.btn{ }\n"
    for i in range(TIER_COUNTS["S"]):
        add(
            "S",
            f"s_{i+1:03d}_boss",
            "Босс: карточка героя",
            "Сделай `.stats` flex с `gap: 10px`, а `.btn` — `cursor: pointer`.",
            page(boss_html, boss_css),
            [
                {"type": "css_property", "expected": {"selector": ".stats", "property": "display", "value": "flex"}},
                {"type": "css_property", "expected": {"selector": ".stats", "property": "gap", "value": "10px"}},
                {"type": "css_property", "expected": {"selector": ".btn", "property": "cursor", "value": "pointer"}},
            ],
        )

    # sanity
    by = {t: 0 for t in TIER_COUNTS}
    seen = set()
    for s in specs:
        by[s["tier"]] += 1
        if s["slug"] in seen:
            raise SystemExit(f"Duplicate frontend slug: {s['slug']}")
        seen.add(s["slug"])
    for tier, need in TIER_COUNTS.items():
        if by[tier] != need:
            raise SystemExit(f"Frontend tier {tier} mismatch: {by[tier]} != {need}")
    return specs


def scratch_specs() -> list[dict[str, Any]]:
    """Returns 200 scratch specs (tier distribution from TIER_COUNTS)."""
    specs: list[dict[str, Any]] = []

    def add(tier: str, slug: str, concept: str, description: str, required_blocks: list[str]) -> None:
        specs.append({"tier": tier, "slug": slug, "concept": concept, "description": description, "required_blocks": required_blocks})

    # ---- D (40): 20 templates × 2 ----
    d_templates = [
        ("move", "Первые шаги", "При зелёном флаге пройди 20 шагов.", ["event_whenflagclicked", "motion_movesteps"]),
        ("turn", "Поворот", "При зелёном флаге повернись вправо на 15°.", ["event_whenflagclicked", "motion_turnright"]),
        ("x", "Сдвиг по X", "При зелёном флаге измени x на 10.", ["event_whenflagclicked", "motion_changexby"]),
        ("y", "Сдвиг по Y", "При зелёном флаге измени y на 30.", ["event_whenflagclicked", "motion_changeyby"]),
        ("goto0", "Старт в точке", "При зелёном флаге перейди в x:0 y:0.", ["event_whenflagclicked", "motion_gotoxy"]),
        ("glide", "Скольжение", "При зелёном флаге скользи к точке x:0 y:0.", ["event_whenflagclicked", "motion_glideto"]),
        ("say", "Фраза", "При зелёном флаге скажи 'Привет!' 2 секунды.", ["event_whenflagclicked", "looks_sayforsecs"]),
        ("costume", "Костюм", "При зелёном флаге смени костюм на следующий.", ["event_whenflagclicked", "looks_nextcostume"]),
        ("sound", "Звук", "При зелёном флаге проиграй звук до конца.", ["event_whenflagclicked", "sound_playuntildone"]),
        ("wait", "Пауза", "Подожди 1 секунду и скажи 'В путь!'.", ["event_whenflagclicked", "control_wait", "looks_sayforsecs"]),
        ("size", "Размер", "Установи размер спрайта 150%.", ["event_whenflagclicked", "looks_setsizeto"]),
        ("hide_show", "Появление", "Спрячься, подожди 1 сек, затем покажись.", ["event_whenflagclicked", "looks_hide", "control_wait", "looks_show"]),
        ("backdrop", "Фон", "Переключи фон сцены на следующий.", ["event_whenflagclicked", "looks_nextbackdrop"]),
        ("effect", "Эффект", "Измени эффект цвета на 25.", ["event_whenflagclicked", "looks_changeeffectby"]),
        ("var_set", "Переменная", "Создай переменную и задай ей значение при флаге.", ["event_whenflagclicked", "data_setvariableto"]),
        ("random_xy", "Случайная точка", "Перейди в случайные x,y.", ["event_whenflagclicked", "operator_random", "motion_gotoxy"]),
        ("point_dir", "Направление", "Повернись в направлении 90° при флаге.", ["event_whenflagclicked", "motion_pointindirection"]),
        ("stop_all", "Стоп", "Добавь кнопку/клавишу, которая останавливает всё.", ["event_whenkeypressed", "control_stop"]),
        ("think", "Мысль", "При флаге подумай 2 секунды.", ["event_whenflagclicked", "looks_thinkforsecs"]),
        ("go_mouse", "К мыши", "При флаге перейди к указателю мыши.", ["event_whenflagclicked", "motion_goto"]),
    ]
    for i in range(TIER_COUNTS["D"]):
        base, concept, desc, req = d_templates[i % len(d_templates)]
        add("D", f"d_{i+1:03d}_{base}", concept, desc, req)

    # ---- C (60): 30 templates × 2 ----
    c_templates = [
        ("forever_bounce", "Патруль", "В цикле всегда двигайся и отскакивай от края.", ["event_whenflagclicked", "control_forever", "motion_movesteps", "motion_ifonedgebounce"]),
        ("repeat_walk", "Повтор", "10 раз перемести спрайт на 10 шагов.", ["event_whenflagclicked", "control_repeat", "motion_movesteps"]),
        ("ask_name", "Вопрос", "Спроси имя и поприветствуй.", ["event_whenflagclicked", "sensing_askandwait", "looks_sayforsecs"]),
        ("broadcast", "Сигнал", "По клавише отправь сообщение, другой скрипт отреагирует.", ["event_whenkeypressed", "event_broadcast", "event_whenbroadcastreceived"]),
        ("timer_if", "Таймер", "Если таймер > 5 — скажи 'Время вышло!'.", ["event_whenflagclicked", "sensing_timer", "operator_gt", "control_if", "looks_sayforsecs"]),
        ("score", "Очки", "Сделай переменную score: обнуляй и увеличивай по клавише.", ["event_whenflagclicked", "data_setvariableto", "event_whenkeypressed", "data_changevariableby"]),
        ("if_else_score", "Порог", "Если score > 10 — 'Мастер', иначе 'Ученик'.", ["control_if_else", "operator_gt", "looks_sayforsecs"]),
        ("random_turn", "Случайный поворот", "В цикле всегда поворачивайся на случайное -10..10.", ["control_forever", "operator_random", "motion_turnright"]),
        ("touch_edge", "Стена", "Если касается края — скажи 'Стена!'.", ["control_if", "sensing_touchingobject", "looks_sayforsecs"]),
        ("touch_color", "Цвет-стена", "Если касается цвета — вернись на старт.", ["control_if", "sensing_touchingcolor", "motion_gotoxy"]),
        ("key_left", "Влево", "По стрелке влево меняй x на -10.", ["event_whenkeypressed", "motion_changexby"]),
        ("key_right", "Вправо", "По стрелке вправо меняй x на 10.", ["event_whenkeypressed", "motion_changexby"]),
        ("animate", "Анимация", "Меняй костюм каждые 0.2 сек в цикле.", ["control_forever", "looks_nextcostume", "control_wait"]),
        ("wait_until", "Ждать", "Жди, пока нажата клавиша пробел.", ["control_wait_until", "sensing_keypressed"]),
        ("repeat_until", "Повтор до", "Повторяй, пока не коснёшься края.", ["control_repeat_until", "sensing_touchingobject"]),
        ("random_x", "Случайный X", "Установи x в случайное -200..200.", ["event_whenflagclicked", "operator_random", "motion_setx"]),
        ("random_y", "Случайный Y", "Установи y в случайное -150..150.", ["event_whenflagclicked", "operator_random", "motion_sety"]),
        ("join_text", "Склей текст", "Скажи строку, собранную оператором join.", ["operator_join", "looks_sayforsecs"]),
        ("math_add", "Сложение", "Сохрани сумму двух чисел в переменную.", ["operator_add", "data_setvariableto"]),
        ("math_mul", "Умножение", "Сохрани произведение двух чисел в переменную.", ["operator_multiply", "data_setvariableto"]),
        ("switch_backdrop", "Смена сцены", "Переключи фон по сообщению.", ["event_whenbroadcastreceived", "looks_switchbackdropto"]),
        ("show_var", "Показ переменной", "Покажи переменную на сцене.", ["data_showvariable"]),
        ("hide_var", "Скрыть переменную", "Спрячь переменную на сцене.", ["data_hidevariable"]),
        ("glide_points", "Маршрут", "Скользи по 3 точкам по кругу.", ["control_forever", "motion_glideto"]),
        ("distance", "Дистанция", "Покажи расстояние до указателя мыши (переменная).", ["sensing_distanceto", "data_setvariableto"]),
        ("point_mouse", "Повернуться к мыши", "Повернись к мыши и сделай шаг.", ["motion_pointtowards", "motion_movesteps"]),
        ("edge_bounce", "Отскок", "Сделай отскок при касании края.", ["motion_ifonedgebounce"]),
        ("operator_gt", "Сравнение", "Используй `>` в условии.", ["operator_gt", "control_if"]),
        ("broadcast_restart", "Рестарт", "Сообщение `restart` обнуляет переменную и возвращает в точку.", ["event_broadcast", "event_whenbroadcastreceived", "data_setvariableto", "motion_gotoxy"]),
    ]
    for i in range(TIER_COUNTS["C"]):
        base, concept, desc, req = c_templates[i % len(c_templates)]
        add("C", f"c_{i+1:03d}_{base}", concept, desc, req)

    # ---- B (60): 30 templates × 2 ----
    b_templates = [
        ("coin", "Ловец монет", "Монета падает, герой ловит. За ловлю +1 к score.", ["operator_random", "sensing_touchingobject", "data_changevariableby"]),
        ("clones", "Клоны врагов", "Создавай клонов, клон движется и удаляется.", ["control_create_clone_of", "control_start_as_clone", "control_delete_this_clone"]),
        ("loot_list", "Список трофеев", "По клавише добавляй предмет в список.", ["data_addtolist", "event_whenkeypressed"]),
        ("platform", "Платформер", "Гравитация вниз, остановка при касании платформы.", ["control_forever", "motion_changeyby", "sensing_touchingobject", "control_if"]),
        ("bullets", "Пули-клоны", "По пробелу создавай пулю-клон, она летит и исчезает.", ["event_whenkeypressed", "control_create_clone_of", "control_start_as_clone", "motion_movesteps"]),
        ("maze", "Лабиринт", "Не проходи сквозь стену (касание цвета).", ["sensing_touchingcolor", "control_if"]),
        ("timer_end", "Конец по таймеру", "Останови игру на 30 секунде.", ["sensing_timer", "operator_gt", "control_if", "control_stop"]),
        ("teleport", "Телепорт", "При сообщении перемести героя в точку.", ["event_whenbroadcastreceived", "motion_gotoxy"]),
        ("hp", "HP-система", "HP уменьшается при касании врага, при 0 — поражение.", ["data_changevariableby", "control_if_else", "operator_lt"]),
        ("spawn", "Спавн", "Создавай врага в случайной точке.", ["operator_random", "motion_gotoxy"]),
        ("score_list", "Таблица результатов", "Храни последние 5 результатов в списке.", ["data_addtolist", "data_deleteoflist"]),
        ("wave", "Волны", "Сообщение `wave` запускает волну врагов.", ["event_broadcast", "event_whenbroadcastreceived"]),
        ("lava", "Лава", "Касание красного цвета отнимает HP.", ["sensing_touchingcolor", "data_changevariableby"]),
        ("shop", "Лавка", "Покупка за золото и добавление в список.", ["control_if_else", "data_changevariableby", "data_addtolist"]),
        ("dialog", "Диалог", "Вопрос и ветвление по ответу.", ["sensing_askandwait", "control_if_else"]),
        ("boss_phase", "Фазы босса", "При HP < 50% меняй поведение.", ["operator_lt", "control_if_else"]),
        ("projectile_hit", "Попадание", "Пуля удаляется при касании врага и даёт очки.", ["sensing_touchingobject", "control_delete_this_clone", "data_changevariableby"]),
        ("inventory_ui", "UI списка", "Покажи список предметов на сцене.", ["data_showlist"]),
        ("save_load", "Сохранение", "Сохрани значение в список и восстанови.", ["data_addtolist", "data_itemoflist", "data_setvariableto"]),
        ("level_up", "Повышение уровня", "Каждые 10 очков увеличивай уровень.", ["operator_mod", "control_if"]),
        ("clone_timer", "Клоны по времени", "Клон живёт 3 секунды и удаляется.", ["control_start_as_clone", "control_wait", "control_delete_this_clone"]),
        ("message_score", "Счёт по сигналу", "Сообщение увеличивает счёт.", ["event_whenbroadcastreceived", "data_changevariableby"]),
        ("rng_drop", "Случайный дроп", "С вероятностью 50% добавь предмет в список.", ["operator_random", "control_if"]),
        ("edge_kill", "Край=смерть", "Если спрайт касается края — поражение.", ["sensing_touchingobject", "control_if"]),
        ("speed_inc", "Ускорение", "Каждые 10 секунд увеличивай скорость (переменная).", ["control_wait", "data_changevariableby"]),
        ("checkpoint", "Чекпоинт", "Сохраняй позицию в переменных и возвращайся по клавише.", ["data_setvariableto", "event_whenkeypressed", "motion_gotoxy"]),
        ("countdown_ui", "UI таймера", "Покажи обратный отсчёт в переменной.", ["sensing_timer", "data_setvariableto"]),
        ("clone_score", "Очки за клонов", "Каждый удалённый клон добавляет очки.", ["control_delete_this_clone", "data_changevariableby"]),
        ("random_costume", "Случайный костюм", "Выбирай случайный костюм (если есть).", ["operator_random", "looks_switchcostumeto"]),
    ]
    for i in range(TIER_COUNTS["B"]):
        base, concept, desc, req = b_templates[i % len(b_templates)]
        add("B", f"b_{i+1:03d}_{base}", concept, desc, req)

    # ---- A (30): 15 templates × 2 ----
    a_templates = [
        ("platform_jump", "Прыжок", "Прыжок по клавише и гравитация.", ["event_whenkeypressed", "control_if", "motion_changeyby"]),
        ("shooter", "Шутер", "Стрельба, враги, попадания и счёт.", ["control_create_clone_of", "sensing_touchingobject", "data_changevariableby"]),
        ("flappy", "Flappy", "Гравитация, прыжок, препятствия клонами.", ["control_forever", "motion_changeyby", "control_create_clone_of"]),
        ("levels", "Уровни", "2 уровня через фон + обнуление переменных.", ["looks_switchbackdropto", "data_setvariableto"]),
        ("inventory", "Инвентарь", "Инвентарь списком: добавить/удалить/показать.", ["data_addtolist", "data_deleteoflist", "data_showlist"]),
        ("quest", "Квест", "Короткий квест с ветвлениями и вопросами.", ["sensing_askandwait", "control_if_else"]),
        ("procedures", "Свои блоки", "Создай свой блок и используй его 3 раза.", ["procedures_definition"]),
        ("boss_bar", "HP босса", "HP босса + смена фазы при <50%.", ["operator_lt", "control_if_else", "data_changevariableby"]),
        ("minimap", "Миникарта", "Миникарта: клон/спрайт показывает позицию героя.", ["control_create_clone_of", "motion_xposition"]),
        ("music", "Музыка", "Проигрывание мелодии по списку нот/индексу.", ["control_repeat", "sound_playuntildone"]),
        ("save_system", "Сейв", "Сохрани несколько параметров в списки.", ["data_addtolist", "data_itemoflist"]),
        ("ai_follow", "Преследование", "Враг следует за героем (упрощённо).", ["motion_pointtowards", "motion_movesteps"]),
        ("particles", "Частицы", "Эффект частиц через клоны.", ["control_create_clone_of", "control_start_as_clone"]),
        ("dialog_tree", "Дерево диалога", "Диалоговое дерево из списка фраз.", ["data_itemoflist", "sensing_askandwait"]),
        ("combo_timer", "Комбо", "Комбо сбрасывается, если нет действий 3 секунды.", ["sensing_timer", "operator_gt", "control_if_else"]),
    ]
    for i in range(TIER_COUNTS["A"]):
        base, concept, desc, req = a_templates[i % len(a_templates)]
        add("A", f"a_{i+1:03d}_{base}", concept, desc, req)

    # ---- S (10): big projects ----
    s_templates = [
        ("boss_fight", "Арена босса", "Бой с боссом: HP героя/босса, атака, победа/поражение.", ["data_changevariableby", "control_if_else", "sensing_touchingobject"]),
        ("tower_defense", "Tower Defense", "Враги по пути, башни стреляют, волны.", ["control_create_clone_of", "event_broadcast", "data_changevariableby"]),
        ("rpg_shop", "RPG-лавка", "Магазин: золото, покупка, инвентарь (список).", ["data_addtolist", "data_changevariableby"]),
        ("platform_levels", "Платформер-уровни", "Ключ, дверь, переход на следующий фон.", ["looks_switchbackdropto", "sensing_touchingobject", "event_broadcast"]),
        ("music_seq", "Секвенсор", "Сетка 8 шагов: клики включают ноты, проигрывание.", ["control_repeat", "sound_playuntildone"]),
        ("racing", "Гонка", "Гонка по таймеру: круги, скорость, финиш.", ["sensing_timer", "operator_gt", "data_changevariableby"]),
        ("puzzle_rooms", "Комнаты", "3 комнаты-головоломки, ключи, двери, сообщения.", ["event_broadcast", "looks_switchbackdropto"]),
        ("survival", "Выживание", "Ресурсы, энергия, крафт (список).", ["data_addtolist", "control_if_else"]),
        ("city", "Город", "Размещение зданий и счёт ресурсов.", ["event_whenkeypressed", "data_changevariableby"]),
        ("boss_rush", "Boss Rush", "3 босса подряд: фазы, счёт, рестарт.", ["control_if_else", "event_broadcast", "data_setvariableto"]),
    ]
    for i, (base, concept, desc, req) in enumerate(s_templates, start=1):
        add("S", f"s_{i:03d}_{base}", concept, desc, req)

    # sanity
    by = {t: 0 for t in TIER_COUNTS}
    seen = set()
    for s in specs:
        by[s["tier"]] += 1
        if s["slug"] in seen:
            raise SystemExit(f"Duplicate scratch slug: {s['slug']}")
        seen.add(s["slug"])
    for tier, need in TIER_COUNTS.items():
        if by[tier] != need:
            raise SystemExit(f"Scratch tier {tier} mismatch: {by[tier]} != {need}")
    return specs


def remove_generated(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prefixes = tuple(CUR_PREFIX.values())
    kept = [t for t in tasks if not str(t.get("id") or "").startswith(prefixes)]
    print(f"Removed generated tasks: {len(tasks) - len(kept)}")
    return kept


def load_existing_ids(extra_tasks: Iterable[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for path in (TASKS_FILE, LEGACY_FILE):
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for t in raw.get("tasks") or []:
                if isinstance(t, dict) and t.get("id"):
                    ids.add(str(t["id"]))
        except Exception:
            continue
    for t in extra_tasks:
        if isinstance(t, dict) and t.get("id"):
            ids.add(str(t["id"]))
    return ids


def make_code_tasks(category: str, patterns: list[CodePattern], existing_ids: set[str]) -> list[dict[str, Any]]:
    prefix = CUR_PREFIX[category]
    per_tier_index = {t: 0 for t in TIER_COUNTS}
    tasks: list[dict[str, Any]] = []

    for pat in patterns:
        tier = pat.tier
        idx0 = per_tier_index[tier]
        per_tier_index[tier] += 1
        xp = xp_for(category, tier, idx0, TIER_COUNTS[tier])

        fn_py = pat.slug
        fn_js = snake_to_camel(pat.slug)
        fn = fn_py if category == "python" else fn_js
        params = pat.params if category == "python" else [snake_to_camel(x) for x in pat.params]

        tid = f"{prefix}{tier.lower()}_{idx0+1:03d}_{pat.slug}"
        if tid in existing_ids:
            raise SystemExit(f"ID collision: {tid}")

        hint = pat.rule_ru
        description = f"Реализуй функцию `{fn}({', '.join(params)})`: {pat.rule_ru}."
        initial = py_initial(fn, params, pat.return_kind, hint, pat.py_imports) if category == "python" else js_initial(fn, params, pat.return_kind, hint)

        visible = build_cases("python" if category == "python" else "javascript", fn, pat.cases_args, pat.solve)
        hidden = build_cases("python" if category == "python" else "javascript", fn, pat.hidden_args or [], pat.solve) if pat.hidden_args else []

        task: dict[str, Any] = {
            "id": tid,
            "category": category,
            "tier": tier,
            "xp": xp,
            "title": title_for(pat.concept, idx0),
            "story": story_for(tier, idx0),
            "description": description,
            "initial_code": initial,
            "resources": DEFAULT_RESOURCES[category],
            "check_logic": {"engine": ("pyodide" if category == "python" else "javascript"), "cases": visible},
        }
        if hidden:
            task["check_logic"]["hidden_cases"] = hidden
        tasks.append(task)
        existing_ids.add(tid)

    if len(tasks) != sum(TIER_COUNTS.values()):
        raise SystemExit(f"Internal error: {category} code tasks {len(tasks)} != 200")
    return tasks


def make_frontend_tasks(existing_ids: set[str]) -> list[dict[str, Any]]:
    specs = frontend_specs()
    prefix = CUR_PREFIX["frontend"]
    per_tier_index = {t: 0 for t in TIER_COUNTS}
    tasks: list[dict[str, Any]] = []

    for s in specs:
        tier = s["tier"]
        idx0 = per_tier_index[tier]
        per_tier_index[tier] += 1
        xp = xp_for("frontend", tier, idx0, TIER_COUNTS[tier])
        tid = f"{prefix}{tier.lower()}_{idx0+1:03d}_{s['slug']}"
        if tid in existing_ids:
            raise SystemExit(f"ID collision: {tid}")
        tasks.append(
            {
                "id": tid,
                "category": "frontend",
                "tier": tier,
                "xp": xp,
                "title": title_for(s["concept"], idx0),
                "story": story_for(tier, idx0),
                "description": s["description"],
                "initial_code": s["initial_code"],
                "resources": DEFAULT_RESOURCES["frontend"],
                "check_logic": {"engine": "iframe", "cases": s["cases"]},
            }
        )
        existing_ids.add(tid)
    if len(tasks) != sum(TIER_COUNTS.values()):
        raise SystemExit(f"Internal error: frontend tasks {len(tasks)} != 200")
    return tasks


def make_scratch_tasks(existing_ids: set[str]) -> list[dict[str, Any]]:
    specs = scratch_specs()
    prefix = CUR_PREFIX["scratch"]
    per_tier_index = {t: 0 for t in TIER_COUNTS}
    tasks: list[dict[str, Any]] = []

    for s in specs:
        tier = s["tier"]
        idx0 = per_tier_index[tier]
        per_tier_index[tier] += 1
        xp = xp_for("scratch", tier, idx0, TIER_COUNTS[tier])
        tid = f"{prefix}{tier.lower()}_{idx0+1:03d}_{s['slug']}"
        if tid in existing_ids:
            raise SystemExit(f"ID collision: {tid}")
        tasks.append(
            {
                "id": tid,
                "category": "scratch",
                "tier": tier,
                "xp": xp,
                "title": title_for(s["concept"], idx0),
                "story": story_for(tier, idx0),
                "description": s["description"],
                "initial_code": "https://scratch.mit.edu/projects/editor/",
                "resources": DEFAULT_RESOURCES["scratch"],
                "check_logic": {"engine": "manual", "required_blocks": s["required_blocks"]},
            }
        )
        existing_ids.add(tid)
    if len(tasks) != sum(TIER_COUNTS.values()):
        raise SystemExit(f"Internal error: scratch tasks {len(tasks)} != 200")
    return tasks


def main() -> int:
    raw = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
    tasks = remove_generated(list(raw.get("tasks") or []))
    existing_ids = load_existing_ids(tasks)

    patterns = code_patterns()
    py_tasks = make_code_tasks("python", patterns, existing_ids)
    js_tasks = make_code_tasks("javascript", patterns, existing_ids)
    fe_tasks = make_frontend_tasks(existing_ids)
    sc_tasks = make_scratch_tasks(existing_ids)

    raw["tasks"] = tasks + py_tasks + js_tasks + fe_tasks + sc_tasks
    TASKS_FILE.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Generated:", len(py_tasks), "python,", len(js_tasks), "js,", len(fe_tasks), "frontend,", len(sc_tasks), "scratch")
    print("Total tasks now:", len(raw["tasks"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
