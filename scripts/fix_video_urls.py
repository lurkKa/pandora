#!/usr/bin/env python3
"""
Replace ALL tutorial videos with VERIFIED (oEmbed-checked) Russian YouTube videos.
Every video ID here has been confirmed alive via youtube.com/oembed.
"""
import json

TASKS_FILE = "tasks.json"
YT = "https://www.youtube.com/watch?v="

# ══════════════════════════════════════════════════════════════
# ALL IDs VERIFIED ALIVE via oEmbed API on 2026-04-06
# Format: category -> topic -> [[set_01], [set_02]]
# ══════════════════════════════════════════════════════════════

VIDEOS = {
    "python": {
        "variables": [
            [
                {"title": "🇷🇺 Переменные и типы данных — itProger #4", "url": f"{YT}DZvNZ9l9NT4"},
                {"title": "🇷🇺 Типы данных, переменные — Web Developer Blog", "url": f"{YT}bpASbXwjSp4"},
                {"title": "🇷🇺 Переменные. Типы данных — Иван Викторович", "url": f"{YT}H81Osr7YO8w"},
            ],
            [
                {"title": "🇷🇺 Алгоритмы на Python — Хирьянов МФТИ", "url": f"{YT}KdZ4HF1SrFs"},
                {"title": "🇷🇺 Типы данных, переменные — Web Developer Blog", "url": f"{YT}bpASbXwjSp4"},
                {"title": "🇷🇺 Переменные. Типы данных — Иван Викторович", "url": f"{YT}H81Osr7YO8w"},
            ],
        ],
        "math_ops": [
            [
                {"title": "🇷🇺 Арифметические операции — Web Developer Blog", "url": f"{YT}g-4JbaY-yWU"},
                {"title": "🇷🇺 Числа и операции — Простые решения", "url": f"{YT}mxjuKJSwrWk"},
                {"title": "🇷🇺 Математические операции — Evrone", "url": f"{YT}VwHc36NXCUY"},
            ],
            [
                {"title": "🇷🇺 Числа и операции — Простые решения", "url": f"{YT}mxjuKJSwrWk"},
                {"title": "🇷🇺 Математические операции — Evrone", "url": f"{YT}VwHc36NXCUY"},
                {"title": "🇷🇺 Арифметические операции — Web Developer Blog", "url": f"{YT}g-4JbaY-yWU"},
            ],
        ],
        "functions": [
            [
                {"title": "🇷🇺 Функции (def, lambda) — itProger #12", "url": f"{YT}6K5v4--G__U"},
                {"title": "🇷🇺 Функции def и return — Об Коде", "url": f"{YT}ZCAejgQOsKg"},
                {"title": "🇷🇺 Оператор return — egoroff_channel", "url": f"{YT}Upok64s2Fgk"},
            ],
            [
                {"title": "🇷🇺 Функции def и return — Об Коде", "url": f"{YT}ZCAejgQOsKg"},
                {"title": "🇷🇺 Оператор return — egoroff_channel", "url": f"{YT}Upok64s2Fgk"},
                {"title": "🇷🇺 Функции (def, lambda) — itProger #12", "url": f"{YT}6K5v4--G__U"},
            ],
        ],
        "if_else": [
            [
                {"title": "🇷🇺 Оператор if-elif-else — DoCode #18", "url": f"{YT}x_S9HxhdzRo"},
                {"title": "🇷🇺 Условные операторы — itProger #5", "url": f"{YT}SUDNfS_0X-Q"},
                {"title": "🇷🇺 Конструкция if elif else — Олег Шпагин", "url": f"{YT}bmS1QmE6wYM"},
            ],
            [
                {"title": "🇷🇺 Условные операторы — itProger #5", "url": f"{YT}SUDNfS_0X-Q"},
                {"title": "🇷🇺 Конструкция if elif else — Олег Шпагин", "url": f"{YT}bmS1QmE6wYM"},
                {"title": "🇷🇺 Оператор if-elif-else — DoCode #18", "url": f"{YT}x_S9HxhdzRo"},
            ],
        ],
        "loops": [
            [
                {"title": "🇷🇺 Циклы for, while — itProger #6", "url": f"{YT}vMD6-jzgDvI"},
                {"title": "🇷🇺 Цикл while — Информатика без воды", "url": f"{YT}tHLm0bUnUVI"},
                {"title": "🇷🇺 Циклы (for, while) — Иван Викторович", "url": f"{YT}sZ0EIwgLblY"},
            ],
            [
                {"title": "🇷🇺 Цикл while — Информатика без воды", "url": f"{YT}tHLm0bUnUVI"},
                {"title": "🇷🇺 Циклы (for, while) — Иван Викторович", "url": f"{YT}sZ0EIwgLblY"},
                {"title": "🇷🇺 Циклы for, while — itProger #6", "url": f"{YT}vMD6-jzgDvI"},
            ],
        ],
        "strings": [
            [
                {"title": "🇷🇺 Функции строк, индексы, срезы — itProger #8", "url": f"{YT}pqaBWcsBGyA"},
                {"title": "🇷🇺 Строки в Python — PythonToday", "url": f"{YT}BrHhnwKPCKI"},
                {"title": "🇷🇺 Строки в Python — про АйТи", "url": f"{YT}TWBlNaiH3_g"},
            ],
            [
                {"title": "🇷🇺 Строки в Python — PythonToday", "url": f"{YT}BrHhnwKPCKI"},
                {"title": "🇷🇺 Строки в Python — про АйТи", "url": f"{YT}TWBlNaiH3_g"},
                {"title": "🇷🇺 Функции строк, индексы, срезы — itProger #8", "url": f"{YT}pqaBWcsBGyA"},
            ],
        ],
        "lists": [
            [
                {"title": "🇷🇺 Списки (list) и методы — itProger #7", "url": f"{YT}-X2ubBdP2Ak"},
                {"title": "🇷🇺 Списки (list) — Гоша Дударь #7", "url": f"{YT}ol23jnhVAOY"},
                {"title": "🇷🇺 Списки, методы, срезы — PythonToday", "url": f"{YT}PM2ncjqLLgY"},
            ],
            [
                {"title": "🇷🇺 Списки (list) — Гоша Дударь #7", "url": f"{YT}ol23jnhVAOY"},
                {"title": "🇷🇺 Списки, методы, срезы — PythonToday", "url": f"{YT}PM2ncjqLLgY"},
                {"title": "🇷🇺 Списки (list) и методы — itProger #7", "url": f"{YT}-X2ubBdP2Ak"},
            ],
        ],
        "dicts": [
            [
                {"title": "🇷🇺 Словари (dict) — itProger #10", "url": f"{YT}W2oO1Y-QDzo"},
                {"title": "🇷🇺 Словари. Операции и методы — egoroff_channel", "url": f"{YT}7_Zrh1--d5o"},
                {"title": "🇷🇺 Словари (dict), методы — Гоша Дударь #10", "url": f"{YT}NaA2H25gxN4"},
            ],
            [
                {"title": "🇷🇺 Словари. Операции и методы — egoroff_channel", "url": f"{YT}7_Zrh1--d5o"},
                {"title": "🇷🇺 Словари (dict), методы — Гоша Дударь #10", "url": f"{YT}NaA2H25gxN4"},
                {"title": "🇷🇺 Словари (dict) — itProger #10", "url": f"{YT}W2oO1Y-QDzo"},
            ],
        ],
        "classes": [
            [
                {"title": "🇷🇺 Классы и объекты — Иван Викторович", "url": f"{YT}esSIFatS6kM"},
                {"title": "🇷🇺 Основы ООП, классы — itProger #17", "url": f"{YT}gFRa6qVN980"},
                {"title": "🇷🇺 Что такое ООП — Merion Academy", "url": f"{YT}ChEdFh7Q-Vw"},
            ],
            [
                {"title": "🇷🇺 Основы ООП, классы — itProger #17", "url": f"{YT}gFRa6qVN980"},
                {"title": "🇷🇺 Что такое ООП — Merion Academy", "url": f"{YT}ChEdFh7Q-Vw"},
                {"title": "🇷🇺 Классы и объекты — Иван Викторович", "url": f"{YT}esSIFatS6kM"},
            ],
        ],
        "algorithms": [
            [
                {"title": "🇷🇺 Сортировка пузырьком — egoroff_channel", "url": f"{YT}WBaL7ANQbzQ"},
                {"title": "🇷🇺 Сортировка вставками — selfedu #9", "url": f"{YT}jMWvNTp_wFA"},
                {"title": "🇷🇺 Как работают сортировки — Alek OS", "url": f"{YT}PF7AqefS4MU"},
            ],
        ],
        "regex": [
            [
                {"title": "🇷🇺 Регулярные выражения ч.1 — Иван Викторович", "url": f"{YT}_PSyCOuueFs"},
                {"title": "🇷🇺 Основы RegExp, модуль re — PyLounge", "url": f"{YT}8sv-6AN0_cg"},
                {"title": "🇷🇺 Регулярные выражения ч.2 — Иван Викторович", "url": f"{YT}kbeC4djs0mo"},
            ],
        ],
        "file_io": [
            [
                {"title": "🇷🇺 Работа с файлами — itProger #13", "url": f"{YT}t-xQAhLNYSs"},
                {"title": "🇷🇺 Менеджер with...as — itProger #15", "url": f"{YT}uGsSTZjUoIc"},
                {"title": "🇷🇺 Работа с файлами — Захаров Андрей #20", "url": f"{YT}xoix5pT40xs"},
            ],
        ],
    },

    "javascript": {
        "variables": [
            [
                {"title": "🇷🇺 Переменные var, let, const — глубокий разбор", "url": f"{YT}hJ_hGnvXNdc"},
                {"title": "🇷🇺 Как правильно создавать переменные в JS", "url": f"{YT}BQM09-rrfNs"},
                {"title": "🇷🇺 JavaScript — Полный Курс [11 ЧАСОВ]", "url": f"{YT}CxgOKJh4zWE"},
            ],
            [
                {"title": "🇷🇺 JavaScript Основы — Полный Курс за 6 часов", "url": f"{YT}Bluxbh9CaQ0"},
                {"title": "🇷🇺 Как правильно создавать переменные в JS", "url": f"{YT}BQM09-rrfNs"},
                {"title": "🇷🇺 Переменные var, let, const — глубокий разбор", "url": f"{YT}hJ_hGnvXNdc"},
            ],
        ],
        "math_ops": [
            [
                {"title": "🇷🇺 Prompt и математические операции — JS урок 3.3", "url": f"{YT}ill_GWEmjpA"},
                {"title": "🇷🇺 Числа, объект Math, округление — JS", "url": f"{YT}yIvIAU-7_SY"},
                {"title": "🇷🇺 Операторы и математика в JavaScript", "url": f"{YT}PSjJ3BKtHfo"},
            ],
            [
                {"title": "🇷🇺 Prompt и математические операции (ч.2)", "url": f"{YT}ftUNp_uD_W8"},
                {"title": "🇷🇺 Числа, объект Math, округление — JS", "url": f"{YT}yIvIAU-7_SY"},
                {"title": "🇷🇺 Операторы и математика в JavaScript", "url": f"{YT}PSjJ3BKtHfo"},
            ],
        ],
        "functions": [
            [
                {"title": "🇷🇺 Функции в JS. Область видимости. Параметры", "url": f"{YT}rJK0eMkI3BE"},
                {"title": "🇷🇺 Функции в JavaScript #6", "url": f"{YT}hgxEmdvmNUQ"},
                {"title": "🇷🇺 Функции на практике, стрелочные функции", "url": f"{YT}nGVYdna4kq4"},
            ],
            [
                {"title": "🇷🇺 Функция и return в JavaScript", "url": f"{YT}q7QNFPZwiho"},
                {"title": "🇷🇺 Функции в JS. Область видимости. Параметры", "url": f"{YT}rJK0eMkI3BE"},
                {"title": "🇷🇺 Функции на практике, стрелочные функции", "url": f"{YT}nGVYdna4kq4"},
            ],
        ],
        "if_else": [
            [
                {"title": "🇷🇺 JS условия if else. Тернарный оператор", "url": f"{YT}ugio2BJOO04"},
                {"title": "🇷🇺 Условия (if-else) и switch в JavaScript", "url": f"{YT}Km-HSCqE0o4"},
                {"title": "🇷🇺 IF ELSE в JavaScript. Примеры", "url": f"{YT}tFyRhDZgHaU"},
            ],
            [
                {"title": "🇷🇺 Ветвление If, else, switch — JS v.2.0", "url": f"{YT}OIIBECEaYKI"},
                {"title": "🇷🇺 JS условия if else. Тернарный оператор", "url": f"{YT}ugio2BJOO04"},
                {"title": "🇷🇺 IF ELSE в JavaScript. Примеры", "url": f"{YT}tFyRhDZgHaU"},
            ],
        ],
        "loops": [
            [
                {"title": "🇷🇺 Массивы, циклы (for, while, foreach) — JS", "url": f"{YT}sYRSQU96e_I"},
                {"title": "🇷🇺 Циклы FOR, WHILE — полный курс с задачами", "url": f"{YT}jwrPJ55OZ4k"},
                {"title": "🇷🇺 Циклы while, do while, for в JavaScript", "url": f"{YT}_WlC6UxMyNE"},
            ],
            [
                {"title": "🇷🇺 Циклы FOR, WHILE — полный курс с задачами", "url": f"{YT}jwrPJ55OZ4k"},
                {"title": "🇷🇺 Циклы while, do while, for в JavaScript", "url": f"{YT}_WlC6UxMyNE"},
                {"title": "🇷🇺 Массивы, циклы (for, while, foreach) — JS", "url": f"{YT}sYRSQU96e_I"},
            ],
        ],
        "strings": [
            [
                {"title": "🇷🇺 Работа со строками JS: length, substr, slice", "url": f"{YT}AwzOh-4_oZc"},
                {"title": "🇷🇺 Строки в JS. Методы at, replace, slice", "url": f"{YT}MGrpBVpctNo"},
                {"title": "🇷🇺 Строчные методы JS: slice, substring", "url": f"{YT}YsMR2WclYcM"},
            ],
            [
                {"title": "🇷🇺 Строки в JS. Методы at, replace, slice", "url": f"{YT}MGrpBVpctNo"},
                {"title": "🇷🇺 Строчные методы JS: slice, substring", "url": f"{YT}YsMR2WclYcM"},
                {"title": "🇷🇺 Работа со строками JS: length, substr, slice", "url": f"{YT}AwzOh-4_oZc"},
            ],
        ],
        "arrays": [
            [
                {"title": "🇷🇺 Методы массивов: forEach, map, filter, reduce", "url": f"{YT}SjTTDZX2hIA"},
                {"title": "🇷🇺 Методы массивов: map, reduce, filter", "url": f"{YT}WJUk3GXarMw"},
                {"title": "🇷🇺 Методы массивов — Владилен Минин #12", "url": f"{YT}nEabP9CYCAQ"},
            ],
            [
                {"title": "🇷🇺 Методы массивов: map, reduce, filter", "url": f"{YT}WJUk3GXarMw"},
                {"title": "🇷🇺 Методы массивов — Владилен Минин #12", "url": f"{YT}nEabP9CYCAQ"},
                {"title": "🇷🇺 Методы массивов: forEach, map, filter, reduce", "url": f"{YT}SjTTDZX2hIA"},
            ],
        ],
        "objects": [
            [
                {"title": "🇷🇺 Object.keys, values, entries в JS", "url": f"{YT}RSwpa-HN0y8"},
                {"title": "🇷🇺 Методы массивов к объектам — JS", "url": f"{YT}Ha2geO5Qw_Q"},
                {"title": "🇷🇺 Объекты: ключи и значения — JS", "url": f"{YT}JQnRVtTGd7U"},
            ],
            [
                {"title": "🇷🇺 Перебор объекта. Map и Set — JS", "url": f"{YT}vm-M4m-OH0U"},
                {"title": "🇷🇺 Object.keys, values, entries в JS", "url": f"{YT}RSwpa-HN0y8"},
                {"title": "🇷🇺 Объекты: ключи и значения — JS", "url": f"{YT}JQnRVtTGd7U"},
            ],
        ],
        "classes": [
            [
                {"title": "🇷🇺 Классы JavaScript — полный курс 2024", "url": f"{YT}hcKaQyYW9B0"},
                {"title": "🇷🇺 Классы в JS — наследование, конструктор", "url": f"{YT}us1GTgdUsJo"},
                {"title": "🇷🇺 ООП в JS. Наследование, классы, super", "url": f"{YT}JWwSH92tq7E"},
            ],
            [
                {"title": "🇷🇺 ES6 Классы — Владилен Минин #7", "url": f"{YT}uLY9GXGMXaA"},
                {"title": "🇷🇺 Классы JavaScript — полный курс 2024", "url": f"{YT}hcKaQyYW9B0"},
                {"title": "🇷🇺 ООП в JS. Наследование, классы, super", "url": f"{YT}JWwSH92tq7E"},
            ],
        ],
        "algorithms": [
            [
                {"title": "🇷🇺 Алгоритмы и структуры данных JS — полный курс", "url": f"{YT}NErrGZ64OdE"},
                {"title": "🇷🇺 Алгоритмы и структуры данных — Ulbi TV", "url": f"{YT}hXYHZVMHec0"},
                {"title": "🇷🇺 RegExp. Регулярные выражения — intro", "url": f"{YT}htPtv6r2uOs"},
            ],
        ],
        "regex": [
            [
                {"title": "🇷🇺 RegExp — введение. JavaScript", "url": f"{YT}htPtv6r2uOs"},
                {"title": "🇷🇺 Базовый курс JS: функции, RegExp", "url": f"{YT}HrazmFq4YIg"},
                {"title": "🇷🇺 RegExp — это просто", "url": f"{YT}wMZ6gLNtefQ"},
            ],
        ],
        "file_io": [
            [
                {"title": "🇷🇺 Fetch, XMLHttpRequest, Ajax — Владилен #14", "url": f"{YT}eKCD9djJQKc"},
                {"title": "🇷🇺 AJAX, запросы на сервер + бесплатные API", "url": f"{YT}OaqD8sSuY1k"},
                {"title": "🇷🇺 JS fetch — клиент-серверное взаимодействие", "url": f"{YT}klVGCxWsN2A"},
            ],
        ],
    },

    "frontend": {
        "html_elements": [
            [
                {"title": "🇷🇺 Основы HTML для начинающих (2026)", "url": f"{YT}SKRydSA2bYA"},
                {"title": "🇷🇺 HTML полезные теги и свойства", "url": f"{YT}kEo6y-wSgRU"},
                {"title": "🇷🇺 HTML — Полный курс [3 ЧАСА]", "url": f"{YT}W4MIiV4nZDY"},
            ],
            [
                {"title": "🇷🇺 Начни учить HTML (понятно даже чайнику)", "url": f"{YT}DOEtVdkKwcU"},
                {"title": "🇷🇺 Основы HTML для начинающих (2026)", "url": f"{YT}SKRydSA2bYA"},
                {"title": "🇷🇺 HTML полезные теги и свойства", "url": f"{YT}kEo6y-wSgRU"},
            ],
        ],
        "text_styling": [
            [
                {"title": "🇷🇺 Как подключить шрифты в CSS", "url": f"{YT}fN_ic_MNgAU"},
                {"title": "🇷🇺 Как добавить шрифт в HTML CSS", "url": f"{YT}yjdxUlvG99c"},
                {"title": "🇷🇺 HTML — Полный курс [3 ЧАСА]", "url": f"{YT}W4MIiV4nZDY"},
            ],
        ],
        "colors_bg": [
            [
                {"title": "🇷🇺 CSS фоновый цвет, изображение, градиент", "url": f"{YT}bWoqW6PjqBE"},
                {"title": "🇷🇺 Красивый фон с градиентом на CSS", "url": f"{YT}dePDJ_D-o8A"},
                {"title": "🇷🇺 Красивый градиент в CSS за 1 минуту", "url": f"{YT}uqoR6KB7Hv8"},
            ],
        ],
        "layout": [
            [
                {"title": "🇷🇺 Flexbox CSS практический курс за 6 минут", "url": f"{YT}eVZEwEQg4pg"},
                {"title": "🇷🇺 Flexbox vs Grid: когда и что лучше?", "url": f"{YT}PPBqZ8fuzRg"},
                {"title": "🇷🇺 Flex и Grid: изучаю CSS раскладки", "url": f"{YT}BjQw7gQxNHk"},
            ],
            [
                {"title": "🇷🇺 Как правильно пользоваться Flex-Box", "url": f"{YT}s4K2av6VV1w"},
                {"title": "🇷🇺 CSS Flexbox — Введение", "url": f"{YT}O-ytfplFQ3c"},
                {"title": "🇷🇺 CSS Grid — Введение", "url": f"{YT}LHW_M9mf4Is"},
            ],
        ],
        "selectors": [
            [
                {"title": "🇷🇺 Псевдоклассы и псевдоэлементы CSS #4", "url": f"{YT}nZHrCDJEnw4"},
                {"title": "🇷🇺 CSS селекторы — ответ на собеседовании", "url": f"{YT}81XUV42LEXY"},
                {"title": "🇷🇺 CSS: Псевдоклассы :not и :has на примере", "url": f"{YT}Cz3zIWY_A2U"},
            ],
            [
                {"title": "🇷🇺 ТОП-3 правила для адаптива в CSS", "url": f"{YT}0eyxg9xlQT8"},
                {"title": "🇷🇺 Псевдоклассы и псевдоэлементы CSS #4", "url": f"{YT}nZHrCDJEnw4"},
                {"title": "🇷🇺 CSS: Псевдоклассы :not и :has на примере", "url": f"{YT}Cz3zIWY_A2U"},
            ],
        ],
        "animations": [
            [
                {"title": "🇷🇺 CSS animation и @keyframes за 12 минут", "url": f"{YT}GKgOOuTL0po"},
                {"title": "🇷🇺 Анимации в CSS. @keyframes. Свойство animation", "url": f"{YT}3a_iaHqazHo"},
                {"title": "🇷🇺 CSS анимация — функция steps", "url": f"{YT}jxCwnTqMda0"},
            ],
        ],
        "responsive": [
            [
                {"title": "🇷🇺 Адаптивная верстка CSS. Desktop и mobile first", "url": f"{YT}ahYuxTRjY0g"},
                {"title": "🇷🇺 Адаптивная верстка за 5 минут", "url": f"{YT}ENEviJIMiHA"},
                {"title": "🇷🇺 Медиа-запросы за 2 минуты — CSS", "url": f"{YT}ICO6NwLZx_s"},
            ],
            [
                {"title": "🇷🇺 Медиа-запросы не нужны, если писать стили так", "url": f"{YT}PJJsrca0n-Y"},
                {"title": "🇷🇺 Адаптивная верстка CSS. Desktop и mobile first", "url": f"{YT}ahYuxTRjY0g"},
                {"title": "🇷🇺 Адаптивная верстка за 5 минут", "url": f"{YT}ENEviJIMiHA"},
            ],
        ],
        "forms": [
            [
                {"title": "🇷🇺 HTML формы: form, fieldset, legend, label", "url": f"{YT}_in4LAdxAUA"},
                {"title": "🇷🇺 Всё о select и textarea в HTML", "url": f"{YT}OuHUc5SaLno"},
                {"title": "🇷🇺 HTML form, input, textarea, button", "url": f"{YT}Zt2tFxTUhHo"},
            ],
            [
                {"title": "🇷🇺 Формы: textarea, select, option, optgroup", "url": f"{YT}FMjuLXNTPfU"},
                {"title": "🇷🇺 HTML формы: form, fieldset, legend, label", "url": f"{YT}_in4LAdxAUA"},
                {"title": "🇷🇺 HTML form, input, textarea, button", "url": f"{YT}Zt2tFxTUhHo"},
            ],
        ],
    },

    "scratch": {
        "motion": [
            [
                {"title": "🇷🇺 Координаты и движение Scratch — Пиксель #4", "url": f"{YT}G81fOkh6g7k"},
                {"title": "🇷🇺 Что такое Спрайт — IT Skill #4", "url": f"{YT}HKwVcOYie7k"},
                {"title": "🇷🇺 Траектория движения спрайта — russkihtv", "url": f"{YT}e4tdvAb4QRA"},
            ],
            [
                {"title": "🇷🇺 Что такое Спрайт — IT Skill #4", "url": f"{YT}HKwVcOYie7k"},
                {"title": "🇷🇺 Траектория движения спрайта — russkihtv", "url": f"{YT}e4tdvAb4QRA"},
                {"title": "🇷🇺 Координаты и движение Scratch — Пиксель #4", "url": f"{YT}G81fOkh6g7k"},
            ],
        ],
        "looks": [
            [
                {"title": "🇷🇺 Скретч урок — костюмы", "url": f"{YT}s7CAb1NgxrI"},
                {"title": "🇷🇺 Редактор костюмов — UP! School #38", "url": f"{YT}1bunkknHvJY"},
                {"title": "🇷🇺 Внешний вид, костюмы — Вивитроника", "url": f"{YT}bzWV-tyZL8U"},
            ],
            [
                {"title": "🇷🇺 Редактор костюмов — UP! School #38", "url": f"{YT}1bunkknHvJY"},
                {"title": "🇷🇺 Внешний вид, костюмы — Вивитроника", "url": f"{YT}bzWV-tyZL8U"},
                {"title": "🇷🇺 Скретч урок — костюмы", "url": f"{YT}s7CAb1NgxrI"},
            ],
        ],
        "sound": [
            [
                {"title": "🇷🇺 Звуки и музыка в Scratch — IT-куб TV", "url": f"{YT}zFjKcYMmUic"},
                {"title": "🇷🇺 Фоновые звуки — CODDY School #8", "url": f"{YT}57pwFcpUqOc"},
                {"title": "🇷🇺 Звуки — IT Skill #5", "url": f"{YT}KPZTzlANprQ"},
            ],
            [
                {"title": "🇷🇺 Фоновые звуки — CODDY School #8", "url": f"{YT}57pwFcpUqOc"},
                {"title": "🇷🇺 Звуки — IT Skill #5", "url": f"{YT}KPZTzlANprQ"},
                {"title": "🇷🇺 Scratch уроки — создание первого проекта", "url": f"{YT}Vc8moYRG-bE"},
            ],
        ],
        "events": [
            [
                {"title": "🇷🇺 Передача сообщений — Scratch", "url": f"{YT}dKUvWLbBzJg"},
                {"title": "🇷🇺 Scratch — сообщения и операторы #4", "url": f"{YT}89y4QJp01dQ"},
                {"title": "🇷🇺 Сообщения в Scratch — Co-Learning #6", "url": f"{YT}8R3gS48saN4"},
            ],
            [
                {"title": "🇷🇺 Scratch — сообщения и операторы #4", "url": f"{YT}89y4QJp01dQ"},
                {"title": "🇷🇺 Сообщения в Scratch — Co-Learning #6", "url": f"{YT}8R3gS48saN4"},
                {"title": "🇷🇺 Передача сообщений — Scratch", "url": f"{YT}dKUvWLbBzJg"},
            ],
        ],
        "control": [
            [
                {"title": "🇷🇺 Циклы и ветвления — PapaCoder101 #4", "url": f"{YT}gkiyEDpVzqc"},
                {"title": "🇷🇺 Scratch 3: Циклы — CyberSkill #9", "url": f"{YT}lxHv_YeR9wM"},
                {"title": "🇷🇺 Циклы и ветвления в Scratch", "url": f"{YT}vmWVI0h3TSo"},
            ],
            [
                {"title": "🇷🇺 Scratch 3: Циклы — CyberSkill #9", "url": f"{YT}lxHv_YeR9wM"},
                {"title": "🇷🇺 Циклы и ветвления в Scratch", "url": f"{YT}vmWVI0h3TSo"},
                {"title": "🇷🇺 Циклы и ветвления — PapaCoder101 #4", "url": f"{YT}gkiyEDpVzqc"},
            ],
        ],
        "sensing": [
            [
                {"title": "🇷🇺 Команды «Сенсоры» — Medvedev School #7", "url": f"{YT}xQHbXxp1Ibo"},
                {"title": "🇷🇺 Scratch: таймер — Anzhelika #5", "url": f"{YT}dST3RYV-ZF0"},
                {"title": "🇷🇺 Вопросы по блокам Сенсоры — IT Skill", "url": f"{YT}u5rQPbbzJY0"},
            ],
            [
                {"title": "🇷🇺 Scratch: таймер — Anzhelika #5", "url": f"{YT}dST3RYV-ZF0"},
                {"title": "🇷🇺 Вопросы по блокам Сенсоры — IT Skill", "url": f"{YT}u5rQPbbzJY0"},
                {"title": "🇷🇺 Команды «Сенсоры» — Medvedev School #7", "url": f"{YT}xQHbXxp1Ibo"},
            ],
        ],
        "operators": [
            [
                {"title": "🇷🇺 Scratch: блок «Операторы» — HeyGo #6", "url": f"{YT}Ku49b0fkHBM"},
                {"title": "🇷🇺 Операторы: Scratch для детей", "url": f"{YT}BvCXHKWcqis"},
                {"title": "🇷🇺 Арифметические операторы в Scratch", "url": f"{YT}-scpN0I6vnE"},
            ],
            [
                {"title": "🇷🇺 Операторы: Scratch для детей", "url": f"{YT}BvCXHKWcqis"},
                {"title": "🇷🇺 Арифметические операторы в Scratch", "url": f"{YT}-scpN0I6vnE"},
                {"title": "🇷🇺 Scratch: блок «Операторы» — HeyGo #6", "url": f"{YT}Ku49b0fkHBM"},
            ],
        ],
        "variables": [
            [
                {"title": "🇷🇺 Списки в Scratch — Пиксель", "url": f"{YT}ppR46SU8ZMI"},
                {"title": "🇷🇺 Переменные, списки и блоки — Mr. Programmist", "url": f"{YT}dZCcBHOce0c"},
                {"title": "🇷🇺 Заменить переменные списком — MonoculaRus", "url": f"{YT}QIpHjdvo8kg"},
            ],
            [
                {"title": "🇷🇺 Переменные, списки и блоки — Mr. Programmist", "url": f"{YT}dZCcBHOce0c"},
                {"title": "🇷🇺 Заменить переменные списком — MonoculaRus", "url": f"{YT}QIpHjdvo8kg"},
                {"title": "🇷🇺 Списки в Scratch — Пиксель", "url": f"{YT}ppR46SU8ZMI"},
            ],
        ],
        "my_blocks": [
            [
                {"title": "🇷🇺 Scratch: создание блока — PlaySchool #3", "url": f"{YT}Qk1HiIBRuwg"},
                {"title": "🇷🇺 Процедуры (другие блоки) — Scratch Ru", "url": f"{YT}E9lBESircq4"},
                {"title": "🇷🇺 Создание и использование процедур — Айтигенио", "url": f"{YT}d4F1OwMvtSs"},
            ],
        ],
    },

    "alextype": {
        "typing": [
            [
                {"title": "🇷🇺 Слепая печать. Бесплатный тренажер — Kodiki", "url": f"{YT}YZFDWRFOswQ"},
                {"title": "🇷🇺 Слепая печать, как научиться — EasyCode", "url": f"{YT}udI4mLyykr4"},
                {"title": "🇷🇺 Слепая печать за неделю — программист с нуля", "url": f"{YT}l2LZzdgHccw"},
            ],
            [
                {"title": "🇷🇺 Слепая печать, как научиться — EasyCode", "url": f"{YT}udI4mLyykr4"},
                {"title": "🇷🇺 Слепая печать за неделю — программист с нуля", "url": f"{YT}l2LZzdgHccw"},
                {"title": "🇷🇺 Слепая печать. Бесплатный тренажер — Kodiki", "url": f"{YT}YZFDWRFOswQ"},
            ],
        ],
    },
}


def main():
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    topic_counters = {}
    updated = 0
    skipped = 0

    for task in data.get("tasks", []):
        if task.get("task_type") != "tutorial":
            continue

        cat = task.get("category", "")
        topic = task.get("topic", "")
        cat_pool = VIDEOS.get(cat, {})
        topic_pool = cat_pool.get(topic, [])

        if not topic_pool:
            skipped += 1
            print(f"  ⚠ No videos for {cat}/{topic} ({task['id']})")
            continue

        key = f"{cat}:{topic}"
        idx = topic_counters.get(key, 0)
        topic_counters[key] = idx + 1
        video_set = topic_pool[idx % len(topic_pool)]

        if "resources" not in task:
            task["resources"] = {}
        task["resources"]["videos"] = list(video_set)
        task["video_url"] = video_set[0]["url"]
        updated += 1

    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Updated {updated} tutorials")
    if skipped:
        print(f"⚠ Skipped {skipped}")


if __name__ == "__main__":
    main()
