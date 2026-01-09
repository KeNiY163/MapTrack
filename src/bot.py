"""
MapTrack Bot - Telegram бот для отслеживания контейнеров
Использует python-telegram-bot с JobQueue для расписания
"""
import asyncio
import json
import os
import sys
import threading
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Dict, List
from zoneinfo import ZoneInfo

# Настройка кодировки для Windows
if sys.platform == 'win32':
    try:
        # Пытаемся установить UTF-8 для stdout
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass  # Если не получилось, продолжаем с дефолтной кодировкой

def safe_print(text: str):
    """Безопасный вывод текста с поддержкой эмодзи в Windows"""
    if not text:
        return
    try:
        # Пытаемся вывести как есть
        print(text)
        sys.stdout.flush()
    except (UnicodeEncodeError, UnicodeDecodeError) as e:
        # Если не удалось вывести, пробуем безопасную кодировку
        try:
            # Сначала пробуем UTF-8 с заменой проблемных символов
            if isinstance(text, str):
                safe_text = text.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
            else:
                safe_text = str(text).encode('utf-8', errors='replace').decode('utf-8', errors='replace')
            print(safe_text)
            sys.stdout.flush()
        except Exception:
            # Если и это не помогло, выводим ASCII версию
            try:
                if isinstance(text, str):
                    safe_text = text.encode('ascii', 'ignore').decode('ascii')
                else:
                    safe_text = str(text).encode('ascii', 'ignore').decode('ascii')
                if safe_text.strip():
                    print(safe_text)
                    sys.stdout.flush()
                else:
                    print(f"[Error printing: {type(e).__name__}]")
                    sys.stdout.flush()
            except Exception:
                # Последняя попытка - просто сообщение об ошибке
                print(f"[Error printing: {type(e).__name__}]")
                sys.stdout.flush()

# Попытка загрузить из .env файла (опционально)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv не установлен, используем только переменные окружения

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.error import NetworkError, TelegramError
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
CONTRACT_HISTORY_FILE = DATA_DIR / 'contract_history.json'
SCHEDULE_FILE = DATA_DIR / 'schedule.json'
CITIES_FILE = DATA_DIR / 'cities.json'
CONTRACTS_FILE = DATA_DIR / 'contracts.json'

# Таймзона для расписания (по умолчанию МСК, можно переопределить переменной TIMEZONE)
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
TZINFO = ZoneInfo(TIMEZONE)

# Создаем директорию data если её нет
DATA_DIR.mkdir(exist_ok=True)

# Блокировки для безопасной работы с JSON файлами
history_lock = threading.Lock()
contract_history_lock = threading.Lock()
schedule_lock = threading.Lock()
cities_lock = threading.Lock()
contracts_lock = threading.Lock()

# Инициализация сервиса отслеживания
tracker_service = ContainerTrackerService(enable_screenshots=True)

# Состояния пользователей
user_states: Dict[int, Dict] = {}

# Сохраненные карты для удаления при возврате в меню
user_map_messages: Dict[int, int] = {}  # chat_id -> message_id карты


# Вспомогательная функция для безопасной отправки сообщений с retry
async def safe_reply_text(update: Update, text: str, reply_markup=None, max_retries=3):
    """Безопасная отправка сообщения с повторными попытками при сетевых ошибках"""
    for attempt in range(max_retries):
        try:
            return await update.message.reply_text(text, reply_markup=reply_markup)
        except NetworkError as e:
            if attempt < max_retries - 1:
                safe_print(f"⚠️ Network error (attempt {attempt + 1}/{max_retries}): {e}. Retrying...")
                await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
            else:
                safe_print(f"❌ Failed to send message after {max_retries} attempts: {e}")
                # Пытаемся отправить без клавиатуры
                try:
                    return await update.message.reply_text(text)
                except:
                    raise
        except TelegramError as e:
            safe_print(f"❌ Telegram error: {e}")
            # Пытаемся отправить без клавиатуры
            try:
                return await update.message.reply_text(text)
            except:
                raise
        except Exception as e:
            safe_print(f"❌ Unexpected error in safe_reply_text: {e}")
            import traceback
            traceback.print_exc()
            raise

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

def load_contracts() -> Dict[str, Dict]:
    """Безопасная загрузка договоров с блокировкой"""
    with contracts_lock:
        try:
            with open(CONTRACTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

def save_contracts(contracts: Dict[str, Dict]):
    """Безопасное сохранение договоров с блокировкой"""
    with contracts_lock:
        with open(CONTRACTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(contracts, f, ensure_ascii=False, indent=2)

def load_contract_history() -> Dict[str, List[str]]:
    """Безопасная загрузка истории договоров с блокировкой"""
    with contract_history_lock:
        try:
            with open(CONTRACT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

def save_contract_history(history: Dict[str, List[str]]):
    """Безопасное сохранение истории договоров с блокировкой"""
    with contract_history_lock:
        with open(CONTRACT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

# Клавиатуры
def create_reply_keyboard() -> ReplyKeyboardMarkup:
    """Создает постоянную клавиатуру внизу экрана"""
    keyboard = [
        [KeyboardButton('📦 Отследить'), KeyboardButton('📊 История')],
        [KeyboardButton('⏰ Расписание'), KeyboardButton('🏙️ Мой город')],
        [KeyboardButton('🔍 Поиск по договору'), KeyboardButton('📝 Мое расписание')],
        [KeyboardButton('❤️ Поддержать')]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def create_main_menu() -> InlineKeyboardMarkup:
    """Создает главное меню (только кнопка возврата)"""
    keyboard = [
        [InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_history_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру истории - всегда загружает свежие данные (контейнеры и договоры)"""
    container_history = load_history()
    contract_history = load_contract_history()
    
    user_container_history = container_history.get(str(chat_id), [])
    user_contract_history = contract_history.get(str(chat_id), [])
    
    keyboard = []
    
    # Показываем контейнеры
    if user_container_history:
        for track in user_container_history[-5:]:
            keyboard.append([InlineKeyboardButton(f'📦 {track}', callback_data=f'search_{track}')])
    
    # Показываем договоры
    if user_contract_history:
        for contract in user_contract_history[-5:]:
            keyboard.append([InlineKeyboardButton(f'📋 {contract}', callback_data=f'search_contract_{contract}')])
    
    # Если обе истории пусты
    if not user_container_history and not user_contract_history:
        keyboard.append([InlineKeyboardButton('❌ История пуста', callback_data='none')])
    
    keyboard.append([InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')])
    return InlineKeyboardMarkup(keyboard)

def create_container_history_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру истории контейнеров - всегда загружает свежие данные"""
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

def create_contract_history_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру истории договоров - всегда загружает свежие данные"""
    history = load_contract_history()
    user_history = history.get(str(chat_id), [])
    keyboard = []
    
    if user_history:
        for contract in user_history[-5:]:
            keyboard.append([InlineKeyboardButton(contract, callback_data=f'search_contract_{contract}')])
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
    user_name = update.effective_user.username or f"ID:{chat_id}"
    safe_print(f"👋 [КОМАНДА] Пользователь {user_name} (chat_id: {chat_id}) выполнил команду /start")
    
    cities = load_cities()
    current_city = cities.get(str(chat_id), 'Москва')
    
    welcome_msg = (
        "👋 Добро пожаловать в бот отслеживания контейнеров!\n\n"
        "🔹 Что умеет бот:\n\n"
        "📦 Отследить контейнер - отправьте трек-номер (например: TKRU4471976) для получения информации о местонахождении контейнера\n\n"
        "🔍 Поиск по договору - найдите информацию об автомобиле по номеру договора\n\n"
        "📊 История - просмотр последних 5 поисков\n\n"
        "⏰ Расписание - настройте автоматические уведомления о статусе контейнера в выбранные дни и время\n\n"
        "📝 Мое расписание - посмотрите текущие настройки уведомлений\n\n"
        f"🏙️ Мой город - установите город назначения для расчета расстояния (сейчас: {current_city})\n\n"
        "❤️ Поддержать проект - помогите развитию бота\n\n"
        "💡 Просто отправьте трек-номер контейнера или используйте кнопки меню!"
    )
    
    try:
        await safe_reply_text(update, welcome_msg, reply_markup=create_reply_keyboard())
    except Exception as e:
        safe_print(f"❌ Ошибка отправки приветственного сообщения: {e}")
        import traceback
        traceback.print_exc()
        # Пытаемся отправить простое сообщение без клавиатуры
        try:
            await update.message.reply_text("👋 Добро пожаловать! Используйте кнопки меню для навигации.")
        except:
            pass

async def track_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /track"""
    track_command('track')
    chat_id = update.effective_chat.id
    user_name = update.effective_user.username or f"ID:{chat_id}"
    safe_print(f"📦 [КОМАНДА] Пользователь {user_name} (chat_id: {chat_id}) выполнил команду /track")
    
    try:
        await safe_reply_text(
            update,
            "📦 Отслеживание контейнера\n\nОтправьте трек-номер контейнера (например: TKRU4471976)",
            reply_markup=create_reply_keyboard()
        )
    except (NetworkError, TelegramError) as e:
        safe_print(f"❌ [ОШИБКА] Ошибка отправки сообщения пользователю {user_name}: {e}")

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /history"""
    track_command('history')
    chat_id = update.effective_chat.id
    user_name = update.effective_user.username or f"ID:{chat_id}"
    safe_print(f"📊 [КОМАНДА] Пользователь {user_name} (chat_id: {chat_id}) выполнил команду /history")
    
    await update.message.reply_text(
        "📊 История поиска\n\nВыберите контейнер или договор:",
        reply_markup=create_history_keyboard(chat_id)
    )

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /schedule"""
    track_command('schedule')
    chat_id = update.effective_chat.id
    user_name = update.effective_user.username or f"ID:{chat_id}"
    safe_print(f"⏰ [КОМАНДА] Пользователь {user_name} (chat_id: {chat_id}) выполнил команду /schedule")
    
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
    user_name = update.effective_user.username or f"ID:{chat_id}"
    text = update.message.text.strip()
    
    safe_print(f"💬 [СООБЩЕНИЕ] Пользователь {user_name} (chat_id: {chat_id}) отправил сообщение: {text[:50]}...")
    
    # Обрабатываем нажатия на кнопки постоянной клавиатуры
    if text == '📦 Отследить':
        safe_print(f"📦 [КНОПКА] Пользователь {user_name} нажал кнопку 'Отследить'")
        # Показываем историю контейнеров
        history = load_history()
        user_history = history.get(str(chat_id), [])
        
        if user_history:
            await update.message.reply_text(
                "📦 Отслеживание контейнера\n\nВыберите контейнер из истории или отправьте новый трек-номер:",
                reply_markup=create_container_history_keyboard(chat_id)
            )
        else:
            await update.message.reply_text(
                "📦 Отслеживание контейнера\n\nОтправьте трек-номер контейнера (например: TKRU4471976)",
                reply_markup=create_reply_keyboard()
            )
        return
    elif text == '📊 История':
        safe_print(f"📊 [КНОПКА] Пользователь {user_name} нажал кнопку 'История'")
        await update.message.reply_text(
            "📊 История поиска\n\nВыберите контейнер или договор:",
            reply_markup=create_history_keyboard(chat_id)
        )
        return
    elif text == '⏰ Расписание':
        safe_print(f"⏰ [КНОПКА] Пользователь {user_name} нажал кнопку 'Расписание'")
        user_states[chat_id] = {'days': [], 'times': [], 'msg_id': None}
        await update.message.reply_text(
            "⏰ Настройка расписания\n\nВыберите дни недели для уведомлений:",
            reply_markup=create_days_keyboard([])
        )
        return
    elif text == '🏙️ Мой город':
        safe_print(f"🏙️ [КНОПКА] Пользователь {user_name} нажал кнопку 'Мой город'")
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
        safe_print(f"📝 [КНОПКА] Пользователь {user_name} нажал кнопку 'Мое расписание'")
        schedule = load_schedule()
        user_schedule = schedule.get(str(chat_id))
        if user_schedule:
            days_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
            selected_days = ', '.join([days_names[d] for d in sorted(user_schedule['days'])])
            selected_times = ', '.join(sorted(user_schedule['times']))
            
            # Формируем сообщение с информацией о расписании
            msg_parts = [f"⏰ Ваше расписание\n\nДни: {selected_days}\nВремя: {selected_times} (МСК)\n"]
            
            # Проверяем контейнеры в расписании
            containers = user_schedule.get('containers', [])
            if containers:
                msg_parts.append(f"\n📦 Отслеживание контейнеров:")
                for container in containers:
                    msg_parts.append(f"   • {container}")
            
            # Проверяем договоры в расписании
            contracts = user_schedule.get('contracts', [])
            if contracts:
                msg_parts.append(f"\n📋 Отслеживание договоров:")
                for contract in contracts:
                    msg_parts.append(f"   • {contract}")
            
            msg = "\n".join(msg_parts)
            
            # Создаем клавиатуру с кнопками удаления
            keyboard_buttons = []
            # Кнопки удаления контейнеров
            if containers:
                for container in containers:
                    keyboard_buttons.append([
                        InlineKeyboardButton(f'❌ Удалить контейнер {container}', callback_data=f'remove_container_{container}')
                    ])
            # Кнопки удаления договоров
            if contracts:
                for contract in contracts:
                    keyboard_buttons.append([
                        InlineKeyboardButton(f'❌ Удалить договор {contract}', callback_data=f'remove_contract_{contract}')
                    ])
            keyboard_buttons.append([InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')])
            reply_markup = InlineKeyboardMarkup(keyboard_buttons)
            
            await update.message.reply_text(msg, reply_markup=reply_markup)
        else:
            msg = "⏰ Расписание не настроено"
            await update.message.reply_text(msg, reply_markup=create_reply_keyboard())
        return
    elif text == '🔍 Поиск по договору':
        safe_print(f"🔍 [КНОПКА] Пользователь {user_name} нажал кнопку 'Поиск по договору'")
        # Показываем историю договоров
        contract_history = load_contract_history()
        user_contract_history = contract_history.get(str(chat_id), [])
        
        if user_contract_history:
            await update.message.reply_text(
                "🔍 Поиск по договору\n\nВыберите договор из истории или отправьте новый номер:",
                reply_markup=create_contract_history_keyboard(chat_id)
            )
        else:
            user_states[chat_id] = {'waiting_for': 'contract'}
            await update.message.reply_text(
                "🔍 Поиск по договору\n\nОтправьте номер договора (например: 122707МС7177)",
                reply_markup=create_reply_keyboard()
            )
        return
    elif text == '❤️ Поддержать' or text == '❤️ Поддержать проект':
        safe_print(f"❤️ [КНОПКА] Пользователь {user_name} нажал кнопку 'Поддержать'")
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
    
    if state.get('waiting_for') == 'contract':
        # Пользователь отправляет номер договора
        contract_number = text.strip()
        await handle_contract_search(update, context, contract_number)
        del user_states[chat_id]
        return
    
    # Проверяем, является ли сообщение трек-номером
    if len(text) == 11 and text.startswith('TKRU'):
        safe_print(f"📦 [РАСПОЗНАНО] Сообщение распознано как трек-номер контейнера: {text}")
        await handle_track_request(update, context, text)
        return
    
    # Неизвестное сообщение
    await update.message.reply_text(
        "Отправьте трек-номер контейнера (например: TKRU4471976)",
        reply_markup=create_reply_keyboard()
    )

async def handle_contract_search(update: Update, context: ContextTypes.DEFAULT_TYPE, contract_number: str):
    """Обработка поиска по договору"""
    chat_id = update.effective_chat.id
    user_name = update.effective_user.username or f"ID:{chat_id}"
    
    safe_print(f"🔍 [ЗАПРОС] Пользователь {user_name} (chat_id: {chat_id}) запросил поиск по договору: {contract_number}")
    
    # Отправляем сообщение о начале поиска СРАЗУ
    try:
        status_msg = await update.message.reply_text(
            "⏳ Ищу информацию по договору...\n(Это может занять несколько секунд)"
        )
        safe_print(f"✅ [ОТПРАВКА] Сообщение о начале поиска по договору отправлено пользователю {user_name} (message_id: {status_msg.message_id})")
    except Exception as e:
        safe_print(f"❌ [ОШИБКА] Не удалось отправить сообщение пользователю {user_name}: {e}")
        return
    
    # Запускаем поиск в фоне
    context.application.create_task(
        search_contract_async(chat_id, contract_number, status_msg.message_id, context, user_name)
    )
    safe_print(f"🚀 [ЗАПУСК] Асинхронная задача поиска по договору запущена для пользователя {user_name}, договор: {contract_number}")

async def search_contract_async(
    chat_id: int,
    contract_number: str,
    status_msg_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    user_name: str = None
):
    """Асинхронный поиск по договору"""
    if user_name is None:
        user_name = f"ID:{chat_id}"
    
    try:
        safe_print(f"🔄 [ПОИСК ДОГОВОРА] Начало поиска договора {contract_number} для пользователя {user_name}")
        
        # Выполняем запрос к API
        result = await fetch_contract_data(contract_number)
        safe_print(f"✅ [ПОИСК ДОГОВОРА] Данные по договору {contract_number} получены для пользователя {user_name}")
        
        if result:
            safe_print(f"📋 [ОБРАБОТКА] Обработка данных договора {contract_number} для пользователя {user_name}")
            message, has_container = format_contract_data(result, contract_number, chat_id)
            
            # Сохраняем в историю договоров
            safe_print(f"💾 [СОХРАНЕНИЕ] Сохранение договора {contract_number} в историю для пользователя {user_name}")
            contract_history = load_contract_history()
            chat_id_str = str(chat_id)
            contract_history.setdefault(chat_id_str, [])
            if contract_number not in contract_history[chat_id_str]:
                contract_history[chat_id_str].append(contract_number)
                save_contract_history(contract_history)
                safe_print(f"✅ [СОХРАНЕНИЕ] Договор {contract_number} добавлен в историю для пользователя {user_name}")
            else:
                safe_print(f"ℹ️ [СОХРАНЕНИЕ] Договор {contract_number} уже был в истории пользователя {user_name}")
        else:
            safe_print(f"⚠️ [ПОИСК ДОГОВОРА] Договор {contract_number} не найден для пользователя {user_name}")
            message = f"❌ Не удалось найти информацию по договору {contract_number}\n\nПроверьте правильность номера договора."
            has_container = None
        
        # Создаем клавиатуру
        keyboard_buttons = []
        
        # Если контейнер не найден, проверяем, не добавлен ли уже договор в расписание
        if has_container is False:
            schedule = load_schedule()
            user_schedule = schedule.get(str(chat_id), {})
            contracts_in_schedule = user_schedule.get('contracts', [])
            
            if contract_number not in contracts_in_schedule:
                # Договор не в расписании - показываем кнопку добавления
                keyboard_buttons.append([
                    InlineKeyboardButton('⏰ Добавить в расписание', callback_data=f'add_contract_schedule_{contract_number}')
                ])
            else:
                # Договор уже в расписании - добавляем сообщение в текст
                message += "\n\n✅ Этот договор уже добавлен в расписание"
        
        # Если контейнер найден, предлагаем отследить его
        if has_container is True:
            contracts = load_contracts()
            contract_info = contracts.get(str(chat_id), {})
            container_number = contract_info.get('container_number', '')
            if container_number:
                keyboard_buttons.append([
                    InlineKeyboardButton('📦 Отследить контейнер', callback_data=f'track_container_{container_number}')
                ])
        
        keyboard_buttons.append([InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')])
        reply_markup = InlineKeyboardMarkup(keyboard_buttons)
        
        # Обновляем сообщение с результатом
        safe_print(f"📤 [ОТПРАВКА] Отправка результатов поиска по договору пользователю {user_name} (message_id: {status_msg_id})")
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg_id,
            text=message,
            reply_markup=reply_markup
        )
        safe_print(f"✅ [ОТПРАВКА] Результаты поиска по договору успешно отправлены пользователю {user_name}")
        
    except Exception as e:
        track_error('contract_search')
        safe_print(f"❌ [ОШИБКА] Ошибка при поиске по договору {contract_number} для пользователя {user_name}: {str(e)}")
        import traceback
        safe_print(f"📋 [ОШИБКА] Traceback:\n{traceback.format_exc()}")
        
        error_msg = f"❌ Ошибка при поиске по договору: {str(e)}"
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg_id,
                text=error_msg,
                reply_markup=create_main_menu()
            )
            safe_print(f"✅ [ОТПРАВКА] Сообщение об ошибке отправлено пользователю {user_name}")
        except Exception as send_error:
            safe_print(f"❌ [КРИТИЧЕСКАЯ ОШИБКА] Не удалось отправить сообщение об ошибке пользователю {user_name}: {send_error}")

async def fetch_contract_data(contract_number: str) -> dict:
    """Запрос данных по договору через Selenium с перехватом AJAX ответа"""
    import asyncio
    
    safe_print(f"🌐 [SELENIUM] Запрос данных по договору {contract_number} через Selenium")
    
    # Используем Selenium для получения данных
    def _get_contract_selenium():
        """Синхронный запрос через Selenium, выполняется в отдельном потоке"""
        try:
            # Используем существующий сервис отслеживания
            result = tracker_service.track_contract(contract_number)
            return result
        except Exception as e:
            safe_print(f"❌ [SELENIUM] Ошибка при получении данных по договору {contract_number}: {e}")
            import traceback
            safe_print(f"📋 [SELENIUM] Traceback:\n{traceback.format_exc()}")
            return None
    
    # Выполняем запрос в отдельном потоке, чтобы не блокировать event loop
    loop = asyncio.get_event_loop()
    safe_print(f"⚙️ [SELENIUM] Запуск Selenium запроса в executor для договора {contract_number}")
    result = await loop.run_in_executor(None, _get_contract_selenium)
    safe_print(f"✅ [SELENIUM] Запрос для договора {contract_number} завершен")
    return result

def format_contract_data(data: dict, contract_number: str, chat_id: int = None) -> tuple[str, bool]:
    """Форматирование данных договора для отправки пользователю
    
    Args:
        data: Данные от API
        contract_number: Номер договора
        chat_id: ID чата для сохранения контейнера (опционально)
    
    Returns:
        Отформатированное сообщение
    """
    if not data:
        return (f"❌ Данные по договору {contract_number} не найдены", False)
    
    # Маппинг полей на русские названия
    field_names = {
        'kod_proverki': 'Код проверки',
        'nomer_dogovora': '№ договора',
        'data_priema': 'Дата приема',
        'model_avtomobilya': 'Модель автомобиля',
        'nomer_kuzova': 'ВИН / Номер кузова',
        'punkt_dostavki': 'Пункт доставки',
        'data_pogruzki_v_kontejner': 'Дата погрузки в контейнер',
        'nazvanie_sudna': '№ Контейнера / Название судна',
        'data_otpravki': 'Дата отправки',
        'status_oplaty': 'Статус оплаты'
    }
    
    message_parts = [f"📋 Информация по договору: {contract_number}\n"]
    
    # Проверяем структуру ответа
    if not isinstance(data, dict):
        safe_print(f"⚠️ [ФОРМАТИРОВАНИЕ] Данные не являются словарем для договора {contract_number}, тип: {type(data)}")
        return (f"❌ Неверный формат данных по договору {contract_number}", False)
    
    # Проверяем, не вернулся ли HTML/текст вместо JSON
    if 'error' in data and data.get('error') == 'not_json':
        safe_print(f"⚠️ [ФОРМАТИРОВАНИЕ] API вернул не-JSON ответ для договора {contract_number}")
        html_content = data.get('raw', '') or data.get('html', '')
        content_lower = html_content.lower().strip() if html_content else ''
        
        safe_print(f"🔍 [ФОРМАТИРОВАНИЕ] Анализ содержимого ответа для договора {contract_number}: '{html_content}'")
        
        # Пытаемся найти сообщение об ошибке в HTML
        if 'security check failed' in content_lower:
            safe_print(f"🔒 [ФОРМАТИРОВАНИЕ] Обнаружена ошибка безопасности для договора {contract_number}")
            return (f"❌ Ошибка безопасности при запросе данных по договору {contract_number}\n\n"
                   f"⚠️ Проблема с проверкой безопасности на сервере.\n\n"
                   f"💡 Попробуйте:\n"
                   f"   • Проверить номер договора\n"
                   f"   • Попробовать позже", False)
        elif 'не найден' in content_lower or 'not found' in content_lower:
            safe_print(f"🔍 [ФОРМАТИРОВАНИЕ] Договор {contract_number} не найден")
            return (f"❌ Договор {contract_number} не найден в системе", False)
        elif 'ошибка' in content_lower or 'error' in content_lower:
            safe_print(f"❌ [ФОРМАТИРОВАНИЕ] Обнаружена общая ошибка для договора {contract_number}")
            return (f"❌ Ошибка при запросе данных по договору {contract_number}\n"
                   f"Ответ сервера: {html_content}\n\nПопробуйте позже", False)
        else:
            safe_print(f"⚠️ [ФОРМАТИРОВАНИЕ] Неизвестный формат ответа для договора {contract_number}: {html_content}")
            return (f"❌ Не удалось получить данные по договору {contract_number}\n"
                   f"Сервер вернул неожиданный формат ответа: {html_content}\n\n"
                   f"Попробуйте позже или проверьте номер договора.", False)
    
    # Извлекаем данные из поля 'data'
    # Структура: {'success': True, 'data': {'found': True, 'data': {...}}}
    inner_data = data.get('data')
    
    if inner_data and isinstance(inner_data, dict):
        # Проверяем наличие found
        if 'found' in inner_data:
            if not inner_data.get('found', False):
                return (f"❌ Договор {contract_number} не найден", False)
        
        # Извлекаем реальные данные из inner_data['data']
        contract_data = inner_data.get('data')
        
        if contract_data and isinstance(contract_data, dict):
            # Структурированные данные
            message_parts.append("📄 Данные по договору:\n")
            
            # Проверяем наличие контейнера
            container_number = contract_data.get('nazvanie_sudna', '')
            data_otpravki = contract_data.get('data_otpravki', '')
            
            # Проверяем, есть ли контейнер (не прочерк и не пусто)
            has_container = (
                container_number and 
                str(container_number).strip() not in ('—', '-', '', 'None', 'null', '\u2014') and
                data_otpravki and 
                str(data_otpravki).strip() not in ('—', '-', '', 'None', 'null', '\u2014')
            )
            
            # Выводим только существующие поля с непустыми значениями
            for key, value in contract_data.items():
                # Пропускаем пустые значения и прочерки
                if value and str(value).strip() not in ('—', '-', '', 'None', 'null', '\u2014'):
                    field_name = field_names.get(key, key)
                    message_parts.append(f"  • {field_name}: {value}")
            
            # Если контейнер найден, сохраняем его
            if has_container and chat_id:
                contracts = load_contracts()
                contracts[str(chat_id)] = {
                    'contract_number': contract_number,
                    'container_number': str(container_number).strip(),
                    'data_otpravki': str(data_otpravki).strip(),
                    'model_avtomobilya': contract_data.get('model_avtomobilya', ''),
                    'nomer_kuzova': contract_data.get('nomer_kuzova', ''),
                    'punkt_dostavki': contract_data.get('punkt_dostavki', '')
                }
                save_contracts(contracts)
            elif not has_container:
                # Если контейнера нет, добавляем сообщение
                message_parts.append("\n⚠️ Автомобиль еще не отправлен")
                message_parts.append("📦 № Контейнера пока не присвоен")
                message_parts.append("\n💡 Вы можете добавить этот договор в расписание для автоматической проверки")
            
            result = "\n".join(message_parts)
            
            # Ограничиваем длину сообщения
            if len(result) > 4000:
                result = result[:4000] + "\n\n... (сообщение обрезано)"
            
            return (result, has_container)
    
    # Если данные не обработаны выше, возвращаем сообщение об ошибке
    return (f"❌ Не удалось обработать данные по договору {contract_number}", False)

async def handle_track_request(update: Update, context: ContextTypes.DEFAULT_TYPE, track_number: str):
    """Обработка запроса на отслеживание"""
    chat_id = update.effective_chat.id
    user_name = update.effective_user.username or f"ID:{chat_id}"
    
    safe_print(f"🔍 [ЗАПРОС] Пользователь {user_name} (chat_id: {chat_id}) запросил отслеживание контейнера: {track_number}")
    
    cities = load_cities()
    destination_city = cities.get(str(chat_id), 'Москва')
    
    safe_print(f"📍 [ЗАПРОС] Город назначения для пользователя {user_name}: {destination_city}")
    
    # Отправляем сообщение о начале поиска СРАЗУ
    try:
        status_msg = await update.message.reply_text(
            "⏳ Ищу информацию о контейнере...\n(Это может занять 30-60 секунд)"
        )
        safe_print(f"✅ [ОТПРАВКА] Сообщение о начале поиска отправлено пользователю {user_name} (message_id: {status_msg.message_id})")
    except Exception as e:
        safe_print(f"❌ [ОШИБКА] Не удалось отправить сообщение пользователю {user_name}: {e}")
        return
    
    # Запускаем отслеживание в фоне (не блокируя event loop)
    context.application.create_task(
        track_container_async(chat_id, track_number, destination_city, status_msg.message_id, context, user_name)
    )
    safe_print(f"🚀 [ЗАПУСК] Асинхронная задача отслеживания запущена для пользователя {user_name}, контейнер: {track_number}")

async def track_container_async(
    chat_id: int,
    track_number: str,
    destination_city: str,
    status_msg_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    user_name: str = None
):
    """Асинхронное отслеживание контейнера"""
    if user_name is None:
        user_name = f"ID:{chat_id}"
    
    try:
        track_tracking_request()
        start_time = datetime.now()
        
        safe_print(f"🔄 [ОТСЛЕЖИВАНИЕ] Начало отслеживания контейнера {track_number} для пользователя {user_name}")
        
        # Выполняем синхронный вызов track() в отдельном потоке, чтобы не блокировать event loop
        # Это позволяет обрабатывать запросы от других пользователей параллельно
        loop = asyncio.get_event_loop()
        safe_print(f"⚙️ [ОТСЛЕЖИВАНИЕ] Запуск синхронного отслеживания в executor для пользователя {user_name}")
        
        message, coords, distance = await loop.run_in_executor(
            None,  # Используем дефолтный ThreadPoolExecutor
            lambda: tracker_service.track(track_number, destination_city)
        )
        
        safe_print(f"✅ [ОТСЛЕЖИВАНИЕ] Отслеживание контейнера {track_number} завершено для пользователя {user_name}")
        
        # Отслеживаем метрики
        duration = (datetime.now() - start_time).total_seconds()
        track_tracking_duration(duration)
        safe_print(f"⏱️ [МЕТРИКИ] Время отслеживания для пользователя {user_name}: {duration:.2f} секунд")
        
        # Создаем клавиатуру с кнопкой "Показать на карте" если есть координаты
        keyboard_buttons = []
        if coords:
            # Округляем координаты для callback_data (ограничение 64 байта)
            lat = round(coords[0], 4)
            lon = round(coords[1], 4)
            keyboard_buttons.append([InlineKeyboardButton('📍 Показать на карте', callback_data=f'show_map_{lat}_{lon}_{status_msg_id}')])
        
        # Проверяем, не добавлен ли уже контейнер в расписание
        schedule = load_schedule()
        user_schedule = schedule.get(str(chat_id), {})
        containers_in_schedule = user_schedule.get('containers', [])
        
        if track_number not in containers_in_schedule:
            keyboard_buttons.append([
                InlineKeyboardButton('⏰ Добавить в расписание', callback_data=f'add_container_schedule_{track_number}')
            ])
        else:
            # Контейнер уже в расписании - добавляем сообщение в текст
            message += "\n\n✅ Этот контейнер уже добавлен в расписание"
        
        # Всегда добавляем кнопку "В главное меню"
        keyboard_buttons.append([InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')])
        reply_markup = InlineKeyboardMarkup(keyboard_buttons)
        
        # Обновляем сообщение с результатом
        safe_print(f"📤 [ОТПРАВКА] Отправка результатов пользователю {user_name} (message_id: {status_msg_id})")
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg_id,
            text=message,
            reply_markup=reply_markup
        )
        safe_print(f"✅ [ОТПРАВКА] Результаты успешно отправлены пользователю {user_name}")
        
        # Сохраняем в историю
        safe_print(f"💾 [СОХРАНЕНИЕ] Сохранение контейнера {track_number} в историю для пользователя {user_name}")
        history = load_history()
        chat_id_str = str(chat_id)
        history.setdefault(chat_id_str, [])
        if track_number not in history[chat_id_str]:
            history[chat_id_str].append(track_number)
            save_history(history)
            safe_print(f"✅ [СОХРАНЕНИЕ] Контейнер {track_number} добавлен в историю для пользователя {user_name}")
        else:
            safe_print(f"ℹ️ [СОХРАНЕНИЕ] Контейнер {track_number} уже был в истории пользователя {user_name}")
        
    except Exception as e:
        track_error('track_container')
        safe_print(f"❌ [ОШИБКА] Ошибка при отслеживании контейнера {track_number} для пользователя {user_name}: {str(e)}")
        import traceback
        safe_print(f"📋 [ОШИБКА] Traceback:\n{traceback.format_exc()}")
        
        error_msg = f"❌ Ошибка: {str(e)}"
        error_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')]
        ])
        try:
            safe_print(f"📤 [ОТПРАВКА] Отправка сообщения об ошибке пользователю {user_name}")
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg_id,
                text=error_msg,
                reply_markup=error_keyboard
            )
            safe_print(f"✅ [ОТПРАВКА] Сообщение об ошибке отправлено пользователю {user_name}")
        except Exception as send_error:
            safe_print(f"⚠️ [ОШИБКА] Не удалось отредактировать сообщение, отправляю новое: {send_error}")
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=error_msg,
                    reply_markup=error_keyboard
                )
                safe_print(f"✅ [ОТПРАВКА] Новое сообщение об ошибке отправлено пользователю {user_name}")
            except Exception as final_error:
                safe_print(f"❌ [КРИТИЧЕСКАЯ ОШИБКА] Не удалось отправить сообщение об ошибке пользователю {user_name}: {final_error}")

# Обработчики callback'ов
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback запросов"""
    track_message('callback')
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat.id
    user_name = query.from_user.username or f"ID:{chat_id}"
    data = query.data
    
    safe_print(f"🔘 [CALLBACK] Пользователь {user_name} (chat_id: {chat_id}) нажал кнопку: {data}")
    
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
    
    elif data.startswith('add_contract_schedule_'):
        # Формат: add_contract_schedule_{contract_number}
        contract_number = data.replace('add_contract_schedule_', '')
        # Сохраняем договор для расписания
        schedule = load_schedule()
        if str(chat_id) not in schedule:
            schedule[str(chat_id)] = {'days': [], 'times': [], 'contracts': [], 'containers': []}
        if 'contracts' not in schedule[str(chat_id)]:
            schedule[str(chat_id)]['contracts'] = []
        if 'containers' not in schedule[str(chat_id)]:
            schedule[str(chat_id)]['containers'] = []
        
        # Проверяем, не добавлен ли уже договор
        if contract_number in schedule[str(chat_id)]['contracts']:
            await query.answer("⚠️ Этот договор уже в расписании", show_alert=True)
            return
        
        # Добавляем договор
        schedule[str(chat_id)]['contracts'].append(contract_number)
        save_schedule(schedule)
        
        # Перерегистрируем задачи расписания, чтобы включить новый договор
        if context.application.job_queue is not None:
            days = schedule[str(chat_id)].get('days', [])
            times = schedule[str(chat_id)].get('times', [])
            contracts = schedule[str(chat_id)].get('contracts', [])
            containers = schedule[str(chat_id)].get('containers', [])
            if days and times:
                await register_schedule_jobs(context.application.job_queue, chat_id, days, times, contracts, containers)
        
        await query.edit_message_text(
            f"✅ Договор {contract_number} добавлен в расписание\n\n"
            "Теперь бот будет автоматически проверять этот договор по вашему расписанию.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')]
            ])
        )
    
    elif data.startswith('remove_contract_'):
        # Формат: remove_contract_{contract_number}
        contract_number = data.replace('remove_contract_', '')
        schedule = load_schedule()
        if str(chat_id) in schedule:
            if 'contracts' in schedule[str(chat_id)]:
                if contract_number in schedule[str(chat_id)]['contracts']:
                    schedule[str(chat_id)]['contracts'].remove(contract_number)
                    save_schedule(schedule)
                    
                    # Перерегистрируем задачи расписания
                    if context.application.job_queue is not None:
                        days = schedule[str(chat_id)].get('days', [])
                        times = schedule[str(chat_id)].get('times', [])
                        contracts = schedule[str(chat_id)].get('contracts', [])
                        containers = schedule[str(chat_id)].get('containers', [])
                        if days and times:
                            await register_schedule_jobs(context.application.job_queue, chat_id, days, times, contracts, containers)
                    
                    await query.answer(f"✅ Договор {contract_number} удален из расписания")
                    
                    # Обновляем сообщение
                    days_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
                    selected_days = ', '.join([days_names[d] for d in sorted(schedule[str(chat_id)]['days'])])
                    selected_times = ', '.join(sorted(schedule[str(chat_id)]['times']))
                    
                    msg_parts = [f"⏰ Ваше расписание\n\nДни: {selected_days}\nВремя: {selected_times} (МСК)\n"]
                    
                    containers = schedule[str(chat_id)].get('containers', [])
                    if containers:
                        msg_parts.append(f"\n📦 Отслеживание контейнеров:")
                        for container in containers:
                            msg_parts.append(f"   • {container}")
                    
                    contracts = schedule[str(chat_id)].get('contracts', [])
                    if contracts:
                        msg_parts.append(f"\n📋 Отслеживание договоров:")
                        for contract in contracts:
                            msg_parts.append(f"   • {contract}")
                    
                    msg = "\n".join(msg_parts)
                    
                    keyboard_buttons = []
                    if containers:
                        for container in containers:
                            keyboard_buttons.append([
                                InlineKeyboardButton(f'❌ Удалить контейнер {container}', callback_data=f'remove_container_{container}')
                            ])
                    if contracts:
                        for contract in contracts:
                            keyboard_buttons.append([
                                InlineKeyboardButton(f'❌ Удалить договор {contract}', callback_data=f'remove_contract_{contract}')
                            ])
                    keyboard_buttons.append([InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')])
                    reply_markup = InlineKeyboardMarkup(keyboard_buttons)
                    
                    await query.edit_message_text(msg, reply_markup=reply_markup)
                else:
                    await query.answer("⚠️ Договор не найден в расписании", show_alert=True)
            else:
                await query.answer("⚠️ В расписании нет договоров", show_alert=True)
        else:
            await query.answer("⚠️ Расписание не найдено", show_alert=True)
    
    elif data.startswith('track_container_'):
        # Формат: track_container_{container_number}
        container_number = data.replace('track_container_', '')
        user_name = query.from_user.username or f"ID:{chat_id}"
        safe_print(f"🔍 [CALLBACK] Пользователь {user_name} (chat_id: {chat_id}) запросил отслеживание контейнера через callback: {container_number}")
        
        # Запускаем отслеживание контейнера
        cities = load_cities()
        destination_city = cities.get(str(chat_id), 'Москва')
        
        try:
            status_msg = await query.message.reply_text(
                "⏳ Ищу информацию о контейнере...\n(Это может занять 30-60 секунд)"
            )
            safe_print(f"✅ [ОТПРАВКА] Сообщение о начале поиска отправлено пользователю {user_name} (message_id: {status_msg.message_id})")
        except Exception as e:
            safe_print(f"❌ [ОШИБКА] Не удалось отправить сообщение пользователю {user_name}: {e}")
            await query.answer("❌ Ошибка отправки сообщения", show_alert=True)
            return
        
        # Запускаем отслеживание в фоне
        context.application.create_task(
            track_container_async(chat_id, container_number, destination_city, status_msg.message_id, context, user_name)
        )
        safe_print(f"🚀 [ЗАПУСК] Асинхронная задача отслеживания запущена для пользователя {user_name}, контейнер: {container_number}")
        
        await query.answer("📦 Запущено отслеживание контейнера")
    
    elif data.startswith('add_container_schedule_'):
        # Формат: add_container_schedule_{container_number}
        container_number = data.replace('add_container_schedule_', '')
        # Сохраняем контейнер для расписания
        schedule = load_schedule()
        if str(chat_id) not in schedule:
            schedule[str(chat_id)] = {'days': [], 'times': [], 'contracts': [], 'containers': []}
        if 'containers' not in schedule[str(chat_id)]:
            schedule[str(chat_id)]['containers'] = []
        
        # Проверяем, не добавлен ли уже контейнер
        if container_number in schedule[str(chat_id)]['containers']:
            await query.answer("⚠️ Этот контейнер уже в расписании", show_alert=True)
            return
        
        # Добавляем контейнер
        schedule[str(chat_id)]['containers'].append(container_number)
        save_schedule(schedule)
        
        # Перерегистрируем задачи расписания, чтобы включить новый контейнер
        if context.application.job_queue is not None:
            days = schedule[str(chat_id)].get('days', [])
            times = schedule[str(chat_id)].get('times', [])
            contracts = schedule[str(chat_id)].get('contracts', [])
            containers = schedule[str(chat_id)].get('containers', [])
            if days and times:
                await register_schedule_jobs(context.application.job_queue, chat_id, days, times, contracts, containers)
        
        await query.edit_message_text(
            f"✅ Контейнер {container_number} добавлен в расписание\n\n"
            "Теперь бот будет автоматически проверять этот контейнер по вашему расписанию.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')]
            ])
        )
    
    elif data.startswith('remove_container_'):
        # Формат: remove_container_{container_number}
        container_number = data.replace('remove_container_', '')
        schedule = load_schedule()
        if str(chat_id) in schedule:
            if 'containers' in schedule[str(chat_id)]:
                if container_number in schedule[str(chat_id)]['containers']:
                    schedule[str(chat_id)]['containers'].remove(container_number)
                    save_schedule(schedule)
                    
                    # Перерегистрируем задачи расписания
                    if context.application.job_queue is not None:
                        days = schedule[str(chat_id)].get('days', [])
                        times = schedule[str(chat_id)].get('times', [])
                        contracts = schedule[str(chat_id)].get('contracts', [])
                        containers = schedule[str(chat_id)].get('containers', [])
                        if days and times:
                            await register_schedule_jobs(context.application.job_queue, chat_id, days, times, contracts, containers)
                    
                    await query.answer(f"✅ Контейнер {container_number} удален из расписания")
                    
                    # Обновляем сообщение
                    days_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
                    selected_days = ', '.join([days_names[d] for d in sorted(schedule[str(chat_id)]['days'])])
                    selected_times = ', '.join(sorted(schedule[str(chat_id)]['times']))
                    
                    msg_parts = [f"⏰ Ваше расписание\n\nДни: {selected_days}\nВремя: {selected_times} (МСК)\n"]
                    
                    containers = schedule[str(chat_id)].get('containers', [])
                    if containers:
                        msg_parts.append(f"\n📦 Отслеживание контейнеров:")
                        for container in containers:
                            msg_parts.append(f"   • {container}")
                    
                    contracts = schedule[str(chat_id)].get('contracts', [])
                    if contracts:
                        msg_parts.append(f"\n📋 Отслеживание договоров:")
                        for contract in contracts:
                            msg_parts.append(f"   • {contract}")
                    
                    msg = "\n".join(msg_parts)
                    
                    keyboard_buttons = []
                    if containers:
                        for container in containers:
                            keyboard_buttons.append([
                                InlineKeyboardButton(f'❌ Удалить контейнер {container}', callback_data=f'remove_container_{container}')
                            ])
                    if contracts:
                        for contract in contracts:
                            keyboard_buttons.append([
                                InlineKeyboardButton(f'❌ Удалить договор {contract}', callback_data=f'remove_contract_{contract}')
                            ])
                    keyboard_buttons.append([InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')])
                    reply_markup = InlineKeyboardMarkup(keyboard_buttons)
                    
                    await query.edit_message_text(msg, reply_markup=reply_markup)
                else:
                    await query.answer("⚠️ Контейнер не найден в расписании", show_alert=True)
            else:
                await query.answer("⚠️ В расписании нет контейнеров", show_alert=True)
        else:
            await query.answer("⚠️ Расписание не найдено", show_alert=True)
    
    elif data.startswith('search_contract_'):
        # Поиск договора из истории
        contract_number = data.replace('search_contract_', '')
        await handle_contract_search_from_history(query, context, contract_number, chat_id)
    
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
            if str(chat_id) not in schedule:
                schedule[str(chat_id)] = {'days': [], 'times': [], 'contracts': []}
            schedule[str(chat_id)]['days'] = state['days']
            schedule[str(chat_id)]['times'] = state['times']
            if 'contracts' not in schedule[str(chat_id)]:
                schedule[str(chat_id)]['contracts'] = []
            save_schedule(schedule)
            
            # Регистрируем задачи в JobQueue (если доступен)
            if context.application.job_queue is not None:
                contracts = schedule[str(chat_id)].get('contracts', [])
                containers = schedule[str(chat_id)].get('containers', [])
                await register_schedule_jobs(context.application.job_queue, chat_id, state['days'], state['times'], contracts, containers)
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
    user_name = query.from_user.username or f"ID:{chat_id}"
    safe_print(f"🔍 [ИСТОРИЯ] Пользователь {user_name} (chat_id: {chat_id}) выбрал контейнер из истории: {track_number}")
    
    cities = load_cities()
    destination_city = cities.get(str(chat_id), 'Москва')
    
    try:
        await query.edit_message_text(
            "⏳ Ищу информацию о контейнере...\n(Это может занять 30-60 секунд)"
        )
        safe_print(f"✅ [ОТПРАВКА] Сообщение о начале поиска обновлено для пользователя {user_name}")
    except Exception as e:
        safe_print(f"❌ [ОШИБКА] Не удалось обновить сообщение для пользователя {user_name}: {e}")
        return
    
    # Запускаем отслеживание
    context.application.create_task(
        track_container_async(chat_id, track_number, destination_city, query.message.message_id, context, user_name)
    )
    safe_print(f"🚀 [ЗАПУСК] Асинхронная задача отслеживания из истории запущена для пользователя {user_name}, контейнер: {track_number}")

async def handle_contract_search_from_history(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    contract_number: str,
    chat_id: int
):
    """Обработка поиска договора из истории"""
    user_name = query.from_user.username or f"ID:{chat_id}"
    safe_print(f"🔍 [ИСТОРИЯ] Пользователь {user_name} (chat_id: {chat_id}) выбрал договор из истории: {contract_number}")
    
    try:
        await query.edit_message_text(
            "⏳ Ищу информацию по договору...\n(Это может занять несколько секунд)"
        )
        safe_print(f"✅ [ОТПРАВКА] Сообщение о начале поиска обновлено для пользователя {user_name}")
    except Exception as e:
        safe_print(f"❌ [ОШИБКА] Не удалось обновить сообщение для пользователя {user_name}: {e}")
        return
    
    # Запускаем поиск
    context.application.create_task(
        search_contract_async(chat_id, contract_number, query.message.message_id, context, user_name)
    )
    safe_print(f"🚀 [ЗАПУСК] Асинхронная задача поиска по договору из истории запущена для пользователя {user_name}, договор: {contract_number}")

# Расписание через JobQueue
async def register_schedule_jobs(job_queue: JobQueue, chat_id: int, days: List[int], times: List[str], contracts: List[str] = None, containers: List[str] = None):
    """Регистрирует задачи расписания в JobQueue"""
    # Удаляем старые задачи для этого пользователя
    jobs_to_remove = [job for job in job_queue.jobs() if job.name and (job.name.startswith(f"schedule_{chat_id}_") or job.name.startswith(f"schedule_container_{chat_id}_") or job.name.startswith(f"schedule_contract_{chat_id}_"))]
    for job in jobs_to_remove:
        job.schedule_removal()
    
    # Создаем задачи для контейнеров из расписания
    if containers:
        for container_number in containers:
            for day in days:
                for time_str in times:
                    hour, minute = map(int, time_str.split(':'))
                    job_queue.run_daily(
                        scheduled_check_callback,
                        time=dt_time(hour, minute, tzinfo=TZINFO),
                        days=(day,),
                        name=f"schedule_container_{chat_id}_{container_number}_{day}_{time_str}",
                        data={'chat_id': chat_id, 'type': 'container', 'container_number': container_number}
                    )
    
    # Создаем задачи для договоров
    if contracts:
        for contract_number in contracts:
            for day in days:
                for time_str in times:
                    hour, minute = map(int, time_str.split(':'))
                    job_queue.run_daily(
                        scheduled_check_callback,
                        time=dt_time(hour, minute, tzinfo=TZINFO),
                        days=(day,),
                        name=f"schedule_contract_{chat_id}_{contract_number}_{day}_{time_str}",
                        data={'chat_id': chat_id, 'type': 'contract', 'contract_number': contract_number}
                    )

async def scheduled_check_callback(context: ContextTypes.DEFAULT_TYPE):
    """Callback для запланированной проверки"""
    chat_id = context.job.data.get('chat_id') if context.job.data else None
    check_type = context.job.data.get('type', 'container') if context.job.data else 'container'  # 'container' или 'contract'
    contract_number = context.job.data.get('contract_number') if context.job.data else None
    
    if not chat_id:
        safe_print(f"⚠️ [РАСПИСАНИЕ] Нет chat_id в задаче расписания")
        return
    
    user_name = f"ID:{chat_id}"  # В расписании username недоступен
    
    try:
        track_scheduled_check('attempt')
        safe_print(f"⏰ [РАСПИСАНИЕ] Начало запланированной проверки для пользователя {user_name}, тип: {check_type}")
        
        if check_type == 'contract' and contract_number:
            # Проверка договора
            safe_print(f"📋 [РАСПИСАНИЕ] Проверка договора {contract_number} для пользователя {user_name}")
            result = await fetch_contract_data(contract_number)
            if result:
                message, has_container = format_contract_data(result, contract_number, chat_id)
                
                # Создаем клавиатуру
                keyboard_buttons = []
                if has_container:
                    contracts = load_contracts()
                    contract_info = contracts.get(str(chat_id), {})
                    container_number = contract_info.get('container_number', '')
                    if container_number:
                        keyboard_buttons.append([
                            InlineKeyboardButton('📦 Отследить контейнер', callback_data=f'track_container_{container_number}')
                        ])
                else:
                    # Проверяем, не добавлен ли уже договор в расписание
                    schedule = load_schedule()
                    user_schedule = schedule.get(str(chat_id), {})
                    contracts_in_schedule = user_schedule.get('contracts', [])
                    
                    if contract_number not in contracts_in_schedule:
                        keyboard_buttons.append([
                            InlineKeyboardButton('⏰ Добавить в расписание', callback_data=f'add_contract_schedule_{contract_number}')
                        ])
                    # Если договор уже в расписании, кнопку не показываем
                
                keyboard_buttons.append([InlineKeyboardButton('⬅️ Главное меню', callback_data='main_menu')])
                reply_markup = InlineKeyboardMarkup(keyboard_buttons)
                
                safe_print(f"📤 [РАСПИСАНИЕ] Отправка запланированного уведомления о договоре пользователю {user_name}")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🔔 Запланированная проверка договора\n\n{message}",
                    reply_markup=reply_markup
                )
                safe_print(f"✅ [РАСПИСАНИЕ] Уведомление о договоре отправлено пользователю {user_name}")
        elif check_type == 'container' and context.job.data.get('container_number'):
            # Проверка конкретного контейнера из расписания
            container_number = context.job.data.get('container_number')
            safe_print(f"📦 [РАСПИСАНИЕ] Проверка контейнера {container_number} для пользователя {user_name}")
            
            cities = load_cities()
            destination = cities.get(str(chat_id), 'Москва')
            
            # Отслеживаем контейнер (выполняем в executor, чтобы не блокировать event loop)
            safe_print(f"⚙️ [РАСПИСАНИЕ] Запуск отслеживания контейнера {container_number} в executor для пользователя {user_name}")
            loop = asyncio.get_event_loop()
            message, coords, distance = await loop.run_in_executor(
                None,
                lambda: tracker_service.track(container_number, destination)
            )
            safe_print(f"✅ [РАСПИСАНИЕ] Отслеживание контейнера {container_number} завершено для пользователя {user_name}")
            
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
            safe_print(f"📤 [РАСПИСАНИЕ] Отправка запланированного уведомления пользователю {user_name}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🔔 Запланированное обновление контейнера {container_number}\n\n{message}",
                reply_markup=reply_markup
            )
            safe_print(f"✅ [РАСПИСАНИЕ] Уведомление отправлено пользователю {user_name}")
        
        track_scheduled_check('success')
        safe_print(f"✅ [РАСПИСАНИЕ] Запланированная проверка успешно завершена для пользователя {user_name}")
    except Exception as e:
        track_scheduled_check('error')
        safe_print(f"❌ [РАСПИСАНИЕ] Ошибка в scheduled_check_callback для пользователя {user_name}: {e}")
        import traceback
        safe_print(f"📋 [РАСПИСАНИЕ] Traceback:\n{traceback.format_exc()}")


#
# Тестовый одноразовый джоб удален по завершении проверки

async def load_existing_schedules(application: Application):
    """Загружает существующие расписания при запуске"""
    schedule = load_schedule()
    for chat_id_str, config in schedule.items():
        chat_id = int(chat_id_str)
        days = config.get('days', [])
        times = config.get('times', [])
        contracts = config.get('contracts', [])
        containers = config.get('containers', [])
        await register_schedule_jobs(application.job_queue, chat_id, days, times, contracts, containers)

# Обработка ошибок
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    track_error('update_processing')
    error = context.error
    
    # Игнорируем сетевые ошибки - они обрабатываются в safe_reply_text
    if isinstance(error, NetworkError):
        safe_print(f"⚠️ Network error (will retry): {error}")
        return
    
    safe_print(f"❌ Ошибка обработки update: {error}")
    safe_print(f"❌ Update: {update}")
    import traceback
    traceback.print_exc()
    
    # Пытаемся отправить сообщение об ошибке пользователю, если это возможно
    if update and hasattr(update, 'effective_chat'):
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Произошла ошибка при обработке вашего запроса. Попробуйте еще раз."
            )
        except:
            pass

# Главная функция
def main():
    """Главная функция запуска бота"""
    # Проверяем токен
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        raise ValueError("❌ BOT_TOKEN не установлен! Установите переменную окружения BOT_TOKEN")
    
    # Запускаем метрики
    start_metrics_server(8000)
    
    # Создаем приложение с настройками для обработки сетевых ошибок
    application = (
        Application.builder()
        .token(bot_token)
        .connection_pool_size(8)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )
    
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
        safe_print("⚠️ JobQueue не установлен. Расписание не будет работать.")
        safe_print("   Установите: pip install 'python-telegram-bot[job-queue]'")
    
    # Обновляем метрики активных пользователей
    try:
        history = load_history()
        active_count = len(set(str(uid) for uid in history.keys()))
        update_active_users(active_count)
    except:
        pass
    
    safe_print("🤖 [ЗАПУСК] Бот запущен и готов к работе...")
    safe_print("📊 [МЕТРИКИ] Метрики доступны на порту 8000")
    safe_print("🚀 [ЗАПУСК] Бот настроен на параллельную обработку запросов через run_in_executor")
    
    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

