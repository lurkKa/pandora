
import json
import sys

try:
    with open('tasks.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    print("JSON is valid.")
    print(f"Loaded {len(data.get('tasks', []))} tasks.")
    # Print first task title to check encoding
    if data['tasks']:
        print(f"First task title: {data['tasks'][0]['title']}")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
