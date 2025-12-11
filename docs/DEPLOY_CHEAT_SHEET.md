# 🚀 MapTrack Bot - Шпаргалка по деплою

## ⚡ Супер быстрый деплой (1 команда)

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/MapTrack/main/install.sh | sudo bash
```

---

## 🛠️ Ручной деплой (5 минут)

### 1. Подготовка VPS
```bash
# Подключение
ssh root@YOUR_VPS_IP

# Обновление
apt update && apt upgrade -y

# Docker
curl -fsSL https://get.docker.com | sh
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

### 2. Загрузка проекта
```bash
mkdir -p /opt/maptrack && cd /opt/maptrack

# Вариант A: Git
git clone https://github.com/YOUR_USERNAME/MapTrack.git .

# Вариант B: Загрузка архива
scp maptrack.zip root@YOUR_VPS_IP:/tmp/
unzip /tmp/maptrack.zip
```

### 3. Настройка и запуск
```bash
# Токен
cp .env.example .env
nano .env  # BOT_TOKEN=your_token

# Запуск
docker-compose up -d --build

# Проверка
docker-compose logs -f bot
```

---

## 📋 Чек-лист файлов

- [ ] `bot.py` - основной код
- [ ] `metrics.py` - метрики  
- [ ] `bot_runner.py` - автоперезапуск
- [ ] `requirements.txt` - зависимости
- [ ] `Dockerfile` - контейнер
- [ ] `docker-compose.yml` - оркестрация
- [ ] `prometheus.yml` - мониторинг
- [ ] `.env` - токен бота

---

## 🔧 Полезные команды

```bash
# Управление
docker-compose up -d --build    # Запуск
docker-compose stop             # Остановка
docker-compose restart bot      # Перезапуск бота
docker-compose logs -f bot      # Логи
docker-compose ps               # Статус

# Обновление
git pull && docker-compose up -d --build

# Очистка
docker system prune -a

# Резервная копия
tar -czf backup-$(date +%Y%m%d).tar.gz data/
```

---

## 🌐 Доступ к сервисам

- **Метрики**: `http://YOUR_VPS_IP:8000/metrics`
- **Prometheus**: `http://YOUR_VPS_IP:9090`
- **Grafana**: `http://YOUR_VPS_IP:3000` (admin/admin)

---

## 🔥 Файрвол

```bash
ufw enable
ufw allow ssh
ufw allow 8000,9090,3000/tcp
```

---

## 🆘 Быстрые фиксы

```bash
# Бот не запускается
docker-compose logs bot
nano .env  # Проверить токен

# Нет доступа к метрикам
ufw allow 8000/tcp
netstat -tlnp | grep :8000

# Мало места
docker system prune -a
df -h

# Высокая нагрузка
docker stats
htop
```

---

## 📊 Проверка работы

```bash
# Статус контейнеров
docker-compose ps

# Тест метрик
curl localhost:8000/metrics | grep bot_messages

# Тест бота в Telegram
# Отправьте /start боту

# Мониторинг ресурсов
docker stats --no-stream
```

---

## 🔄 Автообновление

```bash
# Создать скрипт
cat > /opt/maptrack/update.sh << 'EOF'
#!/bin/bash
cd /opt/maptrack
git pull
docker-compose up -d --build
docker system prune -f
EOF

chmod +x /opt/maptrack/update.sh

# Запуск обновления
/opt/maptrack/update.sh
```

---

## 📈 Мониторинг

### Grafana Dashboard
1. Откройте `http://YOUR_VPS_IP:3000`
2. Логин: admin/admin
3. Add Data Source → Prometheus → `http://prometheus:9090`
4. Create Dashboard с метриками:
   - `rate(bot_messages_total[5m])`
   - `bot_active_users`
   - `rate(bot_errors_total[5m])`

### Алерты
```bash
# Проверка здоровья
curl -f http://localhost:8000/metrics || echo "Bot down!"
curl -f http://localhost:9090/-/healthy || echo "Prometheus down!"
```

---

## 🎯 Готовые команды для копирования

```bash
# Полная установка одной командой
ssh root@YOUR_VPS_IP "curl -fsSL https://get.docker.com | sh && curl -L 'https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)' -o /usr/local/bin/docker-compose && chmod +x /usr/local/bin/docker-compose && mkdir -p /opt/maptrack"

# Загрузка файлов (если есть Git репозиторий)
ssh root@YOUR_VPS_IP "cd /opt/maptrack && git clone https://github.com/YOUR_USERNAME/MapTrack.git ."

# Настройка токена и запуск
ssh root@YOUR_VPS_IP "cd /opt/maptrack && cp .env.example .env && echo 'Отредактируйте .env файл с вашим токеном' && docker-compose up -d --build"
```

---

**💡 Совет**: Сохраните эту шпаргалку - она содержит все необходимые команды для быстрого деплоя и управления ботом на VPS!