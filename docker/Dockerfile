FROM selenium/standalone-chrome:latest

USER root

# Установка Python и pip
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копирование зависимостей и установка
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY src/ ./src/

# Создание директорий для данных и скриншотов
RUN mkdir -p /app/data /app/screenshots && \
    chown -R seluser:seluser /app/data /app/screenshots

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DISPLAY=:99

# Порт для метрик
EXPOSE 8000

# Healthcheck для мониторинга
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/metrics || exit 1

# Переключение на пользователя seluser для безопасности
USER seluser

# Запуск бота (без bot_runner - перезапуски отдаем оркестратору)
CMD ["python", "-m", "src.bot"]

