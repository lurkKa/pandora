#!/usr/bin/env python3
"""Generate JS tasks with proper tier progression."""
import json, random

TIERS = ["D","C","B","A","S"]
XP = {"D":(50,60),"C":(80,120),"B":(150,200),"A":(250,400),"S":(500,600)}
STORIES = {
    "D":["Юный странник получает первое задание гильдии.","Смотритель башни доверил тебе базовое заклинание.","Новобранец проходит вступительное испытание."],
    "C":["Караван готовится к переходу через перевал.","В мастерской алхимика нужны аккуратные расчёты.","Гильдия торговцев просит навести порядок."],
    "B":["Разведчики принесли отчёт из руин. Обработай.","Арсенал гильдии растёт. Построй надёжную логику.","Маг-архивариус поручил упорядочить свитки."],
    "A":["Совет магов поручил задачу повышенной сложности.","Хроники цитадели содержат запутанные данные.","Командор крепости требует оптимальную стратегию."],
    "S":["Испытание мастеров у врат древнего ядра.","Архимаги запускают финальный протокол башни.","Последний страж кода открывает портал."],
}

JS = [
  # D: basics
  {"id":"js_v3_d_01","tier":"D","title":"Приветствие JS","desc":"Напиши функцию `greet(name)`, возвращающую `'Hello, <name>!'`.",
   "init":"function greet(name) {\n  // return greeting\n  return '';\n}","cases":[{"code":"greet('World')","expected":"Hello, World!"},{"code":"greet('')","expected":"Hello, !"}]},
  {"id":"js_v3_d_02","tier":"D","title":"Сумма двух","desc":"Напиши функцию `add(a, b)`, возвращающую сумму.",
   "init":"function add(a, b) {\n  return 0;\n}","cases":[{"code":"add(2,3)","expected":5},{"code":"add(-1,1)","expected":0}]},
  {"id":"js_v3_d_03","tier":"D","title":"Тип данных","desc":"Напиши функцию `getType(x)`, возвращающую typeof x.",
   "init":"function getType(x) {\n  return '';\n}","cases":[{"code":"getType(42)","expected":"number"},{"code":"getType('hi')","expected":"string"},{"code":"getType(true)","expected":"boolean"}]},
  {"id":"js_v3_d_04","tier":"D","title":"Длина массива","desc":"Напиши функцию `arrLen(arr)`, возвращающую длину массива.",
   "init":"function arrLen(arr) {\n  return 0;\n}","cases":[{"code":"arrLen([1,2,3])","expected":3},{"code":"arrLen([])","expected":0}]},
  {"id":"js_v3_d_05","tier":"D","title":"Последний элемент","desc":"Напиши функцию `last(arr)`, возвращающую последний элемент массива или undefined.",
   "init":"function last(arr) {\n  return undefined;\n}","cases":[{"code":"last([1,2,3])","expected":3},{"code":"last(['a'])","expected":"a"}]},
  {"id":"js_v3_d_06","tier":"D","title":"Чётность JS","desc":"Напиши функцию `isEven(n)`, возвращающую true если число чётное.",
   "init":"function isEven(n) {\n  return false;\n}","cases":[{"code":"isEven(4)","expected":True},{"code":"isEven(7)","expected":False},{"code":"isEven(0)","expected":True}]},
  {"id":"js_v3_d_07","tier":"D","title":"Строка в число","desc":"Напиши функцию `toNum(s)`, конвертирующую строку в число.",
   "init":"function toNum(s) {\n  return 0;\n}","cases":[{"code":"toNum('42')","expected":42},{"code":"toNum('-5')","expected":-5}]},
  {"id":"js_v3_d_08","tier":"D","title":"Конкатенация","desc":"Напиши функцию `concat(a, b)`, объединяющую два массива.",
   "init":"function concat(a, b) {\n  return [];\n}","cases":[{"code":"concat([1,2],[3,4])","expected":[1,2,3,4]},{"code":"concat([],[1])","expected":[1]}]},
  {"id":"js_v3_d_09","tier":"D","title":"Минимум","desc":"Напиши функцию `min2(a, b)`, возвращающую меньшее из двух чисел.",
   "init":"function min2(a, b) {\n  return 0;\n}","cases":[{"code":"min2(3,7)","expected":3},{"code":"min2(-1,5)","expected":-1},{"code":"min2(4,4)","expected":4}]},
  {"id":"js_v3_d_10","tier":"D","title":"Повтор строки","desc":"Напиши функцию `repeatStr(s, n)`, повторяющую строку n раз.",
   "init":"function repeatStr(s, n) {\n  return '';\n}","cases":[{"code":"repeatStr('ab',3)","expected":"ababab"},{"code":"repeatStr('x',0)","expected":""}]},

  # C: functions, conditions, loops
  {"id":"js_v3_c_01","tier":"C","title":"FizzBuzz JS","desc":"Напиши функцию `fizzBuzz(n)`: 'FizzBuzz' если делится на 15, 'Fizz' на 3, 'Buzz' на 5, иначе число строкой.",
   "init":"function fizzBuzz(n) {\n  return '';\n}","cases":[{"code":"fizzBuzz(15)","expected":"FizzBuzz"},{"code":"fizzBuzz(9)","expected":"Fizz"},{"code":"fizzBuzz(10)","expected":"Buzz"},{"code":"fizzBuzz(7)","expected":"7"}]},
  {"id":"js_v3_c_02","tier":"C","title":"Разворот массива","desc":"Напиши функцию `reverseArr(arr)`, разворачивающую массив без .reverse().",
   "init":"function reverseArr(arr) {\n  return [];\n}","cases":[{"code":"reverseArr([1,2,3])","expected":[3,2,1]},{"code":"reverseArr([])","expected":[]}]},
  {"id":"js_v3_c_03","tier":"C","title":"Палиндром JS","desc":"Напиши функцию `isPalindrome(s)`, проверяющую палиндром (без учёта регистра).",
   "init":"function isPalindrome(s) {\n  return false;\n}","cases":[{"code":"isPalindrome('Racecar')","expected":True},{"code":"isPalindrome('hello')","expected":False}]},
  {"id":"js_v3_c_04","tier":"C","title":"Сумма массива","desc":"Напиши функцию `sumArr(arr)`, суммирующую все числа без .reduce().",
   "init":"function sumArr(arr) {\n  return 0;\n}","cases":[{"code":"sumArr([1,2,3,4])","expected":10},{"code":"sumArr([])","expected":0},{"code":"sumArr([-1,1])","expected":0}]},
  {"id":"js_v3_c_05","tier":"C","title":"Подсчёт символов","desc":"Напиши функцию `charCount(s)`, возвращающую объект с подсчётом каждого символа.",
   "init":"function charCount(s) {\n  return {};\n}","cases":[{"code":"charCount('aab')","expected":{"a":2,"b":1}},{"code":"charCount('')","expected":{}}]},
  {"id":"js_v3_c_06","tier":"C","title":"Уникальные значения","desc":"Напиши функцию `unique(arr)`, возвращающую массив уникальных элементов.",
   "init":"function unique(arr) {\n  return [];\n}","cases":[{"code":"unique([1,2,2,3,1])","expected":[1,2,3]},{"code":"unique([])","expected":[]}]},
  {"id":"js_v3_c_07","tier":"C","title":"Capitalize слова","desc":"Напиши функцию `capitalize(s)`, делающую первую букву каждого слова заглавной.",
   "init":"function capitalize(s) {\n  return '';\n}","cases":[{"code":"capitalize('hello world')","expected":"Hello World"},{"code":"capitalize('')","expected":""}]},
  {"id":"js_v3_c_08","tier":"C","title":"Диапазон чисел","desc":"Напиши функцию `range(start, end)`, возвращающую массив чисел от start до end (включительно).",
   "init":"function range(start, end) {\n  return [];\n}","cases":[{"code":"range(1,5)","expected":[1,2,3,4,5]},{"code":"range(3,3)","expected":[3]}]},
  {"id":"js_v3_c_09","tier":"C","title":"Степень двойки","desc":"Напиши функцию `isPowerOfTwo(n)`, проверяющую является ли число степенью 2.",
   "init":"function isPowerOfTwo(n) {\n  return false;\n}","cases":[{"code":"isPowerOfTwo(8)","expected":True},{"code":"isPowerOfTwo(6)","expected":False},{"code":"isPowerOfTwo(1)","expected":True}]},
  {"id":"js_v3_c_10","tier":"C","title":"Chunk массива","desc":"Напиши функцию `chunk(arr, size)`, разбивающую массив на подмассивы указанного размера.",
   "init":"function chunk(arr, size) {\n  return [];\n}","cases":[{"code":"chunk([1,2,3,4,5],2)","expected":[[1,2],[3,4],[5]]},{"code":"chunk([1,2,3],1)","expected":[[1],[2],[3]]}]},

  # B: arrays, objects, algorithms
  {"id":"js_v3_b_01","tier":"B","title":"Плоский массив","desc":"Напиши функцию `flatten(arr)`, рекурсивно разворачивающую вложенные массивы.",
   "init":"function flatten(arr) {\n  return [];\n}","cases":[{"code":"flatten([1,[2,[3,4],5],6])","expected":[1,2,3,4,5,6]},{"code":"flatten([[[]]])","expected":[]}]},
  {"id":"js_v3_b_02","tier":"B","title":"Debounce","desc":"Напиши функцию `debounce(fn, ms)`, возвращающую новую функцию, вызывающую fn не чаще чем раз в ms мс.",
   "init":"function debounce(fn, ms) {\n  return function() {};\n}","cases":[{"code":"let c=0;const f=debounce(()=>c++,100);f();f();c","expected":0}]},
  {"id":"js_v3_b_03","tier":"B","title":"Deep clone","desc":"Напиши функцию `deepClone(obj)`, создающую глубокую копию объекта.",
   "init":"function deepClone(obj) {\n  return {};\n}","cases":[{"code":"const o={a:{b:1}};const c=deepClone(o);c.a.b=2;o.a.b","expected":1}]},
  {"id":"js_v3_b_04","tier":"B","title":"Пересечение массивов","desc":"Напиши функцию `intersect(a, b)`, возвращающую общие элементы двух массивов.",
   "init":"function intersect(a, b) {\n  return [];\n}","cases":[{"code":"intersect([1,2,3],[2,3,4]).sort()","expected":[2,3]},{"code":"intersect([1],[2])","expected":[]}]},
  {"id":"js_v3_b_05","tier":"B","title":"Разница массивов","desc":"Напиши функцию `diff(a, b)`, возвращающую элементы a, которых нет в b.",
   "init":"function diff(a, b) {\n  return [];\n}","cases":[{"code":"diff([1,2,3],[2,4])","expected":[1,3]},{"code":"diff([],[1])","expected":[]}]},
  {"id":"js_v3_b_06","tier":"B","title":"Группировка по ключу","desc":"Напиши функцию `groupBy(arr, key)`, группирующую объекты массива по значению ключа.",
   "init":"function groupBy(arr, key) {\n  return {};\n}","cases":[{"code":"groupBy([{a:1,b:'x'},{a:2,b:'x'},{a:3,b:'y'}],'b')","expected":{"x":[{"a":1,"b":"x"},{"a":2,"b":"x"}],"y":[{"a":3,"b":"y"}]}}]},
  {"id":"js_v3_b_07","tier":"B","title":"Каррирование","desc":"Напиши функцию `curry(fn)`, возвращающую каррированную версию fn.",
   "init":"function curry(fn) {\n  return function() {};\n}","cases":[{"code":"const add=curry((a,b,c)=>a+b+c);add(1)(2)(3)","expected":6},{"code":"const add=curry((a,b)=>a+b);add(1,2)","expected":3}]},
  {"id":"js_v3_b_08","tier":"B","title":"Мемоизация","desc":"Напиши функцию `memoize(fn)`, кеширующую результаты вызовов fn.",
   "init":"function memoize(fn) {\n  return function() {};\n}","cases":[{"code":"let calls=0;const f=memoize((x)=>{calls++;return x*2});f(5);f(5);calls","expected":1}]},
  {"id":"js_v3_b_09","tier":"B","title":"Pipe функций","desc":"Напиши функцию `pipe(...fns)`, создающую композицию функций слева направо.",
   "init":"function pipe(...fns) {\n  return function(x) { return x; };\n}","cases":[{"code":"pipe(x=>x+1,x=>x*2)(3)","expected":8},{"code":"pipe(x=>x.toUpperCase())('hi')","expected":"HI"}]},
  {"id":"js_v3_b_10","tier":"B","title":"Парсер шаблонов","desc":"Напиши функцию `template(str, data)`, заменяющую `{{key}}` на значения из data.",
   "init":"function template(str, data) {\n  return '';\n}","cases":[{"code":"template('Hello {{name}}!',{name:'World'})","expected":"Hello World!"},{"code":"template('{{a}}-{{b}}',{a:1,b:2})","expected":"1-2"}]},

  # A: async, DOM, patterns
  {"id":"js_v3_a_01","tier":"A","title":"Promise.all вручную","desc":"Напиши функцию `promiseAll(promises)`, аналог Promise.all без использования Promise.all.",
   "init":"function promiseAll(promises) {\n  return new Promise((resolve) => resolve([]));\n}","cases":[{"code":"await promiseAll([Promise.resolve(1),Promise.resolve(2)])","expected":[1,2]}]},
  {"id":"js_v3_a_02","tier":"A","title":"EventEmitter","desc":"Напиши класс `Emitter` с методами `on(event, fn)`, `emit(event, ...args)`, `off(event, fn)`.",
   "init":"class Emitter {\n  on(e,fn){}\n  emit(e,...args){}\n  off(e,fn){}\n}","cases":[{"code":"const e=new Emitter();let r=0;const f=x=>r+=x;e.on('a',f);e.emit('a',5);r","expected":5}]},
  {"id":"js_v3_a_03","tier":"A","title":"Deep Equal","desc":"Напиши функцию `deepEqual(a, b)`, рекурсивно сравнивающую два значения.",
   "init":"function deepEqual(a, b) {\n  return false;\n}","cases":[{"code":"deepEqual({a:{b:1}},{a:{b:1}})","expected":True},{"code":"deepEqual({a:1},{a:2})","expected":False},{"code":"deepEqual([1,[2]],[1,[2]])","expected":True}]},
  {"id":"js_v3_a_04","tier":"A","title":"Throttle","desc":"Напиши функцию `throttle(fn, delay)`, вызывающую fn не чаще одного раза за delay мс.",
   "init":"function throttle(fn, delay) {\n  return function() {};\n}","cases":[{"code":"let c=0;const f=throttle(()=>c++,1000);f();f();c","expected":1}]},
  {"id":"js_v3_a_05","tier":"A","title":"JSON парсер","desc":"Напиши функцию `parseJSON(s)`, парсящую JSON строку без JSON.parse. Поддержи числа, строки, массивы, объекты, true/false/null.",
   "init":"function parseJSON(s) {\n  return null;\n}","cases":[{"code":"parseJSON('42')","expected":42},{"code":"parseJSON('[1,2]')","expected":[1,2]},{"code":"parseJSON('{\"a\":1}')","expected":{"a":1}}]},
  {"id":"js_v3_a_06","tier":"A","title":"Lazy range","desc":"Напиши генератор `lazyRange(start, end, step)`, лениво возвращающий числа.",
   "init":"function* lazyRange(start, end, step=1) {\n  yield start;\n}","cases":[{"code":"[...lazyRange(0,5,2)]","expected":[0,2,4]},{"code":"[...lazyRange(1,4)]","expected":[1,2,3]}]},
  {"id":"js_v3_a_07","tier":"A","title":"Retry с backoff","desc":"Напиши async функцию `retry(fn, times, delay)`, повторяющую fn до times раз с задержкой delay мс.",
   "init":"async function retry(fn, times, delay) {\n  return await fn();\n}","cases":[{"code":"let c=0;await retry(()=>{c++;if(c<3)throw 'fail';return 'ok'},5,10)","expected":"ok"}]},
  {"id":"js_v3_a_08","tier":"A","title":"Наблюдатель","desc":"Напиши класс `Observable` с методами `subscribe(fn)` (возвращает {unsubscribe}) и `next(val)`.",
   "init":"class Observable {\n  subscribe(fn) { return {unsubscribe(){}}; }\n  next(val) {}\n}","cases":[{"code":"const o=new Observable();let r=0;const s=o.subscribe(v=>r+=v);o.next(5);o.next(3);r","expected":8}]},
  {"id":"js_v3_a_09","tier":"A","title":"Два указателя","desc":"Напиши функцию `twoSum(arr, target)`, находящую индексы двух элементов с суммой target.",
   "init":"function twoSum(arr, target) {\n  return [];\n}","cases":[{"code":"twoSum([2,7,11,15],9)","expected":[0,1]},{"code":"twoSum([3,2,4],6)","expected":[1,2]}]},
  {"id":"js_v3_a_10","tier":"A","title":"Сжатие строки","desc":"Напиши функцию `compress(s)`, сжимающую повторы: 'aaabbc' → 'a3b2c1'.",
   "init":"function compress(s) {\n  return '';\n}","cases":[{"code":"compress('aaabbc')","expected":"a3b2c1"},{"code":"compress('')","expected":""}]},

  # S: system design
  {"id":"js_v3_s_01","tier":"S","title":"Virtual DOM diff","desc":"Напиши функцию `diff(oldTree, newTree)`, возвращающую массив патчей для преобразования old в new. Узлы: {tag, props, children}.",
   "init":"function diff(oldTree, newTree) {\n  return [];\n}","cases":[{"code":"diff({tag:'div',props:{},children:[]},{tag:'span',props:{},children:[]})[0].type","expected":"REPLACE"}]},
  {"id":"js_v3_s_02","tier":"S","title":"Реактивный стейт","desc":"Напиши функцию `reactive(obj)`, возвращающую Proxy, отслеживающий изменения. Метод `subscribe(fn)` для подписки.",
   "init":"function reactive(obj) {\n  return obj;\n}","cases":[{"code":"const s=reactive({a:1});let r=0;s.subscribe(()=>r++);s.a=2;r","expected":1}]},
  {"id":"js_v3_s_03","tier":"S","title":"Promise scheduler","desc":"Напиши класс `Scheduler(limit)` с методом `add(promiseFn)`, выполняющий не более limit промисов одновременно.",
   "init":"class Scheduler {\n  constructor(limit) { this.limit = limit; }\n  add(fn) { return fn(); }\n}","cases":[{"code":"const s=new Scheduler(2);let r=[];await Promise.all([s.add(()=>new Promise(ok=>setTimeout(()=>{r.push(1);ok()},50))),s.add(()=>new Promise(ok=>setTimeout(()=>{r.push(2);ok()},30))),s.add(()=>new Promise(ok=>setTimeout(()=>{r.push(3);ok()},10)))]);r.length","expected":3}]},
  {"id":"js_v3_s_04","tier":"S","title":"Middleware chain","desc":"Напиши функцию `createApp()`, возвращающую объект с `use(middleware)` и `handle(ctx)`. Middleware: (ctx, next) => {}.",
   "init":"function createApp() {\n  return { use(fn){}, handle(ctx){ return ctx; } };\n}","cases":[{"code":"const app=createApp();app.use((ctx,next)=>{ctx.a=1;next()});app.use((ctx,next)=>{ctx.b=2;next()});const c={};app.handle(c);c.a+c.b","expected":3}]},
  {"id":"js_v3_s_05","tier":"S","title":"Трай-дерево","desc":"Напиши класс `Trie` с методами `insert(word)`, `search(word)`, `startsWith(prefix)`.",
   "init":"class Trie {\n  insert(word) {}\n  search(word) { return false; }\n  startsWith(prefix) { return false; }\n}","cases":[{"code":"const t=new Trie();t.insert('apple');t.search('apple')","expected":True},{"code":"const t=new Trie();t.insert('apple');t.startsWith('app')","expected":True},{"code":"const t=new Trie();t.insert('apple');t.search('app')","expected":False}]},
  {"id":"js_v3_s_06","tier":"S","title":"JSON Schema валидатор","desc":"Напиши функцию `validate(data, schema)`, валидирующую данные по JSON Schema (type, required, properties, items).",
   "init":"function validate(data, schema) {\n  return true;\n}","cases":[{"code":"validate(42,{type:'number'})","expected":True},{"code":"validate('hi',{type:'number'})","expected":False}]},
  {"id":"js_v3_s_07","tier":"S","title":"Undo/Redo стек","desc":"Напиши класс `History` с `push(state)`, `undo()`, `redo()`, `current()`.",
   "init":"class History {\n  push(s){}\n  undo(){}\n  redo(){}\n  current(){ return null; }\n}","cases":[{"code":"const h=new History();h.push(1);h.push(2);h.undo();h.current()","expected":1},{"code":"const h=new History();h.push(1);h.push(2);h.undo();h.redo();h.current()","expected":2}]},
  {"id":"js_v3_s_08","tier":"S","title":"Цепочка промисов","desc":"Напиши функцию `chainPromises(fns)`, последовательно выполняющую массив async функций, передавая результат предыдущей в следующую.",
   "init":"async function chainPromises(fns) {\n  return null;\n}","cases":[{"code":"await chainPromises([()=>Promise.resolve(1),x=>Promise.resolve(x+1),x=>Promise.resolve(x*2)])","expected":4}]},
  {"id":"js_v3_s_09","tier":"S","title":"Маршрутизатор","desc":"Напиши класс `Router` с `add(path, handler)` и `match(url)`. Поддержи параметры `:param`.",
   "init":"class Router {\n  add(path, handler) {}\n  match(url) { return null; }\n}","cases":[{"code":"const r=new Router();r.add('/user/:id',p=>p);const m=r.match('/user/42');m.params.id","expected":"42"}]},
  {"id":"js_v3_s_10","tier":"S","title":"Pub/Sub система","desc":"Напиши класс `PubSub` с `publish(topic, data)`, `subscribe(topic, fn)` возвращающим unsubscribe, и поддержкой wildcards `*`.",
   "init":"class PubSub {\n  publish(topic, data) {}\n  subscribe(topic, fn) { return ()=>{}; }\n}","cases":[{"code":"const ps=new PubSub();let r=0;ps.subscribe('a',v=>r+=v);ps.publish('a',5);r","expected":5}]},
]

def build_task(t, category, engine):
    xp_lo, xp_hi = XP[t["tier"]]
    return {"id":t["id"],"category":category,"tier":t["tier"],"title":t["title"],
            "xp":random.randint(xp_lo,xp_hi),"story":random.choice(STORIES[t["tier"]]),
            "description":t["desc"],"initial_code":t["init"],
            "check_logic":{"engine":engine,"cases":t["cases"]}}

with open("tasks.json") as f: data = json.load(f)
new = [build_task(t,"javascript","js-eval") for t in JS]
data["tasks"].extend(new)
with open("tasks.json","w") as f: json.dump(data, f, ensure_ascii=False, indent=2)
print(f"Added {len(new)} JS tasks. Total: {len(data['tasks'])}")
