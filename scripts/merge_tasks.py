import json
import os
import shutil

BASE_DIR = "/home/qarrooak/Documents/PANDORA"
TASKS_FILE = os.path.join(BASE_DIR, "tasks.json")
CONTENT_DIR = os.path.join(BASE_DIR, "content")

def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def main():
    # 1. Load existing tasks
    if os.path.exists(TASKS_FILE):
        print(f"Loading existing tasks from {TASKS_FILE}...")
        main_data = load_json(TASKS_FILE)
        # Backup
        shutil.copy2(TASKS_FILE, TASKS_FILE + ".bak")
    else:
        print("Creating new tasks.json structure...")
        main_data = {
            "meta": {"version": "2.1", "theme": "isekai_adventures", "description": "Auto-generated tasks"},
            "categories": ["python", "javascript", "frontend", "scratch"],
            "tasks": []
        }

    existing_ids = {t['id'] for t in main_data.get('tasks', [])}
    print(f"Found {len(existing_ids)} existing tasks.")

    # 2. Load and merge new content
    files = [
        "tasks_python.json",
        "tasks_javascript.json",
        "tasks_frontend.json",
        "tasks_scratch.json"
    ]

    new_tasks_count = 0
    skipped_count = 0

    for filename in files:
        path = os.path.join(CONTENT_DIR, filename)
        if not os.path.exists(path):
            print(f"Warning: {filename} not found.")
            continue

        print(f"Processing {filename}...")
        new_tasks = load_json(path)
        
        for task in new_tasks:
            if task['id'] in existing_ids:
                print(f"  Skipping duplicate ID: {task['id']}")
                skipped_count += 1
                continue
            
            # Basic validation
            if 'category' not in task or 'tier' not in task:
                print(f"  Skipping invalid task {task.get('id', '?')}: Missing category/tier")
                continue

            main_data['tasks'].append(task)
            existing_ids.add(task['id'])
            new_tasks_count += 1

    # 3. Save
    save_json(TASKS_FILE, main_data)
    print("="*40)
    print(f"Merge Complete.")
    print(f"Added: {new_tasks_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Total tasks: {len(main_data['tasks'])}")
    print("="*40)

if __name__ == "__main__":
    main()
