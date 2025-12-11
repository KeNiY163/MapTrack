"""
MapTrack Bot - Telegram бот для отслеживания контейнеров
Использует python-telegram-bot с JobQueue для расписания
"""
import json
import os
import threading
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Dict, List
from zoneinfo import ZoneInfo

# Попытка загрузить из .env файла (опционально)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv не установлен, используем только переменные окружения

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    JobQueue,
    filters
)

# Поддержка запуска как скрипта и как модуля
try:
    from .container_tracker import ContainerTrackerService
    from .metrics import (
        start_metrics_server, track_message, track_command,
        track_error, track_tracking_request, track_tracking_duration,
        update_active_users, track_scheduled_check
    )
except ImportError:
    # Если запускаем как скрипт (python src/bot.py)
    import sys
    from pathlib import Path
    # Добавляем родительскую директорию в путь
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from src.container_tracker import ContainerTrackerService
    from src.metrics import (
        start_metrics_server, track_message, track_command,
        track_error, track_tracking_request, track_tracking_duration,
        update_active_users, track_scheduled_check
    )

# Пути к файлам данных
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
HISTORY_FILE = DATA_DIR / 'history.json'
SCHEDULE_FILE = DATA_DIR / 'schedule.json'
CITIES_FILE = DATA_DIR / 'cities.json'

# Таймзона для расписания (по умолчанию МСК, можно переопределить переменной TIMEZONE)
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
TZINFO = ZoneInfo(TIMEZONE)

# Создаем директорию data если её нет
DATA_DIR.mkdir(exist_ok=True)

# Блокировки для безопасной работы с JSON файлами
history_lock = threading.Lock()
schedule_lock = threading.Lock()
cities_lock = threading.Lock()

# Инициализация сервиса отслеживания
tracker_service = ContainerTrackerService(enable_screenshots=True)

# Состояния пользователей
user_states: Dict[int, Dict] = {}

# Сохраненные карты для удаления при возврате в меню
user_map_messages: Dict[int, int] = {}  # chat_id -> message_id карты

# Загрузка и сохранение данных
def load_history() -> Dict[str, List[str]]:
    """Безопасная загрузка истории с блокировкой"""
    with history_lock:
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

def save_history(history: Dict[str, List[str]]):
    """Безопасное сохранение истории с блокировкой"""
    with history_lock:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

def load_schedule() -> Dict[str, Dict]:
    """Безопасная загрузка расписания с блокировкой"""
    with schedule_lock:
        try:
            with open(SCHEDULE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

def save_schedule(schedule: Dict[str, Dict]):
    """Безопасное сохранение расписания с блокировкой"""
    with schedule_lock:
        with open(SCHEDULE_FILE, 'w', encoding='utf-8') as f:
            json.dump(schedule, f, ensure_ascii=False, indent=2)

def load_cities() -> Dict[str, str]:
    """Безопасная загрузка городов с блокировкой"""
    with cities_lock:
        try:
            with open(CITIES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

def save_cities(cities: Dict[str, str]):
    """Безопасное сохранение городов с блокировкой"""
    with cities_lock:
        with open(CITIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(cities, f, ensure_ascii=False, indent=2)

# Клавиатуры
def create_reply_keyboard() -> ReplyKeyboardMarkup:
    """Создает постоянную клавиатуру внизу экрана"""
    keyboard = [
        [KeyboardButton('📦 Отследить'), KeyboardButton('📊 История')],
        [KeyboardButton('⏰ Расписание'), KeyboardButton('🏙️ Мой город')],
        [KeyboardButton('📝 Мое расписание'), KeyboardButton('❤️ Поддержать')]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def create_main_menu() -> InlineKeyboardMarkup:
    """Создает главное меню (только кнопка возврата)"""
    keyboard = [
        [InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_history_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру истории - всегда загружает свежие данные"""
    history = load_history()
    user_history = history.get(str(chat_id), [])
    keyboard = []
    
    if user_history:
        for track in user_history[-5:]:
            keyboard.append([InlineKeyboardButton(track, callback_data=f'search_{track}')])
    else:
        keyboard.append([InlineKeyboardButton('❌ История пуста', callback_data='none')])
    
    keyboard.append([InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')])
    return InlineKeyboardMarkup(keyboard)

def create_days_keyboard(selected_days: List[int]) -> InlineKeyboardMarkup:
    """Создает клавиатуру выбора дней недели"""
    days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    keyboard = []
    row = []
    
    for i, day in enumerate(days):
        mark = '✅ ' if i in selected_days else ''
        row.append(InlineKeyboardButton(f'{mark}{day}', callback_data=f'day_{i}'))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton('➡️ Далее (выбрать время)', callback_data='select_time')])
    keyboard.append([InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')])
    return InlineKeyboardMarkup(keyboard)

def create_time_keyboard(selected_times: List[str]) -> InlineKeyboardMarkup:
    """Создает клавиатуру выбора времени"""
    times = ['00:00', '06:00', '09:00', '12:00', '15:00', '18:00', '21:00']
    keyboard = []
    row = []
    
    for time_str in times:
        mark = '✅ ' if time_str in selected_times else ''
        row.append(InlineKeyboardButton(f'{mark}{time_str}', callback_data=f'time_{time_str}'))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton('✅ Сохранить расписание', callback_data='save_schedule')])
    keyboard.append([InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')])
    return InlineKeyboardMarkup(keyboard)

# Обработчики команд
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    track_command('start')
    track_message('text')
    
    chat_id = update.effective_chat.id
    cities = load_cities()
    current_city = cities.get(str(chat_id), 'Москва')
    
    welcome_msg = (
        "👋 Добро пожаловать в бот отслеживания контейнеров!\n\n"
        "🔹 Что умеет бот:\n\n"
        "📦 Отследить контейнер - отправьте трек-номер (например: TKRU4471976) для получения информации о местонахождении контейнера\n\n"
        "📊 История - просмотр последних 5 поисков\n\n"
        "⏰ Расписание - настройте автоматические уведомления о статусе контейнера в выбранные дни и время\n\n"
        "📝 Мое расписание - посмотрите текущие настройки уведомлений\n\n"
        f"🏙️ Мой город - установите город назначения для расчета расстояния (сейчас: {current_city})\n\n"
        "❤️ Поддержать проект - помогите развитию бота\n\n"
        "💡 Просто отправьте трек-номер контейнера, чтобы начать отслеживание!"
    )
    
    await update.message.reply_text(welcome_msg, reply_markup=create_reply_keyboard())

async def track_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /track"""
    track_command('track')
    await update.message.reply_text(
        "📦 Отслеживание контейнера\n\nОтправьте трек-номер контейнера (например: TKRU4471976)",
        reply_markup=create_reply_keyboard()
    )

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /history"""
    track_command('history')
    await update.message.reply_text(
        "📊 История поиска\n\nВыберите трек-номер:",
        reply_markup=create_history_keyboard(update.effective_chat.id)
    )

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /schedule"""
    track_command('schedule')
    chat_id = update.effective_chat.id
    user_states[chat_id] = {'days': [], 'times': [], 'msg_id': None}
    
    await update.message.reply_text(
        "⏰ Настройка расписания\n\nВыберите дни недели для уведомлений:",
        reply_markup=create_days_keyboard([])
    )

# Обработчик текстовых сообщений
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    track_message('text')
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    # Обрабатываем нажатия на кнопки постоянной клавиатуры
    if text == '📦 Отследить':
        await update.message.reply_text(
            "📦 Отслеживание контейнера\n\nОтправьте трек-номер контейнера (например: TKRU4471976)",
            reply_markup=create_reply_keyboard()
        )
        return
    elif text == '📊 История':
        await update.message.reply_text(
            "📊 История поиска\n\nВыберите трек-номер:",
            reply_markup=create_history_keyboard(chat_id)
        )
        return
    elif text == '⏰ Расписание':
        user_states[chat_id] = {'days': [], 'times': [], 'msg_id': None}
        await update.message.reply_text(
            "⏰ Настройка расписания\n\nВыберите дни недели для уведомлений:",
            reply_markup=create_days_keyboard([])
        )
        return
    elif text == '🏙️ Мой город':
        cities = load_cities()
        current_city = cities.get(str(chat_id), 'Москва')
        user_states[chat_id] = {'waiting_for': 'city'}
        await update.message.reply_text(
            f"🏙️ Город назначения\n\nТекущий город: {current_city}\n\n"
            f"Отправьте название города для расчета расстояния (например: Москва, Санкт-Петербург, Новосибирск)",
            reply_markup=create_reply_keyboard()
        )
        return
    elif text == '📝 Мое расписание':
        schedule = load_schedule()
        user_schedule = schedule.get(str(chat_id))
        if user_schedule:
            days_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
            selected_days = ', '.join([days_names[d] for d in sorted(user_schedule['days'])])
            selected_times = ', '.join(sorted(user_schedule['times']))
            msg = f"⏰ Ваше расписание\n\nДни: {selected_days}\nВремя: {selected_times} (МСК)"
        else:
            msg = "⏰ Расписание не настроено"
        await update.message.reply_text(msg, reply_markup=create_reply_keyboard())
        return
    elif text == '❤️ Поддержать' or text == '❤️ Поддержать проект':
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton('💖 Поддержать', url='https://www.donationalerts.com/r/container_bot')],
            [InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')]
        ])
        await update.message.reply_text(
            "❤️ Поддержать проект\n\nЕсли вам нравится этот бот, вы можете поддержать его развитие! 🚀\n\n"
            "Ваша поддержка поможет добавить новые функции и улучшить работу бота. Спасибо! 🙏",
            reply_markup=keyboard
        )
        return
    
    # Проверяем состояние пользователя
    state = user_states.get(chat_id, {})
    
    if state.get('waiting_for') == 'city':
        # Пользователь отправляет город
        cities = load_cities()
        cities[str(chat_id)] = text
        save_cities(cities)
        
        if 'msg_id' in state:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=state['msg_id'],
                text=f"✅ Город назначения установлен: {text}\n\nТеперь расстояние будет рассчитываться до этого города.",
                reply_markup=None
            )
        await update.message.reply_text(
            f"✅ Город назначения установлен: {text}\n\nТеперь расстояние будет рассчитываться до этого города.",
            reply_markup=create_reply_keyboard()
        )
        
        del user_states[chat_id]
        return
    
    # Проверяем, является ли сообщение трек-номером
    if len(text) == 11 and text.startswith('TKRU'):
        await handle_track_request(update, context, text)
        return
    
    # Неизвестное сообщение
    await update.message.reply_text(
        "Отправьте трек-номер контейнера (например: TKRU4471976)",
        reply_markup=create_reply_keyboard()
    )

async def handle_track_request(update: Update, context: ContextTypes.DEFAULT_TYPE, track_number: str):
    """Обработка запроса на отслеживание"""
    chat_id = update.effective_chat.id
    cities = load_cities()
    destination_city = cities.get(str(chat_id), 'Москва')
    
    # Отправляем сообщение о начале поиска
    status_msg = await update.message.reply_text(
        "⏳ Ищу информацию о контейнере...\n(Это может занять 30-60 секунд)"
    )
    
    # Запускаем отслеживание в фоне
    context.application.create_task(
        track_container_async(chat_id, track_number, destination_city, status_msg.message_id, context)
    )

async def track_container_async(
    chat_id: int,
    track_number: str,
    destination_city: str,
    status_msg_id: int,
    context: ContextTypes.DEFAULT_TYPE
):
    """Асинхронное отслеживание контейнера"""
    try:
        track_tracking_request()
        start_time = datetime.now()
        
        # Используем сервис отслеживания
        message, coords, distance = tracker_service.track(track_number, destination_city)
        
        # Отслеживаем метрики
        duration = (datetime.now() - start_time).total_seconds()
        track_tracking_duration(duration)
        
        # Создаем клавиатуру с кнопкой "Показать на карте" если есть координаты
        keyboard_buttons = []
        if coords:
            # Округляем координаты для callback_data (ограничение 64 байта)
            lat = round(coords[0], 4)
            lon = round(coords[1], 4)
            keyboard_buttons.append([InlineKeyboardButton('📍 Показать на карте', callback_data=f'show_map_{lat}_{lon}_{status_msg_id}')])
        
        # Всегда добавляем кнопку "В главное меню"
        keyboard_buttons.append([InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')])
        reply_markup = InlineKeyboardMarkup(keyboard_buttons)
        
        # Обновляем сообщение с результатом
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg_id,
            text=message,
            reply_markup=reply_markup
        )
        
        # Сохраняем в историю
        history = load_history()
        chat_id_str = str(chat_id)
        history.setdefault(chat_id_str, [])
        if track_number not in history[chat_id_str]:
            history[chat_id_str].append(track_number)
        save_history(history)
        
    except Exception as e:
        track_error('track_container')
        error_msg = f"❌ Ошибка: {str(e)}"
        error_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')]
        ])
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg_id,
                text=error_msg,
                reply_markup=error_keyboard
            )
        except:
            await context.bot.send_message(
                chat_id=chat_id,
                text=error_msg,
                reply_markup=error_keyboard
            )

# Обработчики callback'ов
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback запросов"""
    track_message('callback')
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat.id
    data = query.data
    
    if data == 'main_menu':
        if chat_id in user_states:
            del user_states[chat_id]
        
        # Удаляем сохраненную карту, если она есть
        if chat_id in user_map_messages:
            try:
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=user_map_messages[chat_id]
                )
                del user_map_messages[chat_id]
            except Exception:
                # Если не удалось удалить (например, карта уже удалена), просто удаляем из словаря
                if chat_id in user_map_messages:
                    del user_map_messages[chat_id]
        
        await query.edit_message_text(
            "👋 Главное меню\n\nИспользуйте кнопки внизу для навигации."
        )
    
    elif data.startswith('show_map_'):
        # Формат: show_map_{lat}_{lon}_{message_id}
        parts = data.split('_')
        if len(parts) >= 4:
            try:
                lat = float(parts[2])
                lon = float(parts[3])
                original_msg_id = int(parts[4]) if len(parts) > 4 else query.message.message_id
                
                # Сохраняем текст сообщения
                message_text = query.message.text
                
                # Удаляем старое сообщение с результатами
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=original_msg_id)
                except Exception:
                    pass  # Если не удалось удалить, продолжаем
                
                # Удаляем предыдущую карту, если она есть
                if chat_id in user_map_messages:
                    try:
                        await context.bot.delete_message(
                            chat_id=chat_id,
                            message_id=user_map_messages[chat_id]
                        )
                    except Exception:
                        pass  # Если не удалось удалить, продолжаем
                    del user_map_messages[chat_id]
                
                # Отправляем карту (будет сверху) и сохраняем её message_id
                location_message = await context.bot.send_location(chat_id=chat_id, latitude=lat, longitude=lon)
                user_map_messages[chat_id] = location_message.message_id
                
                # Отправляем сообщение с результатами (будет снизу)
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')]
                ])
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                    reply_markup=keyboard
                )
                
                await query.answer("📍 Карта отправлена")
            except (ValueError, IndexError) as e:
                await query.answer("❌ Ошибка при обработке координат", show_alert=True)
    
    elif data.startswith('show_map_'):
        # Формат: show_map_{lat}_{lon}_{message_id}
        parts = data.split('_')
        if len(parts) >= 5:
            try:
                lat = float(parts[2])
                lon = float(parts[3])
                
                # Отправляем карту
                await context.bot.send_location(chat_id=chat_id, latitude=lat, longitude=lon)
                
                # Отправляем сообщение с результатами, чтобы оно было снизу
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=query.message.text
                )
                
                await query.answer("📍 Карта отправлена")
            except (ValueError, IndexError) as e:
                await query.answer("❌ Ошибка при обработке координат", show_alert=True)
    
    elif data.startswith('search_'):
        track_number = data.replace('search_', '')
        await handle_search_from_history(query, context, track_number, chat_id)
    
    elif data == 'schedule_setup':
        user_states[chat_id] = {'days': [], 'times': [], 'msg_id': query.message.message_id}
        await query.edit_message_text(
            "⏰ Настройка расписания\n\nВыберите дни недели для уведомлений:",
            reply_markup=create_days_keyboard([])
        )
    
    elif data.startswith('day_'):
        day = int(data.split('_')[1])
        state = user_states.get(chat_id, {'days': [], 'times': [], 'msg_id': query.message.message_id})
        if day in state['days']:
            state['days'].remove(day)
        else:
            state['days'].append(day)
        user_states[chat_id] = state
        await query.edit_message_text(
            "Выберите дни недели для уведомлений:",
            reply_markup=create_days_keyboard(state['days'])
        )
    
    elif data == 'select_time':
        state = user_states.get(chat_id, {'days': [], 'times': [], 'msg_id': query.message.message_id})
        if not state['days']:
            await query.edit_message_text(
                "❌ Выберите хотя бы один день!\n\nВыберите дни недели:",
                reply_markup=create_days_keyboard(state['days'])
            )
        else:
            await query.edit_message_text(
                "⏰ Выберите время для уведомлений\n\n🕐 Время указано по Москве (МСК)",
                reply_markup=create_time_keyboard([])
            )
    
    elif data.startswith('time_'):
        time_str = data.split('_')[1]
        state = user_states.get(chat_id, {'days': [], 'times': [], 'msg_id': query.message.message_id})
        if time_str in state['times']:
            state['times'].remove(time_str)
        else:
            state['times'].append(time_str)
        user_states[chat_id] = state
        await query.edit_message_text(
            "⏰ Выберите время для уведомлений\n\n🕐 Время указано по Москве (МСК)",
            reply_markup=create_time_keyboard(state['times'])
        )
    
    elif data == 'save_schedule':
        state = user_states.get(chat_id, {'days': [], 'times': [], 'msg_id': query.message.message_id})
        if not state['times']:
            await query.edit_message_text(
                "❌ Выберите хотя бы одно время!\n\nВыберите время:",
                reply_markup=create_time_keyboard(state['times'])
            )
        else:
            schedule = load_schedule()
            schedule[str(chat_id)] = {'days': state['days'], 'times': state['times']}
            save_schedule(schedule)
            
            # Регистрируем задачи в JobQueue (если доступен)
            if context.application.job_queue is not None:
                await register_schedule_jobs(context.application.job_queue, chat_id, state['days'], state['times'])
            else:
                await query.edit_message_text(
                    "⚠️ JobQueue не установлен. Расписание сохранено, но не будет работать.\n"
                    "Установите: pip install 'python-telegram-bot[job-queue]'",
                    reply_markup=create_main_menu()
                )
                del user_states[chat_id]
                return
            
            days_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
            selected_days = ', '.join([days_names[d] for d in sorted(state['days'])])
            selected_times = ', '.join(sorted(state['times']))
            await query.edit_message_text(
                f"✅ Расписание сохранено!\n\nДни: {selected_days}\nВремя: {selected_times}",
                reply_markup=create_main_menu()
            )
            del user_states[chat_id]

async def handle_search_from_history(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    track_number: str,
    chat_id: int
):
    """Обработка поиска из истории"""
    cities = load_cities()
    destination_city = cities.get(str(chat_id), 'Москва')
    
    await query.edit_message_text(
        "⏳ Ищу информацию о контейнере...\n(Это может занять 30-60 секунд)"
    )
    
    # Запускаем отслеживание
    context.application.create_task(
        track_container_async(chat_id, track_number, destination_city, query.message.message_id, context)
    )

# Расписание через JobQueue
async def register_schedule_jobs(job_queue: JobQueue, chat_id: int, days: List[int], times: List[str]):
    """Регистрирует задачи расписания в JobQueue"""
    # Удаляем старые задачи для этого пользователя
    jobs_to_remove = [job for job in job_queue.jobs() if job.name and job.name.startswith(f"schedule_{chat_id}_")]
    for job in jobs_to_remove:
        job.schedule_removal()
    
    # Создаем новые задачи
    for day in days:
        for time_str in times:
            hour, minute = map(int, time_str.split(':'))
            job_queue.run_daily(
                scheduled_check_callback,
                time=dt_time(hour, minute, tzinfo=TZINFO),
                days=(day,),
                name=f"schedule_{chat_id}_{day}_{time_str}",
                data={'chat_id': chat_id}
            )

async def scheduled_check_callback(context: ContextTypes.DEFAULT_TYPE):
    """Callback для запланированной проверки"""
    chat_id = context.job.data.get('chat_id') if context.job.data else None
    if not chat_id:
        return
    
    try:
        track_scheduled_check('attempt')
        history = load_history()
        cities = load_cities()
        
        tracks = history.get(str(chat_id), [])
        if not tracks:
            return
        
        last_track = tracks[-1]
        destination = cities.get(str(chat_id), 'Москва')
        
        # Отслеживаем контейнер
        message, coords, distance = tracker_service.track(last_track, destination)
        
        # Создаем клавиатуру с кнопкой "Показать на карте" если есть координаты
        keyboard_buttons = []
        if coords:
            lat = round(coords[0], 4)
            lon = round(coords[1], 4)
            keyboard_buttons.append([InlineKeyboardButton('📍 Показать на карте', callback_data=f'show_map_{lat}_{lon}_0')])
        
        # Всегда добавляем кнопку "В главное меню"
        keyboard_buttons.append([InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')])
        reply_markup = InlineKeyboardMarkup(keyboard_buttons)
        
        # Отправляем уведомление
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🔔 Запланированное обновление\n\n{message}",
            reply_markup=reply_markup
        )
        
        track_scheduled_check('success')
    except Exception:
        track_scheduled_check('error')


#
# Тестовый одноразовый джоб удален по завершении проверки

async def load_existing_schedules(application: Application):
    """Загружает существующие расписания при запуске"""
    schedule = load_schedule()
    for chat_id_str, config in schedule.items():
        chat_id = int(chat_id_str)
        days = config.get('days', [])
        times = config.get('times', [])
        await register_schedule_jobs(application.job_queue, chat_id, days, times)

# Обработка ошибок
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    track_error('update_processing')
    print(f"❌ Ошибка обработки update: {context.error}")
    import traceback
    traceback.print_exc()

# Главная функция
def main():
    """Главная функция запуска бота"""
    # Проверяем токен
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        raise ValueError("❌ BOT_TOKEN не установлен! Установите переменную окружения BOT_TOKEN")
    
    # Запускаем метрики
    start_metrics_server(8000)
    
    # Создаем приложение
    application = Application.builder().token(bot_token).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("track", track_command_handler))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("schedule", schedule_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_error_handler(error_handler)
    
    # Загружаем существующие расписания (если JobQueue доступен)
    if application.job_queue is not None:
        async def post_init(app: Application):
            await load_existing_schedules(app)
        
        application.post_init = post_init
    else:
        print("⚠️ JobQueue не установлен. Расписание не будет работать.")
        print("   Установите: pip install 'python-telegram-bot[job-queue]'")
    
    # Обновляем метрики активных пользователей
    try:
        history = load_history()
        active_count = len(set(str(uid) for uid in history.keys()))
        update_active_users(active_count)
    except:
        pass
    
    print("🤖 Бот запущен...")
    print("📊 Метрики доступны на порту 8000")
    
    # Загружаем существующие расписания после инициализации (если JobQueue доступен)
    if application.job_queue is not None:
        async def post_init(app: Application):
            await load_existing_schedules(app)
        
        application.post_init = post_init
    else:
        print("⚠️ JobQueue не установлен. Расписание не будет работать.")
        print("   Установите: pip install 'python-telegram-bot[job-queue]'")
    
    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

