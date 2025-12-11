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

# Расширенные метрики
geocache_hits = Counter('bot_geocache_hits_total', 'Total geocache hits')
geocache_misses = Counter('bot_geocache_misses_total', 'Total geocache misses')
geocache_size = Gauge('bot_geocache_size', 'Number of entries in geocache')
geocoding_duration = Histogram('bot_geocoding_duration_seconds', 'Geocoding request duration')
selenium_duration = Histogram('bot_selenium_duration_seconds', 'Selenium operations duration')

def start_metrics_server(port=8000):
    """Запуск HTTP сервера для метрик"""
    try:
        start_http_server(port)
        print(f"📊 Metrics server started on port {port}")
        print(f"📊 Metrics available at http://0.0.0.0:{port}/metrics")
    except Exception as e:
        print(f"⚠️ Failed to start metrics server: {e}")

def track_message(msg_type='text'):
    """Учёт сообщения"""
    messages_total.labels(type=msg_type).inc()

def track_command(command):
    """Учёт команды"""
    commands_total.labels(command=command).inc()

def track_error(error_type):
    """Учёт ошибки"""
    errors_total.labels(type=error_type).inc()

def track_tracking_request():
    """Учёт запроса отслеживания"""
    track_requests.inc()

def track_tracking_duration(duration):
    """Учёт длительности отслеживания"""
    track_duration.observe(duration)

def update_active_users(count):
    """Обновление количества активных пользователей"""
    active_users.set(count)

def track_scheduled_check(status='success'):
    """Учёт запланированной проверки"""
    scheduled_checks.labels(status=status).inc()

def track_geocache_hit():
    """Учёт попадания в кеш геокодинга"""
    geocache_hits.inc()

def track_geocache_miss():
    """Учёт промаха кеша геокодинга"""
    geocache_misses.inc()

def update_geocache_size(size: int):
    """Обновление размера кеша"""
    geocache_size.set(size)

def track_geocoding_duration(duration: float):
    """Учёт длительности геокодинга"""
    geocoding_duration.observe(duration)

def track_selenium_duration(duration: float):
    """Учёт длительности операций Selenium"""
    selenium_duration.observe(duration)
