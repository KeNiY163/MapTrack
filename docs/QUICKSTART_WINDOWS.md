# Быстрый старт для Windows (PowerShell)

## Установка переменной окружения

В PowerShell используйте другой синтаксис:

### Вариант 1: Для текущей сессии
```powershell
$env:BOT_TOKEN="your_token_here"
```

### Вариант 2: Через .env файл (рекомендуется)

Создайте файл `.env` в корне проекта:
```env
BOT_TOKEN=your_token_here
```

И установите python-dotenv:
```bash
pip install python-dotenv
```

Затем обновите `src/bot.py` для загрузки из .env файла.

### Вариант 3: Постоянная установка (для всей системы)
```powershell
[System.Environment]::SetEnvironmentVariable('BOT_TOKEN', 'your_token_here', 'User')
```

После этого перезапустите PowerShell.

## Запуск бота

```powershell
# Установите токен
$env:BOT_TOKEN="your_token_here"

# Запустите бота
python src/bot.py
```

## Важно: Безопасность

⚠️ **НЕ вставляйте токен прямо в команду** - он останется в истории PowerShell!

Лучше использовать .env файл или установить переменную через системные настройки.



