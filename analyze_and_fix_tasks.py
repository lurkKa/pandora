#!/usr/bin/env python3
"""
Скрипт анализа и исправления задач в PANDORA LMS.
Выполняет:
1. Поиск явных подсказок в initial_code
2. Проверку валидности задач
3. Отчет о проблемах
"""

import json
import re
from pathlib import Path

# Паттерны явных подсказок (hints) которые нужно убрать
HINT_PATTERNS = [
    # Python комментарии с подсказками
    r'#\s*(Преобразуй|Удали|Используй|Разверни|Посчитай|Верни|Найди|Фильтр|filtered|set\(\))',
    r'#\s*.*(в верхний регистр|из списка|оператор in|может помочь)',
    r'#\s*(STR|NUM|ID)\s*',  # Технические артефакты
    # JavaScript комментарии с подсказками  
    r'//\s*(Верни|Удали|Найди|Используй)',
]

# Что считать НЕ подсказкой (допустимые комментарии)
ALLOWED_COMMENTS = [
    r'#\s*Твой код',
    r'#\s*Твое',  
    r'#\s*Создай',
    r'//\s*Твой код',
]

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def find_hints_in_code(code: str) -> list[str]:
    """Найти явные подсказки в коде."""
    hints = []
    for pattern in HINT_PATTERNS:
        matches = re.findall(pattern, code, re.IGNORECASE)
        if matches:
            hints.extend(matches)
    return hints

def clean_initial_code(code: str, category: str) -> str:
    """Удалить явные подсказки из initial_code."""
    if not code:
        return code
    
    lines = code.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Проверяем каждый паттерн подсказок
        is_hint = False
        for pattern in HINT_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                is_hint = True
                break
        
        # Проверяем, является ли комментарий допустимым
        is_allowed = False
        for pattern in ALLOWED_COMMENTS:
            if re.search(pattern, line, re.IGNORECASE):
                is_allowed = True
                break
        
        if is_hint and not is_allowed:
            # Если строка содержит только комментарий-подсказку - пропускаем
            if category == 'python' and stripped.startswith('#'):
                continue
            elif category == 'javascript' and stripped.startswith('//'):
                continue
            # Если код + комментарий - убираем только комментарий
            if category == 'python' and '#' in line:
                line = line.split('#')[0].rstrip()
            elif category == 'javascript' and '//' in line:
                line = line.split('//')[0].rstrip()
        
        cleaned_lines.append(line)
    
    # Убираем пустые строки в конце
    while cleaned_lines and not cleaned_lines[-1].strip():
        cleaned_lines.pop()
    
    return '\n'.join(cleaned_lines)

def validate_task(task: dict) -> list[str]:
    """Проверить валидность задачи."""
    errors = []
    task_id = task.get('id', 'UNKNOWN')
    
    # Обязательные поля
    required = ['id', 'category', 'tier', 'xp', 'title', 'description']
    for field in required:
        if not task.get(field):
            errors.append(f"[{task_id}] Отсутствует поле: {field}")
    
    # Проверка tier
    valid_tiers = ['D', 'C', 'B', 'A', 'S']
    if task.get('tier') and task['tier'] not in valid_tiers:
        errors.append(f"[{task_id}] Недопустимый tier: {task['tier']}")
    
    # Проверка XP
    if task.get('xp') and not isinstance(task['xp'], int):
        errors.append(f"[{task_id}] XP должен быть целым числом")
    
    # Проверка check_logic
    check_logic = task.get('check_logic', {})
    engine = check_logic.get('engine', '')
    
    if task.get('category') != 'scratch':
        if not engine:
            errors.append(f"[{task_id}] Отсутствует engine в check_logic")
        elif engine in ('pyodide', 'python', 'javascript', 'js'):
            if not check_logic.get('cases'):
                errors.append(f"[{task_id}] Отсутствуют test cases для {engine}")
    
    return errors

def analyze_tasks():
    """Анализ всех задач."""
    tasks_file = Path('tasks.json')
    if not tasks_file.exists():
        print("❌ Файл tasks.json не найден!")
        return
    
    data = load_json(tasks_file)
    tasks = data.get('tasks', [])
    
    print(f"📊 Анализ {len(tasks)} задач...\n")
    
    hints_found = []
    validation_errors = []
    stats = {'total': len(tasks), 'with_hints': 0, 'invalid': 0}
    
    for task in tasks:
        task_id = task.get('id', 'UNKNOWN')
        category = task.get('category', '')
        initial_code = task.get('initial_code', '')
        
        # Поиск подсказок
        hints = find_hints_in_code(initial_code)
        if hints:
            hints_found.append({
                'id': task_id,
                'title': task.get('title', ''),
                'hints': hints,
                'code': initial_code[:100] + '...' if len(initial_code) > 100 else initial_code
            })
            stats['with_hints'] += 1
        
        # Валидация
        errors = validate_task(task)
        if errors:
            validation_errors.extend(errors)
            stats['invalid'] += 1
    
    # Отчет
    print("=" * 60)
    print("📋 ОТЧЕТ АНАЛИЗА ЗАДАЧ")
    print("=" * 60)
    
    print(f"\n📈 Статистика:")
    print(f"   Всего задач: {stats['total']}")
    print(f"   С явными подсказками: {stats['with_hints']}")
    print(f"   С ошибками валидации: {stats['invalid']}")
    
    if hints_found:
        print(f"\n🔍 Задачи с явными подсказками ({len(hints_found)}):")
        for h in hints_found[:20]:  # Показываем первые 20
            print(f"   [{h['id']}] {h['title']}")
            print(f"      Подсказки: {h['hints']}")
    
    if validation_errors:
        print(f"\n⚠️ Ошибки валидации ({len(validation_errors)}):")
        for err in validation_errors[:20]:
            print(f"   {err}")
    
    return hints_found, validation_errors

def fix_tasks(dry_run=True):
    """Исправить задачи: удалить подсказки."""
    tasks_file = Path('tasks.json')
    data = load_json(tasks_file)
    tasks = data.get('tasks', [])
    
    fixed_count = 0
    
    for task in tasks:
        category = task.get('category', '')
        initial_code = task.get('initial_code', '')
        
        if category in ('python', 'javascript') and initial_code:
            cleaned = clean_initial_code(initial_code, category)
            if cleaned != initial_code:
                fixed_count += 1
                if not dry_run:
                    task['initial_code'] = cleaned
                print(f"✏️ Исправлено: [{task['id']}] {task['title']}")
    
    if not dry_run and fixed_count > 0:
        # Создаем бэкап
        backup_file = Path('tasks_backup.json')
        save_json(backup_file, load_json(tasks_file))
        print(f"\n💾 Создан бэкап: {backup_file}")
        
        # Сохраняем исправления
        save_json(tasks_file, data)
        print(f"✅ Исправлено {fixed_count} задач")
    else:
        print(f"\n📝 Dry run: {fixed_count} задач будет исправлено")
        print("   Для применения изменений запустите: fix_tasks(dry_run=False)")
    
    return fixed_count

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--fix':
        fix_tasks(dry_run=False)
    else:
        hints, errors = analyze_tasks()
        print("\n" + "=" * 60)
        print("💡 Для исправления задач запустите:")
        print("   python analyze_and_fix_tasks.py --fix")
