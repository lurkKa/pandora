#!/usr/bin/env python3
"""
Add campaign system metadata to all tasks in tasks.json.

Campaign Structure:
- Act 1 (Tier D): Chapters 1-2, ~40 tasks + 2 bosses
- Act 2 (Tier C): Chapters 3-5, ~78 tasks + 3 bosses  
- Act 3 (Tier B): Chapters 6-8, ~71 tasks + 3 bosses
- Act 4 (Tier A): Chapters 9-10, ~33 tasks + 2 bosses
- Act 5 (Tier S): Chapter 11, ~11 tasks + 1 final boss
"""

import json
from pathlib import Path

# Campaign configuration
CAMPAIGN_CONFIG = {
    'D': {'act': 1, 'chapters': [1, 2], 'tasks_per_chapter': 20},
    'C': {'act': 2, 'chapters': [3, 4, 5], 'tasks_per_chapter': 26},
    'B': {'act': 3, 'chapters': [6, 7, 8], 'tasks_per_chapter': 24},
    'A': {'act': 4, 'chapters': [9, 10], 'tasks_per_chapter': 17},
    'S': {'act': 5, 'chapters': [11], 'tasks_per_chapter': 11},
}

# Boss task IDs - last task of each chapter becomes a boss
BOSS_MARKERS = {
    'D': ['py_05_dict', 'js_04_find'],  # Example boss tasks per tier
    'C': ['py_10_party_leader', 'scr_12_broadcast', 'js_03_obj'],
    'B': ['py_15_level_up', 'scr_18_timer', 'fe_03_card'],
    'A': ['py_19_anagram_rune', 'scr_23_custom_block'],
    'S': ['py_25_path_exists'],
}

def add_campaign_metadata(tasks_file: Path):
    """Add campaign field to all tasks."""
    
    with open(tasks_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Group tasks by tier and category
    tier_tasks = {'D': [], 'C': [], 'B': [], 'A': [], 'S': []}
    for i, task in enumerate(data['tasks']):
        tier = task.get('tier', 'D')
        tier_tasks[tier].append((i, task))
    
    # Flatten all boss IDs for lookup
    all_bosses = set()
    for bosses in BOSS_MARKERS.values():
        all_bosses.update(bosses)
    
    # Assign campaign metadata per tier
    for tier, config in CAMPAIGN_CONFIG.items():
        tasks = tier_tasks.get(tier, [])
        if not tasks:
            continue
        
        chapters = config['chapters']
        tasks_per_chapter = len(tasks) // len(chapters)
        
        for idx, (orig_idx, task) in enumerate(tasks):
            # Determine chapter
            chapter_idx = min(idx // max(tasks_per_chapter, 1), len(chapters) - 1)
            chapter = chapters[chapter_idx]
            order = (idx % max(tasks_per_chapter, 1)) + 1
            
            # Determine type
            task_id = task.get('id', '')
            if task_id in all_bosses:
                task_type = 'boss'
            elif task.get('category') == 'scratch':
                task_type = 'side'  # Scratch tasks are side quests (manual review)
            else:
                task_type = 'quest'
            
            # Add campaign metadata
            campaign = {
                'act': config['act'],
                'chapter': chapter,
                'order': order,
                'type': task_type
            }
            
            # Update task in original data
            data['tasks'][orig_idx]['campaign'] = campaign
    
    # Write back
    with open(tasks_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    # Print summary
    print(f"Updated {len(data['tasks'])} tasks with campaign metadata.")
    
    # Count by type
    types = {'quest': 0, 'boss': 0, 'side': 0}
    acts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for task in data['tasks']:
        if 'campaign' in task:
            types[task['campaign']['type']] = types.get(task['campaign']['type'], 0) + 1
            acts[task['campaign']['act']] = acts.get(task['campaign']['act'], 0) + 1
    
    print(f"\nBy type: {types}")
    print(f"By act: {acts}")

if __name__ == '__main__':
    tasks_file = Path(__file__).parent / 'tasks.json'
    add_campaign_metadata(tasks_file)
