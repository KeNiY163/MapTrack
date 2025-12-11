# Организация репозитория - Выполнено ✅

## Структура создана

```
MapTrack/
├── src/                    # Исходный код бота
│   ├── __init__.py
│   ├── bot_runner.py
│   ├── container_tracker.py
│   ├── metrics.py
│   └── view_metrics.py
│
├── tests/                  # Тесты
│   └── quick_thread_test.py
│
├── scripts/                # Скрипты
│   ├── install.sh
│   └── start_bot.bat
│
├── data/                   # Данные
│   ├── cities.json
│   └── schedule.json
│
├── config/                 # Конфигурация
│   ├── docker-compose.yml
│   └── docker-compose.simple.yml
│
├── docker/                 # Docker
│   └── Dockerfile.simple
│
├── docs/                   # Документация
│   └── (все .md и .txt файлы)
│
└── trash/                  # Мусор
```

## Что нужно обновить

### 1. Пути к файлам данных
В `src/bot.py` (когда он будет найден/создан):
```python
HISTORY_FILE = 'data/history.json'
SCHEDULE_FILE = 'data/schedule.json'
CITIES_FILE = 'data/cities.json'
```

### 2. Импорты
В `src/bot.py`:
```python
from .metrics import ...
from .container_tracker import ContainerTrackerService
```

### 3. Путь к скриншотам
В `src/container_tracker.py` можно оставить `screenshots/` (относительно корня проекта)

### 4. Docker файлы
Обновить пути в `docker/Dockerfile` и `config/docker-compose.yml`:
- `COPY bot.py` → `COPY src/bot.py`
- `COPY requirements.txt` → оставить в корне
- `WORKDIR /app` → обновить пути копирования

## Статус

✅ Структура папок создана
✅ Файлы перемещены
⏳ Требуется обновление путей в коде (после восстановления bot.py)

