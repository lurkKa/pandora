#!/usr/bin/env python3
"""Build a standalone Python/JavaScript Kahoot-style quiz bank.

The output intentionally contains no source-task ids, source references, or
comment-based hints inside code snippets.
"""

from __future__ import annotations

import json
import re
import random
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "kahoot_1_2.json"
SOURCE_FILES = [ROOT / "kahoot_2.json", ROOT / "kahoot_1_2.json"]
TODAY = "2026-05-25"
RNG = random.Random(20260525)
TARGET_PER_DOMAIN = 5000
MAX_EXISTING_PER_DOMAIN = 900

PREFIXES = [
    "Разбор без подсказок: ",
    "Ревью решения: ",
    "Квест знаний: ",
    "Мини-квиз: ",
    "Код-дуэль: ",
    "Проверка понимания: ",
    "Вопрос наставника: ",
    "Раунд на внимательность: ",
    "Тренировка перед боссом: ",
    "Быстрый раунд: ",
]

BAD_QUESTION_RE = re.compile(
    r"Контекст задания|source_task|source task|По описанию узнай|Посмотри видео|"
    r"Черновик логики|task_id|source_id|карточк[аи]|исходн(?:ое|ого|ые)?\s+задани",
    re.IGNORECASE,
)
BAD_CODE_RE = re.compile(
    r"(^|\n)\s*(#|//)|/\*|Черновик|Посмотри|Ответь|подсказ|TODO|pass\s*$|return\s+None",
    re.IGNORECASE,
)
CONTEXT_TAIL_RE = re.compile(
    r"\s*(?:Ситуация:|Представь, что это используется в)\s*[^.?!]+[.?!]?$",
    re.IGNORECASE,
)
ANSWER_TAIL_RE = re.compile(r"\s*В каком варианте ответ точнее\??$", re.IGNORECASE)

TIER_BY_DIFF = {
    "beginner": "D",
    "easy": "C",
    "medium": "B",
    "hard": "A",
    "expert": "S",
}
POINTS_BY_DIFF = {
    "beginner": 20,
    "easy": 35,
    "medium": 55,
    "hard": 80,
    "expert": 100,
}
TIME_BY_DIFF = {
    "beginner": 20,
    "easy": 25,
    "medium": 30,
    "hard": 40,
    "expert": 50,
}
TYPE_MAP = {
    "syntax_flashcard_mc": "syntax",
    "function_name_mc": "purpose",
    "task_goal_mc": "scenario",
    "topic_identification_mc": "purpose",
    "variable_name_mc": "debug",
    "variable_value_mc": "output",
    "test_case_output_mc": "output",
    "code_cloze_mc": "syntax",
    "syntax": "syntax",
    "purpose": "purpose",
    "debug": "debug",
    "scenario": "scenario",
    "system": "system",
    "output": "output",
}

ROUND_TAILS = [
    "Выбери точный ответ.",
    "Какой вариант верный?",
    "Что здесь правильно?",
    "Найди лучший ответ.",
    "Один вариант корректен.",
]
WRAPPERS = [
    "{base}",
    "{base} {tail}",
    "В код-ревью спросили: {base}",
    "Для короткого квиза: {base}",
    "Проверь понимание: {base}",
]

PY_CONTEXTS = [
    "Мини-сценарий: короткий учебный пример.",
    "Мини-сценарий: выбор самого точного варианта.",
    "Мини-сценарий: ревью маленькой функции.",
    "Мини-сценарий: разбор чужого решения.",
    "Мини-сценарий: подготовка к самостоятельной задаче.",
    "Мини-сценарий: быстрый вопрос на синтаксис.",
    "Мини-сценарий: короткая отладка.",
    "Мини-сценарий: проверка понимания перед практикой.",
    "Мини-сценарий: маленькая программа без внешних данных.",
    "Мини-сценарий: вопрос на внимательность.",
    "Мини-сценарий: поиск аккуратного решения.",
    "Мини-сценарий: обсуждение ответа с наставником.",
    "Мини-сценарий: контроль базовой идеи.",
    "Мини-сценарий: шаг перед задачей на код.",
    "Мини-сценарий: проверка языкового нюанса.",
    "Мини-сценарий: выбор безопасного подхода.",
    "Мини-сценарий: упражнение на чтение кода.",
    "Мини-сценарий: короткий блиц-вопрос.",
    "Мини-сценарий: сравнение похожих вариантов.",
    "Мини-сценарий: финальная проверка перед запуском.",
]

JS_CONTEXTS = [
    "Мини-сценарий: короткий учебный пример.",
    "Мини-сценарий: выбор самого точного варианта.",
    "Мини-сценарий: ревью маленькой функции.",
    "Мини-сценарий: разбор чужого решения.",
    "Мини-сценарий: подготовка к самостоятельной задаче.",
    "Мини-сценарий: быстрый вопрос на синтаксис.",
    "Мини-сценарий: короткая отладка.",
    "Мини-сценарий: проверка понимания перед практикой.",
    "Мини-сценарий: маленькая программа без внешних данных.",
    "Мини-сценарий: вопрос на внимательность.",
    "Мини-сценарий: поиск аккуратного решения.",
    "Мини-сценарий: обсуждение ответа с наставником.",
    "Мини-сценарий: контроль базовой идеи.",
    "Мини-сценарий: шаг перед задачей на код.",
    "Мини-сценарий: проверка языкового нюанса.",
    "Мини-сценарий: выбор безопасного подхода.",
    "Мини-сценарий: упражнение на чтение кода.",
    "Мини-сценарий: короткий блиц-вопрос.",
    "Мини-сценарий: сравнение похожих вариантов.",
    "Мини-сценарий: финальная проверка перед запуском.",
]


PY_CONCEPTS = [
    ("variables", "syntax", "beginner", "Как в Python присвоить переменной `coins` значение 10?", ["coins = 10", "let coins = 10", "var coins = 10", "coins :=: 10"], 0, "Обычное присваивание в Python записывается через `=`."),
    ("strings", "syntax", "easy", "Какой вариант создаёт f-строку с подстановкой переменной `name`?", ["f'Hi {name}'", "'Hi {name}'", "format'Hi {name}'", "`Hi ${name}`"], 0, "Префикс `f` включает подстановку выражений в фигурных скобках."),
    ("lists", "purpose", "beginner", "Что делает `items.append(x)`?", ["добавляет элемент в конец списка", "создаёт новый список и возвращает его", "сортирует список", "удаляет первый элемент"], 0, "`append` меняет список на месте."),
    ("lists", "debug", "medium", "Почему `items[3]` может вызвать `IndexError`?", ["в списке может не быть элемента с индексом 3", "индексы начинаются с 1", "индексы нельзя использовать", "3 зарезервировано"], 0, "Индекс 3 означает четвёртый элемент, он существует не в каждом списке."),
    ("dicts", "purpose", "easy", "Зачем используют `d.get(key, default)`?", ["получить значение без `KeyError`, если ключа нет", "удалить ключ", "отсортировать словарь", "сделать ключ приватным"], 0, "`get` возвращает default при отсутствующем ключе."),
    ("truthiness", "debug", "hard", "Чем `is` отличается от `==`?", ["`is` проверяет идентичность объекта, `==` проверяет равенство значений", "`is` работает только со строками", "`==` меняет объект", "разницы нет"], 0, "`is` отвечает на вопрос: это тот же самый объект?"),
    ("functions", "debug", "expert", "Почему изменяемый список как аргумент по умолчанию часто опасен?", ["один и тот же объект может переиспользоваться между вызовами", "списки нельзя передавать в функции", "Python удаляет список после return", "аргументы по умолчанию вычисляются при каждом вызове"], 0, "Значение по умолчанию создаётся при определении функции."),
    ("loops", "scenario", "easy", "Нужно выполнить действие ровно 10 раз. Что выбрать?", ["for n in range(10)", "while True без break", "try/except", "import range"], 0, "`range(10)` даёт 10 итераций: от 0 до 9."),
    ("exceptions", "scenario", "medium", "Пользователь может ввести `abc` вместо числа. Что поможет не уронить программу при `int(text)`?", ["try/except ValueError", "global text", "list(text)", "assert text"], 0, "`ValueError` ловит нечисловой ввод при преобразовании."),
    ("files", "purpose", "medium", "Зачем обычно пишут `with open(path) as f`?", ["автоматически закрыть файл после блока", "ускорить CPU", "создать новый синтаксис", "запретить чтение файла"], 0, "Контекстный менеджер закрывает ресурс корректно."),
    ("iterators", "purpose", "hard", "Что делает `yield` внутри функции?", ["превращает функцию в генератор значений", "останавливает программу навсегда", "создаёт класс", "импортирует модуль"], 0, "`yield` возвращает значение и сохраняет состояние генератора."),
    ("modules", "system", "easy", "Для чего нужен `venv`?", ["изолировать зависимости конкретного проекта", "ускорить каждый цикл", "заменить Git", "спрятать исходный код"], 0, "Виртуальное окружение помогает не смешивать пакеты проектов."),
    ("modules", "system", "easy", "Что делает `pip install requests`?", ["устанавливает пакет `requests` в Python-окружение", "создаёт файл requests.py", "запускает браузер", "форматирует код"], 0, "`pip install` ставит пакет."),
    ("classes", "scenario", "medium", "Нужно описать объект с состоянием `hp` и методом `attack()`. Что лучше подходит?", ["class", "lambda", "json.loads", "break"], 0, "Класс объединяет данные и поведение объекта."),
    ("comprehensions", "syntax", "medium", "Как получить квадраты чётных чисел из `nums`?", ["[n*n for n in nums if n % 2 == 0]", "[for n in nums: n*n if even]", "nums.square(even=True)", "{n*n in nums if n % 2}"], 0, "List comprehension может одновременно фильтровать и преобразовывать."),
    ("dicts", "syntax", "easy", "Как пройтись по ключам и значениям словаря `d`?", ["for key, value in d.items():", "for key, value of d:", "foreach d as key,value:", "for d.items(key, value):"], 0, "`items()` возвращает пары ключ-значение."),
    ("strings", "purpose", "easy", "Что делает `'-'.join(parts)`?", ["склеивает строки из `parts` через дефис", "делит строку по дефису", "удаляет дефисы", "сортирует строки"], 0, "`join` соединяет элементы последовательности строк."),
    ("lists", "purpose", "medium", "Что возвращает `sorted(items)`?", ["новый отсортированный список", "`None`, потому что сортирует на месте", "исходный список без изменений порядка", "словарь индексов"], 0, "`sorted` не меняет исходную коллекцию."),
    ("lists", "debug", "medium", "Почему `result = items.append(5)` обычно даёт `None` в `result`?", ["`append` меняет список на месте и ничего полезного не возвращает", "5 нельзя добавлять в список", "append удаляет список", "список становится строкой"], 0, "Методы-мутаторы часто возвращают `None`."),
    ("functions", "syntax", "hard", "Что означает `*args` в параметрах функции?", ["собирает лишние позиционные аргументы в кортеж", "распаковывает словарь в JSON", "делает функцию асинхронной", "запрещает аргументы"], 0, "`*args` принимает переменное число позиционных аргументов."),
    ("functions", "syntax", "hard", "Что означает `**kwargs` в параметрах функции?", ["собирает именованные аргументы в словарь", "возводит kwargs в степень", "создаёт список аргументов", "вызывает исключение"], 0, "`**kwargs` принимает переменное число именованных аргументов."),
    ("modules", "system", "medium", "Зачем используют `if __name__ == '__main__'`?", ["запустить код только при прямом запуске файла", "запретить импорт модуля", "создать главный класс", "ускорить функцию"], 0, "При импорте такой блок не выполняется."),
    ("types", "debug", "hard", "Почему `copy.copy()` может быть недостаточно для вложенных списков?", ["это поверхностная копия: вложенные объекты остаются общими", "она всегда возвращает строку", "она удаляет вложенные элементы", "она работает только с числами"], 0, "Для независимых вложенных структур нужен `deepcopy`."),
    ("regex", "purpose", "hard", "Когда уместно использовать регулярное выражение?", ["для поиска текста по шаблону", "для ускорения любого цикла", "для хранения пар ключ-значение", "для создания виртуального окружения"], 0, "Regex описывает шаблоны текста."),
    ("typing", "purpose", "medium", "Что дают аннотации типов вроде `def f(x: int) -> str`?", ["подсказывают ожидаемые типы людям и инструментам", "автоматически шифруют данные", "заменяют тесты", "запрещают запуск без компиляции"], 0, "Аннотации помогают анализаторам и читаемости."),
]

JS_CONCEPTS = [
    ("variables", "syntax", "beginner", "Как объявить переменную, значение которой планируется менять?", ["let score = 0;", "const score = 0;", "def score = 0", "score := 0"], 0, "`let` подходит для переназначаемой переменной."),
    ("variables", "debug", "medium", "Почему `const user = {}; user.name = 'Ada'` допустимо?", ["нельзя переназначить binding, но можно менять сам объект", "const делает объект строкой", "const запрещает свойства", "name является глобальной переменной"], 0, "`const` фиксирует ссылку, а не глубоко замораживает объект."),
    ("arrays", "purpose", "easy", "Что делает `arr.map(fn)`?", ["создаёт новый массив результатов", "оставляет только подходящие элементы", "суммирует массив", "меняет каждый элемент HTML"], 0, "`map` преобразует каждый элемент и сохраняет длину."),
    ("arrays", "purpose", "easy", "Что делает `arr.filter(fn)`?", ["создаёт новый массив элементов, прошедших проверку", "преобразует все элементы", "возвращает первый элемент", "сортирует массив"], 0, "`filter` оставляет элементы, для которых callback вернул truthy."),
    ("arrays", "debug", "medium", "Почему `forEach` неудобен, если нужен новый массив?", ["`forEach` не возвращает итоговый массив", "`forEach` работает только в Node.js", "`forEach` удаляет элементы", "`forEach` сортирует массив"], 0, "Для нового массива обычно используют `map` или `filter`."),
    ("objects", "debug", "medium", "Почему `user.name` может дать `undefined`?", ["свойства `name` может не быть в объекте", "точечный доступ запрещён", "JS удаляет строки", "`name` всегда приватное"], 0, "Отсутствующее свойство объекта даёт `undefined`."),
    ("coercion", "debug", "hard", "Почему часто лучше `===`, чем `==`?", ["`===` не делает неожиданное приведение типов", "`===` работает только со строками", "`==` вообще не работает", "`===` всегда асинхронный"], 0, "Строгое сравнение проверяет тип и значение."),
    ("types", "purpose", "medium", "Что означает `undefined`?", ["значение не было задано или свойства нет", "число не является целым", "пустой массив", "ошибка сети"], 0, "`undefined` часто означает отсутствие присвоенного значения."),
    ("objects", "syntax", "medium", "Как безопасно прочитать `user.profile.name`, если `profile` может отсутствовать?", ["user.profile?.name", "user.?profile.name", "optional(user.profile.name)", "user.profile!name"], 0, "Optional chaining останавливает чтение при `null` или `undefined`."),
    ("truthiness", "syntax", "hard", "Когда `??` отличается от `||`?", ["когда значение `0` или пустая строка должно сохраниться", "никогда, операторы одинаковые", "только внутри HTML", "только для массивов"], 0, "`??` заменяет только `null` и `undefined`."),
    ("functions", "purpose", "medium", "Что такое callback?", ["функция, переданная другой функции для вызова позже", "глобальный CSS-селектор", "тип базы данных", "ключ package.json"], 0, "Callback передают как значение."),
    ("functions", "debug", "hard", "Чем стрелочная функция отличается от обычной по `this`?", ["она берёт `this` из внешней области", "она всегда создаёт новый `this`", "она не может возвращать значения", "она работает только с массивами"], 0, "Arrow function не имеет собственного `this`."),
    ("async", "purpose", "medium", "Что такое `Promise`?", ["объект будущего результата асинхронной операции", "массив DOM-элементов", "CSS-переход", "синхронный цикл"], 0, "Promise представляет будущий результат операции."),
    ("async", "system", "hard", "Что такое event loop в JavaScript?", ["механизм обработки очередей задач и асинхронных callbacks", "цикл `for` внутри HTML", "алгоритм сортировки CSS", "файл настроек npm"], 0, "Event loop координирует стек вызовов и очереди задач."),
    ("async", "debug", "hard", "Почему `fetch(url).json()` проблемно?", ["`json()` вызывают у `Response` после `await` или `.then`", "`fetch` сразу возвращает строку", "`url` обязан быть числом", "`json` является CSS-свойством"], 0, "`fetch` возвращает Promise<Response>."),
    ("dom", "scenario", "easy", "Нужно выполнить код при клике на кнопку. Что выбрать?", ["button.addEventListener('click', handler)", "button.JSON.parse(handler)", "Math.round(button)", "localStorage.click(handler)"], 0, "События DOM подписываются через `addEventListener`."),
    ("dom", "scenario", "easy", "Нужно найти первую кнопку с классом `.start`. Что выбрать?", ["document.querySelector('.start')", "Array.isArray('.start')", "JSON.stringify('.start')", "Math.max('.start')"], 0, "`querySelector` принимает CSS-селектор."),
    ("dom", "system", "medium", "Когда срабатывает `DOMContentLoaded`?", ["когда HTML разобран, но картинки ещё могут грузиться", "после каждого клика", "до получения HTML", "после закрытия вкладки"], 0, "Событие означает готовность DOM-дерева."),
    ("storage", "scenario", "medium", "Нужно сохранить выбранную тему между заходами на страницу. Что использовать?", ["localStorage", "Math.random", "querySelectorAll", "console.log"], 0, "`localStorage` хранит строки между сессиями браузера."),
    ("modules", "syntax", "medium", "Как экспортировать именованную функцию `sum` из модуля?", ["export function sum(a, b) { return a + b; }", "import function sum from 'sum'", "module sum(a,b)", "public sum = function"], 0, "`export` делает именованный экспорт."),
    ("modules", "system", "easy", "Что делает `npm install`?", ["устанавливает зависимости проекта", "форматирует CSS", "запускает HTML", "удаляет package.json"], 0, "npm устанавливает пакеты из package.json или аргумента."),
    ("runtime", "system", "easy", "Что такое Node.js?", ["среда выполнения JavaScript вне браузера", "HTML-фреймворк", "CSS-препроцессор", "графический редактор"], 0, "Node.js запускает JS на сервере или локально."),
    ("json", "purpose", "easy", "Что делает `JSON.parse(text)`?", ["преобразует JSON-строку в значение JavaScript", "делает запрос на сервер", "сортирует массив", "создаёт CSS-класс"], 0, "`JSON.parse` разбирает JSON."),
    ("json", "purpose", "easy", "Что делает `JSON.stringify(value)`?", ["преобразует значение JavaScript в JSON-строку", "запускает Promise", "удаляет свойства объекта", "находит DOM-элемент"], 0, "`stringify` сериализует значение."),
    ("classes", "purpose", "hard", "Что такое prototype chain?", ["цепочка объектов, по которой ищутся свойства", "очередь сетевых запросов", "список CSS-классов", "алгоритм шифрования"], 0, "Если свойства нет на объекте, поиск идёт по прототипу."),
]


def as_text_options(options):
    out = []
    for opt in options or []:
        if isinstance(opt, dict):
            out.append(str(opt.get("text", "")).strip())
        else:
            out.append(str(opt).strip())
    return out


def answer_text(item, options):
    idx = item.get("answer_index")
    ans = item.get("answer")
    if isinstance(ans, dict):
        ans = ans.get("text")
    if ans is None and isinstance(idx, int) and 0 <= idx < len(options):
        ans = options[idx]
    return str(ans).strip() if ans is not None else ""


def clean_question(question, domain, qtype):
    q = " ".join(str(question or "").replace("\n", " ").split())
    for prefix in PREFIXES:
        if q.startswith(prefix):
            q = q[len(prefix):]
            break
    q = CONTEXT_TAIL_RE.sub("", q)
    q = ANSWER_TAIL_RE.sub("", q).strip()
    if qtype == "output":
        lang = "Python" if domain == "python" else "JavaScript"
        return f"Что выведет этот {lang}-код?"
    if not q.endswith(("?", ".")):
        q += "?"
    return q


def unique_options(answer, candidates, local_rng):
    answer = str(answer)
    opts = [answer]
    for candidate in candidates:
        text = str(candidate)
        if text and text not in opts:
            opts.append(text)
        if len(opts) == 4:
            break
    for fallback in ["ошибка выполнения", "None", "undefined", "0", "1", "True", "False", "NaN", "[]", "{}", "null"]:
        if len(opts) == 4:
            break
        if fallback not in opts:
            opts.append(fallback)
    opts = opts[:4]
    local_rng.shuffle(opts)
    return opts, opts.index(answer)


def infer_topic(text, code=""):
    source = f"{text} {code}".lower()
    checks = [
        ("async", ["async", "await", "promise", "event loop", "микрозадач"]),
        ("dom", ["queryselector", "addeventlistener", "domcontentloaded", "dom", "клик"]),
        ("arrays", ["array", "массив", "push", "map", "filter", "reduce", "slice", "splice"]),
        ("lists", ["list", "спис", "append", "sorted"]),
        ("dicts", ["dict", "словар", "ключ", "get("]),
        ("objects", ["object", "объект", "property", "свойств"]),
        ("strings", ["string", "строк", "split", "join", "strip", "lower", "upper", "replace"]),
        ("functions", ["function", "def ", "lambda", "функц", "return", "callback"]),
        ("classes", ["class", "класс", "prototype", "метод"]),
        ("loops", ["for ", "while", "цикл", "range", "continue", "break"]),
        ("exceptions", ["except", "exception", "ошиб", "try", "catch", "finally", "throw"]),
        ("modules", ["import", "export", "module", "npm", "pip", "venv", "package"]),
        ("truthiness", ["true", "false", "truth", "bool", "boolean", "nan", "null", "undefined"]),
        ("math_ops", ["%", "//", "**", "math", "числ", "остат", "делен"]),
    ]
    for topic, needles in checks:
        if any(needle in source for needle in needles):
            return topic
    return "core"


def make_item(domain, topic, qtype, difficulty, question, options, answer_index, answer, code=None, explanation=None):
    item = {
        "id": "",
        "domain": domain,
        "language": "ru",
        "topic": topic,
        "type": qtype,
        "format": "single_choice",
        "difficulty": difficulty,
        "tier": TIER_BY_DIFF[difficulty],
        "question": question.strip(),
        "options": [str(option) for option in options],
        "answer_index": int(answer_index),
        "answer": str(answer),
        "explanation": explanation or f"Правильный ответ: {answer}.",
        "time_limit_sec": TIME_BY_DIFF[difficulty],
        "points": POINTS_BY_DIFF[difficulty],
        "tags": [domain, topic, qtype],
        "standalone": True,
    }
    if code:
        item["code"] = code.strip("\n")
    return item


def from_existing(item):
    domain = item.get("domain")
    if domain not in {"python", "javascript"}:
        return None
    qtype = TYPE_MAP.get(item.get("type"))
    if not qtype:
        return None
    options = as_text_options(item.get("options"))
    if len(options) != 4 or len(set(options)) != 4:
        return None
    idx = item.get("answer_index")
    if not isinstance(idx, int) or idx < 0 or idx > 3:
        return None
    answer = answer_text(item, options)
    if not answer or options[idx] != answer:
        return None
    question = clean_question(item.get("question", ""), domain, qtype)
    if BAD_QUESTION_RE.search(question):
        return None
    code = str(item.get("code") or "").strip("\n")
    if qtype == "output" and not code:
        return None
    if code and BAD_CODE_RE.search(code):
        return None
    if qtype == "output" and re.search(r"\.(lower|upper)\(\)", code) and re.search(r"['\"](?:\s+[^'\"]*|[^'\"]*\s+)['\"]", code):
        return None
    if len(question) > 180 or len(answer) > 90:
        return None
    raw_diff = item.get("difficulty")
    if isinstance(raw_diff, int):
        difficulty = ["beginner", "easy", "medium", "hard", "expert"][max(0, min(4, raw_diff - 1))]
    else:
        difficulty = raw_diff if raw_diff in TIER_BY_DIFF else "medium"
    topic = item.get("topic") or infer_topic(question, code)
    if domain == "javascript" and topic == "lists":
        topic = "arrays"
    explanation = item.get("explanation")
    if qtype == "output":
        explanation = f"Код выводит `{answer}`."
    elif not explanation or BAD_QUESTION_RE.search(str(explanation)):
        explanation = f"Правильный ответ: {answer}."
    return make_item(domain, topic, qtype, difficulty, question, options, idx, answer, code or None, explanation)


def item_key(item):
    code = item.get("code", "")
    if code:
        return (item["domain"], item["type"], code.strip(), item["answer"])
    return (item["domain"], item["type"], item["question"].lower(), item["answer"].lower())


def py_output_template(local_rng, n):
    templates = []
    m = n // 12

    a = 20 + (m * 17 + n * 7) % 991
    b = 2 + ((m + n) % 8)
    q, r = divmod(a, b)
    code = f"a = {a}\nb = {b}\nprint(a // b, a % b)"
    templates.append(("math_ops", "medium", code, f"{q} {r}", [str(q), f"{a / b}", f"{r} {q}", str(r)]))

    words = ["pythonista", "castle", "wizard", "backend", "academy", "syntax", "iterator", "closure"]
    word = words[(m + n) % len(words)]
    start = (m + n) % 3
    end = start + 2 + ((m + n) % 4)
    step = 2 if (m + n) % 5 == 0 else 1
    slice_expr = f"{start}:{end}" + (":2" if step == 2 else "")
    sliced = word[start:end:step]
    code = f"word = {word!r}\nprint(word[{slice_expr}])"
    templates.append(("strings", "easy" if step == 1 else "medium", code, sliced, [word[start:end], word, str(len(sliced)), word[:end]]))

    base = [1 + ((m + n + i) * 3) % 97 for i in range(4)]
    x = 20 + (m * 5 + n) % 99
    code = f"items = {base}\nalias = items\nalias.append({x})\nprint(len(items), items[-1])"
    templates.append(("lists", "hard", code, f"{len(base) + 1} {x}", [f"{len(base)} {x}", f"{len(base) + 1} {base[-1]}", str(len(base) + 1), str(x)]))

    keys = ["hp", "mana", "gold", "speed"]
    present = keys[(m + n) % 3]
    missing = keys[(m + n + 2) % 4]
    if missing == present:
        missing = "armor"
    val = 5 + (m + n) % 90
    default = (m + n) % 7
    code = f"hero = {{{present!r}: {val}}}\nprint(hero.get({missing!r}, {default}))"
    templates.append(("dicts", "medium", code, str(default), [str(val), "None", "KeyError", str(default + val)]))

    start_r = (m + n) % 7
    stop_r = start_r + 6 + (m + n) % 9
    mod = 2 + (m + n) % 5
    total = sum(v for v in range(start_r, stop_r) if v % mod != 0)
    code = f"total = 0\nfor n in range({start_r}, {stop_r}):\n    if n % {mod} == 0:\n        continue\n    total += n\nprint(total)"
    templates.append(("loops", "hard", code, str(total), [str(sum(range(start_r, stop_r))), str(total + mod), str(total - mod), str(stop_r - start_r)]))

    nums = [((m + n + i) % 13) - 6 for i in range(6)]
    comp = [v * v for v in nums if v > 0]
    code = f"nums = {nums}\nprint([n * n for n in nums if n > 0])"
    templates.append(("comprehensions", "medium", code, str(comp), [str([v for v in nums if v > 0]), str([v * v for v in nums]), str(len(comp)), "[]"]))

    x1 = 1 + (m + n) % 20
    x2 = x1 + 1
    code = f"def collect(x, box=[]):\n    box.append(x)\n    return len(box)\n\nprint(collect({x1}), collect({x2}))"
    templates.append(("functions", "expert", code, "1 2", ["1 1", "2 2", f"{x1} {x2}", "ошибка выполнения"]))

    count = 3 + (m + n) % 5
    code = f"funcs = []\nfor i in range({count}):\n    funcs.append(lambda: i)\nprint([f() for f in funcs])"
    templates.append(("closures", "expert", code, str([count - 1] * count), [str(list(range(count))), str([0] * count), str(count - 1), "ошибка выполнения"]))

    letters = "abcdef"
    k = 2 + (m + n) % 4
    val2 = 10 + (m * 3 + n) % 90
    pair = (letters[k], val2)
    code = f"pairs = list(zip({letters[:k+1]!r}, range({val2-k}, {val2+1})))\nprint(pairs[-1])"
    templates.append(("iterators", "hard", code, str(pair), [str((letters[0], val2-k)), str((k, val2)), str(pair[0]), str(pair[1])]))

    inner = (m + n) % 20
    add = 5 + (m * 2 + n) % 30
    code = f"grid = [[{inner}], [1]]\ncopy = grid[:]\ncopy[0].append({add})\nprint(grid[0])"
    templates.append(("lists", "expert", code, str([inner, add]), [str([inner]), str([add]), str([[inner, add], [1]]), "ошибка выполнения"]))

    names = ["Ada", "Linus", "Grace", "Guido", "Brendan", "Barbara"]
    name = names[(m + n) % len(names)]
    code = f"name = {name!r}\nprint(f'Hi, {{name.upper()}}!')"
    templates.append(("strings", "medium", code, f"Hi, {name.upper()}!", [f"Hi, {name}!", "Hi, {name.upper()}!", name.upper(), "ошибка выполнения"]))

    values = [False, "", [], [(m + n) % 5], (m + n) % 2]
    true_count = sum(bool(v) for v in values)
    code = f"values = {values}\nprint(sum(bool(x) for x in values))"
    templates.append(("truthiness", "hard", code, str(true_count), [str(len(values)), str(true_count - 1), str(true_count + 1), "True"]))

    topic, diff, code, answer, distractors = templates[n % len(templates)]
    opts, idx = unique_options(answer, distractors, local_rng)
    return make_item("python", topic, "output", diff, "Что выведет этот Python-код?", opts, idx, answer, code, f"Код выводит `{answer}`.")


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def js_output_template(local_rng, n):
    templates = []
    m = n // 14

    a = 3 + (m * 3 + n) % 97
    b = 1 + (m + n * 2) % 17
    code = f"console.log('{a}' + {b});"
    templates.append(("coercion", "easy", code, f"{a}{b}", [str(a + b), "NaN", str(a - b), "ошибка выполнения"]))

    code = f"console.log('{a}' - {b});"
    templates.append(("coercion", "medium", code, str(a - b), [f"{a}{b}", "NaN", str(a + b), "undefined"]))

    nums = [1 + ((m + n + i) * 4) % 41 for i in range(5)]
    parity = (m + n) % 2
    filtered = [x for x in nums if x % 2 == parity]
    code = f"const nums = {compact_json(nums)};\nconsole.log(JSON.stringify(nums.filter(n => n % 2 === {parity})));"
    templates.append(("arrays", "medium", code, compact_json(filtered), [compact_json(nums), str(len(filtered)), "[]", compact_json([x for x in nums if x % 2 != parity])]))

    inc = 2 + (m + n) % 20
    arr = [(m + n) % 30, (m + n) % 30 + 1]
    code = f"const items = {compact_json(arr)};\nconsole.log(items.push({inc}), items.length);"
    templates.append(("arrays", "hard", code, "3 3", ["2 3", f"3 {inc}", "undefined 3", compact_json(arr + [inc])]))

    loop_n = 3 + (m + n) % 6
    code = f"const fns = [];\nfor (var i = 0; i < {loop_n}; i++) {{\n  fns.push(() => i);\n}}\nconsole.log(fns[0](), fns[{loop_n - 1}]());"
    templates.append(("closures", "expert", code, f"{loop_n} {loop_n}", [f"0 {loop_n - 1}", "0 0", f"{loop_n - 1} {loop_n - 1}", "ReferenceError"]))

    code = f"const fns = [];\nfor (let i = 0; i < {loop_n}; i++) {{\n  fns.push(() => i);\n}}\nconsole.log(fns[0](), fns[{loop_n - 1}]());"
    templates.append(("closures", "hard", code, f"0 {loop_n - 1}", [f"{loop_n} {loop_n}", "0 0", f"{loop_n - 1} {loop_n - 1}", "ReferenceError"]))

    count = 1 + (m + n) % 50
    delta = 2 + (m * 2 + n) % 30
    code = f"const a = {{ count: {count} }};\nconst b = a;\nb.count += {delta};\nconsole.log(a.count);"
    templates.append(("objects", "hard", code, str(count + delta), [str(count), str(delta), "undefined", "ошибка выполнения"]))

    score_literal = "0"
    answer = "10 0"
    code = f"const score = {score_literal};\nconsole.log(score || 10, score ?? 10);"
    templates.append(("truthiness", "hard", code, answer, ["0 0", "10 10", "undefined 10", "false false"]))

    arr_sort = [10 + (m + n) % 70, 2 + (m * 2 + n) % 60, 1 + (m * 3 + n) % 50]
    lex = ",".join(sorted(str(x) for x in arr_sort))
    code = f"const nums = {compact_json(arr_sort)};\nnums.sort();\nconsole.log(nums.join(','));"
    templates.append(("arrays", "hard", code, lex, [",".join(str(x) for x in sorted(arr_sort)), ",".join(str(x) for x in arr_sort), "NaN", "ошибка выполнения"]))

    arr2 = [10 + (m + n) % 70, 2 + (m * 2 + n) % 60, 1 + (m * 3 + n) % 50]
    numeric = ",".join(str(x) for x in sorted(arr2))
    code = f"const nums = {compact_json(arr2)};\nnums.sort((a, b) => a - b);\nconsole.log(nums.join(','));"
    templates.append(("arrays", "medium", code, numeric, [",".join(sorted(str(x) for x in arr2)), ",".join(str(x) for x in arr2), "undefined", "ошибка выполнения"]))

    x = 1 + (m + n) % 50
    code = f"const data = [[{x}], [2]];\nconst copy = [...data];\ncopy[0].push(9);\nconsole.log(JSON.stringify(data[0]));"
    templates.append(("arrays", "expert", code, compact_json([x, 9]), [compact_json([x]), "[9]", compact_json([[x, 9], [2]]), "ошибка выполнения"]))

    val = "null" if (m + n) % 2 == 0 else "undefined"
    code = f"const user = {{ profile: {val} }};\nconsole.log(user.profile?.name ?? 'none');"
    templates.append(("objects", "hard", code, "none", ["undefined", "null", "name", "TypeError"]))

    code = "console.log(0 == false, 0 === false);"
    templates.append(("coercion", "hard", code, "true false", ["true true", "false false", "false true", "0 false"]))

    code = "console.log(typeof null);"
    templates.append(("types", "medium", code, "object", ["null", "undefined", "boolean", "number"]))

    topic, diff, code, answer, distractors = templates[n % len(templates)]
    opts, idx = unique_options(answer, distractors, local_rng)
    return make_item("javascript", topic, "output", diff, "Что выведет этот JavaScript-код?", opts, idx, answer, code, f"Код выводит `{answer}`.")


def concept_template(domain, local_rng, n):
    concepts = PY_CONCEPTS if domain == "python" else JS_CONCEPTS
    contexts = PY_CONTEXTS if domain == "python" else JS_CONTEXTS
    topic, qtype, diff, base_q, base_opts, ans_i, explanation = concepts[n % len(concepts)]
    answer = base_opts[ans_i]
    opts, idx = unique_options(answer, [o for o in base_opts if o != answer], local_rng)
    wrapper = WRAPPERS[(n // len(concepts)) % len(WRAPPERS)]
    tail = ROUND_TAILS[(n * 3) % len(ROUND_TAILS)]
    context = contexts[(n // (len(concepts) * len(WRAPPERS))) % len(contexts)]
    question = " ".join(f"{wrapper.format(base=base_q, tail=tail)} {context}".split())
    return make_item(domain, topic, qtype, diff, question, opts, idx, answer, None, explanation)


def generated_item(domain, local_rng, n):
    # About two thirds output/code-tracing and one third concepts/debug/scenarios.
    if n % 3 != 1:
        return py_output_template(local_rng, n) if domain == "python" else js_output_template(local_rng, n)
    return concept_template(domain, local_rng, n)


def load_existing_candidates():
    candidates = []
    for path in SOURCE_FILES:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for raw in data.get("items", []):
            item = from_existing(raw)
            if item:
                priority = 2 if path.name == "kahoot_2.json" else 1
                type_score = {"output": 5, "debug": 4, "scenario": 3, "syntax": 3, "system": 2, "purpose": 2}.get(item["type"], 1)
                diff_score = {"expert": 5, "hard": 4, "medium": 3, "easy": 2, "beginner": 1}.get(item["difficulty"], 1)
                candidates.append((priority, type_score, diff_score, item))
    candidates.sort(key=lambda row: (row[0], row[1], row[2], len(row[3].get("code", ""))), reverse=True)
    return [row[3] for row in candidates]


def build_domain(domain, candidates):
    selected = []
    seen = set()
    type_counts = Counter()
    topic_counts = Counter()
    type_caps = {
        "output": 380,
        "debug": 150,
        "scenario": 130,
        "syntax": 110,
        "system": 90,
        "purpose": 140,
    }

    for item in candidates:
        if item["domain"] != domain:
            continue
        if len(selected) >= MAX_EXISTING_PER_DOMAIN:
            break
        key = item_key(item)
        if key in seen:
            continue
        # Avoid letting one old template family dominate the improved bank.
        if type_counts[item["type"]] >= type_caps.get(item["type"], 100):
            continue
        if topic_counts[item["topic"]] >= 180:
            continue
        selected.append(item)
        seen.add(key)
        type_counts[item["type"]] += 1
        topic_counts[item["topic"]] += 1

    n = 0
    attempts = 0
    while len(selected) < TARGET_PER_DOMAIN:
        item = generated_item(domain, RNG, n)
        attempts += 1
        n += 1
        key = item_key(item)
        if key in seen:
            continue
        selected.append(item)
        seen.add(key)
        if attempts > TARGET_PER_DOMAIN * 20:
            raise RuntimeError(f"Too many attempts while generating {domain}")

    return selected


def assign_ids_and_shuffle(items):
    counters = defaultdict(int)
    for item in items:
        counters[item["domain"]] += 1
        prefix = "py" if item["domain"] == "python" else "js"
        item["id"] = f"{prefix}_quiz_{counters[item['domain']]:05d}"
    RNG.shuffle(items)
    return items


def validate(items):
    errors = []
    ids = set()
    for item in items:
        if item["id"] in ids:
            errors.append(f"duplicate id {item['id']}")
        ids.add(item["id"])
        if item["domain"] not in {"python", "javascript"}:
            errors.append(f"bad domain {item['id']}")
        if len(item.get("options", [])) != 4 or len(set(item["options"])) != 4:
            errors.append(f"bad options {item['id']}")
        idx = item.get("answer_index")
        if not isinstance(idx, int) or not 0 <= idx < 4:
            errors.append(f"bad answer index {item['id']}")
        elif item["options"][idx] != item.get("answer"):
            errors.append(f"answer mismatch {item['id']}")
        question_blob = json.dumps({k: item.get(k) for k in ["question", "explanation"]}, ensure_ascii=False)
        if BAD_QUESTION_RE.search(question_blob):
            errors.append(f"source-like text {item['id']}")
        if item["type"] == "output" and not item.get("code"):
            errors.append(f"output without code {item['id']}")
        if item.get("code") and BAD_CODE_RE.search(item["code"]):
            errors.append(f"hint/comment code {item['id']}")
        forbidden_keys = [k for k in item if k.startswith("source") or k in {"source_task_id", "source_task_title", "context"}]
        if forbidden_keys:
            errors.append(f"forbidden source keys {item['id']}: {forbidden_keys}")
    counts = Counter(item["domain"] for item in items)
    if counts["python"] != TARGET_PER_DOMAIN or counts["javascript"] != TARGET_PER_DOMAIN:
        errors.append(f"bad domain counts {dict(counts)}")
    return errors


def main():
    candidates = load_existing_candidates()
    python_items = build_domain("python", candidates)
    js_items = build_domain("javascript", candidates)
    items = assign_ids_and_shuffle(python_items + js_items)
    errors = validate(items)
    if errors:
        raise SystemExit("\n".join(errors[:30]))

    meta = {
        "schema_version": "standalone_quiz_bank.v3",
        "generated_at": TODAY,
        "language": "ru",
        "standalone": True,
        "domains": ["python", "javascript"],
        "items_per_domain": {"python": TARGET_PER_DOMAIN, "javascript": TARGET_PER_DOMAIN},
        "total_items": len(items),
        "question_style": "kahoot_like_single_choice",
        "notes": [
            "Файл собран как общий Python/JavaScript банк: 5000 вопросов на Python и 5000 вопросов на JavaScript.",
            "Вопросы не содержат source-task id, ссылок на старые задания или служебных source_* полей.",
            "Каждый вопрос про вывод кода содержит поле code; код не содержит комментариев-подсказок.",
            "Смешаны простые и сложные вопросы: синтаксис, вывод кода, debugging, сценарии, runtime/system и глубокие нюансы языка.",
            "kahoot_2.json использован как предпочтительный локальный источник, kahoot_1_2.json как вторичный; недостающие и слабые места заполнены новыми заданиями.",
        ],
        "validation": {
            "items_total": len(items),
            "domain_counts": dict(Counter(item["domain"] for item in items)),
            "type_counts_by_domain": {
                domain: dict(Counter(item["type"] for item in items if item["domain"] == domain))
                for domain in ["python", "javascript"]
            },
            "difficulty_counts_by_domain": {
                domain: dict(Counter(item["difficulty"] for item in items if item["domain"] == domain))
                for domain in ["python", "javascript"]
            },
            "errors": [],
        },
    }
    payload = {"meta": meta, "items": items}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta["validation"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
