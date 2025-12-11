# Настройка для Windows (PowerShell)

## Установка переменной окружения BOT_TOKEN

### ⚠️ В PowerShell используется другой синтаксис!

**НЕПРАВИЛЬНО (это для Linux/bash):**
```bash
export BOT_TOKEN="your_token"  # ❌ Не работает в PowerShell!
```

**ПРАВИЛЬНО для PowerShell:**

### Вариант 1: Для текущей сессии (временная)
```powershell
$env:BOT_TOKEN="8500735697:AAGkhlduEckZt4Cvd0pDs-UfWLNX2ynRYus"
python src/bot.py
```

### Вариант 2: Через .env файл (рекомендуется) ✅

1. Создайте файл `.env` в корне проекта `MapTrack/`:
```
BOT_TOKEN=8500735697:AAGkhlduEckZt4Cvd0pDs-UfWLNX2ynRYus
```

2. Установите python-dotenv (если еще не установлен):
```powershell
pip install python-dotenv
```

3. Запустите бота:
```powershell
python src/bot.py
```

Бот автоматически загрузит токен из `.env` файла.

### Вариант 3: Постоянная установка (для всей системы)

```powershell
[System.Environment]::SetEnvironmentVariable('BOT_TOKEN', '8500735697:AAGkhlduEckZt4Cvd0pDs-UfWLNX2ynRYus', 'User')
```

После этого **перезапустите PowerShell** и запустите:
```powershell
python src/bot.py
```

## Запуск бота

### Простой запуск:
```powershell
# Установите токен
$env:BOT_TOKEN="your_token"

# Запустите
python src/bot.py
```

### С автоперезапуском:
```powershell
$env:BOT_TOKEN="your_token"
python src/bot_runner.py
```

## ⚠️ Важно: Безопасность

**НЕ вставляйте токен прямо в команду** - он останется в истории PowerShell!

Лучше использовать `.env` файл:
1. Создайте `.env` в корне проекта
2. Добавьте `BOT_TOKEN=your_token`
3. Добавьте `.env` в `.gitignore` (чтобы не попало в git)

## Проверка

После установки переменной проверьте:
```powershell
echo $env:BOT_TOKEN
```

Должен вывести ваш токен.



