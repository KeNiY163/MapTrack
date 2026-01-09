# 🌐 Установка MapTrack Bot на VPS

## 📋 Что вам понадобится

- VPS с Ubuntu 20.04+ (минимум 1GB RAM, 1 CPU)
- SSH доступ к серверу
- Telegram Bot Token от [@BotFather](https://t.me/BotFather)

---

## 🚀 Способ 1: Автоматическая установка (рекомендуется)

### Шаг 1: Подключение к VPS
```bash
ssh root@YOUR_VPS_IP
# или
ssh username@YOUR_VPS_IP
```

### Шаг 2: Скачивание и запуск установщика
```bash
curl -fsSL https://raw.githubusercontent.com/KeNiY163/MapTrack/main/scripts/install.sh | bash
```

Если репозиторий приватный, используйте способ 2.

---

## 🛠️ Способ 2: Ручная установка

### Шаг 1: Подключение к VPS
```bash
ssh root@YOUR_VPS_IP
```

### Шаг 2: Обновление системы
```bash
apt update && apt upgrade -y
```

### Шаг 3: Установка Docker
```bash
# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Добавление пользователя в группу docker
usermod -aG docker $USER

# Установка Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Перезагрузка для применения изменений
reboot
```

### Шаг 4: Повторное подключение после перезагрузки
```bash
ssh root@YOUR_VPS_IP
```

### Шаг 5: Создание директории проекта
```bash
mkdir -p /opt/maptrack
cd /opt/maptrack
```

### Шаг 6: Загрузка файлов проекта

#### Вариант A: Через Git (если репозиторий публичный)
```bash
git clone https://github.com/YOUR_USERNAME/MapTrack.git .
```

#### Вариант B: Ручная загрузка файлов

Создайте файлы по очереди:

**1. Создание bot.py:**
```bash
cat > bot.py << 'EOF'
# Скопируйте сюда содержимое bot.py
EOF
```

**2. Создание metrics.py:**
```bash
cat > metrics.py << 'EOF'
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time

# Метрики
messages_total = Counter('bot_messages_total', 'Total messages received', ['type'])
commands_total = Counter('bot_commands_total', 'Total commands executed', ['command'])
errors_total = Counter('bot_errors_total', 'Total errors', ['type'])
track_requests = Counter('bot_track_requests_total', 'Total tracking requests')
track_duration = Histogram('bot_track_duration_seconds', 'Tracking request duration')
active_users = Gauge('bot_active_users', 'Number of active users')
scheduled_checks = Counter('bot_scheduled_checks_total', 'Total scheduled checks', ['status'])

def start_metrics_server(port=8000):
    try:
        start_http_server(port)
        print(f"📊 Metrics server started on port {port}")
    except Exception as e:
        print(f"⚠️ Failed to start metrics server: {e}")

def track_message(msg_type='text'):
    messages_total.labels(type=msg_type).inc()

def track_command(command):
    commands_total.labels(command=command).inc()

def track_error(error_type):
    errors_total.labels(type=error_type).inc()

def track_tracking_request():
    track_requests.inc()

def track_tracking_duration(duration):
    track_duration.observe(duration)

def update_active_users(count):
    active_users.set(count)

def track_scheduled_check(status='success'):
    scheduled_checks.labels(status=status).inc()
EOF
```

**3. Создание bot_runner.py:**
```bash
cat > bot_runner.py << 'EOF'
import subprocess
import sys
import time
from datetime import datetime

def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

def run_bot():
    restart_count = 0
    max_restarts_per_hour = 10
    restart_times = []
    
    while True:
        try:
            log("🚀 Запуск бота...")
            process = subprocess.Popen(
                [sys.executable, "bot.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            for line in process.stdout:
                print(line, end='')
            
            process.wait()
            log(f"⚠️ Бот остановлен с кодом: {process.returncode}")
            
            current_time = time.time()
            restart_times = [t for t in restart_times if current_time - t < 3600]
            
            if len(restart_times) >= max_restarts_per_hour:
                log(f"❌ Превышен лимит перезапусков ({max_restarts_per_hour}/час). Ожидание 1 час...")
                time.sleep(3600)
                restart_times.clear()
            
            restart_times.append(current_time)
            restart_count += 1
            log(f"🔄 Перезапуск #{restart_count} через 5 секунд...")
            time.sleep(5)
            
        except KeyboardInterrupt:
            log("⛔ Остановка по Ctrl+C")
            if 'process' in locals():
                process.terminate()
            break
        except Exception as e:
            log(f"❌ Критическая ошибка: {e}")
            time.sleep(10)

if __name__ == "__main__":
    log("🤖 Запуск системы автоперезапуска бота")
    run_bot()
EOF
```

**4. Создание requirements.txt:**
```bash
cat > requirements.txt << 'EOF'
selenium
requests
prometheus-client
EOF
```

**5. Создание Dockerfile:**
```bash
cat > Dockerfile << 'EOF'
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    wget gnupg unzip curl \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Установка ChromeDriver через Chrome for Testing API (современный способ)
RUN CHROME_VERSION=$(google-chrome --version | awk '{print $3}') \
    && CHROME_MAJOR_VERSION=$(echo $CHROME_VERSION | cut -d '.' -f 1) \
    && wget -q "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_MAJOR_VERSION}" -O /tmp/chromedriver_version \
    && CHROMEDRIVER_VERSION=$(cat /tmp/chromedriver_version) \
    && wget -q "https://storage.googleapis.com/chrome-for-testing-public/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver* \
    && chmod +x /usr/local/bin/chromedriver

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py metrics.py bot_runner.py ./
RUN mkdir -p /app/data
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "bot_runner.py"]
EOF
```

**6. Создание docker-compose.yml:**
```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  bot:
    build: .
    container_name: maptrack_bot
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
    volumes:
      - ./data:/app/data
    ports:
      - "8000:8000"
    restart: unless-stopped
    networks:
      - maptrack_network

  prometheus:
    image: prom/prometheus:latest
    container_name: maptrack_prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: unless-stopped
    networks:
      - maptrack_network
    depends_on:
      - bot

  grafana:
    image: grafana/grafana:latest
    container_name: maptrack_grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana_data:/var/lib/grafana
    depends_on:
      - prometheus
    restart: unless-stopped
    networks:
      - maptrack_network

volumes:
  prometheus_data:
  grafana_data:

networks:
  maptrack_network:
    driver: bridge
EOF
```

**7. Создание prometheus.yml:**
```bash
cat > prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'maptrack_bot'
    static_configs:
      - targets: ['bot:8000']
EOF
```

**8. Создание .env файла:**
```bash
cat > .env << 'EOF'
BOT_TOKEN=YOUR_BOT_TOKEN_HERE
EOF
```

### Шаг 7: Настройка токена бота
```bash
nano .env
```

Замените `YOUR_BOT_TOKEN_HERE` на ваш реальный токен от BotFather.

### Шаг 8: Запуск бота
```bash
docker-compose up -d --build
```

### Шаг 9: Проверка статуса
```bash
docker-compose ps
docker-compose logs -f bot
```

---

## 🔧 Настройка файрвола (UFW)

```bash
# Включение UFW
ufw enable

# Разрешение SSH
ufw allow ssh

# Разрешение портов для сервисов
ufw allow 8000/tcp  # Метрики
ufw allow 9090/tcp  # Prometheus
ufw allow 3000/tcp  # Grafana

# Проверка статуса
ufw status
```

---

## 🌐 Доступ к сервисам

После успешного запуска сервисы будут доступны по адресам:

- **Метрики бота**: `http://YOUR_VPS_IP:8000/metrics`
- **Prometheus**: `http://YOUR_VPS_IP:9090`
- **Grafana**: `http://YOUR_VPS_IP:3000` (admin/admin)

---

## 📊 Полезные команды

```bash
# Просмотр логов
docker-compose logs -f bot

# Перезапуск бота
docker-compose restart bot

# Остановка всех сервисов
docker-compose stop

# Обновление после изменений
docker-compose up -d --build

# Полная остановка и удаление
docker-compose down -v

# Мониторинг ресурсов
docker stats

# Резервное копирование данных
tar -czf backup-$(date +%Y%m%d).tar.gz data/
```

---

## 🆘 Решение проблем

### Проблема: Бот не запускается
```bash
# Проверьте логи
docker-compose logs bot

# Проверьте токен
cat .env

# Пересоберите контейнер
docker-compose up -d --build --force-recreate
```

### Проблема: Нет доступа к метрикам
```bash
# Проверьте порты
netstat -tlnp | grep :8000

# Проверьте файрвол
ufw status

# Откройте порт
ufw allow 8000/tcp
```

### Проблема: Недостаточно места на диске
```bash
# Очистка Docker
docker system prune -a

# Проверка места
df -h
```

### Проблема: Высокое потребление памяти
```bash
# Ограничение памяти в docker-compose.yml
services:
  bot:
    deploy:
      resources:
        limits:
          memory: 512M
```

---

## 🔄 Автоматическое обновление

Создайте скрипт для автоматического обновления:

```bash
cat > update.sh << 'EOF'
#!/bin/bash
cd /opt/maptrack
git pull
docker-compose up -d --build
docker system prune -f
EOF

chmod +x update.sh
```

Запуск обновления:
```bash
./update.sh
```

---

## 📈 Мониторинг

### Настройка алертов в Grafana
1. Откройте Grafana: `http://YOUR_VPS_IP:3000`
2. Войдите: admin/admin
3. Добавьте Prometheus: `http://prometheus:9090`
4. Создайте дашборд с метриками бота
5. Настройте уведомления при ошибках

### Проверка работоспособности
```bash
# Проверка всех сервисов
curl -s http://localhost:8000/metrics | grep bot_messages_total
curl -s http://localhost:9090/-/healthy
curl -s http://localhost:3000/api/health
```

---

## ✅ Готово!

Ваш бот теперь работает на VPS 24/7 с полным мониторингом и автоматическим перезапуском при сбоях.

**Следующие шаги:**
1. Протестируйте бота в Telegram
2. Настройте дашборд в Grafana
3. Настройте резервное копирование данных
4. Добавьте домен и SSL (опционально)