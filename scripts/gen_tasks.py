#!/usr/bin/env python3
"""Generate quality tasks with proper tier progression."""
import json, random

TIERS = ["D","C","B","A","S"]
XP = {"D":(50,60),"C":(80,120),"B":(150,200),"A":(250,400),"S":(500,600)}

STORIES = {
    "D": [
        "Юный странник получает первое задание гильдии. Простое, но важное.",
        "Смотритель башни доверил тебе базовое заклинание. Выполни без ошибок.",
        "Новобранец лагеря разведчиков проходит вступительное испытание.",
    ],
    "C": [
        "Караван готовится к переходу через перевал. Помоги писарю обработать данные.",
        "В мастерской алхимика нужны аккуратные расчёты для зелья.",
        "Гильдия торговцев просит навести порядок в учёте товаров.",
    ],
    "B": [
        "Разведчики принесли сложный отчёт из руин. Обработай его для штаба.",
        "Арсенал гильдии растёт. Построй надёжную логику учёта.",
        "Маг-архивариус поручил тебе упорядочить древние свитки.",
    ],
    "A": [
        "Совет магов поручил задачу повышенной сложности. Нужен точный алгоритм.",
        "Хроники цитадели содержат запутанные данные. Составь решение.",
        "Командор крепости требует оптимальную стратегию обороны.",
    ],
    "S": [
        "Перед вратами древнего ядра — испытание мастеров. Безупречная работа!",
        "Архимаги запускают финальный протокол башни. Задача уровня легенд.",
        "Последний страж кода открывает портал. Только достойный пройдёт.",
    ],
}

# ============ PYTHON TASKS ============
PY_TASKS = [
  # D-tier: variables, print, basic math
  {"id":"py_v3_d_01","tier":"D","title":"Приветствие странника",
   "desc":"Напиши функцию `greet(name)`, которая возвращает строку `'Привет, <name>!'`.",
   "init":"def greet(name):\n    # Верни приветствие\n    return ''",
   "cases":[{"code":"greet('Артём')","expected":"Привет, Артём!"},{"code":"greet('Мир')","expected":"Привет, Мир!"},{"code":"greet('')","expected":"Привет, !"}]},
  {"id":"py_v3_d_02","tier":"D","title":"Площадь прямоугольника",
   "desc":"Напиши функцию `area(a, b)`, возвращающую площадь прямоугольника.",
   "init":"def area(a, b):\n    return 0",
   "cases":[{"code":"area(3,5)","expected":15},{"code":"area(0,10)","expected":0},{"code":"area(7,7)","expected":49}]},
  {"id":"py_v3_d_03","tier":"D","title":"Чётное или нет",
   "desc":"Напиши функцию `is_even(n)`, возвращающую `True` если число чётное.",
   "init":"def is_even(n):\n    return False",
   "cases":[{"code":"is_even(4)","expected":True},{"code":"is_even(7)","expected":False},{"code":"is_even(0)","expected":True}]},
  {"id":"py_v3_d_04","tier":"D","title":"Удвоитель",
   "desc":"Напиши функцию `double(x)`, возвращающую удвоенное значение.",
   "init":"def double(x):\n    return 0",
   "cases":[{"code":"double(5)","expected":10},{"code":"double(-3)","expected":-6},{"code":"double(0)","expected":0}]},
  {"id":"py_v3_d_05","tier":"D","title":"Первый символ",
   "desc":"Напиши функцию `first_char(s)`, возвращающую первый символ строки или пустую строку.",
   "init":"def first_char(s):\n    return ''",
   "cases":[{"code":"first_char('hello')","expected":"h"},{"code":"first_char('A')","expected":"A"},{"code":"first_char('')","expected":""}]},
  {"id":"py_v3_d_06","tier":"D","title":"Сумма трёх",
   "desc":"Напиши функцию `sum3(a,b,c)`, возвращающую сумму трёх чисел.",
   "init":"def sum3(a,b,c):\n    return 0",
   "cases":[{"code":"sum3(1,2,3)","expected":6},{"code":"sum3(-1,0,1)","expected":0},{"code":"sum3(10,20,30)","expected":60}]},
  {"id":"py_v3_d_07","tier":"D","title":"Длина строки",
   "desc":"Напиши функцию `str_len(s)`, возвращающую длину строки.",
   "init":"def str_len(s):\n    return 0",
   "cases":[{"code":"str_len('abc')","expected":3},{"code":"str_len('')","expected":0},{"code":"str_len('hello world')","expected":11}]},
  {"id":"py_v3_d_08","tier":"D","title":"Абсолютное значение",
   "desc":"Напиши функцию `my_abs(n)`, возвращающую модуль числа без использования abs().",
   "init":"def my_abs(n):\n    return 0",
   "cases":[{"code":"my_abs(-5)","expected":5},{"code":"my_abs(3)","expected":3},{"code":"my_abs(0)","expected":0}]},
  {"id":"py_v3_d_09","tier":"D","title":"Перевод в верхний регистр",
   "desc":"Напиши функцию `shout(s)`, возвращающую строку в верхнем регистре.",
   "init":"def shout(s):\n    return ''",
   "cases":[{"code":"shout('hello')","expected":"HELLO"},{"code":"shout('Мир')","expected":"МИР"},{"code":"shout('')","expected":""}]},
  {"id":"py_v3_d_10","tier":"D","title":"Остаток от деления",
   "desc":"Напиши функцию `remainder(a, b)`, возвращающую остаток от деления a на b.",
   "init":"def remainder(a, b):\n    return 0",
   "cases":[{"code":"remainder(10,3)","expected":1},{"code":"remainder(15,5)","expected":0},{"code":"remainder(7,2)","expected":1}]},

  # C-tier: conditionals, loops, strings
  {"id":"py_v3_c_01","tier":"C","title":"Знак числа",
   "desc":"Напиши функцию `sign(n)`, возвращающую 1 для положительных, -1 для отрицательных, 0 для нуля.",
   "init":"def sign(n):\n    return 0",
   "cases":[{"code":"sign(5)","expected":1},{"code":"sign(-3)","expected":-1},{"code":"sign(0)","expected":0}]},
  {"id":"py_v3_c_02","tier":"C","title":"Счётчик гласных",
   "desc":"Напиши функцию `count_vowels(s)`, считающую гласные (aeiou) в строке (регистр не важен).",
   "init":"def count_vowels(s):\n    return 0",
   "cases":[{"code":"count_vowels('Hello')","expected":2},{"code":"count_vowels('xyz')","expected":0},{"code":"count_vowels('AEIOU')","expected":5}]},
  {"id":"py_v3_c_03","tier":"C","title":"Разворот строки",
   "desc":"Напиши функцию `reverse_str(s)`, возвращающую перевёрнутую строку.",
   "init":"def reverse_str(s):\n    return ''",
   "cases":[{"code":"reverse_str('abc')","expected":"cba"},{"code":"reverse_str('12345')","expected":"54321"},{"code":"reverse_str('')","expected":""}]},
  {"id":"py_v3_c_04","tier":"C","title":"Максимум из трёх",
   "desc":"Напиши функцию `max3(a,b,c)`, возвращающую наибольшее из трёх чисел без max().",
   "init":"def max3(a,b,c):\n    return 0",
   "cases":[{"code":"max3(1,5,3)","expected":5},{"code":"max3(-1,-5,-3)","expected":-1},{"code":"max3(7,7,7)","expected":7}]},
  {"id":"py_v3_c_05","tier":"C","title":"Палиндром?",
   "desc":"Напиши функцию `is_palindrome(s)`, проверяющую, является ли строка палиндромом (без учёта регистра).",
   "init":"def is_palindrome(s):\n    return False",
   "cases":[{"code":"is_palindrome('Abba')","expected":True},{"code":"is_palindrome('hello')","expected":False},{"code":"is_palindrome('A')","expected":True}]},
  {"id":"py_v3_c_06","tier":"C","title":"Сумма цифр",
   "desc":"Напиши функцию `digit_sum(n)`, возвращающую сумму цифр натурального числа.",
   "init":"def digit_sum(n):\n    return 0",
   "cases":[{"code":"digit_sum(123)","expected":6},{"code":"digit_sum(9)","expected":9},{"code":"digit_sum(1000)","expected":1}]},
  {"id":"py_v3_c_07","tier":"C","title":"Факториал",
   "desc":"Напиши функцию `factorial(n)`, возвращающую n! (0! = 1).",
   "init":"def factorial(n):\n    return 0",
   "cases":[{"code":"factorial(5)","expected":120},{"code":"factorial(0)","expected":1},{"code":"factorial(1)","expected":1}]},
  {"id":"py_v3_c_08","tier":"C","title":"Фильтр чётных",
   "desc":"Напиши функцию `evens(lst)`, возвращающую список только чётных чисел.",
   "init":"def evens(lst):\n    return []",
   "cases":[{"code":"evens([1,2,3,4,5])","expected":[2,4]},{"code":"evens([1,3,5])","expected":[]},{"code":"evens([])","expected":[]}]},
  {"id":"py_v3_c_09","tier":"C","title":"Количество слов",
   "desc":"Напиши функцию `word_count(s)`, считающую количество слов в строке.",
   "init":"def word_count(s):\n    return 0",
   "cases":[{"code":"word_count('hello world')","expected":2},{"code":"word_count('one')","expected":1},{"code":"word_count('')","expected":0}]},
  {"id":"py_v3_c_10","tier":"C","title":"FizzBuzz значение",
   "desc":"Напиши функцию `fizzbuzz(n)`: верни 'FizzBuzz' если делится на 15, 'Fizz' на 3, 'Buzz' на 5, иначе число строкой.",
   "init":"def fizzbuzz(n):\n    return ''",
   "cases":[{"code":"fizzbuzz(15)","expected":"FizzBuzz"},{"code":"fizzbuzz(9)","expected":"Fizz"},{"code":"fizzbuzz(10)","expected":"Buzz"},{"code":"fizzbuzz(7)","expected":"7"}]},

  # B-tier: lists, dicts, algorithms
  {"id":"py_v3_b_01","tier":"B","title":"Уникальные элементы",
   "desc":"Напиши функцию `unique(lst)`, возвращающую список уникальных элементов в порядке появления.",
   "init":"def unique(lst):\n    return []",
   "cases":[{"code":"unique([1,2,2,3,1])","expected":[1,2,3]},{"code":"unique([])","expected":[]},{"code":"unique([5,5,5])","expected":[5]}]},
  {"id":"py_v3_b_02","tier":"B","title":"Сортировка пузырьком",
   "desc":"Напиши функцию `bubble_sort(lst)`, сортирующую список по возрастанию (без sort/sorted).",
   "init":"def bubble_sort(lst):\n    return lst",
   "cases":[{"code":"bubble_sort([3,1,2])","expected":[1,2,3]},{"code":"bubble_sort([5,4,3,2,1])","expected":[1,2,3,4,5]},{"code":"bubble_sort([])","expected":[]}]},
  {"id":"py_v3_b_03","tier":"B","title":"Частотный словарь",
   "desc":"Напиши функцию `freq(lst)`, возвращающую dict с частотой каждого элемента.",
   "init":"def freq(lst):\n    return {}",
   "cases":[{"code":"freq(['a','b','a'])","expected":{"a":2,"b":1}},{"code":"freq([])","expected":{}},{"code":"freq([1,1,1])","expected":{1:3}}]},
  {"id":"py_v3_b_04","tier":"B","title":"Вложенная сумма",
   "desc":"Напиши функцию `nested_sum(lst)`, суммирующую все числа во вложенных списках. Пример: [[1,2],[3]] → 6.",
   "init":"def nested_sum(lst):\n    return 0",
   "cases":[{"code":"nested_sum([[1,2],[3]])","expected":6},{"code":"nested_sum([[],[]])","expected":0},{"code":"nested_sum([[10],[-5],[3,2]])","expected":10}]},
  {"id":"py_v3_b_05","tier":"B","title":"Матричная транспозиция",
   "desc":"Напиши функцию `transpose(m)`, транспонирующую матрицу (список списков).",
   "init":"def transpose(m):\n    return []",
   "cases":[{"code":"transpose([[1,2],[3,4]])","expected":[[1,3],[2,4]]},{"code":"transpose([[1,2,3]])","expected":[[1],[2],[3]]}]},
  {"id":"py_v3_b_06","tier":"B","title":"Схлопывание строк",
   "desc":"Напиши функцию `compress(s)`, сжимающую повторы: 'aaabbc' → 'a3b2c1'.",
   "init":"def compress(s):\n    return ''",
   "cases":[{"code":"compress('aaabbc')","expected":"a3b2c1"},{"code":"compress('abc')","expected":"a1b1c1"},{"code":"compress('')","expected":""}]},
  {"id":"py_v3_b_07","tier":"B","title":"Бинарный поиск",
   "desc":"Напиши функцию `binary_search(arr, x)`, возвращающую индекс x в отсортированном arr или -1.",
   "init":"def binary_search(arr, x):\n    return -1",
   "cases":[{"code":"binary_search([1,3,5,7,9],5)","expected":2},{"code":"binary_search([1,3,5,7,9],4)","expected":-1},{"code":"binary_search([],1)","expected":-1}]},
  {"id":"py_v3_b_08","tier":"B","title":"Число в римскую запись",
   "desc":"Напиши функцию `to_roman(n)` для чисел 1-3999. Пример: 14→'XIV'.",
   "init":"def to_roman(n):\n    return ''",
   "cases":[{"code":"to_roman(14)","expected":"XIV"},{"code":"to_roman(1994)","expected":"MCMXCIV"},{"code":"to_roman(1)","expected":"I"}]},
  {"id":"py_v3_b_09","tier":"B","title":"Группировка анаграмм",
   "desc":"Напиши функцию `group_anagrams(words)`, группирующую слова-анаграммы в списки.",
   "init":"def group_anagrams(words):\n    return []",
   "cases":[{"code":"sorted([sorted(g) for g in group_anagrams(['eat','tea','tan','ate','nat','bat'])])","expected":[['ate','eat','tea'],['bat'],['nat','tan']]}]},
  {"id":"py_v3_b_10","tier":"B","title":"Спиральная матрица",
   "desc":"Напиши функцию `spiral(n)`, возвращающую n×n матрицу, заполненную по спирали от 1.",
   "init":"def spiral(n):\n    return []",
   "cases":[{"code":"spiral(2)","expected":[[1,2],[4,3]]},{"code":"spiral(3)","expected":[[1,2,3],[8,9,4],[7,6,5]]}]},

  # A-tier: recursion, algorithms, complexity
  {"id":"py_v3_a_01","tier":"A","title":"Числа Фибоначчи (мемоизация)",
   "desc":"Напиши функцию `fib(n)`, возвращающую n-е число Фибоначчи. Используй мемоизацию. fib(0)=0, fib(1)=1.",
   "init":"def fib(n):\n    return 0",
   "cases":[{"code":"fib(10)","expected":55},{"code":"fib(0)","expected":0},{"code":"fib(30)","expected":832040}]},
  {"id":"py_v3_a_02","tier":"A","title":"Все перестановки",
   "desc":"Напиши функцию `permutations(lst)`, возвращающую все перестановки списка.",
   "init":"def permutations(lst):\n    return []",
   "cases":[{"code":"sorted(permutations([1,2,3]))","expected":[[1,2,3],[1,3,2],[2,1,3],[2,3,1],[3,1,2],[3,2,1]]},{"code":"permutations([1])","expected":[[1]]}]},
  {"id":"py_v3_a_03","tier":"A","title":"Наибольшая подстрока без повторов",
   "desc":"Напиши функцию `longest_unique(s)`, возвращающую длину наибольшей подстроки без повторяющихся символов.",
   "init":"def longest_unique(s):\n    return 0",
   "cases":[{"code":"longest_unique('abcabcbb')","expected":3},{"code":"longest_unique('bbbbb')","expected":1},{"code":"longest_unique('pwwkew')","expected":3}]},
  {"id":"py_v3_a_04","tier":"A","title":"Быстрая сортировка",
   "desc":"Реализуй функцию `quicksort(lst)`, возвращающую отсортированный список (алгоритм quicksort).",
   "init":"def quicksort(lst):\n    return lst",
   "cases":[{"code":"quicksort([3,6,1,8,2])","expected":[1,2,3,6,8]},{"code":"quicksort([])","expected":[]},{"code":"quicksort([5,5,5])","expected":[5,5,5]}]},
  {"id":"py_v3_a_05","tier":"A","title":"Валидация скобок",
   "desc":"Напиши функцию `valid_brackets(s)`, проверяющую правильность скобок ()[]{}.",
   "init":"def valid_brackets(s):\n    return False",
   "cases":[{"code":"valid_brackets('([{}])')","expected":True},{"code":"valid_brackets('([)]')","expected":False},{"code":"valid_brackets('')","expected":True}]},
  {"id":"py_v3_a_06","tier":"A","title":"Плоский итератор",
   "desc":"Напиши функцию `flatten(lst)`, рекурсивно разворачивающую вложенные списки любой глубины.",
   "init":"def flatten(lst):\n    return []",
   "cases":[{"code":"flatten([1,[2,[3,4],5],6])","expected":[1,2,3,4,5,6]},{"code":"flatten([[[]]])","expected":[]},{"code":"flatten([1,2,3])","expected":[1,2,3]}]},
  {"id":"py_v3_a_07","tier":"A","title":"Медиана потока",
   "desc":"Напиши класс `MedianFinder` с методами `add(num)` и `median()` для поиска медианы добавленных чисел.",
   "init":"class MedianFinder:\n    def __init__(self):\n        self.data = []\n    def add(self, num):\n        pass\n    def median(self):\n        return 0",
   "cases":[{"code":"m=MedianFinder();m.add(1);m.add(2);m.median()","expected":1.5},{"code":"m=MedianFinder();m.add(3);m.add(1);m.add(2);m.median()","expected":2}]},
  {"id":"py_v3_a_08","tier":"A","title":"LRU-кеш",
   "desc":"Реализуй класс `LRU(capacity)` с методами `get(key)` (возвращает значение или -1) и `put(key, val)`.",
   "init":"class LRU:\n    def __init__(self, capacity):\n        self.cap = capacity\n        self.cache = {}\n    def get(self, key):\n        return -1\n    def put(self, key, val):\n        pass",
   "cases":[{"code":"c=LRU(2);c.put(1,1);c.put(2,2);c.get(1)","expected":1},{"code":"c=LRU(2);c.put(1,1);c.put(2,2);c.put(3,3);c.get(1)","expected":-1}]},
  {"id":"py_v3_a_09","tier":"A","title":"Подмножества",
   "desc":"Напиши функцию `subsets(lst)`, возвращающую все подмножества списка.",
   "init":"def subsets(lst):\n    return []",
   "cases":[{"code":"sorted([sorted(x) for x in subsets([1,2,3])])","expected":[[],[1],[1,2],[1,2,3],[1,3],[2],[2,3],[3]]}]},
  {"id":"py_v3_a_10","tier":"A","title":"Минимальное окно подстроки",
   "desc":"Напиши функцию `min_window(s, t)`, находящую минимальное окно в s, содержащее все символы t.",
   "init":"def min_window(s, t):\n    return ''",
   "cases":[{"code":"min_window('ADOBECODEBANC','ABC')","expected":"BANC"},{"code":"min_window('a','aa')","expected":""}]},

  # S-tier: system design, optimization
  {"id":"py_v3_s_01","tier":"S","title":"Интерпретатор выражений",
   "desc":"Напиши функцию `calc(expr)`, вычисляющую арифметическое выражение со скобками. Поддержи +,-,*,/ и пробелы.",
   "init":"def calc(expr):\n    return 0",
   "cases":[{"code":"calc('3+2*2')","expected":7},{"code":"calc(' 3/2 ')","expected":1},{"code":"calc('(1+(4+5+2)-3)+(6+8)')","expected":23}]},
  {"id":"py_v3_s_02","tier":"S","title":"Сериализация дерева",
   "desc":"Реализуй функции `serialize(root)` и `deserialize(data)` для бинарного дерева (None = null). Узел: класс Node(val, left, right).",
   "init":"class Node:\n    def __init__(self, val=0, left=None, right=None):\n        self.val=val;self.left=left;self.right=right\ndef serialize(root):\n    return ''\ndef deserialize(data):\n    return None",
   "cases":[{"code":"t=Node(1,Node(2),Node(3,Node(4),Node(5)));deserialize(serialize(t)).val","expected":1},{"code":"serialize(None)","expected":"#"}]},
  {"id":"py_v3_s_03","tier":"S","title":"Топологическая сортировка",
   "desc":"Напиши функцию `topo_sort(n, edges)`, возвращающую топологический порядок n вершин (0..n-1). edges = [(u,v),...].",
   "init":"def topo_sort(n, edges):\n    return []",
   "cases":[{"code":"r=topo_sort(4,[(0,1),(0,2),(1,3),(2,3)]);all(r.index(u)<r.index(v) for u,v in [(0,1),(0,2),(1,3),(2,3)])","expected":True}]},
  {"id":"py_v3_s_04","tier":"S","title":"Сжатие RLE с декодером",
   "desc":"Напиши `encode(s)` и `decode(s)` для RLE: 'aaabbc'↔'3a2b1c'. decode(encode(x))==x.",
   "init":"def encode(s):\n    return ''\ndef decode(s):\n    return ''",
   "cases":[{"code":"encode('aaabbc')","expected":"3a2b1c"},{"code":"decode('3a2b1c')","expected":"aaabbc"},{"code":"decode(encode('hello'))","expected":"hello"}]},
  {"id":"py_v3_s_05","tier":"S","title":"Генератор лабиринта",
   "desc":"Напиши функцию `solve_maze(maze, start, end)`, находящую кратчайший путь в лабиринте (0=проход,1=стена). Возврати список координат.",
   "init":"def solve_maze(maze, start, end):\n    return []",
   "cases":[{"code":"len(solve_maze([[0,0,0],[1,1,0],[0,0,0]],(0,0),(2,2)))","expected":5},{"code":"solve_maze([[0,1],[1,0]],(0,0),(1,1))","expected":[]}]},
  {"id":"py_v3_s_06","tier":"S","title":"Регулярные выражения",
   "desc":"Напиши функцию `regex_match(s, p)`, поддерживающую '.' (любой символ) и '*' (0+ предыдущего).",
   "init":"def regex_match(s, p):\n    return False",
   "cases":[{"code":"regex_match('aab','c*a*b')","expected":True},{"code":"regex_match('ab','.*')","expected":True},{"code":"regex_match('abc','a.c')","expected":True}]},
  {"id":"py_v3_s_07","tier":"S","title":"Кодирование Хаффмана",
   "desc":"Напиши функцию `huffman_encode(text)`, возвращающую (encoded_bits_str, tree_dict) и `huffman_decode(bits, tree)` для восстановления.",
   "init":"def huffman_encode(text):\n    return ('', {})\ndef huffman_decode(bits, tree):\n    return ''",
   "cases":[{"code":"b,t=huffman_encode('aaabbc');huffman_decode(b,t)","expected":"aaabbc"}]},
  {"id":"py_v3_s_08","tier":"S","title":"K ближайших точек",
   "desc":"Напиши функцию `k_closest(points, k)`, возвращающую k ближайших точек к началу координат. points = [[x,y],...].",
   "init":"def k_closest(points, k):\n    return []",
   "cases":[{"code":"sorted(k_closest([[1,3],[-2,2],[5,8],[0,1]],2))","expected":[[-2,2],[0,1]]}]},
  {"id":"py_v3_s_09","tier":"S","title":"Merge интервалов",
   "desc":"Напиши функцию `merge_intervals(intervals)`, объединяющую пересекающиеся интервалы.",
   "init":"def merge_intervals(intervals):\n    return []",
   "cases":[{"code":"merge_intervals([[1,3],[2,6],[8,10],[15,18]])","expected":[[1,6],[8,10],[15,18]]},{"code":"merge_intervals([[1,4],[4,5]])","expected":[[1,5]]}]},
  {"id":"py_v3_s_10","tier":"S","title":"Тетрис-валидатор",
   "desc":"Напиши функцию `can_clear(board, piece)`, определяющую, можно ли разместить фигуру тетриса на поле и убрать строку. board=2D list, piece=list координат.",
   "init":"def can_clear(board, piece):\n    return False",
   "cases":[{"code":"can_clear([[0,0,0,1],[0,0,0,1],[0,0,0,1],[1,1,1,1]],[(0,0),(0,1),(0,2),(1,0)])","expected":False}]},
]

def build_task(t, category, engine):
    tier = t["tier"]
    xp_lo, xp_hi = XP[tier]
    return {
        "id": t["id"],
        "category": category,
        "tier": tier,
        "title": t["title"],
        "xp": random.randint(xp_lo, xp_hi),
        "story": random.choice(STORIES[tier]),
        "description": t["desc"],
        "initial_code": t["init"],
        "check_logic": {"engine": engine, "cases": t["cases"]},
    }

def main():
    with open("tasks.json", "r") as f:
        data = json.load(f)

    new_tasks = []
    for t in PY_TASKS:
        new_tasks.append(build_task(t, "python", "pyodide"))

    data["tasks"].extend(new_tasks)
    with open("tasks.json", "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Stats
    cats = {}; tiers = {}
    for t in data["tasks"]:
        c = t.get("category","?"); cats[c] = cats.get(c,0)+1
        tr = t.get("tier","?"); tiers[tr] = tiers.get(tr,0)+1
    print(f"Added {len(new_tasks)} Python tasks. Total: {len(data['tasks'])}")
    print(f"By category: {cats}")
    print(f"By tier: {tiers}")

if __name__ == "__main__":
    main()
