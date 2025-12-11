# Улучшения Docker ✅

## Что сделано

### 1. Упрощенный Dockerfile ✅

**Оптимизации:**
- ✅ Использует `python:3.11-slim` (меньший размер образа)
- ✅ Правильные пути к файлам (src/, data/)
- ✅ Healthcheck для мониторинга состояния
- ✅ Убрана зависимость от bot_runner (перезапуски отданы оркестратору)
- ✅ Оптимизирован порядок слоев (кэширование)

**Структура:**
```dockerfile
FROM python:3.11-slim
# Установка Chrome и ChromeDriver
# Копирование зависимостей
# Копирование кода
# Healthcheck
CMD ["python", "-m", "src.bot"]
```

### 2. Обновлен docker-compose.yml ✅

**Изменения:**
- ✅ Правильные пути к файлам (context: .., dockerfile: docker/Dockerfile)
- ✅ Volumes для data и screenshots
- ✅ Healthcheck в docker-compose
- ✅ Restart policy: `unless-stopped` (перезапуски отданы оркестратору)

**Преимущества:**
- Docker сам перезапускает контейнер при падении
- Healthcheck мониторит состояние бота
- Не нужен bot_runner для автоперезапуска

### 3. Создан docker-compose.simple.yml ✅

Упрощенная версия без Prometheus/Grafana для быстрого запуска.

## Использование

### Полный запуск (с мониторингом):
```bash
cd config
docker-compose up -d
```

### Упрощенный запуск (только бот):
```bash
cd config
docker-compose -f docker-compose.simple.yml up -d
```

### Проверка статуса:
```bash
docker-compose ps
docker-compose logs -f bot
```

### Остановка:
```bash
docker-compose down
```

## Преимущества

✅ **Упрощение** - один Dockerfile вместо нескольких
✅ **Оптимизация** - меньший размер образа
✅ **Надежность** - healthcheck и restart policies
✅ **Мониторинг** - Docker отслеживает состояние
✅ **Автоперезапуск** - Docker сам перезапускает при падении

## Что изменилось

**Было:**
- bot_runner.py для автоперезапуска
- Несколько Dockerfile'ов
- Ручное управление перезапусками

**Стало:**
- Перезапуски через Docker restart policies
- Один оптимизированный Dockerfile
- Healthcheck для мониторинга
- Автоматическое восстановление при падении

## Структура

```
MapTrack/
├── docker/
│   └── Dockerfile          # Упрощенный и оптимизированный
├── config/
│   ├── docker-compose.yml  # Полная версия (с Prometheus/Grafana)
│   └── docker-compose.simple.yml  # Упрощенная версия
└── src/
    └── bot.py              # Запускается напрямую (без bot_runner)
```

## Healthcheck

Docker автоматически проверяет состояние бота:
- Проверка каждые 30 секунд
- Timeout 10 секунд
- 3 попытки перед пометкой как unhealthy
- Период запуска 40 секунд (время на инициализацию)

Если бот не отвечает на `/metrics`, Docker помечает контейнер как unhealthy и может перезапустить его.



