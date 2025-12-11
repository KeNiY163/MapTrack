#!/bin/bash

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для вывода
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${BLUE}"
    echo "=================================================="
    echo "🚀 MapTrack Bot - Автоматическая установка на VPS"
    echo "=================================================="
    echo -e "${NC}"
}

# Проверка root прав
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "Этот скрипт должен запускаться с правами root"
        print_info "Выполните: sudo $0"
        exit 1
    fi
}

# Проверка операционной системы
check_os() {
    if [[ ! -f /etc/os-release ]]; then
        print_error "Неподдерживаемая операционная система"
        exit 1
    fi
    
    . /etc/os-release
    if [[ "$ID" != "ubuntu" ]] && [[ "$ID" != "debian" ]]; then
        print_warning "Скрипт тестировался на Ubuntu/Debian. Продолжить? (y/N)"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Обновление системы
update_system() {
    print_info "Обновление системы..."
    apt update && apt upgrade -y
    apt install -y curl wget git nano
    print_success "Система обновлена"
}

# Установка Docker
install_docker() {
    if command -v docker &> /dev/null; then
        print_success "Docker уже установлен"
        return
    fi
    
    print_info "Установка Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    
    # Добавление пользователя в группу docker
    if [[ -n "$SUDO_USER" ]]; then
        usermod -aG docker "$SUDO_USER"
    fi
    
    print_success "Docker установлен"
}

# Установка Docker Compose
install_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        print_success "Docker Compose уже установлен"
        return
    fi
    
    print_info "Установка Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    print_success "Docker Compose установлен"
}

# Создание директории проекта
create_project_dir() {
    PROJECT_DIR="/opt/maptrack"
    print_info "Создание директории проекта: $PROJECT_DIR"
    
    if [[ -d "$PROJECT_DIR" ]]; then
        print_warning "Директория $PROJECT_DIR уже существует. Перезаписать? (y/N)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            rm -rf "$PROJECT_DIR"
        else
            print_error "Установка отменена"
            exit 1
        fi
    fi
    
    mkdir -p "$PROJECT_DIR"
    cd "$PROJECT_DIR"
    print_success "Директория создана: $PROJECT_DIR"
}

# Загрузка файлов проекта
download_files() {
    print_info "Загрузка файлов проекта..."
    
    # Попытка клонирования через Git
    if git clone https://github.com/YOUR_USERNAME/MapTrack.git . 2>/dev/null; then
        print_success "Файлы загружены через Git"
        return
    fi
    
    print_warning "Git репозиторий недоступен. Создание файлов вручную..."
    
    # Создание файлов вручную (базовые файлы)
    create_basic_files
}

# Создание базовых файлов
create_basic_files() {
    # requirements.txt
    cat > requirements.txt << 'EOF'
selenium
requests
prometheus-client
EOF

    # .env.example
    cat > .env.example << 'EOF'
BOT_TOKEN=your_bot_token_here
EOF

    # Dockerfile
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
COPY *.py ./
RUN mkdir -p /app/data
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "bot_runner.py"]
EOF

    # docker-compose.yml
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

volumes:
  bot_data:
EOF

    # prometheus.yml
    cat > prometheus.yml << 'EOF'
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'maptrack_bot'
    static_configs:
      - targets: ['bot:8000']
EOF

    print_success "Базовые файлы созданы"
    print_warning "ВНИМАНИЕ: Необходимо добавить файлы bot.py, metrics.py, bot_runner.py"
}

# Настройка токена
setup_token() {
    print_info "Настройка токена бота..."
    
    if [[ -f .env.example ]]; then
        cp .env.example .env
    else
        echo "BOT_TOKEN=your_bot_token_here" > .env
    fi
    
    print_warning "Необходимо настроить токен бота в файле .env"
    print_info "1. Получите токен у @BotFather в Telegram"
    print_info "2. Отредактируйте файл: nano .env"
    print_info "3. Замените 'your_bot_token_here' на ваш токен"
    
    read -p "Нажмите Enter, чтобы открыть редактор .env файла..."
    nano .env
}

# Настройка файрвола
setup_firewall() {
    print_info "Настройка файрвола..."
    
    if command -v ufw &> /dev/null; then
        ufw --force enable
        ufw allow ssh
        ufw allow 8000/tcp
        ufw allow 9090/tcp
        ufw allow 3000/tcp
        print_success "Файрвол настроен"
    else
        print_warning "UFW не установлен. Убедитесь, что порты 8000, 9090, 3000 открыты"
    fi
}

# Запуск сервисов
start_services() {
    print_info "Запуск сервисов..."
    
    # Проверка токена
    if grep -q "your_bot_token_here" .env; then
        print_error "Токен не настроен в файле .env"
        print_info "Отредактируйте файл .env и запустите: docker-compose up -d"
        return
    fi
    
    docker-compose up -d --build
    
    print_info "Ожидание запуска сервисов..."
    sleep 10
    
    print_success "Сервисы запущены!"
}

# Показ информации о доступе
show_access_info() {
    SERVER_IP=$(curl -s ifconfig.me || echo "YOUR_SERVER_IP")
    
    echo -e "${GREEN}"
    echo "=================================================="
    echo "✅ Установка завершена успешно!"
    echo "=================================================="
    echo -e "${NC}"
    
    echo "🔗 Доступ к сервисам:"
    echo "   - Метрики бота: http://$SERVER_IP:8000/metrics"
    echo "   - Prometheus: http://$SERVER_IP:9090"
    echo "   - Grafana: http://$SERVER_IP:3000 (admin/admin)"
    echo ""
    echo "📝 Полезные команды:"
    echo "   cd $PROJECT_DIR"
    echo "   docker-compose logs -f bot      # Логи бота"
    echo "   docker-compose restart bot      # Перезапуск"
    echo "   docker-compose stop             # Остановка"
    echo ""
    echo "📊 Проверка статуса:"
    echo "   docker-compose ps"
    echo ""
}

# Основная функция
main() {
    print_header
    
    check_root
    check_os
    update_system
    install_docker
    install_docker_compose
    create_project_dir
    download_files
    setup_token
    setup_firewall
    start_services
    show_access_info
    
    print_success "Установка завершена! Проверьте работу бота в Telegram."
}

# Обработка ошибок
trap 'print_error "Произошла ошибка на строке $LINENO. Установка прервана."' ERR

# Запуск
main "$@"