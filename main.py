import telebot
from telebot import types
import requests
from datetime import datetime
import sqlite3

DAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]

TOKEN = "8593893339:AAFc--pIlkN1w9qKxUwIPgGUmzH9aHpZykA"
API_URL = "https://api.schedulevtk.kz/api/files/earliest"

bot = telebot.TeleBot(TOKEN)

# --- БАЗА ДАННЫХ ---


def get_api_data():
    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к API: {e}")
        return None


def init_db():
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY,
        role TEXT,
        user_id TEXT,
        selected_day INTEGER
    )""")
    conn.commit()
    conn.close()


def save_user_setting(chat_id, key, value):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    column = {"role": "role", "id": "user_id", "selected_day": "selected_day"}[key]
    c.execute(f"UPDATE users SET {column} = ? WHERE chat_id = ?", (value, chat_id))
    if c.rowcount == 0:
        # Если записи нет, вставляем
        c.execute(
            "INSERT INTO users (chat_id, role, user_id, selected_day) VALUES (?, ?, ?, ?)",
            (
                chat_id,
                value if key == "role" else None,
                value if key == "id" else None,
                value if key == "selected_day" else None,
            ),
        )
    conn.commit()
    conn.close()


def get_user_settings(chat_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute(
        "SELECT role, user_id, selected_day FROM users WHERE chat_id = ?", (chat_id,)
    )
    row = c.fetchone()
    conn.close()
    if row:
        return {"role": row[0], "id": row[1], "selected_day": row[2]}
    return {}


# Инициализация БД
init_db()


def get_teachers_keyboard(data, page=0, per_page=27):
    if not data:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "Ошибка загрузки данных", callback_data="back_to_role"
            )
        )
        return markup

    teachers = data.get("teachers", {}).get("teacher", [])
    start = page * per_page
    end = start + per_page
    page_teachers = teachers[start:end]

    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = [
        types.InlineKeyboardButton(
            text=t.get("_short", "???"), callback_data=f"set_teach_{t['_id']}"
        )
        for t in page_teachers
    ]
    markup.add(*buttons)

    # Навигация
    nav_row = []
    if page > 0:
        nav_row.append(
            types.InlineKeyboardButton(
                "⬅️ Назад", callback_data=f"teach_page_{page - 1}"
            )
        )
    if end < len(teachers):
        nav_row.append(
            types.InlineKeyboardButton(
                "Вперед ➡️", callback_data=f"teach_page_{page + 1}"
            )
        )
    if nav_row:
        markup.row(*nav_row)

    markup.add(
        types.InlineKeyboardButton("🔙 К выбору роли", callback_data="back_to_role")
    )
    return markup


def get_classes_keyboard(data, page=0, per_page=27):
    if not data:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "Ошибка загрузки данных", callback_data="back_to_role"
            )
        )
        return markup

    classes = data.get("classes", {}).get("class", [])
    start = page * per_page
    end = start + per_page
    page_classes = classes[start:end]

    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = [
        types.InlineKeyboardButton(
            text=c.get("_name", "???"), callback_data=f"set_class_{c['_id']}"
        )
        for c in page_classes
    ]
    markup.add(*buttons)

    # Навигация
    nav_row = []
    if page > 0:
        nav_row.append(
            types.InlineKeyboardButton(
                "⬅️ Назад", callback_data=f"class_page_{page - 1}"
            )
        )
    if end < len(classes):
        nav_row.append(
            types.InlineKeyboardButton(
                "Вперед ➡️", callback_data=f"class_page_{page + 1}"
            )
        )
    if nav_row:
        markup.row(*nav_row)

    markup.add(
        types.InlineKeyboardButton("🔙 К выбору роли", callback_data="back_to_role")
    )
    return markup


# --- ГЕНЕРАТОРЫ КЛАВИАТУР ---


def get_role_keyboard():
    markup = types.InlineKeyboardMarkup()
    # Исправлено: callback_data вместо callback_query_data
    markup.add(
        types.InlineKeyboardButton("👨‍🎓 Студент", callback_data="set_role_student")
    )
    markup.add(
        types.InlineKeyboardButton(
            "👨‍🏫 Преподаватель", callback_data="set_role_teacher"
        )
    )
    return markup


def get_main_menu():
    markup = types.InlineKeyboardMarkup()
    # Исправлено здесь и во всех остальных кнопках
    markup.add(
        types.InlineKeyboardButton("📅 Расписание", callback_data="get_schedule")
    )
    markup.add(
        types.InlineKeyboardButton(
            "🚪 Свободные кабинеты", callback_data="get_free_rooms"
        )
    )
    markup.add(types.InlineKeyboardButton("⚙️ Настройки", callback_data="start_setup"))
    return markup


# --- ОБРАБОТЧИКИ КОМАНД ---


@bot.message_handler(commands=["start", "settings"])
def start_command(message):
    chat_id = message.chat.id
    settings = get_user_settings(chat_id)
    username = message.chat.first_name or "Пользователь"

    if settings.get("role") and settings.get("id"):
        # Профиль уже настроен, показываем инструкцию
        text = (
            f"👋 Привет, {username}!\n\n"
            "📅 Нажмите 'Расписание' для просмотра вашего расписания.\n"
            "🚪 'Свободные кабинеты' покажет доступные аудитории.\n"
            "⚙️ 'Настройки' для изменения профиля.\n\n"
            "Используйте стрелки для навигации по дням недели."
        )

        bot.send_message(chat_id, text, reply_markup=get_main_menu())
    else:
        # Начинаем настройку
        bot.send_message(
            chat_id,
            "Привет! Давай настроим профиль для получения расписания.",
            reply_markup=get_role_keyboard(),
        )


@bot.message_handler(commands=["free_rooms"])
def free_rooms_command(message):
    show_free_rooms(message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == "start_setup")
def handle_start_setup(call):
    bot.edit_message_text(
        "Выберите роль:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=get_role_keyboard(),
    )


@bot.callback_query_handler(func=lambda call: call.data == "back_to_role")
def back_to_role(call):
    bot.edit_message_text(
        "Выберите роль:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=get_role_keyboard(),
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("teach_page_"))
def handle_teach_page(call):
    page = int(call.data.split("_")[-1])
    data = get_api_data()
    markup = get_teachers_keyboard(data, page)
    bot.edit_message_text(
        "Выберите вашу фамилию:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("class_page_"))
def handle_class_page(call):
    page = int(call.data.split("_")[-1])
    data = get_api_data()
    markup = get_classes_keyboard(data, page)
    bot.edit_message_text(
        "Выберите вашу группу:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("set_role_"))
def handle_role_selection(call):
    role = call.data.split("_")[-1]
    save_user_setting(call.message.chat.id, "role", role)

    data = get_api_data()
    if not data:
        bot.edit_message_text(
            "❌ Ошибка загрузки данных. Попробуйте позже.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_role_keyboard(),
        )
        return

    markup = types.InlineKeyboardMarkup(row_width=2)

    if role == "student":
        # Загружаем список КЛАССОВ из API с пагинацией
        markup = get_classes_keyboard(data, 0)
        bot.edit_message_text(
            "Выберите вашу группу:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
        )
    else:
        # Логика для преподавателей
        markup = get_teachers_keyboard(data, 0)
        bot.edit_message_text(
            "Выберите вашу фамилию:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
        )


# --- ГЕНЕРАТОРЫ КЛАВИАТУР ---


def get_schedule_keyboard(day_index):
    """Клавиатура со стрелками и названием дня"""
    markup = types.InlineKeyboardMarkup()

    # Определяем индексы для стрелок (с зацикливанием)
    prev_day = (day_index - 1) % 6
    next_day = (day_index + 1) % 6

    # Ряд с навигацией: [ < ] [ Название дня ] [ > ]
    markup.row(
        types.InlineKeyboardButton("⬅️", callback_data=f"sched_day_{prev_day}"),
        types.InlineKeyboardButton(DAYS[day_index], callback_data="open_days_list"),
        types.InlineKeyboardButton("➡️", callback_data=f"sched_day_{next_day}"),
    )

    markup.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")
    )
    return markup


def get_days_selection_keyboard():
    """Клавиатура со списком всех дней недели"""
    markup = types.InlineKeyboardMarkup(row_width=2)

    # Кнопки для каждого дня
    buttons = [
        types.InlineKeyboardButton(day, callback_data=f"sched_day_{i}")
        for i, day in enumerate(DAYS)
    ]
    markup.add(*buttons)

    # Кнопка возврата
    markup.add(
        types.InlineKeyboardButton("🔙 Вернуться назад", callback_data="get_schedule")
    )
    return markup


# --- ОБРАБОТЧИКИ CALLBACK ---


@bot.callback_query_handler(func=lambda call: call.data == "open_days_list")
def handle_open_days(call):
    """Показ списка дней при нажатии на название текущего дня"""
    bot.edit_message_text(
        "📅 Выберите день недели из списка:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=get_days_selection_keyboard(),
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("sched_day_"))
def handle_day_switch(call):
    """Переключение дня через стрелки или список"""
    day_index = int(call.data.split("_")[-1])

    # Сохраняем выбранный день в настройки пользователя
    save_user_setting(call.message.chat.id, "selected_day", day_index)

    # Обновляем сообщение с расписанием
    show_schedule_view(call.message, day_index)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_to_main(call):
    bot.edit_message_text(
        "Всё готово! Чем могу помочь?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=get_main_menu(),
    )


# --- ОБНОВЛЕННАЯ ФУНКЦИЯ ПРОСМОТРА РАСПИСАНИЯ ---


@bot.callback_query_handler(func=lambda call: call.data == "get_schedule")
def handle_schedule_init(call):
    current_day = datetime.now().weekday()
    if current_day > 5:
        current_day = 0
    show_schedule_view(call.message, current_day)


def show_schedule_view(message, day_index):
    data = get_api_data()
    if not data:
        bot.edit_message_text(
            "❌ Ошибка загрузки данных.",
            message.chat.id,
            message.message_id,
            reply_markup=get_main_menu(),
        )
        return

    chat_id = message.chat.id
    settings = get_user_settings(chat_id)
    user_id = settings.get("id")
    role = settings.get("role")

    if not user_id:
        bot.edit_message_text(
            "⚙️ Сначала настройте профиль (/start)",
            chat_id,
            message.message_id,
            reply_markup=get_role_keyboard(),
        )
        return

    # Извлекаем справочники
    lessons = {l["_id"]: l for l in data.get("lessons", {}).get("lesson", [])}
    subjects = {s["_id"]: s for s in data.get("subjects", {}).get("subject", [])}
    classrooms = {c["_id"]: c for c in data.get("classrooms", {}).get("classroom", [])}
    teachers = {t["_id"]: t for t in data.get("teachers", {}).get("teacher", [])}
    periods = {p["_period"]: p for p in data.get("periods", {}).get("period", [])}

    # Фильтруем карточки на выбранный день
    day_cards = [
        c for c in data.get("cards", {}).get("card", []) if c["_days"][day_index] == "1"
    ]

    schedule = []
    for card in day_cards:
        lesson = lessons.get(card["_lessonid"])
        if not lesson:
            continue

        is_match = False
        # Проверка: входит ли ID пользователя в список ID урока (через запятую)
        if role == "student" and user_id in lesson.get("_classids", "").split(","):
            is_match = True
        elif role == "teacher" and user_id in lesson.get("_teacherids", "").split(","):
            is_match = True

        if is_match:
            subj = subjects.get(lesson["_subjectid"], {}).get("_name", "???")
            room_id = card.get("_classroomids", "")
            room = classrooms.get(room_id, {}).get("_name", "—")
            period = card.get("_period", "?")
            period_info = (
                periods.get(period, {}).get("_starttime", "?")
                + " – "
                + periods.get(period, {}).get("_endtime", "?")
            )
            # Формируем красивый текст пары
            info = f"<b>{period_info}.  {subj}</b>"

            extra_details = []
            if room != "—":
                extra_details.append(f"каб. {room}")

            if role == "student":
                t_ids = lesson.get("_teacherids", "").split(",")
                t_names = [
                    teachers.get(tid, {}).get("_short", "") for tid in t_ids if tid
                ]
                if t_names:
                    extra_details.append(", ".join(t_names))

            if extra_details:
                info += f"\n  └ <i>{'; '.join(extra_details)}</i>"

            schedule.append(
                {
                    "period": int(period) if period.isdigit() else 99,  # Для сортировки
                    "text": info,
                }
            )

    # Сортируем по номеру пары
    schedule.sort(key=lambda x: x["period"])

    day_name = DAYS[day_index]
    header = f"📅 <b>Расписание на {day_name}</b>\n"
    separator = "_" * 30 + "\n"

    if schedule:
        res_text = (
            header + "\n" + f"\n{separator}\n".join([item["text"] for item in schedule])
        )
    else:
        res_text = header + separator + "Занятий нет. Отдыхаем! 🎉"

    try:
        bot.edit_message_text(
            res_text,
            chat_id,
            message.message_id,
            reply_markup=get_schedule_keyboard(day_index),
            parse_mode="HTML",
        )
    except Exception as e:
        # Если сообщение не изменилось, телеграм выдаст ошибку, просто игнорируем её
        pass


# Обработчик сохранения выбранного ID
@bot.callback_query_handler(
    func=lambda call: call.data.startswith(("set_class_", "set_teach_"))
)
def handle_id_selection(call):
    # Извлекаем ID (класса или преподавателя)
    uid = call.data.split("_")[-1]

    save_user_setting(call.message.chat.id, "id", uid)

    bot.answer_callback_query(call.id, "Настройки сохранены!")
    bot.edit_message_text(
        "Всё готово! Профиль настроен.",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=get_main_menu(),
    )


@bot.callback_query_handler(func=lambda call: call.data == "get_free_rooms")
def handle_free_rooms_callback(call):
    show_free_rooms(call.message.chat.id, call.message.message_id)


# --- ЛОГИКА СВОБОДНЫХ КАБИНЕТОВ ---


def show_free_rooms(chat_id, message_id=None):
    data = get_api_data()
    cards = data.get("cards", {}).get("card", [])
    classrooms = data.get("classrooms", {}).get("classroom", [])

    # Текущий день (0-5, где 0 - Пн)
    current_day = datetime.now().weekday()
    if current_day > 5:
        current_day = 0

    # Собираем занятые кабинеты на текущий момент (для примера возьмем 1 пару)
    busy_rooms = {
        c["_classroomids"]
        for c in cards
        if c["_days"][current_day] == "1" and c["_period"] == "1"
    }

    free_list = []
    for room in classrooms:
        if room["_id"] not in busy_rooms:
            free_list.append(room["_name"])

    text = "🚪 **Свободные кабинеты (1 пара):**\n\n" + ", ".join(free_list[:30])

    if message_id:
        bot.edit_message_text(
            text,
            chat_id,
            message_id,
            reply_markup=get_main_menu(),
            parse_mode="Markdown",
        )
    else:
        bot.send_message(
            chat_id, text, reply_markup=get_main_menu(), parse_mode="Markdown"
        )


bot.polling()
