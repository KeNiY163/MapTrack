# Установка и запуск

## Установка зависимостей

```bash
pip install -r requirements.txt
```

Или если requirements.txt обновлен:
```bash
pip install 'python-telegram-bot[job-queue]>=20.0' selenium requests prometheus-client webdriver-manager python-dotenv
```

## Настройка токена

### Windows PowerShell:
```powershell
$env:BOT_TOKEN="your_token_here"
```

### Linux/macOS:
```bash
export BOT_TOKEN="your_token_here"
```

### Через .env файл (рекомендуется):

1. Создайте файл `.env` в корне проекта:
```
BOT_TOKEN=your_token_here
```

2. Бот автоматически загрузит токен из `.env` файла

## Запуск

### Вариант 1: Прямой запуск
```bash
python src/bot.py
```

### Вариант 2: Как модуль
```bash
python -m src.bot
```

### Вариант 3: С автоперезапуском (локально)
```bash
python src/bot_runner.py
```

## Проблемы

### JobQueue не установлен

Если видите предупреждение:
```
⚠️ JobQueue не установлен. Расписание не будет работать.
```

Установите:
```bash
pip install 'python-telegram-bot[job-queue]'
```

Или переустановите все зависимости:
```bash
pip install -r requirements.txt
```

### Импорты не работают

Если видите ошибки импорта, используйте запуск как модуль:
```bash
python -m src.bot
```



