# Кеш Nominatim и расширенные метрики ✅

## Что сделано

### 1. Кеш Nominatim ✅

Создан модуль `src/geocache.py` для кеширования результатов геокодинга.

**Преимущества:**
- ✅ Снижает количество запросов к Nominatim API
- ✅ Ускоряет повторные запросы (мгновенный ответ из кеша)
- ✅ Срок жизни кеша: 30 дней
- ✅ Автоматическая очистка устаревших записей
- ✅ Безопасная работа в многопоточной среде (блокировки)

**Как работает:**
1. При запросе координат сначала проверяется кеш
2. Если запись есть и не устарела - возвращается из кеша
3. Если нет - делается запрос к API и результат сохраняется в кеш
4. Кеш хранится в `data/geocache.json`

**Метрики:**
- `bot_geocache_hits_total` - количество попаданий в кеш
- `bot_geocache_misses_total` - количество промахов (запросов к API)
- `bot_geocache_size` - размер кеша (количество записей)
- `bot_geocoding_duration_seconds` - длительность геокодинга

### 2. Расширенные метрики ✅

Добавлены новые метрики в `src/metrics.py`:

**Геокодинг:**
- `bot_geocache_hits_total` - попадания в кеш
- `bot_geocache_misses_total` - промахи кеша
- `bot_geocache_size` - размер кеша
- `bot_geocoding_duration_seconds` - длительность геокодинга

**Selenium:**
- `bot_selenium_duration_seconds` - длительность операций Selenium

**Все метрики:**
- `bot_messages_total` - сообщения (по типам)
- `bot_commands_total` - команды
- `bot_errors_total` - ошибки (по типам)
- `bot_track_requests_total` - запросы отслеживания
- `bot_track_duration_seconds` - длительность отслеживания
- `bot_active_users` - активные пользователи
- `bot_scheduled_checks_total` - запланированные проверки
- `bot_geocache_hits_total` - попадания в кеш геокодинга
- `bot_geocache_misses_total` - промахи кеша
- `bot_geocache_size` - размер кеша
- `bot_geocoding_duration_seconds` - длительность геокодинга
- `bot_selenium_duration_seconds` - длительность Selenium

## Использование

Кеш работает автоматически - никаких дополнительных действий не требуется.

Для просмотра статистики кеша:
```python
from src.geocache import get_cache_stats

stats = get_cache_stats()
print(f"Всего записей: {stats['total']}")
print(f"Действительных: {stats['valid']}")
print(f"Устаревших: {stats['expired']}")
```

Для очистки устаревших записей:
```python
from src.geocache import clear_expired_cache

removed = clear_expired_cache()
print(f"Удалено {removed} записей")
```

## Файлы

- `src/geocache.py` - модуль кеширования
- `data/geocache.json` - файл кеша (создается автоматически)

## Преимущества

✅ **Производительность** - повторные запросы выполняются мгновенно
✅ **Экономия API** - меньше запросов к Nominatim
✅ **Мониторинг** - метрики показывают эффективность кеша
✅ **Надежность** - безопасная работа в многопоточной среде



