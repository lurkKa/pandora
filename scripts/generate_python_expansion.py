#!/usr/bin/env python3
"""Reproducible Python curriculum: 25 core problems × 8 objectives per tier.

Reference implementations live only in this authoring script, never in public
payloads. Every mission has examples, edge cases and deterministic hidden tests.
Run from any directory: python3 scripts/generate_python_expansion.py
"""
import bisect
import copy
import heapq
import json
import math
import random
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = 'python_expeditions_20261015'


@dataclass
class Problem:
    tier: str
    key: str
    title: str
    rule: str
    body: str
    inputs: list
    topic: str = 'algorithms'
    signature: str = 'data'

    def reference(self):
        namespace = dict(bisect=bisect, heapq=heapq, math=math, Counter=Counter, deque=deque)
        exec('def compute(' + self.signature + '):\n' + '\n'.join('    ' + line for line in self.body.splitlines()), namespace)
        return namespace['compute']


def problem(tier, key, title, rule, body, inputs, topic='algorithms', signature='data'):
    return Problem(tier, key, title, rule, body, inputs, topic, signature)


def curriculum():
    rng = random.Random(15102026)
    numeric = [(0, 1), (1, 1), (7, 3), (18, 5), (99, 10)] + [(rng.randrange(0, 1000), rng.randrange(1, 40)) for _ in range(9)]
    d_specs = [
        ('rations', 'Провизия каравана', 'a пайков на b путников: число полных пайков каждому', 'a // b'),
        ('reserve', 'Запас кладовщика', 'остаток от распределения a кристаллов поровну между b героями', 'a % b'),
        ('wagons', 'Места в повозках', 'минимальное число повозок вместимостью b для a пассажиров', '(a + b - 1) // b'),
        ('forge', 'Кузница искр', 'стоимость a слитков по b монет', 'a * b'),
        ('walls', 'Периметр бастиона', 'периметр прямоугольного бастиона со сторонами a и b', '2 * (a + b)'),
        ('triangles', 'Флаги дозора', 'целую часть площади треугольного флага с основанием a и высотой b', 'a * b // 2'),
        ('clock', 'Часы портала', 'a часов и b минут в минутах', 'a * 60 + b'),
        ('minutes', 'Секунды гонца', 'a часов и b минут в секундах', 'a * 3600 + b * 60'),
        ('difference', 'Два маяка', 'расстояние между отметками a и b на числовой прямой', 'abs(a - b)'),
        ('debt', 'Долг гильдии', 'сколько не хватает до цены b при запасе a монет (не меньше нуля)', 'max(0, b - a)'),
        ('change', 'Кошелёк торговца', 'сдачу с a монет после покупки за b; если денег не хватает, вернуть -1', 'a - b if a >= b else -1'),
        ('levels', 'Лестница башни', 'число ступеней на a этажах: на первом b ступеней, на каждом следующем на одну больше', 'a * b + a * (a - 1) // 2'),
        ('health', 'Щит целителя', 'здоровье после лечения на b при исходном a, максимум 100', 'min(100, a + b)'),
        ('damage', 'Броня стража', 'урон силой a после поглощения бронёй b, не меньше нуля', 'max(0, a - b)'),
        ('temperature', 'Шкала алхимика', 'показание после преобразования a * 9 // 5 + b', 'a * 9 // 5 + b'),
        ('square', 'Мозаика площади', 'число плиток в квадратах со сторонами a и b вместе', 'a * a + b * b'),
        ('digit', 'Шифр последней цифры', 'последнюю цифру суммы a и b', '(a + b) % 10'),
        ('cycle', 'Кольцевой дозор', 'позицию после b шагов от a на кольце из 24 позиций с нумерацией 0–23', '(a + b) % 24'),
        ('discount', 'Скидка мастера', 'целую цену после скидки b процентов на a монет; b может быть больше 100, цена неотрицательна', 'max(0, a * (100 - b) // 100)'),
        ('batches', 'Партия зелий', 'число полных партий по b из a ингредиентов, если на запуск нужно ещё 2 ингредиента', 'max(0, a - 2) // b'),
        ('seats', 'Свободные места', 'число свободных мест в зале на a мест после прихода b гостей, каждый занимает два места (не меньше нуля)', 'max(0, a - 2 * b)'),
        ('stairs', 'Треугольная лестница', 'сумму первых a натуральных чисел плюс b запасных ступеней', 'a * (a + 1) // 2 + b'),
        ('distance', 'Путь разведчика', 'расстояние за a часов со скоростью b и привалом в один час; при a=0 расстояние 0', 'max(0, a - 1) * b'),
        ('tax', 'Налоговый свиток', 'налог b процентов на сумму a с округлением вверх до целой монеты', '(a * b + 99) // 100'),
        ('score', 'Очки арены', '3 очка за каждую из a побед и одно очко за каждую из b ничьих', '3 * a + b'),
    ]
    out = [problem('D', key, title, 'Вход: целые a ≥ 0, b ≥ 1. Найди ' + rule + '.', 'return ' + expr, numeric, 'math_ops', 'a, b') for key, title, rule, expr in d_specs]
    arrays = [[], [0], [3, -1, 3, 0, -4, 2], [5, 5, 5], [-9, -2, -9]] + [[rng.randrange(-20, 21) for _ in range(n)] for n in (2, 7, 12, 18, 31, 40, 55, 65, 80)]
    def add(tier, key, title, rule, body, inputs=arrays, topic='algorithms'):
        out.append(problem(tier, key, title, rule, body, inputs, topic))
    c_specs = [
        ('warm', 'Тёплые сигналы', 'оставь только положительные числа', 'return [x for x in data if x > 0]'),
        ('cold', 'Ледяные сигналы', 'оставь только отрицательные числа', 'return [x for x in data if x < 0]'),
        ('even', 'Чётные печати', 'оставь только чётные числа', 'return [x for x in data if x % 2 == 0]'),
        ('odd', 'Нечётные руны', 'оставь только нечётные числа', 'return [x for x in data if x % 2]'),
        ('abs', 'Модули энергии', 'замени каждое число его модулем', 'return [abs(x) for x in data]'),
        ('squares', 'Квадраты силы', 'замени каждое число его квадратом', 'return [x*x for x in data]'),
        ('reverse', 'Обратный караван', 'разверни порядок чисел', 'return data[::-1]'),
        ('indices', 'Чётные посты', 'оставь элементы с индексами 0, 2, 4 и далее', 'return data[::2]'),
        ('odd_posts', 'Нечётные посты', 'оставь элементы с индексами 1, 3, 5 и далее', 'return data[1::2]'),
        ('nonzero', 'Очистка телеметрии', 'удали нули', 'return [x for x in data if x != 0]'),
        ('clamp', 'Стабилизатор реактора', 'ограничи каждое число диапазоном от -5 до 5 включительно', 'return [max(-5, min(5, x)) for x in data]'),
        ('sign', 'Компас знаков', 'замени положительные числа на 1, отрицательные на -1, нули на 0', 'return [(x > 0) - (x < 0) for x in data]'),
        ('neighbors', 'Соседние станции', 'получи разности соседей data[i+1]-data[i]; при длине меньше 2 список пуст', 'return [data[i+1]-data[i] for i in range(len(data)-1)]'),
        ('pairs', 'Парные запасы', 'сложи пары соседей (индексы 0 и 1, затем 2 и 3); последний одиночный элемент оставь', 'return [sum(data[i:i+2]) for i in range(0,len(data),2)]'),
        ('digits', 'Последние цифры', 'получи последние цифры модулей чисел', 'return [abs(x)%10 for x in data]'),
        ('double', 'Усилитель чётных', 'удвой чётные числа, остальные сохрани', 'return [2*x if x%2==0 else x for x in data]'),
        ('offset', 'Высота над стартом', 'вычти из каждого элемента первый; для пустого входа результат пуст', 'return [x-data[0] for x in data]'),
        ('rotate', 'Смена караула', 'перенеси первый элемент в конец; пустой список оставь пустым', 'return data[1:]+data[:1]'),
        ('mirror', 'Зеркало портала', 'допиши к исходному списку его развёрнутую копию', 'return data+data[::-1]'),
        ('saturate', 'Пустые батареи', 'замени отрицательные значения нулём', 'return [max(0,x) for x in data]'),
        ('repeat', 'Эхо маяков', 'повтори каждый элемент дважды подряд', 'return [x for x in data for _ in range(2)]'),
        ('above_first', 'Выше первого маяка', 'оставь числа строго больше первого элемента; пустой вход даёт пустой список', 'return [x for x in data if x>data[0]]'),
        ('div_three', 'Тройные ключи', 'оставь числа, делящиеся на 3 без остатка', 'return [x for x in data if x%3==0]'),
        ('mid', 'Сердцевина маршрута', 'удали первый и последний элементы; при длине меньше 3 список пуст', 'return data[1:-1]'),
        ('indexed', 'Метка расстояния', 'прибавь к каждому числу его индекс, начиная с нуля', 'return [i+x for i,x in enumerate(data)]'),
    ]
    for key, title, rule, body in c_specs:
        add('C', key, title, 'Вход data — список целых чисел. Построй последовательность: ' + rule + '. Сохраняй порядок, если не сказано иначе.', body, topic='lists')
    b_specs = [
        ('unique', 'Каталог артефактов', 'удали повторения, оставив первое появление каждого значения', 'return list(dict.fromkeys(data))'),
        ('freq', 'Частоты сигналов', 'для каждого исходного элемента запиши число его появлений во всём списке', 'counts=Counter(data)\nreturn [counts[x] for x in data]'),
        ('prefix', 'Накопитель энергии', 'выведи суммы всех непустых префиксов', 'result=[]\ns=0\nfor x in data:\n    s+=x\n    result.append(s)\nreturn result'),
        ('records', 'Новые высоты', 'оставь строгие рекорды максимума при просмотре слева направо; первый элемент — рекорд', 'result=[]\nfor x in data:\n    if not result or x>result[-1]: result.append(x)\nreturn result'),
        ('dedup_runs', 'Сжатие эха', 'сожми каждую серию одинаковых соседних значений в одно', 'return [x for i,x in enumerate(data) if i==0 or x!=data[i-1]]'),
        ('runs', 'Длина тревог', 'выведи длины максимальных серий одинаковых соседних значений', 'result=[]\nfor i,x in enumerate(data):\n    if i==0 or x!=data[i-1]: result.append(1)\n    else: result[-1]+=1\nreturn result'),
        ('windows', 'Тройной сенсор', 'выведи суммы всех окон длиной 3; при длине меньше 3 результат пуст', 'return [sum(data[i:i+3]) for i in range(len(data)-2)]'),
        ('rank', 'Рейтинг бойцов', 'каждый элемент замени его местом среди уникальных значений по возрастанию, начиная с 1', 'ranks={v:i+1 for i,v in enumerate(sorted(set(data)))}\nreturn [ranks[x] for x in data]'),
        ('freqsort', 'Архив повторений', 'отсортируй уникальные числа по убыванию частоты, при равенстве — по возрастанию значения', 'counts=Counter(data)\nreturn sorted(counts,key=lambda x:(-counts[x],x))'),
        ('local_peaks', 'Пики радара', 'верни индексы элементов строго больше обоих соседей; края не считаются', 'return [i for i in range(1,len(data)-1) if data[i]>data[i-1] and data[i]>data[i+1]]'),
        ('missing', 'Потерянные страницы', 'верни отсутствующие целые числа между минимумом и максимумом включительно; для пустого списка верни []', 'return [x for x in range(min(data),max(data)+1) if x not in set(data)] if data else []'),
        ('counts_prefix', 'Новые имена', 'для каждого префикса выведи число разных значений', 'seen=set()\nresult=[]\nfor x in data:\n    seen.add(x)\n    result.append(len(seen))\nreturn result'),
        ('last', 'Последние свидетели', 'сохрани только последнее появление каждого значения в исходном порядке', 'last={x:i for i,x in enumerate(data)}\nreturn [x for i,x in enumerate(data) if last[x]==i]'),
        ('neighbors_gcd', 'Общие ритмы', 'получи НОД модулей каждой пары соседних чисел; НОД(0,0)=0', 'return [math.gcd(a,b) for a,b in zip(data,data[1:])]'),
        ('digit_sum', 'Числовые амулеты', 'каждое число замени суммой цифр его модуля', 'return [sum(map(int,str(abs(x)))) for x in data]'),
        ('balanced', 'Равновесие складов', 'верни индексы, для которых сумма слева равна сумме справа, сам элемент не учитывай', 'total=sum(data)\nleft=0\nresult=[]\nfor i,x in enumerate(data):\n    if left==total-left-x: result.append(i)\n    left+=x\nreturn result'),
        ('streak', 'Серия восхождения', 'для каждой позиции выведи длину строго возрастающей непрерывной серии, заканчивающейся здесь', 'result=[]\nfor i,x in enumerate(data):\n    result.append(result[-1]+1 if i and x>data[i-1] else 1)\nreturn result'),
        ('positions', 'Первый след', 'каждый элемент замени индексом его первого появления', 'first={}\nreturn [first.setdefault(x,i) for i,x in enumerate(data)]'),
        ('gap', 'Разрывы маршрута', 'отсортируй уникальные числа по возрастанию и верни разности соседних значений', 'values=sorted(set(data))\nreturn [b-a for a,b in zip(values,values[1:])]'),
        ('median3', 'Шумоподавление', 'верни медианы всех окон длины 3', 'return [sorted(data[i:i+3])[1] for i in range(len(data)-2)]'),
        ('positive_runs', 'Рабочие смены', 'верни длины максимальных непрерывных серий строго положительных чисел', 'result=[]\ncount=0\nfor x in data+[0]:\n    if x>0: count+=1\n    elif count:\n        result.append(count)\n        count=0\nreturn result'),
        ('zero_pairs', 'Парные заряды', 'для каждого элемента выведи число предыдущих элементов, которые в сумме с ним дают ноль', 'seen=Counter()\nresult=[]\nfor x in data:\n    result.append(seen[-x])\n    seen[x]+=1\nreturn result'),
        ('suffix_max', 'Горизонт будущего', 'для каждой позиции запиши максимум от неё до конца', 'result=[]\nfor x in reversed(data): result.append(max(x,result[-1]) if result else x)\nreturn result[::-1]'),
        ('prefix_min', 'Глубина экспедиции', 'для каждой позиции запиши минимум от начала до неё', 'result=[]\nfor x in data: result.append(min(x,result[-1]) if result else x)\nreturn result'),
        ('alternating', 'Чередование энергий', 'выведи суммы префиксов со знаками +, -, +, - и так далее', 'result=[]\ns=0\nfor i,x in enumerate(data):\n    s+=x if i%2==0 else -x\n    result.append(s)\nreturn result'),
    ]
    for key,title,rule,body in b_specs:
        add('B',key,title,'Вход data — список целых чисел от -100 до 100. Построй последовательность: '+rule+'.',body,topic='dicts' if key in {'unique','freq','freqsort','positions','zero_pairs'} else 'lists')
    a_specs = [
        ('next_greater','Следующий сильный','для каждого числа найди индекс ближайшего справа строго большего; если его нет, -1', 'result=[-1]*len(data)\nstack=[]\nfor i,x in enumerate(data):\n    while stack and data[stack[-1]]<x: result[stack.pop()]=i\n    stack.append(i)\nreturn result'),
        ('prev_smaller','След меньшего','для каждого числа найди индекс ближайшего слева строго меньшего; если его нет, -1','result=[]\nstack=[]\nfor i,x in enumerate(data):\n    while stack and data[stack[-1]]>=x: stack.pop()\n    result.append(stack[-1] if stack else -1)\n    stack.append(i)\nreturn result'),
        ('max3','Патруль максимумов','найди максимумы всех скользящих окон длины 3 за O(n)','q=deque()\nresult=[]\nfor i,x in enumerate(data):\n    while q and q[0]<=i-3: q.popleft()\n    while q and data[q[-1]]<=x: q.pop()\n    q.append(i)\n    if i>=2: result.append(data[q[0]])\nreturn result'),
        ('kadane','Лучший привал','для каждой позиции найди максимальную сумму непустого непрерывного отрезка, заканчивающегося здесь','result=[]\nfor x in data: result.append(max(x,result[-1]+x) if result else x)\nreturn result'),
        ('robber','Несоседние тайники','для каждого префикса найди наибольшую сумму выбранных несоседних элементов; можно ничего не выбирать','a=b=0\nresult=[]\nfor x in data:\n    a,b=b,max(b,a+x)\n    result.append(b)\nreturn result'),
        ('inversions','Нарушенный строй','для каждого элемента посчитай предыдущие элементы строго больше него','seen=[]\nresult=[]\nfor x in data:\n    result.append(len(seen)-bisect.bisect_right(seen,x))\n    bisect.insort(seen,x)\nreturn result'),
        ('zero_subarrays','Нулевые участки','для каждого префикса посчитай в нём все непустые непрерывные отрезки с суммой ноль','seen=Counter({0:1})\ns=total=0\nresult=[]\nfor x in data:\n    s+=x\n    total+=seen[s]\n    seen[s]+=1\n    result.append(total)\nreturn result'),
        ('max_product','Произведение рун','для каждой позиции найди максимальное произведение непустого непрерывного отрезка, заканчивающегося здесь','result=[]\nlo=hi=1\nfor x in data:\n    lo,hi=min(x,x*lo,x*hi),max(x,x*lo,x*hi)\n    result.append(hi)\nreturn result'),
        ('lis','Лестница рекордов','для каждого префикса найди длину самой длинной строго возрастающей подпоследовательности за O(n log n)','tails=[]\nresult=[]\nfor x in data:\n    i=bisect.bisect_left(tails,x)\n    if i==len(tails): tails.append(x)\n    else: tails[i]=x\n    result.append(len(tails))\nreturn result'),
        ('rain','Резервуары дождя','для каждой позиции высоты abs(data[i]) найди количество воды между стенами после дождя, ширина позиции 1','heights=list(map(abs,data))\nleft=[]\nm=0\nfor x in heights:\n    m=max(m,x)\n    left.append(m)\nright=0\nresult=[0]*len(data)\nfor i in range(len(data)-1,-1,-1):\n    right=max(right,heights[i])\n    result[i]=min(left[i],right)-heights[i]\nreturn result'),
        ('partition','Метки разделов','разбей список на минимальные по длине последовательные части так, чтобы каждое значение встречалось только в одной части; верни длины частей','last={x:i for i,x in enumerate(data)}\nresult=[]\nend=start=0\nfor i,x in enumerate(data):\n    end=max(end,last[x])\n    if i==end:\n        result.append(i-start+1)\n        start=i+1\nreturn result'),
        ('asteroids','Столкновение осколков','числа — движущиеся осколки: положительные вправо, отрицательные влево; столкновение уничтожает меньший модуль, равные уничтожаются оба; нули игнорируй; верни уцелевших в исходном порядке','stack=[]\nfor x in data:\n    if not x: continue\n    while x<0 and stack and stack[-1]>0 and stack[-1]<-x: stack.pop()\n    if x<0 and stack and stack[-1]>0:\n        if stack[-1]==-x: stack.pop()\n    else: stack.append(x)\nreturn stack'),
        ('histogram','Опоры гистограммы','для каждого столбца высоты abs(data[i]) найди площадь наибольшего прямоугольника, содержащего столбец i и имеющего эту высоту','h=list(map(abs,data))\nleft=[]\nstack=[]\nfor i,x in enumerate(h):\n    while stack and h[stack[-1]]>=x: stack.pop()\n    left.append(stack[-1] if stack else -1)\n    stack.append(i)\nright=[len(h)]*len(h)\nstack=[]\nfor i in range(len(h)-1,-1,-1):\n    while stack and h[stack[-1]]>=h[i]: stack.pop()\n    if stack: right[i]=stack[-1]\n    stack.append(i)\nreturn [h[i]*(right[i]-left[i]-1) for i in range(len(h))]'),
        ('sorted_squares','Квадраты на двух берегах','сначала получи неубывающий массив исходных чисел; построй неубывающий список квадратов двумя указателями','a=sorted(data)\nresult=[0]*len(a)\nl,r=0,len(a)-1\nfor i in range(len(a)-1,-1,-1):\n    if abs(a[l])>abs(a[r]): result[i]=a[l]**2; l+=1\n    else: result[i]=a[r]**2; r-=1\nreturn result'),
        ('chunks','Безопасные секции','разбей список на максимальное число последовательных частей, сортировка каждой из которых и склейка дают глобально отсортированный список; верни длины частей','right=[float("inf")]*(len(data)+1)\nfor i in range(len(data)-1,-1,-1): right[i]=min(right[i+1],data[i])\nm=float("-inf")\nstart=0\nresult=[]\nfor i,x in enumerate(data):\n    m=max(m,x)\n    if m<=right[i+1]:\n        result.append(i-start+1)\n        start=i+1\nreturn result'),
        ('daily_wait','Ожидание тепла','для каждой позиции найди, сколько шагов до ближайшего строго большего числа справа; если его нет, 0','result=[0]*len(data)\nstack=[]\nfor i,x in enumerate(data):\n    while stack and data[stack[-1]]<x:\n        j=stack.pop()\n        result[j]=i-j\n    stack.append(i)\nreturn result'),
        ('span','Биржевой дозор','для каждой позиции посчитай число подряд идущих элементов слева, включая текущий, не превосходящих текущий','stack=[]\nresult=[]\nfor x in data:\n    n=1\n    while stack and stack[-1][0]<=x: n+=stack.pop()[1]\n    stack.append((x,n))\n    result.append(n)\nreturn result'),
        ('unique_window','Маршрут без повторов','для каждого правого края найди длину самого длинного непрерывного отрезка без повторений, заканчивающегося здесь','last={}\nleft=0\nresult=[]\nfor i,x in enumerate(data):\n    left=max(left,last.get(x,-1)+1)\n    last[x]=i\n    result.append(i-left+1)\nreturn result'),
        ('two_types','Два типа рун','для каждого правого края найди длину самого длинного отрезка, заканчивающегося здесь и содержащего не более двух разных чисел','counts=Counter()\nleft=0\nresult=[]\nfor i,x in enumerate(data):\n    counts[x]+=1\n    while len(counts)>2:\n        y=data[left]\n        counts[y]-=1\n        if not counts[y]: del counts[y]\n        left+=1\n    result.append(i-left+1)\nreturn result'),
        ('products','Все кроме одного','для каждой позиции найди произведение всех элементов кроме неё по модулю 1000000007 без деления; пустой вход даёт [], одиночный — [1]','result=[1]*len(data)\np=1\nfor i,x in enumerate(data): result[i]=p; p=p*x%1000000007\np=1\nfor i in range(len(data)-1,-1,-1): result[i]=result[i]*p%1000000007; p=p*data[i]%1000000007\nreturn result'),
        ('gcd_counts','Сжатие НОД','для каждого правого края посчитай число различных НОД модулей непустых отрезков, заканчивающихся здесь','previous=set()\nresult=[]\nfor x in data:\n    previous={abs(x)}|{math.gcd(g,x) for g in previous}\n    result.append(len(previous))\nreturn result'),
        ('abs_sort','Кодекс устойчивости','верни индексы элементов в порядке возрастания модуля, при равных модулях сохраняй исходный порядок','return sorted(range(len(data)),key=lambda i:abs(data[i]))'),
        ('next_permutation','Следующий пароль','получи следующую лексикографическую перестановку чисел; если её нет, верни числа по возрастанию','a=data[:]\ni=len(a)-2\nwhile i>=0 and a[i]>=a[i+1]: i-=1\nif i>=0:\n    j=len(a)-1\n    while a[j]<=a[i]: j-=1\n    a[i],a[j]=a[j],a[i]\na[i+1:]=reversed(a[i+1:])\nreturn a'),
        ('subarray_min','Минимумы у правой границы','для каждого правого края найди сумму минимумов всех непустых отрезков, заканчивающихся здесь','stack=[]\nresult=[]\ntotal=0\nfor x in data:\n    n=1\n    while stack and stack[-1][0]>=x:\n        v,c=stack.pop()\n        total-=v*c\n        n+=c\n    stack.append((x,n))\n    total+=x*n\n    result.append(total)\nreturn result'),
        ('median_prefix','Живая медиана','для каждого непустого префикса найди нижнюю медиану (элемент с индексом (длина-1)//2 в отсортированной копии)','low=[]\nhigh=[]\nresult=[]\nfor x in data:\n    heapq.heappush(low,-x)\n    heapq.heappush(high,-heapq.heappop(low))\n    if len(low)<len(high): heapq.heappush(low,-heapq.heappop(high))\n    result.append(-low[0])\nreturn result'),
    ]
    for key,title,rule,body in a_specs:
        inputs = [[], [0], [3,-1,3,0,-4,2], [5,5,5], [-9,-2,-9]] + [[rng.randrange(-2,3) for _ in range(n)] for n in (2,7,12,18,20,25,30,40,45)] if key == 'max_product' else arrays
        add('A',key,title,'Вход data — список целых чисел. Построй последовательность: '+rule+'. Пустой вход даёт пустую последовательность.',body,inputs)
    out.extend(expert_problems(rng))
    return out


def expert_problems(rng):
    out=[]
    def add(key,title,rule,body,inputs):
        out.append(problem('S',key,title,rule,body,inputs))
    graphs=[{'n':0,'edges':[]},{'n':1,'edges':[]}, {'n':4,'edges':[[0,1,2],[1,2,3]]}, {'n':3,'edges':[[0,1,4],[1,2,1],[2,0,2]]}]
    for n in (2,5,8,12,20,30,40,50,60,70):
        graphs.append({'n':n,'edges':[[a,b,rng.randrange(1,10)] for a in range(n) for b in range(n) if a!=b and rng.random()<.09]})
    graph_rule='data — словарь {"n": n, "edges": [[u,v,w], ...]}, вершины 0..n-1, веса w — целые 1..9. При n=0 рёбер нет. '
    add('bfs','Маяки туманности',graph_rule+'Рёбра ориентированы. Построй список минимальных чисел рёбер из вершины 0 до каждой вершины; недостижимые пометь -1. Требуется O(n+m).',
        'n=data["n"]\ng=[[] for _ in range(n)]\nfor u,v,w in data["edges"]: g[u].append(v)\nd=[-1]*n\nq=deque([0] if n else [])\nif n: d[0]=0\nwhile q:\n    u=q.popleft()\n    for v in g[u]:\n        if d[v]<0:\n            d[v]=d[u]+1\n            q.append(v)\nreturn d',graphs)
    add('dijkstra','Стоимость звёздных переходов',graph_rule+'Рёбра ориентированы. Построй расстояния по весам от 0, недостижимые -1. Используй очередь с приоритетом, O((n+m) log(n+m)).',
        'n=data["n"]\ng=[[] for _ in range(n)]\nfor u,v,w in data["edges"]: g[u].append((v,w))\nd=[math.inf]*n\nq=[]\nif n: d[0]=0; q=[(0,0)]\nwhile q:\n    dist,u=heapq.heappop(q)\n    if dist!=d[u]: continue\n    for v,w in g[u]:\n        if dist+w<d[v]:\n            d[v]=dist+w\n            heapq.heappush(q,(d[v],v))\nreturn [-1 if x==math.inf else x for x in d]',graphs)
    add('components','Острова созвездий',graph_rule+'Считай рёбра неориентированными, веса игнорируй. Верни размеры компонент связности, отсортированные по возрастанию. O(n+m).',
        'n=data["n"]\ng=[[] for _ in range(n)]\nfor u,v,w in data["edges"]: g[u].append(v); g[v].append(u)\nseen=set()\nresult=[]\nfor root in range(n):\n    if root in seen: continue\n    seen.add(root)\n    stack=[root]\n    size=0\n    while stack:\n        u=stack.pop(); size+=1\n        for v in g[u]:\n            if v not in seen: seen.add(v); stack.append(v)\n    result.append(size)\nreturn sorted(result)',graphs)
    add('bipartite','Два цвета альянса',graph_rule+'Считай рёбра неориентированными. Для компонент в порядке их минимальной вершины верни 1, если компоненту можно раскрасить в два цвета, иначе 0. O(n+m).',
        'n=data["n"]\ng=[[] for _ in range(n)]\nfor u,v,w in data["edges"]: g[u].append(v); g[v].append(u)\ncolors={}\nresult=[]\nfor root in range(n):\n    if root in colors: continue\n    colors[root]=0; q=deque([root]); ok=1\n    while q:\n        u=q.popleft()\n        for v in g[u]:\n            if v not in colors: colors[v]=1-colors[u]; q.append(v)\n            elif colors[v]==colors[u]: ok=0\n    result.append(ok)\nreturn result',graphs)
    add('topological','Порядок запуска порталов',graph_rule+'Рёбра ориентированы. Построй лексикографически минимальный топологический порядок вершин; если есть цикл, последовательность пуста. O((n+m) log n).',
        'n=data["n"]\ng=[[] for _ in range(n)]; degree=[0]*n\nfor u,v,w in data["edges"]: g[u].append(v); degree[v]+=1\nq=[i for i in range(n) if not degree[i]]\nheapq.heapify(q)\nresult=[]\nwhile q:\n    u=heapq.heappop(q); result.append(u)\n    for v in g[u]:\n        degree[v]-=1\n        if not degree[v]: heapq.heappush(q,v)\nreturn result if len(result)==n else []',graphs)
    add('scc','Замкнутые миры',graph_rule+'Найди компоненты сильной связности ориентированного графа. Верни их размеры по возрастанию. Требуется O(n+m), без рекурсивного обхода.',
        'n=data["n"]\ng=[[] for _ in range(n)]; rev=[[] for _ in range(n)]\nfor u,v,w in data["edges"]: g[u].append(v); rev[v].append(u)\nseen=set(); order=[]\nfor root in range(n):\n    if root in seen: continue\n    seen.add(root); stack=[(root,iter(g[root]))]\n    while stack:\n        u,children=stack[-1]\n        v=next(children,None)\n        if v is None: stack.pop(); order.append(u)\n        elif v not in seen: seen.add(v); stack.append((v,iter(g[v])))\nseen=set(); result=[]\nfor root in reversed(order):\n    if root in seen: continue\n    seen.add(root); stack=[root]; size=0\n    while stack:\n        u=stack.pop(); size+=1\n        for v in rev[u]:\n            if v not in seen: seen.add(v); stack.append(v)\n    result.append(size)\nreturn sorted(result)',graphs)
    # DAG fixtures preserve edge order and exercise disconnected vertices.
    dags=[{'n':g['n'],'edges':[e for e in g['edges'] if e[0]<e[1]]} for g in graphs]
    add('dag_paths','Развилки будущего',graph_rule+'Гарантировано u<v. Посчитай число путей из 0 в каждую вершину по модулю 1000000007. Пустой путь в 0 считается одним. Каждое ребро — отдельный выбор. O(n+m).',
        'n=data["n"]; g=[[] for _ in range(n)]\nfor u,v,w in data["edges"]: g[u].append(v)\nways=[0]*n\nif n: ways[0]=1\nfor u in range(n):\n    for v in g[u]: ways[v]=(ways[v]+ways[u])%1000000007\nreturn ways',dags)
    add('dag_longest','Длинная дорога к ядру',graph_rule+'Гарантировано u<v. Построй максимальные суммарные веса путей из 0; для недостижимых вершин -1, для 0 — 0. O(n+m).',
        'n=data["n"]; g=[[] for _ in range(n)]\nfor u,v,w in data["edges"]: g[u].append((v,w))\nd=[-1]*n\nif n: d[0]=0\nfor u in range(n):\n    if d[u]<0: continue\n    for v,w in g[u]: d[v]=max(d[v],d[u]+w)\nreturn d',dags)
    add('kruskal','Сеть без лишних мостов',graph_rule+'Считай рёбра неориентированными. Построй минимальный остовный лес алгоритмом Краскала. Перебирай рёбра по (вес, min(u,v), max(u,v)); верни веса принятых рёбер в этом порядке. O(m log m).',
        'n=data["n"]; parent=list(range(n)); size=[1]*n\ndef find(x):\n    while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]\n    return x\nresult=[]\nfor w,u,v in sorted((w,min(u,v),max(u,v)) for u,v,w in data["edges"]):\n    a,b=find(u),find(v)\n    if a==b: continue\n    if size[a]<size[b]: a,b=b,a\n    parent[b]=a; size[a]+=size[b]; result.append(w)\nreturn result',graphs)
    add('floyd','Атлас всех расстояний',graph_rule+'Рёбра ориентированы. Найди кратчайшие расстояния между всеми парами. Разверни матрицу построчно в список, недостижимые замени -1, диагональ — 0. O(n³).',
        'n=data["n"]; d=[[math.inf]*n for _ in range(n)]\nfor i in range(n): d[i][i]=0\nfor u,v,w in data["edges"]: d[u][v]=min(d[u][v],w)\nfor k in range(n):\n    for i in range(n):\n        if d[i][k]==math.inf: continue\n        for j in range(n): d[i][j]=min(d[i][j],d[i][k]+d[k][j])\nreturn [-1 if x==math.inf else x for row in d for x in row]',graphs[:10])
    strings=['','a','aaaaa','abacaba','abcababcab','абракадабра']+[''.join(rng.choices('abca',k=n)) for n in (2,7,15,30,55,80,100,150)]
    add('kmp','Пограничные заклинания','data — строка. Построй её префикс-функцию: на позиции i длина наибольшего собственного префикса data[:i+1], совпадающего с суффиксом. O(n).',
        'p=[0]*len(data)\nfor i in range(1,len(data)):\n    j=p[i-1]\n    while j and data[i]!=data[j]: j=p[j-1]\n    if data[i]==data[j]: j+=1\n    p[i]=j\nreturn p',strings)
    add('z','Эхо начала','data — строка. Построй Z-функцию: z[i] — длина общего префикса data и data[i:]. Прими z[0]=0. O(n).',
        'n=len(data); z=[0]*n; l=r=0\nfor i in range(1,n):\n    if i<r: z[i]=min(r-i,z[i-l])\n    while i+z[i]<n and data[z[i]]==data[i+z[i]]: z[i]+=1\n    if i+z[i]>r: l,r=i,i+z[i]\nreturn z',strings)
    add('manacher','Зеркала нечётной длины','data — строка. Для каждого центра i найди радиус нечётного палиндрома: число символов от центра до края включительно (один символ имеет радиус 1). O(n).',
        'n=len(data); d=[0]*n; l=0; r=-1\nfor i in range(n):\n    k=1 if i>r else min(d[l+r-i],r-i+1)\n    while i-k>=0 and i+k<n and data[i-k]==data[i+k]: k+=1\n    d[i]=k\n    if i+k-1>r: l,r=i-k+1,i+k-1\nreturn d',strings)
    add('suffix_array','Лексикон суффиксов','data — строка. Верни индексы начал всех непустых суффиксов в лексикографическом порядке по кодам Unicode. Используй удвоение рангов, O(n log² n).',
        'n=len(data); sa=list(range(n)); ranks=[ord(c) for c in data]; k=1\nwhile k<n:\n    sa.sort(key=lambda i:(ranks[i],ranks[i+k] if i+k<n else -1))\n    new=[0]*n\n    for j in range(1,n):\n        a,b=sa[j-1],sa[j]\n        new[b]=new[a]+((ranks[a],ranks[a+k] if a+k<n else -1)!=(ranks[b],ranks[b+k] if b+k<n else -1))\n    ranks=new\n    if not n or ranks[sa[-1]]==n-1: break\n    k*=2\nreturn sa',strings)
    add('pal_even','Парные зеркала','data — строка. Для каждого i верни радиус самого длинного чётного палиндрома с центром между i-1 и i (число пар). O(n).',
        'n=len(data); d=[0]*n; l=0; r=-1\nfor i in range(n):\n    k=0 if i>r else min(d[l+r-i+1],r-i+1)\n    while i-k-1>=0 and i+k<n and data[i-k-1]==data[i+k]: k+=1\n    d[i]=k\n    if i+k-1>r: l,r=i-k,i+k-1\nreturn d',strings)
    pairs=[['',''],['','abc'],['abc',''],['abac','baca'],['aaaa','aa'],['кот','кит']]+[[''.join(rng.choices('abc',k=n)),''.join(rng.choices('abc',k=n//2+2))] for n in (2,7,12,20,30,40,60,80)]
    add('lcs','Общие хроники','data=[a,b] — две строки. Для каждого непустого префикса b выведи длину его наибольшей общей подпоследовательности с полной строкой a. O(len(a)*len(b)), O(len(b)) памяти.',
        'a,b=data; row=[0]*(len(b)+1)\nfor x in a:\n    prev=0\n    for j,y in enumerate(b,1):\n        old=row[j]\n        row[j]=prev+1 if x==y else max(row[j],row[j-1])\n        prev=old\nreturn row[1:]',pairs)
    add('edit','Редактор древних имён','data=[a,b] — две строки. Для каждого непустого префикса b верни расстояние Левенштейна до полной строки a. Вставка, удаление, замена стоят 1. O(len(a)*len(b)), O(len(b)) памяти.',
        'a,b=data; row=list(range(len(b)+1))\nfor i,x in enumerate(a,1):\n    new=[i]+[0]*len(b)\n    for j,y in enumerate(b,1): new[j]=min(row[j]+1,new[j-1]+1,row[j-1]+(x!=y))\n    row=new\nreturn row[1:]',pairs)
    coins=[{'coins':[],'limit':0},{'coins':[],'limit':5},{'coins':[1,2,5],'limit':12},{'coins':[2,4],'limit':9}]+[{'coins':sorted(rng.sample(range(1,16),rng.randrange(1,7))),'limit':n} for n in (1,5,10,20,35,50,70,100,130,160)]
    add('coin_ways','Монетный архив','data={"coins": список разных положительных номиналов, "limit": неотрицательная сумма}. Для сумм от 0 до limit включительно посчитай число неупорядоченных способов оплаты при неограниченном числе монет по модулю 1000000007. Сумма 0 имеет один способ. O(limit*len(coins)).',
        'dp=[1]+[0]*data["limit"]\nfor coin in data["coins"]:\n    for s in range(coin,len(dp)): dp[s]=(dp[s]+dp[s-coin])%1000000007\nreturn dp',coins)
    add('coin_min','Лёгкий кошелёк','data={"coins": разные положительные номиналы, "limit": неотрицательная сумма}. Для сумм 0..limit верни минимальное число монет; невозможные суммы -1. Запас монет неограничен. O(limit*len(coins)).',
        'n=data["limit"]; dp=[0]+[n+1]*n\nfor s in range(1,n+1):\n    for c in data["coins"]:\n        if c<=s: dp[s]=min(dp[s],dp[s-c]+1)\nreturn [-1 if x>n else x for x in dp]',coins)
    sacks=[{'items':[],'capacity':0},{'items':[],'capacity':5},{'items':[[2,3],[3,5],[2,4]],'capacity':7}]+[{'items':[[rng.randrange(1,12),rng.randrange(0,30)] for _ in range(n)],'capacity':n*3} for n in (1,2,4,7,10,15,20,30,40,50,60)]
    add('knapsack','Груз одиночной экспедиции','data={"items": [[вес,ценность],...], "capacity": вместимость}. Для каждой вместимости от 0 до capacity найди максимальную ценность; каждый предмет можно взять не более одного раза. Веса положительные, ценности неотрицательные. O(len(items)*capacity).',
        'dp=[0]*(data["capacity"]+1)\nfor weight,value in data["items"]:\n    for c in range(data["capacity"],weight-1,-1): dp[c]=max(dp[c],dp[c-weight]+value)\nreturn dp',sacks)
    grids=[[],[[]],[[0]],[[1,0,1],[1,0,0],[0,1,1]],[[1,2,3],[4,0,2]]]+[[[rng.randrange(0,4) for _ in range(n+1)] for _ in range(n)] for n in (1,2,3,4,5,7,9,12,16)]
    add('grid_paths','Безопасный спуск','data — прямоугольная матрица неотрицательных стоимостей. Из (0,0) можно идти вправо или вниз. Верни минимальные стоимости путей до каждой клетки последней строки с учётом обеих конечных клеток. Если клеток нет, []. O(rows*cols), O(cols) памяти.',
        'if not data or not data[0]: return []\ndp=[math.inf]*len(data[0]); dp[0]=0\nfor row in data:\n    for j,x in enumerate(row): dp[j]=min(dp[j],dp[j-1] if j else math.inf)+x\nreturn dp',grids)
    add('islands','Материки архипелага','data — прямоугольная матрица неотрицательных чисел. Клетки со значением >0 — суша, остальные вода. Соседство по стороне. Верни площади островов по возрастанию. Не меняй вход. O(rows*cols).',
        'if not data or not data[0]: return []\nr,c=len(data),len(data[0]); seen=set(); result=[]\nfor i in range(r):\n    for j in range(c):\n        if not data[i][j] or (i,j) in seen: continue\n        seen.add((i,j)); stack=[(i,j)]; size=0\n        while stack:\n            x,y=stack.pop(); size+=1\n            for a,b in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):\n                if 0<=a<r and 0<=b<c and data[a][b]>0 and (a,b) not in seen:\n                    seen.add((a,b)); stack.append((a,b))\n        result.append(size)\nreturn sorted(result)',grids)
    schedules=[[],[[0,1,5]],[[0,3,8],[1,2,9],[2,4,7],[4,5,1]],[[1,2,4],[1,2,6]]]+[[[a,a+rng.randrange(1,9),rng.randrange(0,30)] for a in [rng.randrange(0,40) for _ in range(n)]] for n in (2,5,10,20,35,50,70,90,120,160)]
    add('weighted_jobs','Расписание хранителя','data — интервалы [начало,конец,награда], начало<конец, награда≥0. Отсортируй задания по (конец,начало,награда). Для каждого префикса этого порядка найди максимум награды непересекающихся заданий. Касание концов разрешено. O(n log n).',
        'jobs=sorted(data,key=lambda x:(x[1],x[0],x[2])); ends=[x[1] for x in jobs]; dp=[0]\nfor i,(start,end,value) in enumerate(jobs):\n    p=bisect.bisect_right(ends,start,0,i)\n    dp.append(max(dp[-1],dp[p]+value))\nreturn dp[1:]',schedules)
    streams=[{'values':[],'ops':[]},{'values':[5],'ops':[['sum',0,1],['add',0,-3],['sum',0,1]]}]
    for n in (1,2,4,8,16,25,40,60,80,100,120,150):
        values=[rng.randrange(-20,21) for _ in range(n)]
        ops=[]
        for _ in range(n+7):
            if rng.random()<.4: ops.append(['add',rng.randrange(n),rng.randrange(-5,6)])
            else:
                a=rng.randrange(n+1); b=rng.randrange(a,n+1); ops.append(['sum',a,b])
        streams.append({'values':values,'ops':ops})
    add('fenwick','Журнал меняющихся запасов','data={"values": список целых, "ops": операции}. ["add",i,x] увеличивает values[i] на x; ["sum",l,r] запрашивает сумму полуинтервала [l,r). Верни ответы на запросы sum. Индексы валидны, пустые диапазоны дают 0. Используй дерево Фенвика, O((n+q) log(n+1)). Не меняй вход.',
        'a=data["values"]; n=len(a); tree=[0]*(n+1)\ndef add(i,x):\n    i+=1\n    while i<=n: tree[i]+=x; i+=i&-i\ndef prefix(i):\n    result=0\n    while i: result+=tree[i]; i-=i&-i\n    return result\nfor i,x in enumerate(a): add(i,x)\nresult=[]\nfor op,i,x in data["ops"]:\n    if op=="add": add(i,x)\n    else: result.append(prefix(x)-prefix(i))\nreturn result',streams)
    add('segment_min','Минимум на живом маршруте','data={"values": список целых, "ops": операции}. ["add",i,x] увеличивает values[i] на x; ["min",l,r] запрашивает минимум на [l,r). Верни ответы минимумов; пустой диапазон даёт 0. Используй дерево отрезков, O((n+q) log(n+1)). Не меняй вход.',
        'n=len(data["values"]); size=1\nwhile size<n: size*=2\ntree=[math.inf]*(2*size)\ntree[size:size+n]=data["values"]\nfor i in range(size-1,0,-1): tree[i]=min(tree[2*i],tree[2*i+1])\nresult=[]\nfor op,a,b in data["ops"]:\n    if op=="add":\n        i=size+a; tree[i]+=b; i//=2\n        while i: tree[i]=min(tree[2*i],tree[2*i+1]); i//=2\n    else:\n        if a==b: result.append(0); continue\n        l,r=a+size,b+size; value=math.inf\n        while l<r:\n            if l%2: value=min(value,tree[l]); l+=1\n            if r%2: r-=1; value=min(value,tree[r])\n            l//=2; r//=2\n        result.append(value)\nreturn result',[{'values':d['values'],'ops':[[('min' if op=='sum' else op),a,b] for op,a,b in d['ops']]} for d in streams])
    return out


D_OBJECTIVES = [
    ('расчёт','Верни найденное целое число.',lambda value,a,b:value),
    ('двойной рейс','Верни удвоенное найденное значение — запас на два одинаковых рейса.',lambda value,a,b:value*2),
    ('поправка','Добавь к найденному значению b запасных единиц и верни целое число.',lambda value,a,b:value+b),
    ('разница','Верни разницу между найденным значением и исходным a: значение минус a. Отрицательные ответы разрешены.',lambda value,a,b:value-a),
    ('группы по семь','Верни список из частного и остатка при делении найденного значения на 7 (правила // и % Python).',lambda value,a,b:[value//7,value%7]),
    ('маркировка','Верни найденное значение как десятичную строку с ведущими нулями до длины не меньше 4. Знак минус входит в длину: -1 превращается в \"-001\". Более длинные числа не обрезай.',lambda value,a,b:str(value).zfill(4)),
    ('журнал','Верни словарь {"value": найденное значение, "above_limit": найденное значение > a}.',lambda value,a,b:{'value':value,'above_limit':value>a}),
    ('шифр','Верни строку вида "R=<значение>;K=<остаток от деления значения на b>", без пробелов.',lambda value,a,b:f'R={value};K={value%b}'),
]

OBJECTIVES = [
    ('маршрут','Верни полученную последовательность как список целых чисел.',lambda a:a),
    ('сводка','Верни словарь {"count": длина последовательности, "total": сумма её элементов}. Для пустой последовательности оба значения 0.',lambda a:{'count':len(a),'total':sum(a)}),
    ('границы','Верни [минимум, максимум] последовательности; для пустой верни [0,0].',lambda a:[min(a),max(a)] if a else [0,0]),
    ('подпись','Верни контрольную сумму: сумму (i+1)*sequence[i], где индексы i начинаются с 0; для пустой 0.',lambda a:sum((i+1)*x for i,x in enumerate(a))),
    ('отбор','Верни индексы элементов построенной последовательности, не равных нулю, в порядке возрастания.',lambda a:[i for i,x in enumerate(a) if x!=0]),
    ('накопление','Верни список сумм всех непустых префиксов построенной последовательности; для пустой [].',lambda a:prefixes(a)),
    ('серии','Сожми построенную последовательность в список [значение, длина серии] для каждой максимальной серии одинаковых соседних значений; пустая даёт [].',lambda a:run_pairs(a)),
    ('частоты','Верни список [значение, частота] для всех разных значений построенной последовательности по возрастанию значения; пустая даёт [].',lambda a:[[v,c] for v,c in sorted(Counter(a).items())]),
]


def prefixes(values):
    out=[]; total=0
    for x in values:
        total+=x; out.append(total)
    return out


def run_pairs(values):
    out=[]
    for x in values:
        if out and out[-1][0]==x: out[-1][1]+=1
        else: out.append([x,1])
    return out


def short_title(title, label):
    while len(title)+len(label)+2>40 and ' ' in title:
        title=title.rsplit(' ',1)[0]
    return f'{title}: {label}'


def build_tasks():
    tasks=[]
    problems=curriculum()
    assert Counter(p.tier for p in problems)=={t:25 for t in 'DCBAS'}
    for p in problems:
        reference=p.reference()
        variants=D_OBJECTIVES if p.tier=='D' else OBJECTIVES
        for v,(label,objective,project) in enumerate(variants,1):
            cases=[]
            for data in p.inputs:
                args=data if p.tier=='D' else (data,)
                value=reference(*copy.deepcopy(args))
                expected=project(value,*args) if p.tier=='D' else project(value)
                cases.append({'code':'solve('+', '.join(repr(x) for x in args)+')','expected':expected})
            # Examples include an empty/zero, a regular and an edge case;
            # the remaining deterministic cases are kept server-side.
            visible_indices=[0,2,3]
            visible=[cases[i] for i in visible_indices]
            hidden=[c for i,c in enumerate(cases) if i not in visible_indices]
            description=(f'Реализуй функцию `solve({p.signature})`.\n\n{p.rule}\n\n'
                         f'Цель миссии «{label}»: {objective}\n'
                         'Не изменяй входные данные. Верни результат через return, не печатай его. Указанная сложность относится к построению базовой последовательности; обработка результата может добавить сортировку.\n\nПримеры:\n'+
                         '\n'.join(f"{c['code']} → {c['expected']!r}" for c in visible)+
                         '\n\nВ объяснении опиши вход, алгоритм, результат и один граничный случай.')
            tasks.append({
                'id':f'py_expedition_{p.tier.lower()}_{p.key}_{v:02d}',
                'category':'python','tier':p.tier,'topic':p.topic,
                'xp':{'D':25,'C':65,'B':150,'A':300,'S':500}[p.tier],
                'title':short_title(p.title,label),
                'story':f'Экспедиция Пандоры готовит модуль «{p.title}». Твоя миссия — {label}; обработай данные по правилам и объясни работу модуля.',
                'description':description,'initial_code':f'def solve({p.signature}):\n    # {objective}\n    pass\n',
                'resources':{'docs':[{'title':'Python: структуры данных и алгоритмы','url':'https://docs.python.org/3/tutorial/datastructures.html'}],
                             'videos':[{'title':'Python: курс freeCodeCamp (EN)','url':'https://www.youtube.com/watch?v=rfscVS0vtbw'}]},
                'check_logic':{'engine':'pyodide','cases':visible,'hidden_cases':hidden},
                'source_pack':PACK,
            })
    assert Counter(t['tier'] for t in tasks)=={t:200 for t in 'DCBAS'}
    assert len({t['id'] for t in tasks})==1000
    return tasks


def main():
    path=ROOT/'tasks.json'
    data=json.loads(path.read_text())
    tasks=build_tasks()
    # Re-running updates this pack only; existing IDs, order and metadata survive.
    old=[t for t in data['tasks'] if t.get('source_pack')!=PACK]
    assert not ({t['id'] for t in old}&{t['id'] for t in tasks})
    data['tasks']=old+tasks
    data['meta']['python_expeditions_20261015']={'total':1000,'per_tier':200,'tiers':list('DCBAS')}
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2))
    print('Added 1000 Python tasks: 200 per tier D, C, B, A, S.')


if __name__=='__main__':
    main()
