#!/bin/bash
# Скрипт для загрузки файлов на сервер через SCP
# Использование: bash scripts/upload_to_server.sh SERVER_IP [USER] [REMOTE_PATH]

set -e

SERVER_IP="${1:-}"
USER="${2:-root}"
REMOTE_PATH="${3:-/opt/maptrack/MapTrack}"

if [ -z "$SERVER_IP" ]; then
    echo "❌ Использование: $0 SERVER_IP [USER] [REMOTE_PATH]"
    echo "   Пример: $0 192.168.1.100"
    echo "   Пример: $0 192.168.1.100 root /opt/maptrack/MapTrack"
    exit 1
fi

echo "🚀 Загрузка файлов на сервер $SERVER_IP..."

# Файлы и директории для загрузки
ITEMS=("src" "docker" "config" "requirements.txt")

for item in "${ITEMS[@]}"; do
    if [ -e "$item" ]; then
        echo "  → Загрузка $item..."
        if [ -d "$item" ]; then
            scp -r "$item" "${USER}@${SERVER_IP}:${REMOTE_PATH}/"
        else
            scp "$item" "${USER}@${SERVER_IP}:${REMOTE_PATH}/"
        fi
        echo "  ✅ $item загружен"
    else
        echo "  ⚠️  $item не найден, пропускаю..."
    fi
done

echo ""
echo "✅ Загрузка завершена!"
echo ""
echo "Теперь на сервере выполните:"
echo "  cd $REMOTE_PATH/config"
echo "  docker-compose down"
echo "  docker-compose up -d --build"






