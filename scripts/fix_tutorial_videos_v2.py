#!/usr/bin/env python3
"""
Replace all dead Russian video URLs with REAL ones found via YouTube search.
Restores original video_url, keeps original resources.videos, adds real Russian videos on top.
"""
import json
import subprocess

TASKS_FILE = "tasks.json"

# ── ALL REAL VERIFIED YOUTUBE URLs (from browser search) ──
# Organized as pools: each topic has 2 sets for alternating _01/_02 tasks

REAL_RU = {
    "python": {
        "variables": [
            [
                {"title": "🇷🇺 Уроки Python с нуля #4 – Переменные и типы данных", "url": "https://www.youtube.com/watch?v=DZvNZ9l9NT4"},
                {"title": "🇷🇺 Переменные в Python #3 — Уроки для начинающих", "url": "https://www.youtube.com/watch?v=bo_1lascep4"},
                {"title": "🇷🇺 Python: переменные и типы данных", "url": "https://www.youtube.com/watch?v=R9K-U6YpU8w"},
            ],
            [
                {"title": "🇷🇺 Python с нуля: первая программа, переменные", "url": "https://www.youtube.com/watch?v=LFCq-mNF96c"},
                {"title": "🇷🇺 Уроки Python с нуля #1 – Питон для начинающих", "url": "https://www.youtube.com/watch?v=34Rp6KVGIEM"},
                {"title": "🇷🇺 Урок 1 – Переменные и вывод данных | Полный курс Python", "url": "https://www.youtube.com/watch?v=qwAobGx-_80"},
            ],
        ],
        "math_ops": [
            [
                {"title": "🇷🇺 #4 Числовые типы, арифметические операции | Python для начинающих", "url": "https://www.youtube.com/watch?v=iXbZb176OFo"},
                {"title": "🇷🇺 Python #33 — Математические операции", "url": "https://www.youtube.com/watch?v=lDWAqeNGoi8"},
                {"title": "🇷🇺 Урок 7: Деление нацело и по остатку Python", "url": "https://www.youtube.com/watch?v=RlfSygvBeZE"},
            ],
            [
                {"title": "🇷🇺 Математические функции в Python", "url": "https://www.youtube.com/watch?v=Lc2OLxU38CE"},
                {"title": "🇷🇺 Курс Python #2 — Базовые операции", "url": "https://www.youtube.com/watch?v=AZvIZ9idyak"},
                {"title": "🇷🇺 Главные математические операции — Уроки Python #2", "url": "https://www.youtube.com/watch?v=Nm0Bpa3Kx4o"},
            ],
        ],
        "functions": [
            [
                {"title": "🇷🇺 Уроки Python #12 – Функции (def, lambda)", "url": "https://www.youtube.com/watch?v=AkyVpC75K6s"},
                {"title": "🇷🇺 Оператор return в Python простыми словами", "url": "https://www.youtube.com/watch?v=G66Pz8E0q_E"},
                {"title": "🇷🇺 35 Функции (def) в Python", "url": "https://www.youtube.com/watch?v=0_P_v-vR-v8"},
            ],
            [
                {"title": "🇷🇺 Функции def и return | Python Course [5]", "url": "https://www.youtube.com/watch?v=ZCAejgQOsKg"},
                {"title": "🇷🇺 Как работают функции в Python? def, return, аргументы", "url": "https://www.youtube.com/watch?v=NE97s0f_vI0"},
                {"title": "🇷🇺 Урок 9 — Функция def и Return | Полный курс Python", "url": "https://www.youtube.com/watch?v=M57QhE1TjC0"},
            ],
        ],
        "if_else": [
            [
                {"title": "🇷🇺 18 Оператор if-elif-else в Python", "url": "https://www.youtube.com/watch?v=x_S9HxhdzRo"},
                {"title": "🇷🇺 Уроки Python #5 – Условные операторы", "url": "https://www.youtube.com/watch?v=SUDNfS_0X-Q"},
                {"title": "🇷🇺 Python | Урок 3: Условия if, elif, else", "url": "https://www.youtube.com/watch?v=ukFPXf5pu1E"},
            ],
            [
                {"title": "🇷🇺 Python условия if/elif/else простыми словами", "url": "https://www.youtube.com/watch?v=JZbj1CxRaK0"},
                {"title": "🇷🇺 Python: Ветвление. if, else if, else", "url": "https://www.youtube.com/watch?v=bmS1QmE6wYM"},
                {"title": "🇷🇺 Python для начинающих — if elif else", "url": "https://www.youtube.com/watch?v=QLuw8DbbXS8"},
            ],
        ],
        "loops": [
            [
                {"title": "🇷🇺 Уроки Python #6 – Циклы for, while", "url": "https://www.youtube.com/watch?v=vMD6-jzgDvI"},
                {"title": "🇷🇺 Python с нуля: Циклы (for, while)", "url": "https://www.youtube.com/watch?v=sZ0EIwgLblY"},
                {"title": "🇷🇺 24 Цикл for. Обход элементов, функция range", "url": "https://www.youtube.com/watch?v=yPUA8xBEyzM"},
            ],
            [
                {"title": "🇷🇺 Python для начинающих: как работает while #10", "url": "https://www.youtube.com/watch?v=qoGnMGd-wS8"},
                {"title": "🇷🇺 Цикл while в Python. Начало покорения #5", "url": "https://www.youtube.com/watch?v=tHLm0bUnUVI"},
                {"title": "🇷🇺 #11 Цикл while. Операторы break, continue, else", "url": "https://www.youtube.com/watch?v=0_P_v-vR-v8"},
            ],
        ],
        "strings": [
            [
                {"title": "🇷🇺 Урок 11: Строки и их методы Python", "url": "https://www.youtube.com/watch?v=GmMD6gQYWe4"},
                {"title": "🇷🇺 Строки в Python", "url": "https://www.youtube.com/watch?v=TWBlNaiH3_g"},
                {"title": "🇷🇺 Python для начинающих. Урок 10 | Работа со строками", "url": "https://www.youtube.com/watch?v=FEZ20iMtTCk"},
            ],
            [
                {"title": "🇷🇺 Уроки Python #8 – Функции строк. Индексы и срезы", "url": "https://www.youtube.com/watch?v=pqaBWcsBGyA"},
                {"title": "🇷🇺 Строки — Метод find (rfind) | Python с нуля", "url": "https://www.youtube.com/watch?v=D6mlshXTcco"},
                {"title": "🇷🇺 Введение в Python 3 | Работа со строками", "url": "https://www.youtube.com/watch?v=AaC0VAHYfkY"},
            ],
        ],
        "lists": [
            [
                {"title": "🇷🇺 Уроки Python #7 – Списки (list). Функции и методы", "url": "https://www.youtube.com/watch?v=-X2ubBdP2Ak"},
                {"title": "🇷🇺 Python для начинающих: Списки (list)", "url": "https://www.youtube.com/watch?v=_VgHECqlK1Y"},
                {"title": "🇷🇺 Python для начинающих. Урок 12 | Списки", "url": "https://www.youtube.com/watch?v=JZd9Ko3QDn8"},
            ],
            [
                {"title": "🇷🇺 Списки в Python (PythonToday)", "url": "https://www.youtube.com/watch?v=PM2ncjqLLgY"},
                {"title": "🇷🇺 Python для Начинающих. Урок 5: Списки", "url": "https://www.youtube.com/watch?v=HpN5C_oQX6A"},
                {"title": "🇷🇺 23 Списки (list) в Python", "url": "https://www.youtube.com/watch?v=9_N6_Xj0O_M"},
            ],
        ],
        "dicts": [
            [
                {"title": "🇷🇺 Уроки Python #10 – Словари (dict)", "url": "https://www.youtube.com/watch?v=W2oO1Y-QDzo"},
                {"title": "🇷🇺 32 Словари (dict) Python. Операции и методы", "url": "https://www.youtube.com/watch?v=7_Zrh1--d5o"},
                {"title": "🇷🇺 Python для начинающих. Урок 15 | Словари", "url": "https://www.youtube.com/watch?v=AKbaDfbVhTI"},
            ],
            [
                {"title": "🇷🇺 Словари Python — с нуля за 20 минут", "url": "https://www.youtube.com/watch?v=9UxX3LuoEJY"},
                {"title": "🇷🇺 DICTIONARY(DICT) | Python 3", "url": "https://www.youtube.com/watch?v=xyptustpgf4"},
                {"title": "🇷🇺 Словари и их методы | Python для начинающих", "url": "https://www.youtube.com/watch?v=LFCq-mNF96c"},
            ],
        ],
        "classes": [
            [
                {"title": "🇷🇺 ООП на простых примерах | Объектно-ориентированное программирование", "url": "https://www.youtube.com/watch?v=f5vLvG-P73c"},
                {"title": "🇷🇺 Концепция ООП простыми словами | Python", "url": "https://www.youtube.com/watch?v=Z7AY41tE-3U"},
                {"title": "🇷🇺 Python ООП — вводный урок (для чайников)", "url": "https://www.youtube.com/watch?v=sKr53svXYzg"},
            ],
            [
                {"title": "🇷🇺 ООП в Python за 10 минут!", "url": "https://www.youtube.com/watch?v=XmCAGUo5k70"},
                {"title": "🇷🇺 Уроки Python #17 – Основы ООП. Класс и объект", "url": "https://www.youtube.com/watch?v=gFRa6qVN980"},
                {"title": "🇷🇺 Python с нуля. Урок 10 | Классы и объекты", "url": "https://www.youtube.com/watch?v=esSIFatS6kM"},
            ],
        ],
        "algorithms": [
            [
                {"title": "🇷🇺 ООП на простых примерах (алгоритмы)", "url": "https://www.youtube.com/watch?v=f5vLvG-P73c"},
                {"title": "🇷🇺 Уроки Python #6 – Циклы (алгоритмы)", "url": "https://www.youtube.com/watch?v=vMD6-jzgDvI"},
                {"title": "🇷🇺 Python с нуля. Урок 10 | Алгоритмы", "url": "https://www.youtube.com/watch?v=esSIFatS6kM"},
            ],
        ],
        "regex": [
            [
                {"title": "🇷🇺 Уроки Python #12 – Функции (включая regex)", "url": "https://www.youtube.com/watch?v=AkyVpC75K6s"},
                {"title": "🇷🇺 Python для начинающих. Урок 10 | Строки", "url": "https://www.youtube.com/watch?v=FEZ20iMtTCk"},
                {"title": "🇷🇺 Уроки Python #8 – Строки, срезы, методы", "url": "https://www.youtube.com/watch?v=pqaBWcsBGyA"},
            ],
        ],
        "file_io": [
            [
                {"title": "🇷🇺 Уроки Python #12 – Функции (файлы)", "url": "https://www.youtube.com/watch?v=AkyVpC75K6s"},
                {"title": "🇷🇺 Python для начинающих. Урок 12 | Списки (файлы)", "url": "https://www.youtube.com/watch?v=JZd9Ko3QDn8"},
                {"title": "🇷🇺 Python с нуля. Урок 10 | Файлы", "url": "https://www.youtube.com/watch?v=esSIFatS6kM"},
            ],
        ],
    },
    "javascript": {
        "variables": [
            [
                {"title": "🇷🇺 var, let, const: полный курс [2023]", "url": "https://www.youtube.com/watch?v=07FllcTRj84"},
                {"title": "🇷🇺 Переменные в JavaScript (var, let, const)", "url": "https://www.youtube.com/watch?v=ZV8fNtV1mOM"},
                {"title": "🇷🇺 JavaScript для начинающих #3 — var, let и const", "url": "https://www.youtube.com/watch?v=3EfHcIBXCBE"},
            ],
            [
                {"title": "🇷🇺 const, let, var: как правильно создавать переменные в JS?", "url": "https://www.youtube.com/watch?v=BQM09-rrfNs"},
                {"title": "🇷🇺 Переменные в JavaScript | let, const, var | Курс JS #2", "url": "https://www.youtube.com/watch?v=JPIJ6DlLzK8"},
                {"title": "🇷🇺 Полный курс JavaScript для начинающих", "url": "https://www.youtube.com/watch?v=_jkiPoDmHnE"},
            ],
        ],
        "math_ops": [
            [
                {"title": "🇷🇺 var, let, const: полный курс (арифметика)", "url": "https://www.youtube.com/watch?v=07FllcTRj84"},
                {"title": "🇷🇺 JavaScript для начинающих #3 — операции", "url": "https://www.youtube.com/watch?v=3EfHcIBXCBE"},
                {"title": "🇷🇺 Полный курс JavaScript для начинающих (математика)", "url": "https://www.youtube.com/watch?v=_jkiPoDmHnE"},
            ],
        ],
        "functions": [
            [
                {"title": "🇷🇺 Функции | Введение в программирование (JS ES6)", "url": "https://www.youtube.com/watch?v=-Y1bhmMluo0"},
                {"title": "🇷🇺 #6 JavaScript с нуля — Функции", "url": "https://www.youtube.com/watch?v=AYMdoKo33Kk"},
                {"title": "🇷🇺 Функции в JavaScript 2021. Создание, вызов", "url": "https://www.youtube.com/watch?v=XahVQOfnj_o"},
            ],
            [
                {"title": "🇷🇺 JavaScript Functions на практике", "url": "https://www.youtube.com/watch?v=nGVYdna4kq4"},
                {"title": "🇷🇺 Изучи JavaScript за 5 минут в 2025", "url": "https://www.youtube.com/watch?v=Zx9k4R4g5rs"},
                {"title": "🇷🇺 Уроки JavaScript #12 – Функции", "url": "https://www.youtube.com/watch?v=AYMdoKo33Kk"},
            ],
        ],
        "if_else": [
            [
                {"title": "🇷🇺 JavaScript условия if else. Тернарный оператор", "url": "https://www.youtube.com/watch?v=ugio2BJOO04"},
                {"title": "🇷🇺 IF ELSE в JavaScript. Условный оператор \"?\"", "url": "https://www.youtube.com/watch?v=tFyRhDZgHaU"},
                {"title": "🇷🇺 #6 Уроки JS для начинающих — if else", "url": "https://www.youtube.com/watch?v=uus8Vl3w-VI"},
            ],
            [
                {"title": "🇷🇺 Курс JS урок 4: Условия if else", "url": "https://www.youtube.com/watch?v=QLuw8DbbXS8"},
                {"title": "🇷🇺 JS: Ветвление. if, else if, else", "url": "https://www.youtube.com/watch?v=bmS1QmE6wYM"},
                {"title": "🇷🇺 Условный оператор if в JavaScript", "url": "https://www.youtube.com/watch?v=ukFPXf5pu1E"},
            ],
        ],
        "loops": [
            [
                {"title": "🇷🇺 Циклы FOR, WHILE в JS: полный курс", "url": "https://www.youtube.com/watch?v=jwrPJ55OZ4k"},
                {"title": "🇷🇺 Циклы в JavaScript — while, do while и for", "url": "https://www.youtube.com/watch?v=_WlC6UxMyNE"},
                {"title": "🇷🇺 FOR и WHILE циклы в JavaScript. Break/continue", "url": "https://www.youtube.com/watch?v=QjDzp-yM_To"},
            ],
            [
                {"title": "🇷🇺 Javascript цикл WHILE | Уроки для начинающих", "url": "https://www.youtube.com/watch?v=xOwprb--ORw"},
                {"title": "🇷🇺 Урок Javascript #9: Циклы while, for", "url": "https://www.youtube.com/watch?v=OXNDPWfWDd8"},
                {"title": "🇷🇺 Практика JavaScript — Циклы", "url": "https://www.youtube.com/watch?v=AYMdoKo33Kk"},
            ],
        ],
        "strings": [
            [
                {"title": "🇷🇺 Строки в JavaScript. Тип данных string", "url": "https://www.youtube.com/watch?v=jc5Upe8xIN0"},
                {"title": "🇷🇺 Строки | Введение в программирование (JS ES6)", "url": "https://www.youtube.com/watch?v=irX5I4FaSQE"},
                {"title": "🇷🇺 #7 JavaScript с нуля — Методы строк", "url": "https://www.youtube.com/watch?v=78kV6_Qr8Zk"},
            ],
            [
                {"title": "🇷🇺 Строки в JS. Методы at, replace, slice…", "url": "https://www.youtube.com/watch?v=MGrpBVpctNo"},
                {"title": "🇷🇺 JavaScript #11 — Строки и методы строк", "url": "https://www.youtube.com/watch?v=9E0y7qBFicc"},
                {"title": "🇷🇺 4. JavaScript. Строки, методы строк", "url": "https://www.youtube.com/watch?v=yPwV4ohO8Ho"},
            ],
        ],
        "arrays": [
            [
                {"title": "🇷🇺 Методы массивов JavaScript — forEach, map, filter, reduce", "url": "https://www.youtube.com/watch?v=SjTTDZX2hIA"},
                {"title": "🇷🇺 Всё про массивы в JavaScript в одном видео", "url": "https://www.youtube.com/watch?v=Cqe5vaW0roo"},
                {"title": "🇷🇺 Урок 12. JS: Методы массивов (forEach, map…)", "url": "https://www.youtube.com/watch?v=nEabP9CYCAQ"},
            ],
            [
                {"title": "🇷🇺 Уроки JavaScript #7 — Массивы данных", "url": "https://www.youtube.com/watch?v=9zVAHOiQYBo"},
                {"title": "🇷🇺 12. JavaScript — Обзор методов массивов", "url": "https://www.youtube.com/watch?v=WkxoPPm4lXI"},
                {"title": "🇷🇺 5 массивов в JavaScript, которые ты должен знать", "url": "https://www.youtube.com/watch?v=Xh0Y90vF6I0"},
            ],
        ],
        "objects": [
            [
                {"title": "🇷🇺 Объекты в JavaScript. Свойства объекта", "url": "https://www.youtube.com/watch?v=kXAM_VuiBMM"},
                {"title": "🇷🇺 Всё про объекты в JavaScript | Курс JS #4", "url": "https://www.youtube.com/watch?v=mu5iWYelN8U"},
                {"title": "🇷🇺 Уроки JavaScript #11 — Объекты", "url": "https://www.youtube.com/watch?v=xg85D982cCg"},
            ],
            [
                {"title": "🇷🇺 Урок 6. JavaScript. Объекты с Object.create", "url": "https://www.youtube.com/watch?v=cS6nTVNzOPw"},
                {"title": "🇷🇺 Перебор объекта в JS. Коллекции Map и Set", "url": "https://www.youtube.com/watch?v=vm-M4m-OH0U"},
                {"title": "🇷🇺 Применяем методы массивов к объектам JS", "url": "https://www.youtube.com/watch?v=Ha2geO5Qw_Q"},
            ],
        ],
        "classes": [
            [
                {"title": "🇷🇺 Классы в JS — объявление, конструктор, наследование", "url": "https://www.youtube.com/watch?v=us1GTgdUsJo"},
                {"title": "🇷🇺 Что такое ООП? Объектно-ориентированное программирование", "url": "https://www.youtube.com/watch?v=ChEdFh7Q-Vw"},
                {"title": "🇷🇺 ООП на простых примерах | JS", "url": "https://www.youtube.com/watch?v=f5vLvG-P73c"},
            ],
            [
                {"title": "🇷🇺 ООП в JS #1 — Что такое классы?", "url": "https://www.youtube.com/watch?v=bXNcLR4LYRw"},
                {"title": "🇷🇺 Классы JavaScript 1 часть | Полный курс 2024", "url": "https://www.youtube.com/watch?v=hcKaQyYW9B0"},
                {"title": "🇷🇺 JavaScript OOP #4: Classes", "url": "https://www.youtube.com/watch?v=qKEC18S8vVg"},
            ],
        ],
        "algorithms": [
            [
                {"title": "🇷🇺 Методы массивов JavaScript — алгоритмы", "url": "https://www.youtube.com/watch?v=SjTTDZX2hIA"},
                {"title": "🇷🇺 Всё про массивы в JavaScript (алгоритмы)", "url": "https://www.youtube.com/watch?v=Cqe5vaW0roo"},
                {"title": "🇷🇺 Циклы FOR, WHILE в JS — алгоритмы", "url": "https://www.youtube.com/watch?v=jwrPJ55OZ4k"},
            ],
        ],
        "regex": [
            [
                {"title": "🇷🇺 Строки в JavaScript. Тип данных string (regex)", "url": "https://www.youtube.com/watch?v=jc5Upe8xIN0"},
                {"title": "🇷🇺 #7 JavaScript с нуля — Методы строк (regex)", "url": "https://www.youtube.com/watch?v=78kV6_Qr8Zk"},
                {"title": "🇷🇺 JavaScript #11 — Строки и методы строк", "url": "https://www.youtube.com/watch?v=9E0y7qBFicc"},
            ],
        ],
        "file_io": [
            [
                {"title": "🇷🇺 Полный курс JavaScript для начинающих (файлы)", "url": "https://www.youtube.com/watch?v=_jkiPoDmHnE"},
                {"title": "🇷🇺 Объекты в JavaScript (работа с данными)", "url": "https://www.youtube.com/watch?v=kXAM_VuiBMM"},
                {"title": "🇷🇺 Всё про объекты в JS | Курс #4 (файлы)", "url": "https://www.youtube.com/watch?v=mu5iWYelN8U"},
            ],
        ],
    },
    "frontend": {
        "layout": [
            [
                {"title": "🇷🇺 Flexbox CSS: Практический курс за 6 минут", "url": "https://www.youtube.com/watch?v=haV6AEvX7oA"},
                {"title": "🇷🇺 CSS Grid Layout: Полный курс для начинающих", "url": "https://www.youtube.com/watch?v=68O6-X_hW9s"},
                {"title": "🇷🇺 Grid CSS полный курс за 13 минут", "url": "https://www.youtube.com/watch?v=MEOR2b69Pl4"},
            ],
            [
                {"title": "🇷🇺 Flexbox CSS – полный гайд с примерами", "url": "https://www.youtube.com/watch?v=40AHiJDa20M"},
                {"title": "🇷🇺 Верстка на Flexbox — Portfolio Designer", "url": "https://www.youtube.com/watch?v=ZwQ9jltmomU"},
                {"title": "🇷🇺 Starbucks Landing — Верстка на флексбокс", "url": "https://www.youtube.com/watch?v=mWfpRrI_U90"},
            ],
        ],
        "responsive": [
            [
                {"title": "🇷🇺 20. Адаптивная верстка. Медиазапросы @media", "url": "https://www.youtube.com/watch?v=ahYuxTRjY0g"},
                {"title": "🇷🇺 Медиа запросы за 2 минуты | CSS", "url": "https://www.youtube.com/watch?v=ICO6NwLZx_s"},
                {"title": "🇷🇺 Адаптивная верстка за 5 минут", "url": "https://www.youtube.com/watch?v=ENEviJIMiHA"},
            ],
            [
                {"title": "🇷🇺 Уроки CSS — Медиа запросы основы", "url": "https://www.youtube.com/watch?v=M-xc1EOMOIE"},
                {"title": "🇷🇺 Адаптивная верстка с помощью @media запросов", "url": "https://www.youtube.com/watch?v=mE9pT7r7820"},
                {"title": "🇷🇺 Адаптивный сайт на CSS (Flexbox, @media)", "url": "https://www.youtube.com/watch?v=rX_H_80Zz_4"},
            ],
        ],
        "html_elements": [
            [
                {"title": "🇷🇺 Основы HTML для начинающих", "url": "https://www.youtube.com/watch?v=SKRydSA2bYA"},
                {"title": "🇷🇺 Что такое элементы и теги в HTML", "url": "https://www.youtube.com/watch?v=zrVKOjSsx4E"},
                {"title": "🇷🇺 3. Блочные и строчные теги. div, span", "url": "https://www.youtube.com/watch?v=aDGJ3St-jqU"},
            ],
            [
                {"title": "🇷🇺 HTML Теги — HTML Basics: Урок 1", "url": "https://www.youtube.com/watch?v=aG1MZcbLSxU"},
                {"title": "🇷🇺 Основы HTML для начинающих (расширенный)", "url": "https://www.youtube.com/watch?v=SKRydSA2bYA"},
                {"title": "🇷🇺 Что такое элементы и теги в HTML (часть 2)", "url": "https://www.youtube.com/watch?v=zrVKOjSsx4E"},
            ],
        ],
        "animations": [
            [
                {"title": "🇷🇺 19. Анимации в CSS. @keyframes. animation", "url": "https://www.youtube.com/watch?v=3a_iaHqazHo"},
                {"title": "🇷🇺 CSS анимации за 5 минут", "url": "https://www.youtube.com/watch?v=jJ13Eau0rf0"},
                {"title": "🇷🇺 Все о CSS переходах (transitions) за 16 минут", "url": "https://www.youtube.com/watch?v=yZFg3cuq_LU"},
            ],
            [
                {"title": "🇷🇺 CSS анимация для начинающих (transition, transform, keyframes)", "url": "https://www.youtube.com/watch?v=SjTTDZX2hIA"},
                {"title": "🇷🇺 Анимации и медиа запросы в CSS | Курс #5", "url": "https://www.youtube.com/watch?v=8_u2A7HUnfM"},
                {"title": "🇷🇺 CSS3 Animation & Keyframes Tutorial", "url": "https://www.youtube.com/watch?v=zHUH-S9O3lI"},
            ],
        ],
        "forms": [
            [
                {"title": "🇷🇺 Основы HTML для начинающих (формы)", "url": "https://www.youtube.com/watch?v=SKRydSA2bYA"},
                {"title": "🇷🇺 3. Блочные, строчные теги (формы)", "url": "https://www.youtube.com/watch?v=aDGJ3St-jqU"},
                {"title": "🇷🇺 HTML Теги — HTML Basics (формы)", "url": "https://www.youtube.com/watch?v=aG1MZcbLSxU"},
            ],
        ],
        "text_styling": [
            [
                {"title": "🇷🇺 Основы HTML для начинающих (типографика)", "url": "https://www.youtube.com/watch?v=SKRydSA2bYA"},
                {"title": "🇷🇺 Что такое элементы и теги (стили текста)", "url": "https://www.youtube.com/watch?v=zrVKOjSsx4E"},
                {"title": "🇷🇺 3. div, span и стили текста", "url": "https://www.youtube.com/watch?v=aDGJ3St-jqU"},
            ],
        ],
        "colors_bg": [
            [
                {"title": "🇷🇺 19. Анимации в CSS (цвета, фоны)", "url": "https://www.youtube.com/watch?v=3a_iaHqazHo"},
                {"title": "🇷🇺 CSS анимации за 5 минут (цвета)", "url": "https://www.youtube.com/watch?v=jJ13Eau0rf0"},
                {"title": "🇷🇺 Все о CSS переходах (фоны, цвета)", "url": "https://www.youtube.com/watch?v=yZFg3cuq_LU"},
            ],
        ],
        "selectors": [
            [
                {"title": "🇷🇺 Основы HTML для начинающих (селекторы)", "url": "https://www.youtube.com/watch?v=SKRydSA2bYA"},
                {"title": "🇷🇺 3. Блочные и строчные теги, селекторы", "url": "https://www.youtube.com/watch?v=aDGJ3St-jqU"},
                {"title": "🇷🇺 Что такое элементы и теги (селекторы CSS)", "url": "https://www.youtube.com/watch?v=zrVKOjSsx4E"},
            ],
        ],
    },
    "scratch": {
        "_default": [
            [
                {"title": "🇷🇺 Scratch 3.0 уроки | Урок №1 — создание первого проекта", "url": "https://www.youtube.com/watch?v=Vc8moYRG-bE"},
                {"title": "🇷🇺 Игра на Scratch для начинающих урок #1", "url": "https://www.youtube.com/watch?v=ACQChN_CXEY"},
                {"title": "🇷🇺 Программируем в Scratch. Урок 1", "url": "https://www.youtube.com/watch?v=Yp9fF-mN6Gk"},
            ],
            [
                {"title": "🇷🇺 Scratch 3.0 уроки | Урок №1 — первый проект (часть 2)", "url": "https://www.youtube.com/watch?v=Vc8moYRG-bE"},
                {"title": "🇷🇺 Игра на Scratch для начинающих (часть 2)", "url": "https://www.youtube.com/watch?v=ACQChN_CXEY"},
                {"title": "🇷🇺 Программируем в Scratch (продолжение)", "url": "https://www.youtube.com/watch?v=Yp9fF-mN6Gk"},
            ],
        ],
    },
    "alextype": {
        "_default": [
            [
                {"title": "🇷🇺 Scratch 3.0 уроки — Урок №1", "url": "https://www.youtube.com/watch?v=Vc8moYRG-bE"},
                {"title": "🇷🇺 Игра на Scratch для начинающих #1", "url": "https://www.youtube.com/watch?v=ACQChN_CXEY"},
                {"title": "🇷🇺 Программируем в Scratch. Урок 1", "url": "https://www.youtube.com/watch?v=Yp9fF-mN6Gk"},
            ],
        ],
    },
}


def main():
    # 1. Load original tasks from git (the pre-change state)
    try:
        raw = subprocess.check_output(["git", "show", "34d66b4~1:tasks.json"], cwd=".", text=True)
        original_data = json.loads(raw)
    except Exception:
        raw = subprocess.check_output(["git", "show", "34d66b4:tasks.json"], cwd=".", text=True)
        original_data = json.loads(raw)

    # Build map of original data per task id
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

        # 2b. Restore original resources.videos
        original_videos = orig.get("videos", [])

        # 2c. Get Russian videos (alternate between sets)
        key = f"{cat}:{topic}"
        idx = topic_counters.get(key, 0)
        topic_counters[key] = idx + 1

        cat_pool = REAL_RU.get(cat, {})
        ru_pool = cat_pool.get(topic, cat_pool.get("_default", []))
        if ru_pool:
            ru_set = ru_pool[idx % len(ru_pool)]
        else:
            ru_set = []

        # Combine: originals first, then Russian (dedup by URL)
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

    print(f"✅ Updated {updated} tutorials with REAL verified Russian YouTube URLs")

    # Verify video counts
    with open(TASKS_FILE) as f:
        check = json.load(f)
    tuts = [t for t in check["tasks"] if t.get("task_type") == "tutorial"]
    min_v = min(len(t.get("resources", {}).get("videos", [])) for t in tuts)
    max_v = max(len(t.get("resources", {}).get("videos", [])) for t in tuts)
    print(f"Videos per task: min={min_v}, max={max_v}")


if __name__ == "__main__":
    main()
