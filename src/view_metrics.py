import requests
import time
from datetime import datetime

def fetch_metrics():
    """Получить и отобразить метрики"""
    try:
        response = requests.get('http://localhost:8000/metrics', timeout=5)
        if response.status_code == 200:
            return response.text
        else:
            return f"Ошибка: {response.status_code}"
    except Exception as e:
        return f"Не удалось получить метрики: {e}"

def parse_metric(lines, metric_name):
    """Извлечь значение метрики"""
    for line in lines:
        if line.startswith(metric_name) and not line.startswith('#'):
            parts = line.split()
            if len(parts) >= 2:
                return parts[-1]
    return "0"

def display_metrics():
    """Отобразить метрики в читаемом виде"""
    print("\n" + "="*60)
    print(f"📊 MapTrack Bot Metrics - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    metrics_text = fetch_metrics()
    if "Ошибка" in metrics_text or "Не удалось" in metrics_text:
        print(f"\n❌ {metrics_text}")
        print("\n💡 Убедитесь, что бот запущен!")
        return
    
    lines = metrics_text.split('\n')
    
    # Сообщения
    text_msgs = parse_metric(lines, 'bot_messages_total{type="text"}')
    callback_msgs = parse_metric(lines, 'bot_messages_total{type="callback"}')
    print(f"\n📨 Сообщения:")
    print(f"   Текстовые: {text_msgs}")
    print(f"   Callback: {callback_msgs}")
    
    # Команды
    print(f"\n⚡ Команды:")
    for cmd in ['start', 'track', 'history', 'schedule']:
        count = parse_metric(lines, f'bot_commands_total{{command="{cmd}"}}')
        if count != "0":
            print(f"   /{cmd}: {count}")
    
    # Отслеживание
    track_total = parse_metric(lines, 'bot_track_requests_total')
    print(f"\n🔍 Запросы отслеживания: {track_total}")
    
    # Ошибки
    print(f"\n❌ Ошибки:")
    for err_type in ['track_container', 'update_processing', 'critical']:
        count = parse_metric(lines, f'bot_errors_total{{type="{err_type}"}}')
        if count != "0":
            print(f"   {err_type}: {count}")
    
    # Активные пользователи
    active = parse_metric(lines, 'bot_active_users')
    print(f"\n👥 Активные пользователи: {active}")
    
    # Запланированные проверки
    scheduled_success = parse_metric(lines, 'bot_scheduled_checks_total{status="success"}')
    scheduled_error = parse_metric(lines, 'bot_scheduled_checks_total{status="error"}')
    if scheduled_success != "0" or scheduled_error != "0":
        print(f"\n⏰ Запланированные проверки:")
        print(f"   Успешные: {scheduled_success}")
        print(f"   Ошибки: {scheduled_error}")
    
    print("\n" + "="*60)
    print("💡 Полные метрики: http://localhost:8000/metrics")
    print("="*60 + "\n")

if __name__ == "__main__":
    print("🚀 Просмотр метрик MapTrack Bot")
    print("Нажмите Ctrl+C для выхода\n")
    
    try:
        while True:
            display_metrics()
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n\n👋 Выход...")
