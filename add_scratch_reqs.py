
import json

# Map task IDs to required Scratch block opcodes
requirements = {
    "scr_04_glide": ["motion_glideto"],
    "scr_05_costume": ["looks_nextcostume"],
    "scr_06_sound": ["sound_playuntildone"],
    "scr_07_say": ["looks_sayforsecs"],
    "scr_08_size": ["looks_setsizeto", "looks_changesizeby"],
    "scr_09_dialog": ["control_wait", "looks_sayforsecs"],
    "scr_10_backdrop": ["looks_switchbackdropto", "motion_gotoxy"],
    "scr_11_input": ["sensing_askandwait", "control_if_else"],
    "scr_12_broadcast": ["event_broadcast", "event_whenbroadcastreceived"],
    "scr_13_variable": ["data_changevariableby", "data_showvariable"],
    "scr_14_loop": ["control_forever", "motion_ifonedgebounce"],
    "scr_15_if_else": ["control_if_else", "operator_gt"],
    "scr_16_collision": ["sensing_touchingcolor"],
    "scr_17_clone": ["control_create_clone_of", "control_start_as_clone"],
    "scr_18_timer": ["sensing_timer", "control_if"],
    "scr_19_game_catcher": ["motion_changexby", "operator_random"],
    "scr_20_game_platform": ["motion_changeyby", "sensing_touchingobject"],
    "scr_21_game_shooter": ["control_create_clone_of", "motion_movesteps"],
    "scr_22_list": ["data_addtolist", "data_deleteoflist"],
    "scr_23_custom_block": ["procedures_definition"]
}

def add_requirements():
    with open('tasks.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    count = 0
    for task in data['tasks']:
        if task['id'] in requirements:
            # Switch engine to manual (it's hybrid now in backend, but keep 'manual' for frontend compatibility)
            # Add required_blocks
            if 'check_logic' not in task:
                task['check_logic'] = {}
            
            task['check_logic']['required_blocks'] = requirements[task['id']]
            count += 1
            print(f"Updated {task['id']}")

    with open('tasks.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    
    print(f"Updated {count} tasks with requirements.")

if __name__ == "__main__":
    add_requirements()
