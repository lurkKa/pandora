# Task Generation Specification v1.0

> **Purpose**: This document provides a complete specification for AI systems to generate high-quality programming tasks for the Code Adventures LMS.  
> **Target**: GPT-4, Claude, Gemini, or any capable LLM  
> **Output Format**: JSON array of task objects

---

## System Context

You are generating tasks for a gamified LMS that teaches programming through RPG-style quests. Tasks are validated client-side using:

- **Python**: Pyodide (Python 3.11 in WebAssembly)
- **JavaScript**: Native browser engine (V8/SpiderMonkey)
- **Frontend**: HTML/CSS rendered in sandboxed iframe, validated via string matching
- **Scratch**: External links, manually reviewed by teacher

---

## JSON Schema (STRICT)

```json
{
  "id": "string",           // Unique, snake_case: py_03_loops, js_05_objects
  "category": "string",     // ENUM: "python" | "javascript" | "frontend" | "scratch"
  "tier": "string",         // ENUM: "D" | "C" | "B" | "A" | "S"
  "xp": "integer",          // Range: 50-500 based on tier
  "title": "string",        // Max 40 chars, engaging, fantasy-themed
  "story": "string",        // 1-2 sentences, sets narrative context
  "description": "string",  // Technical task description, clear and concise
  "initial_code": "string", // Starter code with placeholders/comments
  "check_logic": {
    "engine": "string",     // ENUM: "pyodide" | "javascript" | "iframe" | "manual"
    "cases": [              // Array of test cases (not for "manual" engine)
      {
        "code": "string",       // Expression to evaluate (e.g., "add(2, 3)")
        "expected": "any",      // Expected return value (number, string, array, object)
        "type": "string"        // Optional: "variable_value" for checking variable existence
      }
    ]
  }
}
```

---

## Tier Guidelines

| Tier | Difficulty | Concepts | XP Range | Test Cases |
|------|------------|----------|----------|------------|
| **D** | Absolute beginner | Variables, print, basic types | 50-60 | 1-2 simple |
| **C** | Beginner | Functions, conditionals, strings | 80-120 | 2-3 |
| **B** | Intermediate | Loops, arrays/lists, objects/dicts | 150-200 | 3-4 edge cases |
| **A** | Advanced | Algorithms, recursion, complex logic | 250-400 | 4-5 with edge cases |
| **S** | Expert/Boss | Optimization, system design, multi-step | 500+ | 5+ comprehensive |

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

### JavaScript Tasks
- Use `function` declarations, not arrow functions for beginners
- Test with `JSON.stringify()` for array/object comparison
- Avoid DOM manipulation (separate category)
- Avoid `async/await` unless tier A+

### Frontend Tasks
- Engine: `iframe` with `content_contain` string check
- Focus on CSS properties, not complex layouts
- Test for presence of key properties: `display: flex`, `border-radius`, etc.
- Include a visible element, not just styles

### Scratch Tasks
- Engine: `manual` (teacher reviews)
- Provide clear, step-by-step instructions
- Initial code should be a placeholder for the Scratch project link
- Focus on visual/interactive concepts: movement, events, loops

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
Generate [N] programming tasks for [CATEGORY] at tier [TIER].

Requirements:
- Follow the JSON schema exactly
- Each task must have a fantasy RPG narrative
- Include [X] test cases with edge cases
- Initial code should have clear placeholders
- Tasks should teach: [CONCEPT LIST]

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
