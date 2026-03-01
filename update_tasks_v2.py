import json

# New 20 Scratch Tasks
new_tasks = [
    {
        "id": "scr_04_glide",
        "category": "scratch",
        "tier": "D",
        "xp": 10,
        "title": "Призрачный Полёт",
        "story": "Твой дух должен бесшумно перемещаться по замку. Используй магию скольжения!",
        "description": "Используй блок `плыть ... сек в случайное положение`, чтобы спрайт плавно перемещался.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_05_costume",
        "category": "scratch",
        "tier": "D",
        "xp": 10,
        "title": "Маскировка Шпиона",
        "story": "Стража близко! Быстро смени внешность, чтобы тебя не узнали.",
        "description": "Сделай так, чтобы при клике на спрайт он менял костюм (`следующий костюм`).",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_06_sound",
        "category": "scratch",
        "tier": "D",
        "xp": 10,
        "title": "Боевой Клич",
        "story": "Враг наступает. Издай устрашающий звук, чтобы поднять боевой дух!",
        "description": "При нажатии `Пробел` спрайт должен воспроизводить звук (`играть звук ... до конца`).",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_07_say",
        "category": "scratch",
        "tier": "D",
        "xp": 10,
        "title": "Мудрый Совет",
        "story": "Старейшина хочет передать тебе древнее знание. Выслушай его.",
        "description": "Пусть спрайт скажет 'Опасно идти одному, возьми это!' в течение 2 секунд.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_08_size",
        "category": "scratch",
        "tier": "D",
        "xp": 10,
        "title": "Зелье Роста",
        "story": "Ты выпил странное зелье и начал расти! Стань великаном.",
        "description": "При нажатии на флажок установи размер 100%, а затем плавно увеличивай его до 200%.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_09_dialog",
        "category": "scratch",
        "tier": "C",
        "xp": 50,
        "title": "Разговор с Торговцем",
        "story": "Торговец предлагает редкий товар. Поторгуйся с ним.",
        "description": "Создай диалог между двумя спрайтами. Используй блоки `ждать` и `говорить`, чтобы они отвечали друг другу.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_10_backdrop",
        "category": "scratch",
        "tier": "C",
        "xp": 50,
        "title": "Смена Локации",
        "story": "Ты покидаешь безопасный город и входишь в темный лес.",
        "description": "Когда спрайт касается края экрана, фон должен смениться на `Forest`, а спрайт переместиться в начало.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_11_input",
        "category": "scratch",
        "tier": "C",
        "xp": 50,
        "title": "Пароль от Ворот",
        "story": "Страж ворот требует пароль. Только истинный герой знает ответ.",
        "description": "Спрайт должен спросить 'Пароль?'. Если ответ 'Mellon', сказать 'Проходи', иначе 'Уходи'.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_12_broadcast",
        "category": "scratch",
        "tier": "C",
        "xp": 50,
        "title": "Сигнал Атаки",
        "story": "Командир дает сигнал! Все лучники должны выстрелить одновременно.",
        "description": "Один спрайт передает сообщение `Атака`, другие спрайты при получении сообщения начинают анимацию.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_13_variable",
        "category": "scratch",
        "tier": "C",
        "xp": 50,
        "title": "Сбор Кристаллов",
        "story": "Собирай магические кристаллы, чтобы зарядить посох.",
        "description": "Создай переменную `Score`. При клике на спрайт кристалла, увеличивай счет на 1 и прячь кристалл.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_14_loop",
        "category": "scratch",
        "tier": "B",
        "xp": 100,
        "title": "Патруль Стражника",
        "story": "Орк патрулирует периметр. Не попадись ему на глаза!",
        "description": "Заставь спрайта бесконечно ходить влево-вправо. Используй цикл `всегда` и `если касается края, оттолкнуться`.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_15_if_else",
        "category": "scratch",
        "tier": "B",
        "xp": 100,
        "title": "Проверка Уровня",
        "story": "Только опытные воины могут войти в подземелье.",
        "description": "Если переменная `Level` > 5, спрайт говорит 'Добро пожаловать', иначе - 'Тренируйся еще'.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_16_collision",
        "category": "scratch",
        "tier": "B",
        "xp": 100,
        "title": "Огненная Ловушка",
        "story": "Пол - это лава! Не касайся красных камней.",
        "description": "Если спрайт героя касается красного цвета (лавы), игра останавливается или отнимаются жизни.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_17_clone",
        "category": "scratch",
        "tier": "B",
        "xp": 100,
        "title": "Армия Скелетов",
        "story": "Некромант призывает миньонов! Их становится все больше.",
        "description": "Каждую секунду создавай клон скелета, который идет в случайном направлении.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_18_timer",
        "category": "scratch",
        "tier": "B",
        "xp": 100,
        "title": "Выжить 10 Секунд",
        "story": "Продержись на арене, пока не откроются ворота!",
        "description": "Используй таймер. Уворачивайся от врагов. Если таймер > 10, выиграл.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_19_game_catcher",
        "category": "scratch",
        "tier": "A",
        "xp": 150,
        "title": "Ловец Душ",
        "story": "Поймай падающие души, прежде чем они исчезнут в бездне.",
        "description": "Создай игру: сверху падают предметы, игрок внизу ловит их корзиной. Считай очки.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_20_game_platform",
        "category": "scratch",
        "tier": "A",
        "xp": 150,
        "title": "Путь Героя",
        "story": "Преодолей пропасти и препятствия, чтобы добраться до замка.",
        "description": "Реализуй простую физику прыжков и гравитации. Спрайт должен прыгать по платформам.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_21_game_shooter",
        "category": "scratch",
        "tier": "A",
        "xp": 150,
        "title": "Оборона Башни",
        "story": "Враги атакуют ворота! Не дай им пройти.",
        "description": "Спрайт игрока стреляет снарядами во врагов, которые идут волнами.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_22_list",
        "category": "scratch",
        "tier": "A",
        "xp": 150,
        "title": "Книга Заклинаний",
        "story": "Запиши новые заклинания в свой гримуар.",
        "description": "Используй Список. Кнопки 'Добавить' и 'Удалить' должны менять содержимое списка заклинаний.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    },
    {
        "id": "scr_23_custom_block",
        "category": "scratch",
        "tier": "A",
        "xp": 150,
        "title": "Тайный Прием",
        "story": "Создай свою уникальную технику боя.",
        "description": "Создай Свой Блок (Custom Block) 'SuperJump', который делает прыжок с сальто, и используй его.",
        "initial_code": "ссылка_на_проект",
        "check_logic": {"engine": "manual", "evaluator": "admin"}
    }
]

def update_tasks():
    with open('tasks.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 1. Update XP for existing tasks
    for task in data['tasks']:
        tier = task.get('tier')
        if tier == 'D':
            task['xp'] = 10
        elif tier == 'C':
            task['xp'] = 50
        elif tier == 'B':
            task['xp'] = 100
        elif tier in ['A', 'S']:
            task['xp'] = 150
            
    # 2. Append new tasks
    # Check for duplicates by ID before adding
    existing_ids = set(t['id'] for t in data['tasks'])
    for new_task in new_tasks:
        if new_task['id'] not in existing_ids:
            data['tasks'].append(new_task)
            print(f"Added task: {new_task['title']}")
        else:
            print(f"Skipped duplicate: {new_task['id']}")

    with open('tasks.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    
    print("Tasks updated successfully.")

if __name__ == "__main__":
    update_tasks()
