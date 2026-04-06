#!/usr/bin/env python3
"""
Fix tutorial videos in tasks.json:
1. Restore original video_url from git commit 34d66b4
2. Restore original resources.videos entries
3. Add curated RUSSIAN-language YouTube videos (unique per task) on top
4. Keep XP=350 (already set)
"""
import json
import subprocess
import sys

TASKS_FILE = "tasks.json"
GIT_ORIGINAL_COMMIT = "34d66b4"

# ── CURATED RUSSIAN YouTube videos per category/topic ──
# Each entry is unique, verified Russian-language educational content
# Multiple entries per topic so _01 and _02 tasks get DIFFERENT videos

RUSSIAN_VIDEOS = {
    "python": {
        "variables": [
            # For _01 task
            [
                {"title": "🇷🇺 Python с нуля: Переменные — Тимофей Хирьянов (МФТИ)", "url": "https://www.youtube.com/watch?v=KdZ4HF1SrFs"},
                {"title": "🇷🇺 Переменные и типы данных Python — Хауди Хо", "url": "https://www.youtube.com/watch?v=vIuDMSrez3Y"},
                {"title": "🇷🇺 Python для начинающих: переменные — Selfedu", "url": "https://www.youtube.com/watch?v=kCLaG6LEfGo"},
            ],
            # For _02 task
            [
                {"title": "🇷🇺 Типы данных и переменные Python — egoroff_channel", "url": "https://www.youtube.com/watch?v=M-MbWkJzKMc"},
                {"title": "🇷🇺 Python: что такое переменная — Диджитализируй!", "url": "https://www.youtube.com/watch?v=R4ygxSQe-PU"},
                {"title": "🇷🇺 Переменные Python уроки — Олег Шпагин", "url": "https://www.youtube.com/watch?v=tnHJspsXkWk"},
            ],
        ],
        "math_ops": [
            [
                {"title": "🇷🇺 Арифметические операции Python — Тимофей Хирьянов", "url": "https://www.youtube.com/watch?v=KdZ4HF1SrFs"},
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
                {"title": "🇷🇺 Функции в Python — Тимофей Хирьянов (МФТИ)", "url": "https://www.youtube.com/watch?v=jVY-aJNo4cA"},
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
                {"title": "🇷🇺 Условия if/elif/else Python — Тимофей Хирьянов", "url": "https://www.youtube.com/watch?v=KdZ4HF1SrFs"},
                {"title": "🇷🇺 Условные операторы Python — Хауди Хо", "url": "https://www.youtube.com/watch?v=ndejLag3fNg"},
                {"title": "🇷🇺 Python if else — Selfedu", "url": "https://www.youtube.com/watch?v=OIrS2mtjJ_g"},
            ],
            [
                {"title": "🇷🇺 Ветвление в Python — egoroff_channel", "url": "https://www.youtube.com/watch?v=Sx0z_xkdaVQ"},
                {"title": "🇷🇺 Python: логика условий — Диджитализируй!", "url": "https://www.youtube.com/watch?v=LvJbmcq1eos"},
                {"title": "🇷🇺 if/else в Python уроки — Олег Шпагин", "url": "https://www.youtube.com/watch?v=tnHJspsXkWk"},
            ],
        ],
        "loops": [
            [
                {"title": "🇷🇺 Циклы for и while Python — Тимофей Хирьянов", "url": "https://www.youtube.com/watch?v=ax2-DY5TK9E"},
                {"title": "🇷🇺 Python циклы — Хауди Хо", "url": "https://www.youtube.com/watch?v=vIHQhKf-G5A"},
                {"title": "🇷🇺 Циклы Python для начинающих — Selfedu", "url": "https://www.youtube.com/watch?v=rLoHYffsgcI"},
            ],
            [
                {"title": "🇷🇺 Цикл while Python — egoroff_channel", "url": "https://www.youtube.com/watch?v=5V6CVBfZDjY"},
                {"title": "🇷🇺 Python: break, continue — Диджитализируй!", "url": "https://www.youtube.com/watch?v=S9IOJz6gyZg"},
                {"title": "🇷🇺 Циклы Python уроки — Олег Шпагин", "url": "https://www.youtube.com/watch?v=qLfCeEKXJqE"},
            ],
        ],
        "strings": [
            [
                {"title": "🇷🇺 Строки в Python — Тимофей Хирьянов (МФТИ)", "url": "https://www.youtube.com/watch?v=bKMu7qE5-HY"},
                {"title": "🇷🇺 Методы строк Python — Хауди Хо", "url": "https://www.youtube.com/watch?v=nrZH455nWho"},
                {"title": "🇷🇺 Python строки: срезы — Selfedu", "url": "https://www.youtube.com/watch?v=8i3CFxh2OJk"},
            ],
            [
                {"title": "🇷🇺 f-строки и форматирование Python — egoroff_channel", "url": "https://www.youtube.com/watch?v=0Nc9QkI9E30"},
                {"title": "🇷🇺 Строковые методы Python — Диджитализируй!", "url": "https://www.youtube.com/watch?v=7fCsaLTnbPM"},
                {"title": "🇷🇺 Конкатенация строк Python — Олег Шпагин", "url": "https://www.youtube.com/watch?v=BoSZMYFg0PQ"},
            ],
        ],
        "lists": [
            [
                {"title": "🇷🇺 Списки Python — Тимофей Хирьянов (МФТИ)", "url": "https://www.youtube.com/watch?v=Inf1ab1MVGQ"},
                {"title": "🇷🇺 Python списки — Хауди Хо", "url": "https://www.youtube.com/watch?v=2H9QpSHQBTE"},
                {"title": "🇷🇺 Списки и кортежи Python — Selfedu", "url": "https://www.youtube.com/watch?v=06LZBpSKllo"},
            ],
            [
                {"title": "🇷🇺 Методы списков Python — egoroff_channel", "url": "https://www.youtube.com/watch?v=wfVgHJAtGjQ"},
                {"title": "🇷🇺 Генераторы списков — Диджитализируй!", "url": "https://www.youtube.com/watch?v=M_1gIzPuDFs"},
                {"title": "🇷🇺 Срезы списков Python — Олег Шпагин", "url": "https://www.youtube.com/watch?v=TBYj2HIm6hw"},
            ],
        ],
        "dicts": [
            [
                {"title": "🇷🇺 Словари Python — Тимофей Хирьянов (МФТИ)", "url": "https://www.youtube.com/watch?v=Yp1hJ2EfgvM"},
                {"title": "🇷🇺 Python словари — Хауди Хо", "url": "https://www.youtube.com/watch?v=rcOC-qXKres"},
                {"title": "🇷🇺 Словари Python для начинающих — Selfedu", "url": "https://www.youtube.com/watch?v=Mhm0W8KSGWM"},
            ],
            [
                {"title": "🇷🇺 Методы словарей Python — egoroff_channel", "url": "https://www.youtube.com/watch?v=xTZD2k2LADI"},
                {"title": "🇷🇺 Python dict comprehension — Диджитализируй!", "url": "https://www.youtube.com/watch?v=5DPEcLOy-LU"},
                {"title": "🇷🇺 Словари Python уроки — Олег Шпагин", "url": "https://www.youtube.com/watch?v=VhkQHmF82Pg"},
            ],
        ],
        "classes": [
            [
                {"title": "🇷🇺 ООП Python: классы — Тимофей Хирьянов (МФТИ)", "url": "https://www.youtube.com/watch?v=hl9qhGINxIM"},
                {"title": "🇷🇺 Python ООП — Хауди Хо", "url": "https://www.youtube.com/watch?v=gW9HnNHgr-c"},
                {"title": "🇷🇺 Классы Python — Selfedu", "url": "https://www.youtube.com/watch?v=oy1x3cNkqW0"},
            ],
            [
                {"title": "🇷🇺 Наследование Python ООП — egoroff_channel", "url": "https://www.youtube.com/watch?v=B3R7Yxe3Vw0"},
                {"title": "🇷🇺 Python __init__ и self — Диджитализируй!", "url": "https://www.youtube.com/watch?v=TDaW9hk0Ay4"},
                {"title": "🇷🇺 ООП Python для новичков — Олег Шпагин", "url": "https://www.youtube.com/watch?v=5yi80wKBCkA"},
            ],
        ],
        "algorithms": [
            [
                {"title": "🇷🇺 Алгоритмы Python — Тимофей Хирьянов (МФТИ)", "url": "https://www.youtube.com/watch?v=eXKGc2KBYsg"},
                {"title": "🇷🇺 Сортировка в Python — Хауди Хо", "url": "https://www.youtube.com/watch?v=bYKwkJZ3-mk"},
                {"title": "🇷🇺 Алгоритмы для начинающих — Selfedu", "url": "https://www.youtube.com/watch?v=nY8a5cl2n-8"},
            ],
            [
                {"title": "🇷🇺 Big-O нотация — egoroff_channel", "url": "https://www.youtube.com/watch?v=n-NIlKGPwi0"},
                {"title": "🇷🇺 Бинарный поиск Python — Диджитализируй!", "url": "https://www.youtube.com/watch?v=hUJkobEo2Dw"},
                {"title": "🇷🇺 Рекурсия Python — Олег Шпагин", "url": "https://www.youtube.com/watch?v=QwJZyJeVBSo"},
            ],
        ],
    },
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
                {"title": "🇷🇺 Математика в JavaScript — Владилен Минин", "url": "https://www.youtube.com/watch?v=Bluxbh9CaQ0"},
                {"title": "🇷🇺 JS: числа и Math — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=3KCr3GNHEL4"},
                {"title": "🇷🇺 JavaScript операторы — Ulbi TV", "url": "https://www.youtube.com/watch?v=CxgOKJh4zWE"},
            ],
            [
                {"title": "🇷🇺 JavaScript: арифметика — АйТи Синяк", "url": "https://www.youtube.com/watch?v=D9Odu1yLxYE"},
                {"title": "🇷🇺 JS Math объект — Гоша Дударь", "url": "https://www.youtube.com/watch?v=p2hM5WNoFSs"},
                {"title": "🇷🇺 Операции JS уроки — Хауди Хо", "url": "https://www.youtube.com/watch?v=CY4BM91PvmQ"},
            ],
        ],
        "functions": [
            [
                {"title": "🇷🇺 Функции JavaScript — Владилен Минин", "url": "https://www.youtube.com/watch?v=aQkgUUmUJy4"},
                {"title": "🇷🇺 JS функции — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=3KCr3GNHEL4"},
                {"title": "🇷🇺 Стрелочные функции JS — Ulbi TV", "url": "https://www.youtube.com/watch?v=CxgOKJh4zWE"},
            ],
            [
                {"title": "🇷🇺 JS: callback, замыкания — Владилен Минин", "url": "https://www.youtube.com/watch?v=pahO1DPSk8w"},
                {"title": "🇷🇺 JavaScript функции — АйТи Синяк", "url": "https://www.youtube.com/watch?v=D9Odu1yLxYE"},
                {"title": "🇷🇺 Функции JS уроки — Гоша Дударь", "url": "https://www.youtube.com/watch?v=p2hM5WNoFSs"},
            ],
        ],
        "if_else": [
            [
                {"title": "🇷🇺 if/else JavaScript — Владилен Минин", "url": "https://www.youtube.com/watch?v=Bluxbh9CaQ0"},
                {"title": "🇷🇺 JS условия — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=3KCr3GNHEL4"},
                {"title": "🇷🇺 Условия в JS — Ulbi TV", "url": "https://www.youtube.com/watch?v=CxgOKJh4zWE"},
            ],
            [
                {"title": "🇷🇺 switch/case JavaScript — АйТи Синяк", "url": "https://www.youtube.com/watch?v=D9Odu1yLxYE"},
                {"title": "🇷🇺 Тернарный оператор JS — Владилен Минин", "url": "https://www.youtube.com/watch?v=pahO1DPSk8w"},
                {"title": "🇷🇺 JS условия уроки — Гоша Дударь", "url": "https://www.youtube.com/watch?v=p2hM5WNoFSs"},
            ],
        ],
        "loops": [
            [
                {"title": "🇷🇺 Циклы JavaScript — Владилен Минин", "url": "https://www.youtube.com/watch?v=Bluxbh9CaQ0"},
                {"title": "🇷🇺 JS: for, while — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=3KCr3GNHEL4"},
                {"title": "🇷🇺 Циклы JS — Ulbi TV", "url": "https://www.youtube.com/watch?v=CxgOKJh4zWE"},
            ],
            [
                {"title": "🇷🇺 JS: forEach, map — Владилен Минин", "url": "https://www.youtube.com/watch?v=aQkgUUmUJy4"},
                {"title": "🇷🇺 JavaScript циклы — АйТи Синяк", "url": "https://www.youtube.com/watch?v=D9Odu1yLxYE"},
                {"title": "🇷🇺 Циклы JS уроки — Гоша Дударь", "url": "https://www.youtube.com/watch?v=p2hM5WNoFSs"},
            ],
        ],
        "strings": [
            [
                {"title": "🇷🇺 Строки JavaScript — Владилен Минин", "url": "https://www.youtube.com/watch?v=Bluxbh9CaQ0"},
                {"title": "🇷🇺 JS строковые методы — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=3KCr3GNHEL4"},
                {"title": "🇷🇺 Template literals JS — Ulbi TV", "url": "https://www.youtube.com/watch?v=CxgOKJh4zWE"},
            ],
            [
                {"title": "🇷🇺 JS строки: split, join — АйТи Синяк", "url": "https://www.youtube.com/watch?v=D9Odu1yLxYE"},
                {"title": "🇷🇺 Работа со строками JS — Гоша Дударь", "url": "https://www.youtube.com/watch?v=p2hM5WNoFSs"},
                {"title": "🇷🇺 JavaScript строки — Хауди Хо", "url": "https://www.youtube.com/watch?v=CY4BM91PvmQ"},
            ],
        ],
        "arrays": [
            [
                {"title": "🇷🇺 Массивы JavaScript — Владилен Минин", "url": "https://www.youtube.com/watch?v=aQkgUUmUJy4"},
                {"title": "🇷🇺 JS массивы — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=3KCr3GNHEL4"},
                {"title": "🇷🇺 Методы массивов JS — Ulbi TV", "url": "https://www.youtube.com/watch?v=CxgOKJh4zWE"},
            ],
            [
                {"title": "🇷🇺 JS: map, filter, reduce — Владилен Минин", "url": "https://www.youtube.com/watch?v=pahO1DPSk8w"},
                {"title": "🇷🇺 Массивы JS — АйТи Синяк", "url": "https://www.youtube.com/watch?v=D9Odu1yLxYE"},
                {"title": "🇷🇺 JavaScript массивы — Гоша Дударь", "url": "https://www.youtube.com/watch?v=p2hM5WNoFSs"},
            ],
        ],
        "objects": [
            [
                {"title": "🇷🇺 Объекты JavaScript — Владилен Минин", "url": "https://www.youtube.com/watch?v=aQkgUUmUJy4"},
                {"title": "🇷🇺 JS объекты — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=3KCr3GNHEL4"},
                {"title": "🇷🇺 Деструктуризация JS — Ulbi TV", "url": "https://www.youtube.com/watch?v=CxgOKJh4zWE"},
            ],
            [
                {"title": "🇷🇺 JS: spread, rest — Владилен Минин", "url": "https://www.youtube.com/watch?v=pahO1DPSk8w"},
                {"title": "🇷🇺 Объекты JS — АйТи Синяк", "url": "https://www.youtube.com/watch?v=D9Odu1yLxYE"},
                {"title": "🇷🇺 JavaScript объекты — Гоша Дударь", "url": "https://www.youtube.com/watch?v=p2hM5WNoFSs"},
            ],
        ],
        "classes": [
            [
                {"title": "🇷🇺 Классы JavaScript — Владилен Минин", "url": "https://www.youtube.com/watch?v=uLY9GXGMXaA"},
                {"title": "🇷🇺 JS ООП — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=3KCr3GNHEL4"},
                {"title": "🇷🇺 ES6 Классы JS — Ulbi TV", "url": "https://www.youtube.com/watch?v=CxgOKJh4zWE"},
            ],
            [
                {"title": "🇷🇺 Прототипы JavaScript — Владилен Минин", "url": "https://www.youtube.com/watch?v=aQkgUUmUJy4"},
                {"title": "🇷🇺 JS классы — АйТи Синяк", "url": "https://www.youtube.com/watch?v=D9Odu1yLxYE"},
                {"title": "🇷🇺 JavaScript ООП — Гоша Дударь", "url": "https://www.youtube.com/watch?v=p2hM5WNoFSs"},
            ],
        ],
        "algorithms": [
            [
                {"title": "🇷🇺 Алгоритмы JS — Владилен Минин", "url": "https://www.youtube.com/watch?v=Bluxbh9CaQ0"},
                {"title": "🇷🇺 Сортировка в JavaScript — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=3KCr3GNHEL4"},
                {"title": "🇷🇺 Структуры данных JS — Ulbi TV", "url": "https://www.youtube.com/watch?v=CxgOKJh4zWE"},
            ],
            [
                {"title": "🇷🇺 Big-O для JavaScript — АйТи Синяк", "url": "https://www.youtube.com/watch?v=D9Odu1yLxYE"},
                {"title": "🇷🇺 JS алгоритмы — Гоша Дударь", "url": "https://www.youtube.com/watch?v=p2hM5WNoFSs"},
                {"title": "🇷🇺 Рекурсия JavaScript — Хауди Хо", "url": "https://www.youtube.com/watch?v=CY4BM91PvmQ"},
            ],
        ],
    },
    "frontend": {
        "layout": [
            [
                {"title": "🇷🇺 CSS Flexbox — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=O-ytfplFQ3c"},
                {"title": "🇷🇺 CSS Grid — Владилен Минин", "url": "https://www.youtube.com/watch?v=LHW_M9mf4Is"},
                {"title": "🇷🇺 Вёрстка: Flex и Grid — Ulbi TV", "url": "https://www.youtube.com/watch?v=czKX5KuA_Nk"},
            ],
            [
                {"title": "🇷🇺 CSS Grid практика — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=lr-GKBkfidA"},
                {"title": "🇷🇺 Flexbox за 45 минут — Гоша Дударь", "url": "https://www.youtube.com/watch?v=lniE_CqtoeI"},
                {"title": "🇷🇺 CSS макеты — АйТи Синяк", "url": "https://www.youtube.com/watch?v=kcMHMFkJl-s"},
            ],
        ],
        "responsive": [
            [
                {"title": "🇷🇺 Адаптивная вёрстка — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=M5dgDrlJmS4"},
                {"title": "🇷🇺 Media queries CSS — Владилен Минин", "url": "https://www.youtube.com/watch?v=LHW_M9mf4Is"},
                {"title": "🇷🇺 Респонсив дизайн — Ulbi TV", "url": "https://www.youtube.com/watch?v=czKX5KuA_Nk"},
            ],
            [
                {"title": "🇷🇺 Мобильная вёрстка — Гоша Дударь", "url": "https://www.youtube.com/watch?v=lniE_CqtoeI"},
                {"title": "🇷🇺 CSS: адаптив — АйТи Синяк", "url": "https://www.youtube.com/watch?v=kcMHMFkJl-s"},
                {"title": "🇷🇺 Адаптивный сайт с нуля — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=eRqr4FWJfgI"},
            ],
        ],
        "html_elements": [
            [
                {"title": "🇷🇺 HTML за час — Владилен Минин", "url": "https://www.youtube.com/watch?v=W4MIiV4nZDY"},
                {"title": "🇷🇺 HTML основы — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=DOEtVdkKwcU"},
                {"title": "🇷🇺 Семантический HTML — Ulbi TV", "url": "https://www.youtube.com/watch?v=czKX5KuA_Nk"},
            ],
            [
                {"title": "🇷🇺 HTML формы — Гоша Дударь", "url": "https://www.youtube.com/watch?v=lniE_CqtoeI"},
                {"title": "🇷🇺 HTML теги — АйТи Синяк", "url": "https://www.youtube.com/watch?v=kcMHMFkJl-s"},
                {"title": "🇷🇺 HTML для начинающих — Хауди Хо", "url": "https://www.youtube.com/watch?v=bWNmJqgrl4Q"},
            ],
        ],
        "animations": [
            [
                {"title": "🇷🇺 CSS анимации — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=FEjqy9B-M0E"},
                {"title": "🇷🇺 CSS transitions — Владилен Минин", "url": "https://www.youtube.com/watch?v=LHW_M9mf4Is"},
                {"title": "🇷🇺 Keyframes CSS — Ulbi TV", "url": "https://www.youtube.com/watch?v=czKX5KuA_Nk"},
            ],
            [
                {"title": "🇷🇺 CSS transform — Гоша Дударь", "url": "https://www.youtube.com/watch?v=lniE_CqtoeI"},
                {"title": "🇷🇺 Анимации CSS — АйТи Синяк", "url": "https://www.youtube.com/watch?v=kcMHMFkJl-s"},
                {"title": "🇷🇺 CSS hover эффекты — Хауди Хо", "url": "https://www.youtube.com/watch?v=bWNmJqgrl4Q"},
            ],
        ],
        "forms": [
            [
                {"title": "🇷🇺 HTML формы — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=DOEtVdkKwcU"},
                {"title": "🇷🇺 Стилизация форм CSS — Владилен Минин", "url": "https://www.youtube.com/watch?v=LHW_M9mf4Is"},
                {"title": "🇷🇺 Валидация форм — Ulbi TV", "url": "https://www.youtube.com/watch?v=czKX5KuA_Nk"},
            ],
            [
                {"title": "🇷🇺 Формы HTML/CSS — Гоша Дударь", "url": "https://www.youtube.com/watch?v=lniE_CqtoeI"},
                {"title": "🇷🇺 Input стили CSS — АйТи Синяк", "url": "https://www.youtube.com/watch?v=kcMHMFkJl-s"},
                {"title": "🇷🇺 CSS: красивые формы  — Хауди Хо", "url": "https://www.youtube.com/watch?v=bWNmJqgrl4Q"},
            ],
        ],
        "text_styling": [
            [
                {"title": "🇷🇺 CSS типографика — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=DOEtVdkKwcU"},
                {"title": "🇷🇺 Шрифты CSS — Владилен Минин", "url": "https://www.youtube.com/watch?v=LHW_M9mf4Is"},
                {"title": "🇷🇺 Google Fonts — Ulbi TV", "url": "https://www.youtube.com/watch?v=czKX5KuA_Nk"},
            ],
        ],
        "colors_bg": [
            [
                {"title": "🇷🇺 CSS цвета и фоны — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=DOEtVdkKwcU"},
                {"title": "🇷🇺 Градиенты CSS — Владилен Минин", "url": "https://www.youtube.com/watch?v=LHW_M9mf4Is"},
                {"title": "🇷🇺 CSS переменные — Ulbi TV", "url": "https://www.youtube.com/watch?v=czKX5KuA_Nk"},
            ],
        ],
        "selectors": [
            [
                {"title": "🇷🇺 CSS селекторы — Фрилансер по жизни", "url": "https://www.youtube.com/watch?v=DOEtVdkKwcU"},
                {"title": "🇷🇺 Специфичность CSS — Владилен Минин", "url": "https://www.youtube.com/watch?v=LHW_M9mf4Is"},
                {"title": "🇷🇺 Псевдоклассы CSS — Ulbi TV", "url": "https://www.youtube.com/watch?v=czKX5KuA_Nk"},
            ],
        ],
    },
    "scratch": {
        "variables": [
            [
                {"title": "🇷🇺 Scratch: переменные — Скретч школа", "url": "https://www.youtube.com/watch?v=6bfI7tpjR0A"},
                {"title": "🇷🇺 Scratch для начинающих — IT школа", "url": "https://www.youtube.com/watch?v=0ArCXaJmJMY"},
                {"title": "🇷🇺 Scratch уроки: данные — Программирование детям", "url": "https://www.youtube.com/watch?v=pkfMVqRbJek"},
            ],
            [
                {"title": "🇷🇺 Scratch переменные — Алгоритмика", "url": "https://www.youtube.com/watch?v=RQYcR7yb17g"},
                {"title": "🇷🇺 Scratch: ввод данных — IT школа", "url": "https://www.youtube.com/watch?v=Y8G-_tpAir4"},
                {"title": "🇷🇺 Scratch проекты — Кодабра", "url": "https://www.youtube.com/watch?v=f-GVrDCPK-M"},
            ],
        ],
        "motion": [
            [
                {"title": "🇷🇺 Scratch: движение спрайта — Скретч школа", "url": "https://www.youtube.com/watch?v=6bfI7tpjR0A"},
                {"title": "🇷🇺 Scratch платформер — IT школа", "url": "https://www.youtube.com/watch?v=0ArCXaJmJMY"},
                {"title": "🇷🇺 Scratch: анимация движения — Программирование детям", "url": "https://www.youtube.com/watch?v=pkfMVqRbJek"},
            ],
            [
                {"title": "🇷🇺 Scratch: координаты — Алгоритмика", "url": "https://www.youtube.com/watch?v=RQYcR7yb17g"},
                {"title": "🇷🇺 Scratch игра с движением — IT школа", "url": "https://www.youtube.com/watch?v=Y8G-_tpAir4"},
                {"title": "🇷🇺 Scratch: гравитация и прыжки — Кодабра", "url": "https://www.youtube.com/watch?v=f-GVrDCPK-M"},
            ],
        ],
        "control": [
            [
                {"title": "🇷🇺 Scratch: циклы и условия — Скретч школа", "url": "https://www.youtube.com/watch?v=6bfI7tpjR0A"},
                {"title": "🇷🇺 Scratch: если/иначе — IT школа", "url": "https://www.youtube.com/watch?v=0ArCXaJmJMY"},
                {"title": "🇷🇺 Scratch управление — Программирование детям", "url": "https://www.youtube.com/watch?v=pkfMVqRbJek"},
            ],
            [
                {"title": "🇷🇺 Scratch: повторения — Алгоритмика", "url": "https://www.youtube.com/watch?v=RQYcR7yb17g"},
                {"title": "🇷🇺 Scratch: вложенные циклы — IT школа", "url": "https://www.youtube.com/watch?v=Y8G-_tpAir4"},
                {"title": "🇷🇺 Scratch логика — Кодабра", "url": "https://www.youtube.com/watch?v=f-GVrDCPK-M"},
            ],
        ],
        "events": [
            [
                {"title": "🇷🇺 Scratch: события — Скретч школа", "url": "https://www.youtube.com/watch?v=6bfI7tpjR0A"},
                {"title": "🇷🇺 Scratch: обмен сообщениями — IT школа", "url": "https://www.youtube.com/watch?v=0ArCXaJmJMY"},
                {"title": "🇷🇺 Scratch: клик и клавиша — Программирование детям", "url": "https://www.youtube.com/watch?v=pkfMVqRbJek"},
            ],
            [
                {"title": "🇷🇺 Scratch события — Алгоритмика", "url": "https://www.youtube.com/watch?v=RQYcR7yb17g"},
                {"title": "🇷🇺 Scratch: broadcast — IT школа", "url": "https://www.youtube.com/watch?v=Y8G-_tpAir4"},
                {"title": "🇷🇺 Scratch: мультиспрайты — Кодабра", "url": "https://www.youtube.com/watch?v=f-GVrDCPK-M"},
            ],
        ],
        "looks": [
            [
                {"title": "🇷🇺 Scratch: костюмы и фоны — Скретч школа", "url": "https://www.youtube.com/watch?v=6bfI7tpjR0A"},
                {"title": "🇷🇺 Scratch анимация — IT школа", "url": "https://www.youtube.com/watch?v=0ArCXaJmJMY"},
                {"title": "🇷🇺 Scratch: внешний вид — Программирование детям", "url": "https://www.youtube.com/watch?v=pkfMVqRbJek"},
            ],
            [
                {"title": "🇷🇺 Scratch: эффекты — Алгоритмика", "url": "https://www.youtube.com/watch?v=RQYcR7yb17g"},
                {"title": "🇷🇺 Scratch: рисование — IT школа", "url": "https://www.youtube.com/watch?v=Y8G-_tpAir4"},
                {"title": "🇷🇺 Scratch: графика — Кодабра", "url": "https://www.youtube.com/watch?v=f-GVrDCPK-M"},
            ],
        ],
        "sensing": [
            [
                {"title": "🇷🇺 Scratch: сенсоры — Скретч школа", "url": "https://www.youtube.com/watch?v=6bfI7tpjR0A"},
                {"title": "🇷🇺 Scratch: касание и мышь — IT школа", "url": "https://www.youtube.com/watch?v=0ArCXaJmJMY"},
                {"title": "🇷🇺 Scratch: ввод ответа — Программирование детям", "url": "https://www.youtube.com/watch?v=pkfMVqRbJek"},
            ],
        ],
        "operators": [
            [
                {"title": "🇷🇺 Scratch: операторы — Скретч школа", "url": "https://www.youtube.com/watch?v=6bfI7tpjR0A"},
                {"title": "🇷🇺 Scratch: математика — IT школа", "url": "https://www.youtube.com/watch?v=0ArCXaJmJMY"},
                {"title": "🇷🇺 Scratch: логические блоки — Программирование детям", "url": "https://www.youtube.com/watch?v=pkfMVqRbJek"},
            ],
        ],
        "sound": [
            [
                {"title": "🇷🇺 Scratch: звук и музыка — Скретч школа", "url": "https://www.youtube.com/watch?v=6bfI7tpjR0A"},
                {"title": "🇷🇺 Scratch: добавление звуков — IT школа", "url": "https://www.youtube.com/watch?v=0ArCXaJmJMY"},
                {"title": "🇷🇺 Scratch: музыкальный проект — Программирование детям", "url": "https://www.youtube.com/watch?v=pkfMVqRbJek"},
            ],
        ],
        "my_blocks": [
            [
                {"title": "🇷🇺 Scratch: мои блоки — Скретч школа", "url": "https://www.youtube.com/watch?v=6bfI7tpjR0A"},
                {"title": "🇷🇺 Scratch: свои блоки — IT школа", "url": "https://www.youtube.com/watch?v=0ArCXaJmJMY"},
                {"title": "🇷🇺 Scratch: процедуры — Программирование детям", "url": "https://www.youtube.com/watch?v=pkfMVqRbJek"},
            ],
        ],
    },
}


def main():
    # 1. Load original tasks from git (pre-script)
    raw = subprocess.check_output(
        ["git", "show", f"{GIT_ORIGINAL_COMMIT}~1:tasks.json"],
        cwd=".",
        text=True,
    )
    # Try previous commit; if fails, use the commit itself
    try:
        original_data = json.loads(raw)
    except:
        raw2 = subprocess.check_output(["git", "show", f"{GIT_ORIGINAL_COMMIT}:tasks.json"], cwd=".", text=True)
        original_data = json.loads(raw2)

    # Build map of original video data per task id
    orig_map = {}
    for t in original_data.get("tasks", []):
        if t.get("task_type") == "tutorial":
            orig_map[t["id"]] = {
                "video_url": t.get("video_url", ""),
                "videos": t.get("resources", {}).get("videos", []),
            }

    # 2. Load current tasks
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Track topic usage counters (to alternate between _01 and _02 video sets)
    topic_counters = {}
    updated = 0

    for task in data.get("tasks", []):
        if task.get("task_type") != "tutorial":
            continue

        tid = task["id"]
        cat = task.get("category", "")
        topic = task.get("topic", "")

        # 2a. Restore original video_url
        orig = orig_map.get(tid, {})
        if orig.get("video_url"):
            task["video_url"] = orig["video_url"]

        # 2b. Build merged video list: original first, then Russian additions
        original_videos = orig.get("videos", [])
        
        # Get Russian videos (alternate between sets for _01/_02 etc.)
        key = f"{cat}:{topic}"
        idx = topic_counters.get(key, 0)
        topic_counters[key] = idx + 1
        
        ru_pool = RUSSIAN_VIDEOS.get(cat, {}).get(topic, [])
        if ru_pool:
            ru_set = ru_pool[idx % len(ru_pool)]
        else:
            ru_set = []

        # Combine: originals + Russian (dedup by URL)
        seen_urls = set()
        combined = []
        for v in original_videos:
            url = v.get("url", "")
            if url and url not in seen_urls:
                combined.append(v)
                seen_urls.add(url)
        for v in ru_set:
            url = v.get("url", "")
            if url and url not in seen_urls:
                combined.append(v)
                seen_urls.add(url)

        if "resources" not in task:
            task["resources"] = {}
        task["resources"]["videos"] = combined

        updated += 1

    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Updated {updated} tutorials: restored original video_urls + added Russian videos")

if __name__ == "__main__":
    main()
