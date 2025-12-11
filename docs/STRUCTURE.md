# Структура репозитория MapTrack

## Организация папок

```
MapTrack/
├── src/                    # Исходный код бота
│   ├── __init__.py
│   ├── bot.py              # Основной файл бота
│   ├── bot_runner.py       # Обертка для автоперезапуска
│   ├── metrics.py          # Метрики Prometheus
│   ├── container_tracker.py # Сервис отслеживания контейнеров
│   └── view_metrics.py     # Просмотр метрик
│
├── tests/                  # Тесты
│   ├── test_multithreading.py
│   └── quick_thread_test.py
│
├── scripts/                # Скрипты для запуска и деплоя
│   ├── deploy.sh
│   ├── install.sh
│   └── start_bot.bat
│
├── data/                   # Данные (JSON файлы)
│   ├── history.json
│   ├── schedule.json
│   └── cities.json
│
├── config/                 # Конфигурационные файлы
│   ├── prometheus.yml
│   ├── docker-compose.yml
│   └── docker-compose.simple.yml
│
├── docker/                 # Docker файлы
│   ├── Dockerfile
│   └── Dockerfile.simple
│
├── docs/                   # Документация
│   ├── README.md
│   ├── CODE_REVIEW.md
│   └── ... (все .md и .txt файлы)
│
├── trash/                  # Неиспользуемые файлы
│   └── ReqPozition.py
│
├── screenshots/            # Скриншоты для отладки
├── requirements.txt        # Зависимости Python
└── organize_repo.py        # Скрипт организации (можно удалить)
```

## Обновление путей в коде

После перемещения файлов нужно обновить:

1. **Пути к файлам данных** в `src/bot.py`:
   - `HISTORY_FILE = 'history.json'` → `'data/history.json'`
   - `SCHEDULE_FILE = 'schedule.json'` → `'data/schedule.json'`
   - `CITIES_FILE = 'cities.json'` → `'data/cities.json'`

2. **Импорты** в `src/bot.py`:
   - `from metrics import ...` → `from src.metrics import ...` или `from .metrics import ...`
   - `from container_tracker import ...` → `from src.container_tracker import ...` или `from .container_tracker import ...`

3. **Путь к скриншотам** в `src/container_tracker.py`:
   - `screenshots/` → можно оставить как есть (относительно корня)

4. **Docker файлы**:
   - Обновить пути в `docker/Dockerfile` и `config/docker-compose.yml`

