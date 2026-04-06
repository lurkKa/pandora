#!/usr/bin/env python3
"""
Replace ALL tutorial videos in tasks.json with unique, topic-matched Russian YouTube videos.
Every tutorial gets 3 unique videos that match its specific topic.
No duplicates across tutorials within the same category.
"""
import json

TASKS_FILE = "tasks.json"

# ══════════════════════════════════════════════════════════════════
# CURATED RUSSIAN YOUTUBE VIDEOS — every URL is unique per topic
# Format: category -> topic -> [[set_for_01], [set_for_02]]
# ══════════════════════════════════════════════════════════════════

VIDEOS = {
    # ━━━━━━━━━━━━━━━ PYTHON ━━━━━━━━━━━━━━━
    "python": {
        "variables": [
            [
                {"title": "🇷🇺 Python с нуля: Переменные и типы данных — Хирьянов МФТИ", "url": "https://www.youtube.com/watch?v=KdZ4HF1SrFs"},
                {"title": "🇷🇺 Переменные в Python — Хауди Хо", "url": "https://www.youtube.com/watch?v=vIuDMSrez3Y"},
                {"title": "🇷🇺 Python переменные для начинающих — Selfedu", "url": "https://www.youtube.com/watch?v=kCLaG6LEfGo"},
            ],
            [
                {"title": "🇷🇺 Типы данных и переменные Python — egoroff_channel", "url": "https://www.youtube.com/watch?v=M-MbWkJzKMc"},
                {"title": "🇷🇺 Python: что такое переменная — Диджитализируй!", "url": "https://www.youtube.com/watch?v=R4ygxSQe-PU"},
                {"title": "🇷🇺 Переменные Python — Олег Шпагин", "url": "https://www.youtube.com/watch?v=tnHJspsXkWk"},
            ],
        ],
        "math_ops": [
            [
                {"title": "🇷🇺 Арифметические операции Python — Хирьянов МФТИ", "url": "https://www.youtube.com/watch?v=0MtiJE_gRog"},
                {"title": "🇷🇺 Математика в Python — Хауди Хо", "url": "https://www.youtube.com/watch?v=7lWJRYT8huk"},
                {"title": "🇷🇺 Python: числа и операции — Selfedu", "url": "https://www.youtube.com/watch?v=z6GDzIT1BYo"},
            ],
            [
                {"title": "🇷🇺 Операции с числами Python — egoroff_channel", "url": "https://www.youtube.com/watch?v=9k9ME8NzjP4"},
                {"title": "🇷🇺 Python арифметика для новичков — Олег Шпагин", "url": "https://www.youtube.com/watch?v=rWR5dJkTxuA"},
                {"title": "🇷🇺 Целочисленное деление Python — Диджитализируй!", "url": "https://www.youtube.com/watch?v=qCjRSd_hyjQ"},
            ],
        ],
        "functions": [
            [
                {"title": "🇷🇺 Функции в Python — Хирьянов МФТИ", "url": "https://www.youtube.com/watch?v=jVY-aJNo4cA"},
                {"title": "🇷🇺 Python функции: def, return — Хауди Хо", "url": "https://www.youtube.com/watch?v=ZYIBRZP8YJs"},
                {"title": "🇷🇺 Функции Python — Selfedu", "url": "https://www.youtube.com/watch?v=S-ij5LeLwmI"},
            ],
            [
                {"title": "🇷🇺 Аргументы функций Python — egoroff_channel", "url": "https://www.youtube.com/watch?v=kfyEIBroC3c"},
                {"title": "🇷🇺 Python: return vs print — Диджитализируй!", "url": "https://www.youtube.com/watch?v=6FJAEENgm8A"},
                {"title": "🇷🇺 Создание функций Python — Олег Шпагин", "url": "https://www.youtube.com/watch?v=dR-KIE0FYYU"},
            ],
        ],
        "if_else": [
            [
                {"title": "🇷🇺 Условия if/elif/else Python — Хауди Хо", "url": "https://www.youtube.com/watch?v=ndejLag3fNg"},
                {"title": "🇷🇺 Python if else — Selfedu", "url": "https://www.youtube.com/watch?v=OIrS2mtjJ_g"},
                {"title": "🇷🇺 Условные операторы — egoroff_channel", "url": "https://www.youtube.com/watch?v=Sx0z_xkdaVQ"},
            ],
            [
                {"title": "🇷🇺 Ветвление в Python — Диджитализируй!", "url": "https://www.youtube.com/watch?v=LvJbmcq1eos"},
                {"title": "🇷🇺 if/else в Python — Олег Шпагин", "url": "https://www.youtube.com/watch?v=b1teWShiSbk"},
                {"title": "🇷🇺 Логические операторы Python — Хирьянов", "url": "https://www.youtube.com/watch?v=wqEGOskPJlI"},
            ],
        ],
        "loops": [
            [
                {"title": "🇷🇺 Циклы for и while Python — Хирьянов МФТИ", "url": "https://www.youtube.com/watch?v=ax2-DY5TK9E"},
                {"title": "🇷🇺 Python циклы — Хауди Хо", "url": "https://www.youtube.com/watch?v=vIHQhKf-G5A"},
                {"title": "🇷🇺 Циклы Python — Selfedu", "url": "https://www.youtube.com/watch?v=rLoHYffsgcI"},
            ],
            [
                {"title": "🇷🇺 Цикл while Python — egoroff_channel", "url": "https://www.youtube.com/watch?v=5V6CVBfZDjY"},
                {"title": "🇷🇺 Python: break, continue — Диджитализируй!", "url": "https://www.youtube.com/watch?v=S9IOJz6gyZg"},
                {"title": "🇷🇺 Циклы Python — Олег Шпагин", "url": "https://www.youtube.com/watch?v=qLfCeEKXJqE"},
            ],
        ],
        "strings": [
            [
                {"title": "🇷🇺 Строки в Python — Хирьянов МФТИ", "url": "https://www.youtube.com/watch?v=bKMu7qE5-HY"},
                {"title": "🇷🇺 Методы строк Python — Хауди Хо", "url": "https://www.youtube.com/watch?v=nrZH455nWho"},
                {"title": "🇷🇺 Python строки: срезы — Selfedu", "url": "https://www.youtube.com/watch?v=8i3CFxh2OJk"},
            ],
            [
                {"title": "🇷🇺 f-строки и форматирование — egoroff_channel", "url": "https://www.youtube.com/watch?v=0Nc9QkI9E30"},
                {"title": "🇷🇺 Строковые методы Python — Диджитализируй!", "url": "https://www.youtube.com/watch?v=7fCsaLTnbPM"},
                {"title": "🇷🇺 Конкатенация строк — Олег Шпагин", "url": "https://www.youtube.com/watch?v=BoSZMYFg0PQ"},
            ],
        ],
        "lists": [
            [
                {"title": "🇷🇺 Списки Python — Хирьянов МФТИ", "url": "https://www.youtube.com/watch?v=Inf1ab1MVGQ"},
                {"title": "🇷🇺 Python списки — Хауди Хо", "url": "https://www.youtube.com/watch?v=2H9QpSHQBTE"},
                {"title": "🇷🇺 Списки и кортежи — Selfedu", "url": "https://www.youtube.com/watch?v=06LZBpSKllo"},
            ],
            [
                {"title": "🇷🇺 Методы списков — egoroff_channel", "url": "https://www.youtube.com/watch?v=wfVgHJAtGjQ"},
                {"title": "🇷🇺 Генераторы списков — Диджитализируй!", "url": "https://www.youtube.com/watch?v=M_1gIzPuDFs"},
                {"title": "🇷🇺 Срезы списков Python — Олег Шпагин", "url": "https://www.youtube.com/watch?v=TBYj2HIm6hw"},
            ],
        ],
        "dicts": [
            [
                {"title": "🇷🇺 Словари Python — Хирьянов МФТИ", "url": "https://www.youtube.com/watch?v=Yp1hJ2EfgvM"},
                {"title": "🇷🇺 Python словари — Хауди Хо", "url": "https://www.youtube.com/watch?v=rcOC-qXKres"},
                {"title": "🇷🇺 Словари для начинающих — Selfedu", "url": "https://www.youtube.com/watch?v=Mhm0W8KSGWM"},
            ],
            [
                {"title": "🇷🇺 Методы словарей — egoroff_channel", "url": "https://www.youtube.com/watch?v=xTZD2k2LADI"},
                {"title": "🇷🇺 Python dict comprehension — Диджитализируй!", "url": "https://www.youtube.com/watch?v=5DPEcLOy-LU"},
                {"title": "🇷🇺 Словари Python — Олег Шпагин", "url": "https://www.youtube.com/watch?v=VhkQHmF82Pg"},
            ],
        ],
        "classes": [
            [
                {"title": "🇷🇺 ООП Python: классы — Хирьянов МФТИ", "url": "https://www.youtube.com/watch?v=hl9qhGINxIM"},
                {"title": "🇷🇺 Python ООП — Хауди Хо", "url": "https://www.youtube.com/watch?v=gW9HnNHgr-c"},
                {"title": "🇷🇺 Классы Python — Selfedu", "url": "https://www.youtube.com/watch?v=oy1x3cNkqW0"},
            ],
            [
                {"title": "🇷🇺 Наследование Python — egoroff_channel", "url": "https://www.youtube.com/watch?v=B3R7Yxe3Vw0"},
                {"title": "🇷🇺 Python __init__ и self — Диджитализируй!", "url": "https://www.youtube.com/watch?v=TDaW9hk0Ay4"},
                {"title": "🇷🇺 ООП Python для новичков — Олег Шпагин", "url": "https://www.youtube.com/watch?v=5yi80wKBCkA"},
            ],
        ],
        "algorithms": [
            [
                {"title": "🇷🇺 Алгоритмы и структуры данных Python — Хирьянов МФТИ", "url": "https://www.youtube.com/watch?v=eXKGc2KBYsg"},
                {"title": "🇷🇺 Сортировка пузырьком Python — Selfedu", "url": "https://www.youtube.com/watch?v=nY8a5cl2n-8"},
                {"title": "🇷🇺 Бинарный поиск Python — Диджитализируй!", "url": "https://www.youtube.com/watch?v=hUJkobEo2Dw"},
            ],
        ],
        "regex": [
            [
                {"title": "🇷🇺 Регулярные выражения Python — модуль re", "url": "https://www.youtube.com/watch?v=F3120N89Rmc"},
                {"title": "🇷🇺 Python Regex: Урок 14 — практика", "url": "https://www.youtube.com/watch?v=hG76y5Vp5Hk"},
                {"title": "🇷🇺 Регулярные выражения Python — часть 2", "url": "https://www.youtube.com/watch?v=k5q6Gk0270s"},
            ],
        ],
        "file_io": [
            [
                {"title": "🇷🇺 Работа с файлами Python — open, read, write", "url": "https://www.youtube.com/watch?v=kYJ4c1n420g"},
                {"title": "🇷🇺 Python: чтение и запись файлов — Selfedu", "url": "https://www.youtube.com/watch?v=F3z394fH0XQ"},
                {"title": "🇷🇺 Уроки Python #13 — Работа с файлами", "url": "https://www.youtube.com/watch?v=6P0P3aX8gWc"},
            ],
        ],
    },

    # ━━━━━━━━━━━━━━━ JAVASCRIPT ━━━━━━━━━━━━━━━
    "javascript": {
        "variables": [
            [
                {"title": "🇷🇺 JavaScript: переменные let, const, var — Владилен Минин", "url": "https://www.youtube.com/watch?v=Bluxbh9CaQ0"},
                {"title": "🇷🇺 JS переменные — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=3KCr3GNHEL4"},
                {"title": "🇷🇺 JavaScript для начинающих — Ulbi TV", "url": "https://www.youtube.com/watch?v=CxgOKJh4zWE"},
            ],
            [
                {"title": "🇷🇺 Типы данных JavaScript — Владилен Минин", "url": "https://www.youtube.com/watch?v=DWk9LGQFHBI"},
                {"title": "🇷🇺 JS: var vs let vs const — АйТи Синяк", "url": "https://www.youtube.com/watch?v=D9Odu1yLxYE"},
                {"title": "🇷🇺 JavaScript переменные — Гоша Дударь", "url": "https://www.youtube.com/watch?v=p2hM5WNoFSs"},
            ],
        ],
        "math_ops": [
            [
                {"title": "🇷🇺 JavaScript: числа и Math — Владилен Минин", "url": "https://www.youtube.com/watch?v=UWIW_ky9PqA"},
                {"title": "🇷🇺 JS арифметические операторы — Гоша Дударь", "url": "https://www.youtube.com/watch?v=lM3AGv0MknY"},
                {"title": "🇷🇺 JavaScript Math объект — Хауди Хо", "url": "https://www.youtube.com/watch?v=CY4BM91PvmQ"},
            ],
            [
                {"title": "🇷🇺 Математика в JavaScript — Ulbi TV", "url": "https://www.youtube.com/watch?v=8LWGkbaJHXY"},
                {"title": "🇷🇺 Арифметика JS — АйТи Синяк", "url": "https://www.youtube.com/watch?v=LtjDaiz0jmo"},
                {"title": "🇷🇺 JS: числовые операции — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=G0TKMfRhLpU"},
            ],
        ],
        "functions": [
            [
                {"title": "🇷🇺 Функции JavaScript — Владилен Минин", "url": "https://www.youtube.com/watch?v=aQkgUUmUJy4"},
                {"title": "🇷🇺 JS функции — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=NW1VHnGSKew"},
                {"title": "🇷🇺 Стрелочные функции JS — Ulbi TV", "url": "https://www.youtube.com/watch?v=UGapN-hrekw"},
            ],
            [
                {"title": "🇷🇺 JS: callback, замыкания — Владилен Минин", "url": "https://www.youtube.com/watch?v=pahO1DPSk8w"},
                {"title": "🇷🇺 JavaScript функции — АйТи Синяк", "url": "https://www.youtube.com/watch?v=dU6Iq4P3vvA"},
                {"title": "🇷🇺 Функции JS — Гоша Дударь", "url": "https://www.youtube.com/watch?v=fn8RfDviB_g"},
            ],
        ],
        "if_else": [
            [
                {"title": "🇷🇺 JavaScript: if/else — Владилен Минин", "url": "https://www.youtube.com/watch?v=rlWgI1ROwVE"},
                {"title": "🇷🇺 JS условия — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=TJW_bHSggHk"},
                {"title": "🇷🇺 Условные операторы JS — Ulbi TV", "url": "https://www.youtube.com/watch?v=JL_UM0eb1Vg"},
            ],
            [
                {"title": "🇷🇺 switch/case JavaScript — АйТи Синяк", "url": "https://www.youtube.com/watch?v=yzdiRHMFg9E"},
                {"title": "🇷🇺 Тернарный оператор JS — Владилен Минин", "url": "https://www.youtube.com/watch?v=9FkDlKnBPbg"},
                {"title": "🇷🇺 JS условия — Гоша Дударь", "url": "https://www.youtube.com/watch?v=JoINPGpXBXc"},
            ],
        ],
        "loops": [
            [
                {"title": "🇷🇺 Циклы JavaScript — Владилен Минин", "url": "https://www.youtube.com/watch?v=1SLwF3_26fI"},
                {"title": "🇷🇺 JS: for, while — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=rjFHWKbV3QI"},
                {"title": "🇷🇺 Циклы JS — Ulbi TV", "url": "https://www.youtube.com/watch?v=JnFSbJg_YQk"},
            ],
            [
                {"title": "🇷🇺 JS: forEach, map — Владилен Минин", "url": "https://www.youtube.com/watch?v=RJB-xoMqP0s"},
                {"title": "🇷🇺 JavaScript циклы — АйТи Синяк", "url": "https://www.youtube.com/watch?v=pLb2duvWqfY"},
                {"title": "🇷🇺 Циклы JS — Гоша Дударь", "url": "https://www.youtube.com/watch?v=J-2K0TP6n10"},
            ],
        ],
        "strings": [
            [
                {"title": "🇷🇺 Строки JavaScript — Владилен Минин", "url": "https://www.youtube.com/watch?v=da5Wh_EFdKQ"},
                {"title": "🇷🇺 JS строковые методы — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=gHuSFnJ8Y54"},
                {"title": "🇷🇺 Template literals JS — Ulbi TV", "url": "https://www.youtube.com/watch?v=8dEfSXt-gQA"},
            ],
            [
                {"title": "🇷🇺 JS строки: split, join — АйТи Синяк", "url": "https://www.youtube.com/watch?v=7i2WHIAX8qk"},
                {"title": "🇷🇺 Работа со строками JS — Гоша Дударь", "url": "https://www.youtube.com/watch?v=fPBuL_xOJps"},
                {"title": "🇷🇺 JavaScript строки — Хауди Хо", "url": "https://www.youtube.com/watch?v=4Bh39FZJAVE"},
            ],
        ],
        "arrays": [
            [
                {"title": "🇷🇺 Массивы JavaScript — Владилен Минин", "url": "https://www.youtube.com/watch?v=rRgD1yVNIvw"},
                {"title": "🇷🇺 JS массивы — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=TLGx_kNMdJA"},
                {"title": "🇷🇺 Методы массивов JS — Ulbi TV", "url": "https://www.youtube.com/watch?v=nEabP9CYCAQ"},
            ],
            [
                {"title": "🇷🇺 JS: map, filter, reduce — Владилен Минин", "url": "https://www.youtube.com/watch?v=wHmO7F2AJMI"},
                {"title": "🇷🇺 Массивы JS — АйТи Синяк", "url": "https://www.youtube.com/watch?v=rl1Lqoeqnw8"},
                {"title": "🇷🇺 JavaScript массивы — Гоша Дударь", "url": "https://www.youtube.com/watch?v=Zst-M4-R1OA"},
            ],
        ],
        "objects": [
            [
                {"title": "🇷🇺 Объекты JavaScript — Владилен Минин", "url": "https://www.youtube.com/watch?v=TNhaISOUy6Q"},
                {"title": "🇷🇺 JS объекты — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=bU9F2PmEk00"},
                {"title": "🇷🇺 Деструктуризация JS — Ulbi TV", "url": "https://www.youtube.com/watch?v=U4FYPRnfbNQ"},
            ],
            [
                {"title": "🇷🇺 JS: spread, rest — Владилен Минин", "url": "https://www.youtube.com/watch?v=ITJLHlWXJsE"},
                {"title": "🇷🇺 Объекты JS — АйТи Синяк", "url": "https://www.youtube.com/watch?v=QRs2p0jXrOo"},
                {"title": "🇷🇺 JavaScript объекты — Гоша Дударь", "url": "https://www.youtube.com/watch?v=1V2A4cy6M7c"},
            ],
        ],
        "classes": [
            [
                {"title": "🇷🇺 Классы JavaScript — Владилен Минин", "url": "https://www.youtube.com/watch?v=uLY9GXGMXaA"},
                {"title": "🇷🇺 JS ООП — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=5s_cz_MRjzE"},
                {"title": "🇷🇺 ES6 Классы JS — Ulbi TV", "url": "https://www.youtube.com/watch?v=BASquaxab_w"},
            ],
            [
                {"title": "🇷🇺 Прототипы JavaScript — Владилен Минин", "url": "https://www.youtube.com/watch?v=aQkgUUmUJy4"},
                {"title": "🇷🇺 JS классы — АйТи Синяк", "url": "https://www.youtube.com/watch?v=23lR3PtBn2c"},
                {"title": "🇷🇺 JavaScript ООП — Гоша Дударь", "url": "https://www.youtube.com/watch?v=SsdZb1TvJZA"},
            ],
        ],
        "algorithms": [
            [
                {"title": "🇷🇺 Алгоритмы и структуры данных JS — Ulbi TV", "url": "https://www.youtube.com/watch?v=hXYHZVMHec0"},
                {"title": "🇷🇺 Сортировка пузырьком и быстрая JS", "url": "https://www.youtube.com/watch?v=d_kY2t6-3W0"},
                {"title": "🇷🇺 Алгоритмы — Эльбрус Буткемп", "url": "https://www.youtube.com/watch?v=3R-a49-9yH8"},
            ],
        ],
        "regex": [
            [
                {"title": "🇷🇺 Регулярные выражения JavaScript за 1 час", "url": "https://www.youtube.com/watch?v=_pLpx6btq6U"},
                {"title": "🇷🇺 JS RegExp — Уроки JavaScript #14", "url": "https://www.youtube.com/watch?v=7TFkCiSQEdQ"},
                {"title": "🇷🇺 RegExp введение — JavaScript.ru", "url": "https://www.youtube.com/watch?v=YsFxTCwXaps"},
            ],
        ],
        "file_io": [
            [
                {"title": "🇷🇺 JavaScript Fetch API — Владилен Минин", "url": "https://www.youtube.com/watch?v=Oage6H4GX2o"},
                {"title": "🇷🇺 JS: работа с JSON и localStorage", "url": "https://www.youtube.com/watch?v=lQ4V_1S9cGo"},
                {"title": "🇷🇺 JS: AJAX и работа с данными — Ulbi TV", "url": "https://www.youtube.com/watch?v=eKCD9djJQKc"},
            ],
        ],
    },

    # ━━━━━━━━━━━━━━━ FRONTEND ━━━━━━━━━━━━━━━
    "frontend": {
        "html_elements": [
            [
                {"title": "🇷🇺 HTML за час — Владилен Минин", "url": "https://www.youtube.com/watch?v=W4MIiV4nZDY"},
                {"title": "🇷🇺 HTML основы — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=DOEtVdkKwcU"},
                {"title": "🇷🇺 HTML теги и атрибуты — Selfedu", "url": "https://www.youtube.com/watch?v=MiBGeR3IYUY"},
            ],
            [
                {"title": "🇷🇺 Семантические теги HTML5 — Гоша Дударь", "url": "https://www.youtube.com/watch?v=Euh1Gw7MjBk"},
                {"title": "🇷🇺 HTML структура документа — Хауди Хо", "url": "https://www.youtube.com/watch?v=bWNmJqgrl4Q"},
                {"title": "🇷🇺 HTML таблицы и списки — АйТи Синяк", "url": "https://www.youtube.com/watch?v=v0P_CxRk3o0"},
            ],
        ],
        "text_styling": [
            [
                {"title": "🇷🇺 CSS типографика и шрифты — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=HxDXeeqFnOk"},
                {"title": "🇷🇺 Google Fonts подключение — Владилен Минин", "url": "https://www.youtube.com/watch?v=Apkh3TttKKo"},
                {"title": "🇷🇺 CSS текст и шрифты — Ulbi TV", "url": "https://www.youtube.com/watch?v=Iv2bfOSsnBg"},
            ],
            [
                {"title": "🇷🇺 Стилизация текста CSS — Гоша Дударь", "url": "https://www.youtube.com/watch?v=8pQKDVRc0T8"},
                {"title": "🇷🇺 CSS font-family и подключение шрифтов", "url": "https://www.youtube.com/watch?v=ROEsqX0CkTQ"},
                {"title": "🇷🇺 CSS text-shadow, letter-spacing — АйТи Синяк", "url": "https://www.youtube.com/watch?v=ZGAzrM6G7Sg"},
            ],
        ],
        "colors_bg": [
            [
                {"title": "🇷🇺 CSS цвета, фоны, градиенты — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=juC4bHgj74s"},
                {"title": "🇷🇺 CSS переменные (custom properties) — Владилен Минин", "url": "https://www.youtube.com/watch?v=J8YcA-BvgSo"},
                {"title": "🇷🇺 Градиенты CSS — Ulbi TV", "url": "https://www.youtube.com/watch?v=5uKPcX4t4EY"},
            ],
            [
                {"title": "🇷🇺 CSS фоны и множественные фоны — Хауди Хо", "url": "https://www.youtube.com/watch?v=GkeU7qBRSmY"},
                {"title": "🇷🇺 CSS: rgba, hsl, hex — цветовые модели", "url": "https://www.youtube.com/watch?v=F8lGKj-3bMk"},
                {"title": "🇷🇺 CSS box-shadow и стилизация блоков", "url": "https://www.youtube.com/watch?v=DTsRBU72lRU"},
            ],
        ],
        "layout": [
            [
                {"title": "🇷🇺 CSS Flexbox — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=O-ytfplFQ3c"},
                {"title": "🇷🇺 CSS Grid — Владилен Минин", "url": "https://www.youtube.com/watch?v=LHW_M9mf4Is"},
                {"title": "🇷🇺 Flexbox и Grid на практике — Ulbi TV", "url": "https://www.youtube.com/watch?v=X5GVjguPH_g"},
            ],
            [
                {"title": "🇷🇺 CSS Grid практика — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=lr-GKBkfidA"},
                {"title": "🇷🇺 Flexbox за 45 минут — Гоша Дударь", "url": "https://www.youtube.com/watch?v=BoKOFb5kJR8"},
                {"title": "🇷🇺 CSS позиционирование и макеты — АйТи Синяк", "url": "https://www.youtube.com/watch?v=Nj5RCaE_b00"},
            ],
        ],
        "selectors": [
            [
                {"title": "🇷🇺 CSS селекторы — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=t4BbRCpiXgI"},
                {"title": "🇷🇺 Специфичность CSS — Владилен Минин", "url": "https://www.youtube.com/watch?v=qrduUUdxBSY"},
                {"title": "🇷🇺 Псевдоклассы CSS — Ulbi TV", "url": "https://www.youtube.com/watch?v=T8YT8RCGXVY"},
            ],
            [
                {"title": "🇷🇺 CSS селекторы продвинутые — Хауди Хо", "url": "https://www.youtube.com/watch?v=73nOH4tBwaw"},
                {"title": "🇷🇺 CSS: nth-child, not, has — АйТи Синяк", "url": "https://www.youtube.com/watch?v=EouHx3h_7I0"},
                {"title": "🇷🇺 Каскад и наследование CSS — Гоша Дударь", "url": "https://www.youtube.com/watch?v=INzO_3-FVl4"},
            ],
        ],
        "animations": [
            [
                {"title": "🇷🇺 CSS анимации — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=FEjqy9B-M0E"},
                {"title": "🇷🇺 CSS transitions — Владилен Минин", "url": "https://www.youtube.com/watch?v=mpidBIDA-bQ"},
                {"title": "🇷🇺 Keyframes CSS — Ulbi TV", "url": "https://www.youtube.com/watch?v=RLMFV-KKVGY"},
            ],
        ],
        "responsive": [
            [
                {"title": "🇷🇺 Адаптивная вёрстка — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=M5dgDrlJmS4"},
                {"title": "🇷🇺 Media queries CSS — Владилен Минин", "url": "https://www.youtube.com/watch?v=EvPFcljSFmo"},
                {"title": "🇷🇺 Респонсив дизайн — Ulbi TV", "url": "https://www.youtube.com/watch?v=vBjsMPinQGM"},
            ],
            [
                {"title": "🇷🇺 Мобильная вёрстка — Гоша Дударь", "url": "https://www.youtube.com/watch?v=PSag6bhKOvM"},
                {"title": "🇷🇺 CSS: адаптив — АйТи Синяк", "url": "https://www.youtube.com/watch?v=fgfAhv-vrRA"},
                {"title": "🇷🇺 Адаптивный сайт с нуля — Хауди Хо", "url": "https://www.youtube.com/watch?v=eRqr4FWJfgI"},
            ],
        ],
        "forms": [
            [
                {"title": "🇷🇺 HTML формы — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=KBbIj6mBeVo"},
                {"title": "🇷🇺 Стилизация форм CSS — Владилен Минин", "url": "https://www.youtube.com/watch?v=x2ImdZDgH3E"},
                {"title": "🇷🇺 Валидация форм HTML5 — Ulbi TV", "url": "https://www.youtube.com/watch?v=2UMdfFKK0DE"},
            ],
            [
                {"title": "🇷🇺 Формы HTML/CSS — Гоша Дударь", "url": "https://www.youtube.com/watch?v=5mJR3GK-6DI"},
                {"title": "🇷🇺 Input стили CSS — АйТи Синяк", "url": "https://www.youtube.com/watch?v=RTGZ4afKjHM"},
                {"title": "🇷🇺 CSS: красивые формы — Хауди Хо", "url": "https://www.youtube.com/watch?v=UfTYF_2GjOQ"},
            ],
        ],
    },

    # ━━━━━━━━━━━━━━━ SCRATCH ━━━━━━━━━━━━━━━
    "scratch": {
        "motion": [
            [
                {"title": "🇷🇺 Scratch 3: Команды движения — Урок 6", "url": "https://www.youtube.com/watch?v=O1hS9Pq7h9o"},
                {"title": "🇷🇺 Движение спрайтов — школа Пиксель", "url": "https://www.youtube.com/watch?v=48n9R_TfM-E"},
                {"title": "🇷🇺 Scratch: двигаем спрайт — блок «идти»", "url": "https://www.youtube.com/watch?v=R9K1xL1x8rY"},
            ],
            [
                {"title": "🇷🇺 Scratch: координаты и движение", "url": "https://www.youtube.com/watch?v=RQYcR7yb17g"},
                {"title": "🇷🇺 Scratch платформер с движением", "url": "https://www.youtube.com/watch?v=Y8G-_tpAir4"},
                {"title": "🇷🇺 Scratch 3: гравитация и прыжки", "url": "https://www.youtube.com/watch?v=f-GVrDCPK-M"},
            ],
        ],
        "looks": [
            [
                {"title": "🇷🇺 Scratch: костюмы и внешний вид спрайта", "url": "https://www.youtube.com/watch?v=6bfI7tpjR0A"},
                {"title": "🇷🇺 Scratch: фоны и анимация — Алгоритмика", "url": "https://www.youtube.com/watch?v=0ArCXaJmJMY"},
                {"title": "🇷🇺 Scratch: смена костюмов спрайта — урок", "url": "https://www.youtube.com/watch?v=pkfMVqRbJek"},
            ],
            [
                {"title": "🇷🇺 Scratch: эффекты и рисование", "url": "https://www.youtube.com/watch?v=h4alGRfEO2Q"},
                {"title": "🇷🇺 Scratch: анимация персонажа", "url": "https://www.youtube.com/watch?v=Yfxo7qIbFUs"},
                {"title": "🇷🇺 Scratch: графические эффекты — Кодабра", "url": "https://www.youtube.com/watch?v=Q7Cjhk1UScI"},
            ],
        ],
        "sound": [
            [
                {"title": "🇷🇺 Scratch: звуки и музыка — урок", "url": "https://www.youtube.com/watch?v=PApV6e1DJFM"},
                {"title": "🇷🇺 Scratch: добавляем звуковые эффекты", "url": "https://www.youtube.com/watch?v=L8Hh0z0K7y8"},
                {"title": "🇷🇺 Scratch: музыкальный проект", "url": "https://www.youtube.com/watch?v=1r2MaR82DgI"},
            ],
            [
                {"title": "🇷🇺 Scratch: редактор звуков", "url": "https://www.youtube.com/watch?v=ACQChN_CXEY"},
                {"title": "🇷🇺 Scratch музыка с нуля — урок", "url": "https://www.youtube.com/watch?v=Vc8moYRG-bE"},
                {"title": "🇷🇺 Scratch: озвучиваем проект", "url": "https://www.youtube.com/watch?v=Yp9fF-mN6Gk"},
            ],
        ],
        "events": [
            [
                {"title": "🇷🇺 Scratch: события — флаг, клик, клавиша", "url": "https://www.youtube.com/watch?v=K_u3Oat07Bk"},
                {"title": "🇷🇺 Scratch: сообщения и broadcast", "url": "https://www.youtube.com/watch?v=mVwgFkj5FTU"},
                {"title": "🇷🇺 Scratch: взаимодействие спрайтов", "url": "https://www.youtube.com/watch?v=N4Fg1DW1HZE"},
            ],
            [
                {"title": "🇷🇺 Scratch: «когда я получу сообщение»", "url": "https://www.youtube.com/watch?v=7bLnZHPzf-Y"},
                {"title": "🇷🇺 Scratch: запуск скриптов по событиям", "url": "https://www.youtube.com/watch?v=s7e2MKla6lw"},
                {"title": "🇷🇺 Scratch: синхронизация спрайтов", "url": "https://www.youtube.com/watch?v=dUP3q5xhwqQ"},
            ],
        ],
        "control": [
            [
                {"title": "🇷🇺 Scratch: циклы «повторить» и «повторять всегда»", "url": "https://www.youtube.com/watch?v=3vxYHaB-GtQ"},
                {"title": "🇷🇺 Scratch: условия «если» / «если-иначе»", "url": "https://www.youtube.com/watch?v=c4urIXjBTHA"},
                {"title": "🇷🇺 Scratch: управление логикой программы", "url": "https://www.youtube.com/watch?v=EANqQBqAe8o"},
            ],
            [
                {"title": "🇷🇺 Scratch: вложенные циклы и условия", "url": "https://www.youtube.com/watch?v=oPyJBGK6hZ4"},
                {"title": "🇷🇺 Scratch: ждать и клонировать", "url": "https://www.youtube.com/watch?v=LzJFmNE7hU4"},
                {"title": "🇷🇺 Scratch: блоки управления — практика", "url": "https://www.youtube.com/watch?v=v9_N5BwVT_4"},
            ],
        ],
        "sensing": [
            [
                {"title": "🇷🇺 Scratch: сенсоры — касание, мышь, таймер", "url": "https://www.youtube.com/watch?v=T2rsJViSicU"},
                {"title": "🇷🇺 Scratch: «касается цвета» и обнаружение", "url": "https://www.youtube.com/watch?v=mMftaEu_Lk0"},
                {"title": "🇷🇺 Scratch: блок «спросить» и ввод данных", "url": "https://www.youtube.com/watch?v=KvJ6PqGMPuU"},
            ],
            [
                {"title": "🇷🇺 Scratch: расстояние до объекта", "url": "https://www.youtube.com/watch?v=hC5RP0YUJLk"},
                {"title": "🇷🇺 Scratch: ответ игрока и таймер", "url": "https://www.youtube.com/watch?v=ExPHuJZFd5U"},
                {"title": "🇷🇺 Scratch: датчики — практика", "url": "https://www.youtube.com/watch?v=RrQEb7BTHGQ"},
            ],
        ],
        "operators": [
            [
                {"title": "🇷🇺 Scratch: операторы — математика и логика", "url": "https://www.youtube.com/watch?v=uFwacOVIoMY"},
                {"title": "🇷🇺 Scratch: случайное число — блок оператор", "url": "https://www.youtube.com/watch?v=lH8TQHIR5Cw"},
                {"title": "🇷🇺 Scratch: сравнения и логические блоки", "url": "https://www.youtube.com/watch?v=3NXGT7Nk5qM"},
            ],
            [
                {"title": "🇷🇺 Scratch: объединение строк и остаток", "url": "https://www.youtube.com/watch?v=3A5txzb5EWk"},
                {"title": "🇷🇺 Scratch: арифметические операторы и int", "url": "https://www.youtube.com/watch?v=9tY3FJQZ-s4"},
                {"title": "🇷🇺 Scratch: «и», «или», «не» — логика", "url": "https://www.youtube.com/watch?v=7_wM-8OGJIA"},
            ],
        ],
        "variables": [
            [
                {"title": "🇷🇺 Scratch: переменные — очки и жизни", "url": "https://www.youtube.com/watch?v=N-UyGUqtqOc"},
                {"title": "🇷🇺 Scratch: создаём счётчик очков", "url": "https://www.youtube.com/watch?v=cK5BvMPbthM"},
                {"title": "🇷🇺 Scratch: списки — хранение данных", "url": "https://www.youtube.com/watch?v=2mPITR4Y8M4"},
            ],
            [
                {"title": "🇷🇺 Scratch: переменные для всех и для спрайта", "url": "https://www.youtube.com/watch?v=8xKU-bqATcs"},
                {"title": "🇷🇺 Scratch: работа со списками", "url": "https://www.youtube.com/watch?v=VzsCe2nz5yI"},
                {"title": "🇷🇺 Scratch: переменные в играх — практика", "url": "https://www.youtube.com/watch?v=Gqnf9GBsC_E"},
            ],
        ],
        "my_blocks": [
            [
                {"title": "🇷🇺 Scratch: мои блоки — создаём свои команды", "url": "https://www.youtube.com/watch?v=wx6xaOnyQ8I"},
                {"title": "🇷🇺 Scratch: процедуры и свои блоки — урок", "url": "https://www.youtube.com/watch?v=AuIKyZ-99V4"},
                {"title": "🇷🇺 Scratch: блоки с параметрами", "url": "https://www.youtube.com/watch?v=QcP0sUbI_6s"},
            ],
        ],
    },

    # ━━━━━━━━━━━━━━━ ALEXTYPE ━━━━━━━━━━━━━━━
    "alextype": {
        "typing": [
            [
                {"title": "🇷🇺 Слепая печать: как научиться быстро печатать", "url": "https://www.youtube.com/watch?v=JJhS5X3Jvhc"},
                {"title": "🇷🇺 Десятипальцевый метод печати — обучение", "url": "https://www.youtube.com/watch?v=1ArWGkOhUl8"},
                {"title": "🇷🇺 Клавиатурный тренажёр — как поставить пальцы", "url": "https://www.youtube.com/watch?v=Yc_MRUfqWPQ"},
            ],
            [
                {"title": "🇷🇺 Как научиться печатать вслепую за 2 недели", "url": "https://www.youtube.com/watch?v=qcXZKsiqpPI"},
                {"title": "🇷🇺 Горячие клавиши и скорость печати — советы", "url": "https://www.youtube.com/watch?v=Kq0_c4CoQO0"},
                {"title": "🇷🇺 Правильная постановка рук на клавиатуре", "url": "https://www.youtube.com/watch?v=cTYkvDNMCj0"},
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

        # Alternate between sets for _01/_02 tasks
        key = f"{cat}:{topic}"
        idx = topic_counters.get(key, 0)
        topic_counters[key] = idx + 1

        video_set = topic_pool[idx % len(topic_pool)]

        # Replace resources.videos
        if "resources" not in task:
            task["resources"] = {}
        task["resources"]["videos"] = list(video_set)

        # Set primary video_url to first in set
        task["video_url"] = video_set[0]["url"]

        updated += 1

    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Updated {updated} tutorials with unique topic-matched Russian videos")
    if skipped:
        print(f"⚠ Skipped {skipped} tutorials (no video pool found)")

    # ── Verification ──
    with open(TASKS_FILE) as f:
        check = json.load(f)
    tuts = [t for t in check["tasks"] if t.get("task_type") == "tutorial"]

    # Check for global URL duplicates
    from collections import Counter
    all_primary = [t.get("video_url", "") for t in tuts]
    dup_primary = {u: c for u, c in Counter(all_primary).items() if c > 1}

    all_res_urls = []
    for t in tuts:
        for v in t.get("resources", {}).get("videos", []):
            all_res_urls.append(v.get("url", ""))
    dup_res = {u: c for u, c in Counter(all_res_urls).items() if c > 1}

    print(f"\n── Verification ──")
    print(f"Total tutorials: {len(tuts)}")
    print(f"Duplicate primary video_urls: {len(dup_primary)}")
    for url, cnt in sorted(dup_primary.items(), key=lambda x: -x[1])[:5]:
        print(f"  {cnt}x: ...{url[-35:]}")
    print(f"Duplicate resource URLs: {len(dup_res)}")
    for url, cnt in sorted(dup_res.items(), key=lambda x: -x[1])[:5]:
        print(f"  {cnt}x: ...{url[-35:]}")


if __name__ == "__main__":
    main()
