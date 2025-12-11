# 🚀 Быстрый старт MapTrack Bot

## За 3 минуты на любом сервере с Docker

### 1. Получите токен бота
Напишите [@BotFather](https://t.me/BotFather) в Telegram:
```
/newbot
```
Скопируйте полученный токен.

### 2. Установите Docker (если еще не установлен)
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

Перезайдите в систему или выполните:
```bash
newgrp docker
```

### 3. Установите Docker Compose
```bash
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 4. Клонируйте и настройте
```bash
git clone <repository_url>
cd MapTrack
cp .env.example .env
nano .env  # Вставьте ваш токен
```

### 5. Запустите
```bash
docker-compose up -d
```

### 6. Проверьте
```bash
docker-compose ps
docker-compose logs -f bot
```

## ✅ Готово!

Ваш бот работает 24/7 с:
- ✅ Автоматическим перезапуском при падениях
- ✅ Метриками на http://your-server:8000/metrics
- ✅ Prometheus на http://your-server:9090
- ✅ Grafana на http://your-server:3000

## 🔧 Полезные команды

```bash
# Остановить
docker-compose stop

# Перезапустить
docker-compose restart

# Обновить
git pull && docker-compose up -d --build

# Логи
docker-compose logs -f bot

# Удалить всё
docker-compose down -v
```

## 🆘 Проблемы?

### Ошибка сборки Docker (Chrome):
```bash
# Остановите и очистите
docker-compose down
docker system prune -f

# Пересоберите
docker-compose up -d --build --force-recreate

# Или используйте простой вариант
docker-compose -f docker-compose.simple.yml up -d --build
```

### Обычные проблемы:
1. **Бот не запускается**: Проверьте токен в `.env`
2. **Нет доступа к метрикам**: Откройте порт 8000
3. **Проблемы с Docker**: См. [DOCKER_FIX.md](DOCKER_FIX.md)

Полная документация: [README.md](README.md)
