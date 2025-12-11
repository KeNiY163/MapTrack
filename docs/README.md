# MapTrack Bot - Система автоперезапуска с метриками

## 📋 Содержание

- [Быстрый старт (Docker)](#быстрый-старт-docker)
- [Установка на сервере](#установка-на-сервере)
- [Локальная установка](#локальная-установка)
- [Метрики и мониторинг](#метрики-prometheus--grafana)
- [Защита от падений](#защита-от-падений)

---

## 🚀 Быстрый старт (Docker)

### Требования
- Docker и Docker Compose
- Telegram Bot Token (получить у [@BotFather](https://t.me/BotFather))

### Шаг 1: Клонирование репозитория
```bash
git clone <repository_url>
cd MapTrack
```

### Шаг 2: Настройка переменных окружения
```bash
cp .env.example .env
nano .env  # или любой другой редактор
```

Вставьте ваш токен:
```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

### Шаг 3: Запуск всех сервисов
```bash
docker-compose up -d
```

### Шаг 4: Проверка статуса
```bash
docker-compose ps
docker-compose logs -f bot
```

### Доступ к сервисам:
- **Бот**: Работает в фоне
- **Метрики**: http://localhost:8000/metrics
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

### Управление:
```bash
# Остановка
docker-compose stop

# Перезапуск
docker-compose restart

# Остановка и удаление
docker-compose down

# Просмотр логов
docker-compose logs -f bot

# Обновление после изменений
docker-compose up -d --build
```

---

## 🖥️ Установка на сервере

### Вариант 1: Docker (рекомендуется)

#### Ubuntu/Debian
```bash
# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Перезагрузка для применения прав
sudo reboot
```

#### После установки Docker:
```bash
# Клонирование проекта
git clone <repository_url>
cd MapTrack

# Настройка токена
cp .env.example .env
nano .env

# Запуск
docker-compose up -d

# Автозапуск при перезагрузке сервера (уже настроено через restart: unless-stopped)
```

### Вариант 2: Systemd Service (без Docker)

#### Установка зависимостей:
```bash
# Python и pip
sudo apt update
sudo apt install -y python3 python3-pip git

# Chrome и ChromeDriver
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
sudo sh -c 'echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list'
sudo apt update
sudo apt install -y google-chrome-stable

# Клонирование проекта
git clone <repository_url>
cd MapTrack

# Установка Python зависимостей
pip3 install -r requirements.txt
```

#### Создание systemd service:
```bash
sudo nano /etc/systemd/system/maptrack-bot.service
```

Вставьте:
```ini
[Unit]
Description=MapTrack Telegram Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/MapTrack
ExecStart=/usr/bin/python3 /path/to/MapTrack/bot_runner.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Запуск сервиса:
```bash
sudo systemctl daemon-reload
sudo systemctl enable maptrack-bot
sudo systemctl start maptrack-bot
sudo systemctl status maptrack-bot

# Просмотр логов
sudo journalctl -u maptrack-bot -f
```

---

## 💻 Локальная установка

### Windows

#### Требования:
- Python 3.8+
- Google Chrome

#### Установка:
```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск с автоперезапуском
python bot_runner.py

# Или через bat-файл
start_bot.bat
```

### Linux/macOS

```bash
# Установка зависимостей
pip3 install -r requirements.txt

# Запуск
python3 bot_runner.py
```

## Защита от падений

Бот защищён от падений на нескольких уровнях:

1. **bot_runner.py** - автоматически перезапускает бот при любом падении
   - Лимит: 10 перезапусков в час
   - Логирование всех перезапусков
   - Защита от бесконечного цикла перезапусков

2. **bot.py** - обработка ошибок внутри бота
   - Защита каждого update от падения
   - Безопасное закрытие браузера
   - Защита scheduled_check от падений

3. **track_container()** - защита функции отслеживания
   - Безопасное закрытие драйвера
   - Обработка всех исключений

---

## ⚙️ Конфигурация

### Переменные окружения

Создайте файл `.env` или установите переменные:

```env
BOT_TOKEN=your_telegram_bot_token
```

### Файлы данных

Бот сохраняет данные в JSON файлы:
- `history.json` - история поисков
- `schedule.json` - расписания пользователей
- `cities.json` - города назначения

При использовании Docker они сохраняются в `./data/`

---

## 🔧 Управление и обслуживание

### Остановка бота

**Docker:**
```bash
docker-compose stop
```

**Локально:**
Нажмите `Ctrl+C`

**Systemd:**
```bash
sudo systemctl stop maptrack-bot
```

### Обновление

```bash
# Получить последние изменения
git pull

# Docker
docker-compose up -d --build

# Systemd
sudo systemctl restart maptrack-bot
```

### Резервное копирование

```bash
# Создание резервной копии
tar -czf backup-$(date +%Y%m%d).tar.gz *.json data/

# Восстановление
tar -xzf backup-20240101.tar.gz
```

---

## 📝 Логи

### Docker
```bash
# Все логи
docker-compose logs -f

# Только бот
docker-compose logs -f bot

# Последние 100 строк
docker-compose logs --tail=100 bot
```

### Systemd
```bash
sudo journalctl -u maptrack-bot -f
```

### Локально
Логи выводятся в консоль с временными метками

---

## Метрики (Prometheus + Grafana)

### Доступные метрики:

- `bot_messages_total` - Общее количество сообщений (по типам)
- `bot_commands_total` - Количество выполненных команд
- `bot_errors_total` - Количество ошибок (по типам)
- `bot_track_requests_total` - Количество запросов отслеживания
- `bot_track_duration_seconds` - Длительность запросов отслеживания
- `bot_active_users` - Количество активных пользователей
- `bot_scheduled_checks_total` - Количество запланированных проверок

### Просмотр метрик:

1. **Прямой доступ к метрикам:**
   ```
   http://localhost:8000/metrics
   ```

2. **Запуск Prometheus + Grafana (требуется Docker):**
   ```bash
   docker-compose up -d
   ```
   
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000 (admin/admin)

3. **Настройка Grafana:**
   - Добавьте Prometheus как источник данных: http://prometheus:9090
   - Создайте дашборд с нужными метриками

### Примеры запросов Prometheus:

```promql
# Количество сообщений в минуту
rate(bot_messages_total[1m])

# Средняя длительность отслеживания
rate(bot_track_duration_seconds_sum[5m]) / rate(bot_track_duration_seconds_count[5m])

# Количество ошибок
sum(bot_errors_total)
```
