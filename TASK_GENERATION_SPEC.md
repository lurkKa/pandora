# Task Generation Specification v2.0

> **Purpose**: This document provides a complete specification for AI systems to generate high-quality programming tasks for the Code Adventures LMS.  
> **Target**: Any capable LLM  
> **Output Format**: JSON array of task objects (to append into `tasks.json`)

---

## System Context

You are generating tasks for a gamified LMS that teaches programming through RPG-style quests. Tasks are validated client-side using:

- **Python**: server-side sandbox harness (Python 3.x) using simple `eval()` expressions from `cases`
- **JavaScript**: server-side sandbox harness (Node.js `vm`) using simple expressions from `cases`
- **Frontend**: server-side HTML/CSS checks (string/regex + basic selector/property heuristics)
- **Scratch**: manual review (student uploads `.sb3`)

---

## JSON Schema (STRICT)

```json
{
  "id": "string",           // Unique, snake_case: py_03_loops, js_05_objects
  "category": "string",     // ENUM: "python" | "javascript" | "frontend" | "scratch"
  "tier": "string",         // ENUM: "D" | "C" | "B" | "A" | "S"
  "xp": "integer",          // Must match tier curve used in tasks.json (see table below)
  "title": "string",        // Max 40 chars, engaging, fantasy-themed
  "story": "string",        // 1-2 sentences, sets narrative context
  "description": "string",  // Technical task description, clear and concise
  "initial_code": "string", // Starter code with placeholders/comments
  "resources": {            // REQUIRED: at least 1 docs + 1 video link
    "docs": [               // list of docs links
      { "title": "string", "url": "string" }
    ],
    "videos": [             // list of video links (can be a playlist/channel link)
      { "title": "string", "url": "string" }
    ]
  },
  "prerequisites": ["string"], // OPTIONAL: task IDs to unlock this task (skill-tree)
  "campaign": {                // OPTIONAL: roadmap metadata for Campaign Map UI
    "act": "integer",
    "chapter": "integer",
    "order": "integer",
    "type": "string"           // "quest" | "boss" | "side"
  },
  "check_logic": {
    "engine": "string",     // ENUM: "pyodide" | "javascript" | "iframe" | "manual"
    "cases": [              // Array of test cases (not for "manual" engine)
      {
        "type": "string",       // OPTIONAL: "variable_value" (python/js) or frontend case type
        "name": "string",       // REQUIRED for type="variable_value"
        "code": "string",       // REQUIRED for python/js (expression to eval, e.g., "add(2, 3)")
        "expected": "any"       // REQUIRED: expected value (or expected pattern for frontend cases)
      }
    ],
    "hidden_cases": [          // OPTIONAL: same schema as cases (server-only)
      { "code": "string", "expected": "any" }
    ]
  }
}
```

---

## Tier Guidelines

| Tier | Difficulty | Concepts | XP Range | Test Cases |
|------|------------|----------|----------|------------|
| **D** | Absolute beginner | Variables, basic types | 15-25 | 1-2 simple |
| **C** | Beginner | Functions, conditionals, strings | 40-80 | 2-3 |
| **B** | Intermediate | Loops, arrays/lists, objects/dicts | 105-180 | 3-4 edge cases |
| **A** | Advanced | Algorithms, regex, tricky cases | 205-325 | 4-5 with edge cases |
| **S** | Expert/Boss | Optimization, multi-step logic | 365-550 | 5+ comprehensive |

---

## Test Case Design Principles

### 1. Cover Edge Cases
```json
// BAD: Only happy path
{ "code": "reverse_string('hello')", "expected": "olleh" }

// GOOD: Include edge cases
{ "code": "reverse_string('hello')", "expected": "olleh" },
{ "code": "reverse_string('')", "expected": "" },
{ "code": "reverse_string('a')", "expected": "a" }
```

### 2. Use Realistic Data
```json
// BAD: Abstract meaningless values
{ "code": "calculate(1, 2)", "expected": 3 }

// GOOD: Context-appropriate values
{ "code": "calculate_damage(sword_power=15, enemy_armor=5)", "expected": 10 }
```

### 3. Test Return Types Explicitly
```json
// For arrays/lists, always test empty case
{ "code": "filter_items([])", "expected": [] }

// For objects/dicts, test structure
{ "code": "create_hero('Kirito', 10)", "expected": {"name": "Kirito", "level": 10, "hp": 100} }
```

---

## Initial Code Guidelines

### Python Template
```python
def function_name(param1, param2):
    # Description of what to do
    # Hint: Use method_name() to achieve X
    pass  # Replace with your code
```

### JavaScript Template
```javascript
function functionName(param1, param2) {
    // Description of what to do
    // Hint: Use methodName() to achieve X
    return null; // Fix this
}
```

### Frontend Template
```html
<style>
  .class-name {
    /* Add required styles */
  }
</style>
<div class="class-name">Content</div>
```

---

## Narrative Guidelines

### 🇷🇺 ЯЗЫК: РУССКИЙ (ОБЯЗАТЕЛЬНО)

**ВСЕ пользовательские тексты должны быть на русском языке:**
- `title` — на русском
- `story` — на русском  
- `description` — на русском

**Код и технические элементы остаются на английском:**
- `id` — snake_case на английском
- `initial_code` — код на английском (Python/JS синтаксис)
- `check_logic.cases` — на английском

---

### Стиль: Литературный Adventure-русский

Используй стиль, который сочетает:
- **Литературность** — красивый, грамотный русский без сленга
- **Adventure-атмосфера** — фэнтези/RPG лексика, эпичность
- **Краткость** — 1-2 предложения максимум

#### Лексика Adventure-русского:
| Использовать | Избегать |
|--------------|----------|
| Гильдия, странник, герой | Чел, мужик, юзер |
| Сокровищница, инвентарь | Хранилка, база |
| Заклинание, артефакт | Штука, фигня |
| Поверженный, сразить | Убитый, замочить |
| Древний, таинственный | Старый, стрёмный |

---

### Примеры историй (Story)

**✅ Хорошо:**
- "Инвентарь гильдии переполнен. Напиши функцию сортировки предметов по редкости."
- "Торговец просит помочь с расчётом скидок — караван уходит на рассвете!"
- "Карта подземелья повреждена. Восстанови путь к логову босса из строки координат."
- "Древний голем охраняет сокровищницу. Чтобы пройти, реши его загадку о числах."
- "Алхимик потерял рецепт зелья. Объедини два списка ингредиентов без дубликатов."

**❌ Плохо:**
- "Напиши функцию сортировки массива." (Сухо, нет нарратива)
- "Ты — Наруто и тебе нужно..." (Копирайт)
- "В мире, где магия и технологии..." (Слишком длинно)
- "Короч надо массив отсортить" (Сленг)

---

### Примеры заголовков (Title)

**✅ Хорошо:**
- "Переполненный инвентарь"
- "Загадка древнего голема"
- "Тайна алхимика"
- "Сокровища подземелья"
- "Расчёт торговца"

**❌ Плохо:**
- "Задача 1"
- "Массивы"
- "Функция для практики"
- "Array Challenge" (не русский)

---

### Примеры описаний (Description)

**✅ Хорошо:**
- "Напиши функцию `merge_inventory(inv1, inv2)`, которая объединяет два словаря. Если ключ есть в обоих — сложи значения."
- "Создай функцию `find_hero(heroes)`, возвращающую первого героя с уровнем выше 10."

**❌ Плохо:**
- "Сделай функцию" (Слишком кратко, непонятно)
- "Write a function that..." (Не русский)

---

## Category-Specific Rules

### Python Tasks
- Use `def` functions, not classes (unless tier A/S)
- Prefer list comprehensions for B+ tier
- Test with `==` comparison (works for primitives, lists, dicts in Pyodide)
- Avoid external imports (no numpy, pandas, etc.)
  - If you MUST use standard-library modules (e.g., `re`, `random`), include them in `initial_code` and keep it explicit.

### JavaScript Tasks
- Use `function` declarations, not arrow functions for beginners
- Avoid DOM manipulation (separate category)
- Avoid `async/await` unless tier A+
  - The harness uses deep-equality for arrays/objects, so `expected` can be objects/arrays directly.

### Frontend Tasks
Engine: `iframe`.

Supported `cases` formats (pick the strictest you can):
- `{ "type": "content_contain", "expected": "<div class=\\"card\\">" }`
- `{ "type": "content_regex", "expected": "..." }` (regex string)
- `{ "type": "selector_exists", "expected": ".card" }` (simple selectors: `.class`, `#id`, or tag)
- `{ "type": "text_contains", "expected": "..." }`
- `{ "type": "css_property", "expected": { "selector": ".card", "property": "display", "value": "grid" } }`

### Scratch Tasks
- Engine: `manual` (teacher reviews)
- Provide clear, step-by-step instructions
- Initial code can be a short checklist or placeholder (it is not executed)
- Focus on visual/interactive concepts: movement, events, loops

---

## Roadmap (Skill Tree) Rules

To make tasks feel like a real learning roadmap (not a random list):
- Keep **one main concept per task** (especially D/C tiers).
- Use `campaign` to place tasks into **Acts/Chapters** (D→C→B→A→S).
- Use `prerequisites` sparingly to create **micro-chains** (e.g., “variables → strings → functions”).
- Add occasional **boss** tasks that combine 2–3 concepts, but keep acceptance criteria crystal clear.
- Do not produce “filler packs” with repeated story/title templates (these are considered junk tasks).

---

## Anti-Patterns (DO NOT DO)

❌ **Impossible edge cases**
```json
{ "code": "divide(10, 0)", "expected": "error" }  // Don't test exception handling in D-C tiers
```

❌ **Ambiguous expected values**
```json
{ "code": "get_items()", "expected": ["a", "b"] }  // Order-dependent, fragile
```

❌ **External dependencies**
```python
import requests  # Will fail in Pyodide
```

❌ **Floating point equality**
```json
{ "code": "calculate_pi()", "expected": 3.14159265359 }  // Use rounding or tolerance
```

❌ **Overly long initial code**
```python
# 50 lines of boilerplate...  // Keep it under 10 lines
```

---

## Generation Prompt Template

Use this prompt to generate tasks:

```
Generate [N] programming tasks for [CATEGORY] at tier [TIER] for the PANDORA LMS.

Requirements:
- Follow the JSON schema exactly
- Each task must have a fantasy RPG narrative (RU text for title/story/description)
- Include [X] test cases with edge cases
- Initial code should have clear placeholders
- Tasks should teach: [CONCEPT LIST]
- Each task MUST include `resources.docs` (>=1) and `resources.videos` (>=1) with working URLs
- Avoid filler / duplicated templates; each task must feel distinct and purposeful

Output format: JSON array only, no explanation.
```

---

## Example Output

```json
[
  {
    "id": "py_06_dict_merge",
    "category": "python",
    "tier": "B",
    "xp": 150,
    "title": "Слияние инвентарей",
    "story": "Два странника решили объединить свои припасы перед долгим путешествием. Предметы с одинаковым названием нужно сложить.",
    "description": "Напиши функцию `merge_inventory(inv1, inv2)`, которая объединяет два словаря. Если ключ есть в обоих — сложи значения.",
    "initial_code": "def merge_inventory(inv1, inv2):\n    # Объедини два инвентаря\n    # Если предмет есть в обоих — сложи количество\n    return {}",
    "check_logic": {
      "engine": "pyodide",
      "cases": [
        { "code": "merge_inventory({'sword': 1}, {'shield': 2})", "expected": {"sword": 1, "shield": 2} },
        { "code": "merge_inventory({'potion': 3}, {'potion': 2})", "expected": {"potion": 5} },
        { "code": "merge_inventory({}, {'gold': 100})", "expected": {"gold": 100} }
      ]
    }
  },
  {
    "id": "js_06_find_boss",
    "category": "javascript",
    "tier": "B",
    "xp": 150,
    "title": "Охота на босса",
    "story": "В подземелье множество монстров, но лишь один из них — настоящий босс. Найди его!",
    "description": "Напиши функцию `findBoss(monsters)`, которая возвращает первого монстра с `isBoss === true`, или `null` если босса нет.",
    "initial_code": "function findBoss(monsters) {\n    // Найди босса в массиве\n    // Босс имеет isBoss: true\n    return null;\n}",
    "check_logic": {
      "engine": "javascript",
      "cases": [
        { "code": "findBoss([{name: 'Слайм'}, {name: 'Дракон', isBoss: true}])", "expected": {"name": "Дракон", "isBoss": true} },
        { "code": "findBoss([{name: 'Гоблин'}])", "expected": null }
      ]
    }
  }
]
```

---

## Validation Checklist

Before submitting generated tasks, verify:

- [ ] `id` is unique and follows naming convention
- [ ] `tier` matches complexity of the solution
- [ ] `xp` is within range for the tier
- [ ] `initial_code` compiles/runs without errors
- [ ] All test cases pass with a correct solution
- [ ] Edge cases are covered (empty input, single element, etc.)
- [ ] Story is engaging but concise
- [ ] No copyrighted names or references

---

## File Location

Save generated tasks to:
```
/home/qarrooak/Documents/PANDORA/tasks.json
```

Append to existing `tasks` array, do not overwrite.

---

*Last Updated: 2026-01-29*
*Revised: 2026-02-20*
