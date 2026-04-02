# Task Grouping Specification

**Purpose:** This document tells an AI assistant how to classify every task in `tasks.json` into a topic group. After classification, the PANDORA frontend will display tasks grouped by topic with collapsible sections and completion tracking.

---

## 1. What You Need to Do

1. Read `tasks.json` from the project root
2. For each task in the `tasks` array, analyze its `description`, `initial_code`, `check_logic`, and `title`
3. Assign a `topic` string field to each task (from the canonical lists below)
4. Write the updated `tasks.json` back (preserving ALL existing fields untouched)

### Input Format

```json
{
  "meta": { ... },
  "categories": ["python", "javascript", "frontend", "scratch", "alextype"],
  "tasks": [
    {
      "id": "py_01_var",
      "category": "python",
      "tier": "D",
      "title": "...",
      "description": "Создай переменную `sword_damage` и установи ей значение `15`.",
      "initial_code": "# ...",
      "check_logic": { "engine": "pyodide", "cases": [...] },
      ...
    }
  ]
}
```

### Output Format

Same JSON, but every task object now has a `"topic"` field:

```json
{
  "id": "py_01_var",
  "category": "python",
  "topic": "variables",
  ...
}
```

**CRITICAL RULES:**
- Do NOT remove, rename, or modify ANY existing fields
- Do NOT reorder tasks
- Only ADD the `"topic"` field to each task object
- Every task MUST have a `topic` assigned (no empty strings)
- Use ONLY values from the canonical topic lists below

---

## 2. Canonical Topic Lists

### Python (`category: "python"`)

| Topic Key | When to assign |
|-----------|----------------|
| `variables` | Task involves creating, assigning, or reading variables. Keywords: "переменную", "variable", `variable_value` check type |
| `math_ops` | Pure arithmetic: `+`, `-`, `*`, `/`, `%`, `**`, `//`. Function does basic math on args |
| `functions` | Generic function definition/calls that don't fit a specialized topic. "Напиши/реализуй функцию" doing simple transformations |
| `if_else` | Conditional logic: `if`, `elif`, `else`, ternary. Keywords: "если", "условие", "проверь", returning different values based on conditions |
| `loops` | `for`, `while`, iteration. Keywords: "цикл", "повтори", "перебери", iterating over ranges or collections |
| `strings` | String manipulation: `.upper()`, `.lower()`, `.replace()`, `.split()`, `.join()`, slicing, formatting. Keywords: "строк", "символ" |
| `lists` | List operations: `.append()`, `.sort()`, `.filter()`, comprehensions, slicing, `sum()`, `len()` on lists. Keywords: "список", "массив", "элемент" |
| `dicts` | Dictionary operations: `.keys()`, `.values()`, `.items()`, `dict[key]`. Keywords: "словарь", "ключ" |
| `classes` | OOP: `class`, `__init__`, `self`, inheritance, methods. Keywords: "класс", "объект", "метод" |
| `regex` | Regular expressions: `re.search()`, `re.match()`, `re.findall()`, pattern matching. Keywords: "regex", "выражени", "паттерн", `\w`, `\d` |
| `algorithms` | Sorting algorithms, searching, recursion, dynamic programming, complex data structure manipulation. Tier A/S tasks involving algorithmic thinking |
| `file_io` | File reading/writing, stdin/stdout, `open()`, `print()` for output formatting |

### JavaScript (`category: "javascript"`)

| Topic Key | When to assign |
|-----------|----------------|
| `variables` | Variable declaration: `let`, `const`, `var`. Assigning values, type checking |
| `math_ops` | Arithmetic operations, `Math.*` functions |
| `functions` | Generic function definition. Arrow functions, callbacks, closures (simple cases) |
| `if_else` | `if/else`, ternary `? :`, `switch`. Conditional returns based on input |
| `loops` | `for`, `while`, `for...of`, `for...in`, `.forEach()` |
| `strings` | `.toUpperCase()`, `.toLowerCase()`, `.split()`, `.replace()`, `.includes()`, template literals, `.trim()` |
| `arrays` | `.map()`, `.filter()`, `.reduce()`, `.sort()`, `.slice()`, `.push()`, `.pop()`, `.find()`, `.every()`, `.some()`, spread operator on arrays |
| `objects` | `Object.keys()`, `Object.values()`, `Object.entries()`, destructuring, spread on objects |
| `classes` | `class`, `constructor`, `extends`, `super`, `this`, `static` |
| `regex` | `/pattern/flags`, `.test()`, `.match()`, `.replace()` with regex |
| `algorithms` | Complex logic: sorting, searching, recursion, DP, graph traversal |
| `file_io` | Node.js file operations (rare in this project) |

### Frontend (`category: "frontend"`)

| Topic Key | When to assign |
|-----------|----------------|
| `html_elements` | Adding HTML tags: `h1`, `div`, `span`, `section`, `article`, `nav`, `footer`, `header`, `table`, `img`, `a`, `ul/li`, `button`, `form`, `input`. Engine: `iframe`. Check type: `selector_exists`, `content_contain` for HTML tags |
| `text_styling` | CSS text properties: `font-size`, `font-weight`, `font-family`, `text-align`, `text-decoration`, `text-transform`, `line-height`, `letter-spacing`, `color` (for text) |
| `colors_bg` | `background`, `background-color`, `background-image`, `gradient`, `opacity`, `box-shadow`, `border-color` |
| `layout` | `display: flex/grid`, `justify-content`, `align-items`, `gap`, `margin`, `padding`, `width`, `height`, `position`, `float`, `overflow` |
| `selectors` | CSS selectors: `:hover`, `:focus`, `:nth-child`, `::before`, `::after`, pseudo-classes, combinators |
| `animations` | `transition`, `animation`, `@keyframes`, `transform`, `rotate`, `scale`, `translate` |
| `responsive` | `@media`, `min-width`, `max-width`, viewport units, `%` sizing for responsiveness |
| `forms` | Form-related: `input`, `textarea`, `select`, `label`, `placeholder`, form validation, `required` |

### Scratch (`category: "scratch"`)

| Topic Key | When to assign |
|-----------|----------------|
| `motion` | Movement blocks: "шаг", "повернись", "перейди в x/y", "скользи", "сдвиг", "направлени" |
| `looks` | Appearance: "костюм", "размер", "скажи", "подумай", "покажись", "спрячься", "эффект", "фон" |
| `sound` | Audio: "звук", "громкость", "проиграй", "Meow" |
| `events` | Event handlers: "флаг", "клавиш", "клик", "сообщен", "получит" |
| `control` | Control flow: "повтори", "если", "ждать", "стоп", "цикл", "клон" |
| `sensing` | Sensing blocks: "касается", "мыши", "расстояние", "спросить", "ответ", "таймер" |
| `operators` | Math/logic operators in Scratch: "сложи", "случайн", "больше", "меньше", "и/или/не" |
| `variables` | Scratch variables and lists: "переменн", "список", "добавь в", "удали из" |
| `my_blocks` | Custom blocks: "мой блок", "процедур", "определит" |

---

## 3. Classification Priority Rules

When a task could belong to multiple topics, use these priority rules:

1. **Most specific wins.** If a task uses `if/else` to process a list → `if_else` (the core skill being tested is conditions, not list manipulation)
2. **Check the `check_logic.cases`:** What does the test verify?
   - `variable_value` check → likely `variables`
   - Function call with conditional returns → `if_else`
   - Function call with loop-dependent logic → `loops`
3. **For Tier D tasks:** bias toward the simplest topic (usually `variables`, `math_ops`, or `functions`)
4. **For Tier S/A tasks:** bias toward `algorithms` unless clearly specialized (e.g., regex)
5. **Look at `initial_code`:** What boilerplate is provided?
   - `class` keyword → `classes`
   - `import re` → `regex`
   - `for` or `while` in template → `loops`
6. **Description keywords** are the strongest signal. Use the keyword lists in the tables above.

---

## 4. Special Cases

### `alextype` category
Tasks with `category: "alextype"` should be assigned `topic: "typing"`. There are very few of these.

### Legacy/archived tasks
Tasks with IDs starting with `leg_` are legacy/archived. Still assign them a topic using the same rules.

### Exam tasks
Tasks in the `exam_tasks` array (if present) follow the same rules as regular tasks.

---

## 5. Validation

After classification, verify:

```python
import json

with open("tasks.json") as f:
    data = json.load(f)

VALID_TOPICS = {
    "python": {"variables", "math_ops", "functions", "if_else", "loops", "strings", "lists", "dicts", "classes", "regex", "algorithms", "file_io"},
    "javascript": {"variables", "math_ops", "functions", "if_else", "loops", "strings", "arrays", "objects", "classes", "regex", "algorithms", "file_io"},
    "frontend": {"html_elements", "text_styling", "colors_bg", "layout", "selectors", "animations", "responsive", "forms"},
    "scratch": {"motion", "looks", "sound", "events", "control", "sensing", "operators", "variables", "my_blocks"},
    "alextype": {"typing"},
}

errors = []
for i, task in enumerate(data["tasks"]):
    tid = task.get("id", f"index_{i}")
    cat = task.get("category", "")
    topic = task.get("topic", "")
    
    if not topic:
        errors.append(f"{tid}: missing topic")
        continue
    
    valid = VALID_TOPICS.get(cat, set())
    if topic not in valid:
        errors.append(f"{tid}: topic '{topic}' not valid for category '{cat}'")

if errors:
    print(f"ERRORS ({len(errors)}):")
    for e in errors[:20]:
        print(f"  {e}")
else:
    print(f"OK: all {len(data['tasks'])} tasks have valid topics")

# Distribution check
from collections import Counter
for cat in VALID_TOPICS:
    cat_tasks = [t for t in data["tasks"] if t.get("category") == cat]
    dist = Counter(t.get("topic") for t in cat_tasks)
    print(f"\n{cat} ({len(cat_tasks)} tasks):")
    for topic, count in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"  {topic}: {count}")
```

### Expected distribution guidelines

No single topic should have more than 40% of a category's tasks. If one topic is too dominant, look for subtopics to split it further or re-examine whether some tasks were misclassified.

---

## 6. Example Classifications

| Task ID | Category | Description excerpt | Correct topic |
|---------|----------|-------------------|---------------|
| `py_01_var` | python | "Создай переменную `sword_damage`" | `variables` |
| `py_cur_d_001_double_xp` | python | "`double_xp(x)`: верни x * 2" | `math_ops` |
| `py_cur_d_007_max_two` | python | "`max_two(a, b)`: верни большее" | `if_else` |
| `py_cur_c_005_choose_path` | python | "верни cave если дождь, иначе road" | `if_else` |
| `py_39_hero_class` | python | "Создай класс `Hero`" | `classes` |
| `js_01_hero_name` | javascript | "Создай переменную `heroName`" | `variables` |
| `js_cur_b_001_dedupe_keep_order` | javascript | "удали дубликаты, сохрани порядок" | `arrays` |
| `js_cur_a_001_extract_numbers` | javascript | "вытащи все целые числа" | `regex` |
| `fe_06_bold_title` | frontend | "`font-weight: bold` к `.title`" | `text_styling` |
| `fe_cur_d_001_d_001_title` | frontend | "Добавь `h1#title`" | `html_elements` |
| `scr_cur_d_001_d_001_move` | scratch | "пройди 20 шагов" | `motion` |
| `scr_cur_d_007_d_007_say` | scratch | "скажи 'Привет!'" | `looks` |
| `scr_cur_d_009_d_009_sound` | scratch | "проиграй звук" | `sound` |

---

## 7. Tutorial Tasks

Tutorial tasks are special tasks where the student watches a YouTube video and submits notes/answers for admin review. They exist in every category and every topic.

### Required Fields for Tutorial Tasks

```json
{
  "id": "py_tut_loops_01",
  "category": "python",
  "tier": "D",
  "topic": "loops",
  "task_type": "tutorial",
  "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "title": "\ud83c\udf93 \u0422\u0443\u0442\u043e\u0440\u0438\u0430\u043b: \u0426\u0438\u043a\u043b\u044b \u0432 Python",
  "story": "\u041c\u0430\u0441\u0442\u0435\u0440 \u043f\u043e\u043a\u0430\u0437\u0430\u043b \u0434\u0440\u0435\u0432\u043d\u0438\u0439 \u0441\u0432\u0438\u0442\u043e\u043a \u0441 \u0443\u0440\u043e\u043a\u043e\u043c...",
  "description": "\u041f\u043e\u0441\u043c\u043e\u0442\u0440\u0438 \u0432\u0438\u0434\u0435\u043e \u043e \u0446\u0438\u043a\u043b\u0430\u0445 for \u0438 while. \u041e\u0442\u0432\u0435\u0442\u044c: 1) \u0427\u0435\u043c for \u043e\u0442\u043b\u0438\u0447\u0430\u0435\u0442\u0441\u044f \u043e\u0442 while? 2) \u041d\u0430\u043f\u0438\u0448\u0438 \u043f\u0440\u0438\u043c\u0435\u0440...",
  "initial_code": "",
  "xp": 10,
  "check_logic": {
    "engine": "manual",
    "cases": []
  },
  "campaign": { "act": 1, "chapter": 1, "order": 0 }
}
```

### Key Rules

| Field | Value | Notes |
|-------|-------|-------|
| `task_type` | `"tutorial"` | **Required.** Regular tasks have `"code"` or omit this field |
| `video_url` | YouTube URL | **Required.** Standard `watch?v=` or `youtu.be/` format |
| `check_logic.engine` | `"manual"` | Forces admin review (no auto-check) |
| `check_logic.cases` | `[]` | Empty — admin reviews manually |
| `initial_code` | `""` | Empty — student writes in notes area, not code editor |
| `id` prefix | `{cat}_tut_{topic}_` | Example: `py_tut_loops_01`, `js_tut_arrays_02` |
| `title` prefix | `\ud83c\udf93 \u0422\u0443\u0442\u043e\u0440\u0438\u0430\u043b:` | Must start with grad emoji |
| `order` in campaign | `0` | Tutorial goes FIRST in each topic (before coding tasks) |

### How Many Tutorials Per Topic

- At least **1 tutorial per topic per category**
- Tier D topics should have 2-3 tutorials (beginner needs more guidance)
- Tier S topics: 1 tutorial is enough

### Description Format

The `description` should contain:
1. What to watch in the video
2. 2-3 specific questions to answer in notes
3. Optional: a small exercise to try after watching

Example:
```
\u041f\u043e\u0441\u043c\u043e\u0442\u0440\u0438 \u0432\u0438\u0434\u0435\u043e \u043e \u0446\u0438\u043a\u043b\u0430\u0445 for \u0438 while \u0432 Python.

\u041e\u0442\u0432\u0435\u0442\u044c \u043d\u0430 \u0432\u043e\u043f\u0440\u043e\u0441\u044b:
1. \u0427\u0435\u043c \u0446\u0438\u043a\u043b for \u043e\u0442\u043b\u0438\u0447\u0430\u0435\u0442\u0441\u044f \u043e\u0442 while?
2. \u041a\u043e\u0433\u0434\u0430 \u043b\u0443\u0447\u0448\u0435 \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u044c for, \u0430 \u043a\u043e\u0433\u0434\u0430 while?
3. \u041d\u0430\u043f\u0438\u0448\u0438 \u0441\u0432\u043e\u0439 \u043f\u0440\u0438\u043c\u0435\u0440 \u0446\u0438\u043a\u043b\u0430, \u043a\u043e\u0442\u043e\u0440\u044b\u0439 \u0432\u044b\u0432\u043e\u0434\u0438\u0442 \u0447\u0438\u0441\u043b\u0430 \u043e\u0442 1 \u0434\u043e 10.
```

### Video URL Guidelines

- Use YouTube videos in **Russian** when possible
- Video should cover the topic at the appropriate tier level
- Duration: 5-15 minutes is ideal
- Prefer well-known channels: \u0422\u0440\u0435\u043f\u0430\u0447\u0451\u0432 \u0414\u043c\u0438\u0442\u0440\u0438\u0439, Selfedu, Winderton, etc.

---

## 8. How to Run

```bash
# 1. Read this spec
# 2. Load tasks.json
# 3. For each task, assign topic
# 4. Add tutorial tasks for each topic
# 5. Save updated tasks.json
# 6. Run validation script from section 5
# 7. Fix any errors and re-validate
```

The frontend is already built and will automatically group tasks once `topic` fields are present. Tutorial tasks with `task_type: "tutorial"` will render with a special golden badge and embedded video player.
