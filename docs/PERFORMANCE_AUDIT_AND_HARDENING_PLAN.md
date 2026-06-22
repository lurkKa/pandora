# 🔴 PANDORA — Аудит производительности и план харднинга (валидированный)

> **Назначение документа.** Это итоговый аудит, проверенный построчно против *текущего*
> состояния кода (`main.py` 12 972 строк, ревизия от 22 Iyn). Он валидирует исходный
> аудит Opus 4.6, отмечает что **уже исправлено / устарело / неверно**, добавляет новые
> находки и даёт приоритизированный план имплементации.
>
> **Имплементировать будет другой ИИ (Opus 4.6).** Здесь — только анализ и план, без правок кода.

---

## 0. Симптом и реальная цепочка причин

**Симптом.** При 7+ одновременных пользователях (открытие заданий, квиз, песочница) в логах:
```
WARNING: Exceeded concurrency limit.        ← uvicorn: >100 одновременных запросов в полёте
INFO: Maximum request limit of 10000 exceeded. Terminating process.   ← uvicorn --limit-max-requests
```

**Это два РАЗНЫХ события, и второе — самоинфликт.**

1. `Maximum request limit of 10000 exceeded` — это **намеренное** поведение флага
   `--limit-max-requests 10000` в `render.yaml`. Воркер сам себя перезапускает каждые 10 000
   запросов. Под нагрузкой квиза/песочницы (polling 1.5–2 с × 7 юзеров ≈ 5–8 req/s) это
   ~20–30 минут до рестарта. Каждый рестарт: роняет запросы в полёте, **сбрасывает все
   in-memory кэши** (их дорого пересобирать → всплеск CPU/RAM), и **ломает sandbox-presence**
   (см. находку #9 — `time.monotonic()` сбрасывается).
2. `Exceeded concurrency limit` — uvicorn `--limit-concurrency 100`: запросы накапливаются
   быстрее, чем обрабатываются. Накопление происходит, когда хендлеры медленные (контеншн
   по SQLite + лишний `SELECT users` в `verify_token` на каждом запросе) и поверх летит
   poll-шторм.

**Вывод о приоритетах:** самые дешёвые и крупные победы — **снять/поднять `--limit-max-requests`**,
**убрать DB-запрос из `verify_token` при `STATELESS_AUTH`** и **сбить частоту polling**. Это
конфиг + точечные правки, не переписывание. Memory-оптимизации (`tasks.json`) — следующий слой.

---

## 1. Что уже сделано (исходный аудит 4.6 этого не учитывал)

Код заметно более защищён, чем предполагает аудит 4.6. Перед имплементацией важно это знать,
чтобы **не дублировать** уже существующее:

| Механизм | Где | Статус |
|---|---|---|
| **MemoryShieldMiddleware** — лимит одновременных запросов (`_MAX_CONCURRENT_REQUESTS=20`) + shed-mode 503 + обработка `MemoryError` с эвикцией кэшей | `main.py:253`, `main.py:86` | ✅ есть |
| **Memory Sentinel** — фоновый демон: RSS из `/proc/self/status`, пороги WARN/HIGH/CRIT, GC и эвикция кэшей | `main.py:158`, `_get_rss_mb` `main.py:98` | ✅ есть (это и есть `🟡 MEMORY WARN…` в логах) |
| **FloodShieldMiddleware** — per-IP + глобальный rate-limit, bounded dict (2048 IP), exempt для `/ping` `/health` `/api/status` | `main.py:329` | ✅ есть (закрывает Open Question #4 про hey.exe на уровне приложения) |
| **WAL + busy_timeout** на SQLite | `main.py:751`, `main.py:820` | ✅ есть |
| **RUNNER_SEMAPHORE** (concurrency=1, `acquire(blocking=False)`) — verify сериализован, лишние попытки → 429 RunnerBusy, а не наваливаются | `main.py:6391`, `main.py:6963` | ✅ есть |
| **Quiz bank** уже `kahoot_1_2.json` (**9 MB**, не 18), lazy-load + cap `QUIZ_BANK_MAX_ITEMS` + per-session эвикция распарсенных вопросов | `main.py:11837`, `main.py:11886`, `main.py:12425` | ✅ есть (закрывает Open Question #2) |
| **ETag / 304** на `/api/tasks` (fast-path: предсериализованные байты + gzip + ETag) | `main.py:7049-7068`, `_get_preserialized_tasks_response` `main.py:4887` | ✅ есть — **готовый паттерн для переноса на roadmap** |
| **Roadmap base-cache** уже хранит только lite-поля + узкий `_raw`, **без** `check_logic.cases` | `main.py:5904-5953` (см. коммент `main.py:5928`) | ✅ частично (но `_TASKS_CACHE` всё ещё держит полный объём — см. #2) |
| **Dashboard sync** уже пропускает polling при скрытой вкладке и грузит roadmap **не каждый тик**, а лёгкий `loadTaskStatus()` | `index.html:5327`, `DASHBOARD_SYNC_MS=45000` `index.html:5090` | ✅ частично |
| **bcrypt** офлоадится в отдельный `_cpu_executor` (ThreadPoolExecutor=2) | `main.py:1796-1801` | ✅ есть |

---

## 2. Валидация 14 находок Opus 4.6

Легенда: ✅ ВАЛИДНО · 🟡 ЧАСТИЧНО · ❌ НЕВЕРНО/УСТАРЕЛО · 🔁 уже сделано.

| # | Находка 4.6 | Вердикт | Комментарий (по текущему коду) |
|---|---|---|---|
| 1 | `verify_task` блокирует **event loop** через `subprocess.run` | 🟡 **механизм неверен, проблема реальна частично** | `attempt_task` — это **sync `def`** (`main.py:7187`), FastAPI исполняет его в **threadpool** (anyio, дефолт 40 потоков), а не в event loop. Event loop НЕ блокируется. Плюс `RUNNER_SEMAPHORE`=1 сериализует verify. Реальный риск — насыщение threadpool при множестве медленных sync-хендлеров (verify до 5с + блокирующий SQLite). Лечится async-конвертацией горячих эндпоинтов, но это **не главная причина** падений. |
| 2 | `tasks.json` 40 MB → ~120–160 MB в RAM, 3 копии | ✅ **ВАЛИДНО (главная memory-проблема)** | `_TASKS_CACHE["data"]` (`main.py:4873`, заполняется в `load_tasks` `main.py:5129`) держит **полный** распарсенный объём, включая `check_logic.cases`/`hidden_cases`. `_TASKS_BY_ID_CACHE` — это **ссылки**, не копии (`main.py:5150`), так что «3-я копия» преувеличена. Но базовый расход на `_TASKS_CACHE` подтверждён и доминирует в RAM-бюджете. |
| 3 | `verify_token` делает DB-запрос на **каждом** запросе даже при STATELESS_AUTH | ✅ **ВАЛИДНО (вторая по важности)** | `main.py:2675`: `SELECT * FROM users WHERE id = ?` выполняется всегда; `if not STATELESS_AUTH` (`main.py:2652`) пропускает только проверку *сессии*, не загрузку юзера. JWT-fallback (`main.py:2681`) срабатывает лишь при ошибке SQLite. Итог: каждый аутентифицированный запрос = открытие отдельного DB-соединения (`get_db` `main.py:737`) + запрос. На poll-шторме это основной DB-оверхед. |
| 4 | Poll-шторм: «8 таймеров на юзера», в т.ч. online-counter 1 с → `/api/status` | 🟡 **частично; таблица интервалов неточна** | Факт: тяжёлый polling — это **quiz `pollSession` 2 с** (`kahoot.html:267`) и **sandbox `pollRoom` 1.5 с** (`sandbox.html:257`), и только на активных страницах. «Online counter 1 с» — **неверно**: `setInterval(update,1000)` (`index.html:9408`) это локальный countdown бонус-попапа, **сетевых запросов нет**. Dashboard sync уже 45 с и уже паузится при hidden. Chat 30/15 с, guild-chat 15 с, heartbeat 30 с. Снижать частоту/добавить backoff — валидно, но цель — quiz/sandbox. |
| 5 | `/api/roadmap` отдаёт ~38 MB на каждый запрос, нет ETag/304 | ✅ **ВАЛИДНО, но severity ниже заявленной** | Нет ETag/304 на `/api/roadmap` (`main.py:5956-6045`) — подтверждено. НО roadmap **не поллится** регулярно: `syncDashboardData` грузит его лишь при первой загрузке/`forceRoadmap`, обычно зовёт лёгкий `loadTaskStatus()` (`index.html:5327`). Значит 38 MB — это всплеск на старте сессии (7 юзеров одновременно), а не на каждый poll. ETag/304 даёт выигрыш на reconnect/refresh. |
| 6 | GZipMiddleware двойное сжатие roadmap | ❌ **УСТАРЕЛО** | Roadmap уже отдаёт готовый gzip с заголовком `Content-Encoding: gzip` (`main.py:6041-6044`); Starlette `GZipMiddleware` пропускает ответы, у которых этот заголовок уже выставлен. Двойного сжатия нет. |
| 7 | `apply_xp_change` — N+1 + рекурсия | ✅ **ВАЛИДНО (и хуже)** | `main.py:1860`: на каждом положительном XP — запросы по гильдии/титулам, **`_get_most_active_student_id` (7-дневный агрегат)** на каждый вызов (`main.py:1929`), а ветка `category_block` зовёт `load_tasks()` и **полностью сканирует ~11 733 задач** (`main.py:1920-1924`). XP начисляется в т.ч. на каждом sandbox-тике (`main.py:12726`) и при награждении квиза — горячий путь. |
| 8 | Quiz bank 18 MB в памяти, cap 2500 | 🔁 **уже сделано / посылка неверна** | Активный банк — `kahoot_1_2.json` **9 MB** (`main.py:11837`), не 18. Lazy-load (`main.py:11886`), cap (render.yaml=2500, дефолт low-res=1500), per-session эвикция. Можно лишь чуть дотюнить cap (см. P2). |
| 9 | Sandbox presence на `time.monotonic()` ломается при рестарте | ✅ **ВАЛИДНО (корректность)** | `sandbox_poll` пишет `last_heartbeat = time.monotonic()` (`main.py:12692,12704`), а `_sandbox_online_users` сравнивает с `time.monotonic()-timeout` (`main.py:12570`). После рестарта (а он раз в ~20–30 мин из-за #0) монотоника из старого процесса бессмысленна → «призраки»/пустые комнаты. Чинить на `time.time()` (epoch). |
| 10 | Неограниченные in-memory dict'ы (утечки) | 🟡 **частично** | `_ACTIVE_TASK_ATTEMPTS` — есть чистка stale (`main.py:6420`); `_ip_windows` — bounded 2048; quiz-сессии — bounded 20 с эвикцией. Реально без чистки: `_sandbox_sync_timestamps` (`main.py:12545`) и `_featured_tasks` (`main.py:4257`, чистится только при доступе). При <50 юзерах это байты — **низкий приоритет**. |
| 11 | Sync `def` хендлеры → нагрузка на threadpool, GIL на SQLite | 🟡 **валидно как класс, не «главная» причина** | Почти все хендлеры — sync `def` → дефолтный anyio threadpool (40). При множестве блокирующих SQLite-операций потоки могут копиться. Дешёвая полумера — поднять размер threadpool; точечно — async + `asyncio.to_thread` для самых горячих (`get_roadmap`, `sandbox_poll`, `attempt_task`). |
| 12 | `load_tasks` re-stat + ре-парс 40 MB блокирует loop | 🟡 **частично** | `stat().st_mtime` на каждый вызов (`main.py:5101`) — дёшево; ре-парс случается только при смене mtime (редко). Так как вызовы идут из sync-хендлеров (threadpool), event loop не блокируется. Низкий приоритет; throttle mtime — опционально. |
| 13 | `index.html` 496 KB на каждую загрузку | 🟢 **валидно, мелочь** | 485 KB. GZipMiddleware его и так жмёт. Польза: `Cache-Control` + предсжатый `.gz`. Низкий приоритет. |
| 14 | `_get_most_active_student_id` без кэша | ✅ **ВАЛИДНО** | Дубликат сути #7. Кэшировать на 5–10 мин. |

---

## 3. Дополнительные находки (не в аудите 4.6)

- **F-A. `--limit-max-requests 10000` — корень рестарт-цикла.** (`render.yaml` startCommand.)
  Самая дешёвая крупная победа. Поднять до 100 000 или убрать; смысл флага (борьба с утечками)
  уже закрыт Memory Sentinel'ом + эвикцией. Перед этим стоит ограничить `_sandbox_sync_timestamps`
  и `_featured_tasks` (#10), чтобы за долгий аптайм ничего не текло.
- **F-B. Два DB-соединения на запрос.** `verify_token` открывает своё соединение (`get_db`),
  затем эндпоинт — ещё одно. Каждое — с `PRAGMA foreign_keys`/`busy_timeout` (`main.py:742-743`).
  Устранение DB-запроса в `verify_token` (#3) убирает одно соединение на каждый запрос.
- **F-C. anyio threadpool не настроен** (нет `setup_threadpool`/`RunVar`) → дефолт 40. Под poll-штормом
  из sync-хендлеров с блокирующим SQLite это потолок параллелизма. Дешёвая правка (P1).
- **F-D. `apply_xp_change` загружает весь `tasks.json` в ветке `category_block`** даже когда задача
  заведомо не в заблокированной категории — линейный скан на каждый XP. Заменить на
  `get_task(task_id)` (O(1) по `_tasks_by_id`, `main.py:5142`).
- **F-E. `get_leaderboard` зовётся каждые 45 с** из `syncDashboardData` для всех (`main.py:3660`).
  Проверить стоимость JOIN'ов; кандидат на короткий (10–15 с) кэш топ-20.

---

## 4. План имплементации (по приоритетам)

> Принцип: сначала **конфиг и точечные правки** с максимальным эффектом и минимальным риском;
> потом — память; структурное (SSE, lazy-парс) — в самом конце и только при необходимости.
> Переиспользовать существующие паттерны: ETag из `/api/tasks`, Memory Sentinel, RUNNER_SEMAPHORE.

### P0 — Остановить рестарт-цикл (конфиг, минуты, риск минимальный)

1. **`render.yaml`: `--limit-max-requests 10000` → `100000`** (или убрать флаг).
   Останавливает перезапуски каждые ~20–30 мин, сохраняет прогретые кэши, чинит первопричину
   sandbox-presence-багов между рестартами. *(Сначала выполнить P2-шаг про bounded dict'ы.)*
2. **`render.yaml`: поднять `--limit-concurrency 100` оставить, но снизить реальный backlog** —
   эффект даст не сам флаг, а P1 (быстрее хендлеры + меньше polling). Менять не обязательно.

### P1 — Сбить нагрузку на запрос (точечный код + фронт, высокий эффект)

3. **`verify_token`: при `STATELESS_AUTH` доверять JWT-claims, без `SELECT users`.**
   Файл: `main.py:2630-2695`. Когда `STATELESS_AUTH=1` и сессии не нужны — возвращать dict из
   payload (`id`, `username`, `role`, и т.д.), **не открывая `get_db`**. Так как многим эндпоинтам
   нужны свежие `xp/level`, они и так читают `users` сами (напр. `apply_xp_change` `main.py:1935`,
   `get_roadmap` через свои запросы) — там свежесть сохраняется. Где админ-проверка по роли —
   роль уже в JWT (`require_admin` `main.py:2704`). **Риск:** ревокация/смена роли «на лету»
   перестанут мгновенно действовать (это и есть смысл stateless). Убедиться, что JWT кладёт
   `username/role` (проверить `create_*token`).
   *Эффект: −1 DB-соединение и −1 запрос на КАЖДЫЙ аутентифицированный вызов (в т.ч. весь polling).*

4. **ETag/304 на `/api/roadmap`.** Файл: `main.py:5956-6045`. Перенести готовый паттерн из
   `/api/tasks` (`main.py:7049-7068`). ETag считать из дешёвой подписи пользовательского состояния:
   `(user_id, completed_count, max(completed_at), pending_count, homework_count, data_id)` — без
   построения полного ответа. Если `If-None-Match` совпал → `304` до тяжёлой сериализации.
   Клиент (`loadRoadmap` в `index.html`) — слать `If-None-Match` и хранить ETag.
   *Эффект: убирает 38 MB-сборку на reconnect/refresh/повторных заходах.*

5. **Снизить частоту тяжёлого polling + backoff на активных страницах.**
   - `kahoot.html:267` `pollSession` 2 с → 3 с; пауза при `document.hidden`; экспон. backoff на
     ошибках/неактивной сессии (lobby/finished — реже).
   - `sandbox.html:257` `pollRoom` 1.5 с → 3 с; пауза при `document.hidden`.
   - `index.html`: чат-поллеры (30/15 с) и guild-chat (15 с) — поднять до 45–60 с и/или паузить
     при hidden (как уже сделано для dashboard sync).
   *Эффект: −40–60 % устойчивого req/s во время квиза/песочницы — прямой удар по обоим симптомам.*

6. **Кэшировать `_get_most_active_student_id` на 5 мин** + **F-D: заменить полный скан в
   `category_block` на `get_task`.** Файл: `main.py:1830`, `main.py:1920-1929`. Простой
   `(value, expires_at)` кэш в module-scope (как `_cleanup_stale_quiz_sessions._last_run`).
   *Эффект: убирает 7-дневный агрегат и линейный скан 11 733 задач с горячего XP-пути
   (sandbox-тики, награды квиза).*

7. **F-C: поднять anyio threadpool** (напр. до 64–80). Через `anyio.to_thread.current_default_thread_limiter().total_tokens = N`
   в startup-хуке, либо `--workers 1` оставить и тюнить лимитер. Дешёвая страховка от насыщения
   потоков sync-хендлерами с блокирующим SQLite. *Эффект: меньше «Exceeded concurrency limit».*

### P2 — Память (снизить базовый RSS, меньше WARN/HIGH/эвикций)

8. **Снять `check_logic.cases`/`hidden_cases` из `_TASKS_CACHE`, грузить кейсы лениво для verify.**
   Файлы: `load_tasks` `main.py:5086`, `get_task` `main.py:5142`, `verify_task` `main.py:6946`.
   Идея: основной кэш держит задачи **без** тяжёлых `cases` (метаданные + текст). Для верификации
   `verify_task` берёт кейсы отдельно: либо отдельный lazy-кэш `{task_id: cases}` (заполняется по
   требованию из исходного файла), либо отдельный «cases-индекс». Это самая крупная RAM-экономия,
   но и самая аккуратная правка — **обязательно** прогнать верификацию всех движков (python/js/
   frontend/manual) до/после. *Эффект: десятки MB RSS.*
9. **Bounded dict'ы (F-A предусловие):** добавить TTL-чистку `_sandbox_sync_timestamps`
   (`main.py:12545`) и `_featured_tasks` (`main.py:4257`) — периодически или по размеру. Нужно
   именно потому, что P0 убирает регулярный рестарт (который раньше «чистил» их сбросом процесса).
10. **Quiz cap (опц.):** `PANDORA_QUIZ_BANK_MAX_ITEMS` в `render.yaml` 2500 → 1200–1500 (для <10
    юзеров с запасом). Низкий риск, небольшая экономия.

### P3 — Структурное (делать только если P0–P2 не хватило)

11. **Sandbox presence на `time.time()` (epoch) вместо monotonic** (#9): `main.py:12570,12692,12704`
    и схема `sandbox_presence` (`main.py:1693`). После P0 (нет частых рестартов) острота падает,
    но фикс корректный и дешёвый.
12. **Async-конвертация горячих эндпоинтов** (`get_roadmap`, `sandbox_poll`, `attempt_task`) с
    `await asyncio.to_thread(...)` для блокирующих частей (#1, #11). Делать **точечно** и измеримо.
13. **SSE вместо polling** для quiz/sandbox (#4 из 4.6). Большой ROI по нагрузке, но и большой
    объём работы + риск по лимиту соединений на free-tier. **Только** если polling-тюнинг (шаг 5)
    окажется недостаточным. Держать fallback на polling.
14. **`index.html`/статика:** `Cache-Control: max-age` + предсжатый `.gz` (#13). Косметика.

---

## 5. План верификации

**Локально (до деплоя):**
```bash
# Базовый RSS и состояние shield
curl -s localhost:8000/api/status | python -m json.tool   # memory.pct, shed_active

# Нагрузка ~10 параллельных на горячих эндпоинтах
hey -n 400 -c 10 -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/roadmap
hey -n 800 -c 10 -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/quiz/session/$CODE"

# 304 работает (после P1-4): второй запрос с ETag должен вернуть 304
curl -si -H "Authorization: Bearer $TOKEN" localhost:8000/api/roadmap | grep -i etag
curl -si -H "Authorization: Bearer $TOKEN" -H 'If-None-Match: "<etag>"' localhost:8000/api/roadmap | head -1  # 304

# verify_token не ходит в БД (после P1-3): /ping остаётся <50ms, эндпоинты не открывают лишних conn
time curl -s -H "Authorization: Bearer $TOKEN" localhost:8000/api/status

# Регрессия верификации задач (КРИТично для P2-8): прогнать attempt по python/js/frontend/manual
```

**Перед/после P2-8 (память):** зафиксировать `RSS` из `/api/status` на холодном старте и под
нагрузкой; цель — стабильно <70 % (≈360 MB), без срабатываний `🟠 MEMORY HIGH`.

**Ручная проверка под реальную нагрузку:**
- 7+ юзеров одновременно в квизе и в песочнице.
- В логах Render: отсутствие `Maximum request limit … Terminating` (после P0) и резкое снижение
  `Exceeded concurrency limit` (после P1).
- Sandbox-presence: список «онлайн» корректен и не «залипает».

---

## 6. Открытые вопросы (часть уже закрыта)

- **Q1. Разбить `tasks.json` по категориям?** Опционально как развитие P2-8; lazy-cases уже даёт
  большую часть экономии без рефакторинга формата.
- **Q2. Какой quiz-банк активен?** ✅ Закрыт: используется `kahoot_1_2.json` (9 MB), не 18 MB.
- **Q3. Бюджет SSE на free-tier.** Открыт; решать только при переходе к P3-13.
- **Q4. Защита от hey.exe/DDoS.** Частично закрыта `FloodShieldMiddleware` (per-IP + глобальный
  лимит). Для серьёзного L7-флуда — Cloudflare-прокси перед Render (внешняя мера).

---

## 7. Краткая шпаргалка приоритетов для имплементатора

| Шаг | Файл(ы) | Эффект | Риск |
|---|---|---|---|
| P0-1 `--limit-max-requests`→100000 | `render.yaml` | убирает рестарт-цикл | низ. (после P2-9) |
| P1-3 verify_token без `SELECT users` | `main.py:2630` | −1 conn/−1 query на КАЖДЫЙ запрос | сред. (ревокация) |
| P1-5 polling 2→3с/1.5→3с + pause hidden | `kahoot.html:267`, `sandbox.html:257`, `index.html` | −40–60 % req/s | низ. |
| P1-4 ETag/304 на roadmap | `main.py:5956` | нет 38 MB на refresh | низ. |
| P1-6 кэш most_active + get_task в xp | `main.py:1830,1920` | дешевле горячий XP-путь | низ. |
| P1-7 threadpool ↑ | startup hook | меньше concurrency-503 | низ. |
| P2-8 strip check_logic из кэша | `main.py:5086,6946` | −десятки MB RSS | **сред.-выс.** (регрессия verify) |
| P2-9 bounded dicts | `main.py:12545,4257` | предусловие P0 | низ. |
| P3-11 epoch heartbeat | `main.py:12570…` | корректность presence | низ. |
