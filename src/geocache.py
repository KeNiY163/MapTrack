"""
Кеш для результатов геокодинга Nominatim
Снижает количество запросов к API и ускоряет работу
"""
import json
import os
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

import requests

# Импортируем метрики (с проверкой на случай если модуль не доступен)
try:
    from .metrics import track_geocache_hit, track_geocache_miss, update_geocache_size, track_geocoding_duration
except ImportError:
    try:
        # Если запускаем как скрипт
        from src.metrics import track_geocache_hit, track_geocache_miss, update_geocache_size, track_geocoding_duration
    except ImportError:
        # Заглушки если метрики не доступны
        def track_geocache_hit(): pass
        def track_geocache_miss(): pass
        def update_geocache_size(size): pass
        def track_geocoding_duration(duration): pass

# Путь к файлу кеша
BASE_DIR = Path(__file__).parent.parent
CACHE_FILE = BASE_DIR / 'data' / 'geocache.json'
CACHE_TTL = 30 * 24 * 60 * 60  # 30 дней в секундах

# Блокировка для безопасной работы с кешем
cache_lock = threading.Lock()

# Загрузка кеша
def _load_cache() -> dict:
    """Загружает кеш из файла"""
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Сохранение кеша
def _save_cache(cache: dict):
    """Сохраняет кеш в файл"""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def geocode(query: str, country: str = 'Russia') -> Optional[Tuple[float, float]]:
    """
    Геокодинг с кешированием
    
    Args:
        query: Название места для поиска
        country: Страна (по умолчанию Russia)
        
    Returns:
        Tuple[lat, lon] или None если не найдено
    """
    # Нормализуем запрос для кеша
    cache_key = f"{query},{country}".lower().strip()
    
    with cache_lock:
        cache = _load_cache()
        current_time = time.time()
        
        # Проверяем кеш
        if cache_key in cache:
            cached_data = cache[cache_key]
            # Проверяем срок действия
            if current_time - cached_data.get('timestamp', 0) < CACHE_TTL:
                track_geocache_hit()
                update_geocache_size(len(cache))
                return (cached_data['lat'], cached_data['lon'])
            else:
                # Кеш устарел, удаляем
                del cache[cache_key]
        
        # Делаем запрос к API
        track_geocache_miss()
        geocoding_start = time.time()
        try:
            geocode_url = f"https://nominatim.openstreetmap.org/search?q={query},{country}&format=json&limit=1"
            headers = {'User-Agent': 'Mozilla/5.0 (MapTrack Bot)'}
            response = requests.get(geocode_url, headers=headers, timeout=10)
            data = response.json()
            
            if data and isinstance(data, list) and len(data) > 0:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                
                # Сохраняем в кеш
                cache[cache_key] = {
                    'lat': lat,
                    'lon': lon,
                    'timestamp': current_time,
                    'query': query
                }
                _save_cache(cache)
                
                # Обновляем метрики
                geocoding_duration = time.time() - geocoding_start
                track_geocoding_duration(geocoding_duration)
                update_geocache_size(len(cache))
                
                return (lat, lon)
            else:
                return None
                
        except Exception:
            return None

def get_cache_stats() -> dict:
    """Возвращает статистику кеша"""
    with cache_lock:
        cache = _load_cache()
        current_time = time.time()
        
        total = len(cache)
        valid = sum(1 for item in cache.values() 
                   if current_time - item.get('timestamp', 0) < CACHE_TTL)
        expired = total - valid
        
        return {
            'total': total,
            'valid': valid,
            'expired': expired,
            'cache_file': str(CACHE_FILE)
        }

def clear_expired_cache():
    """Очищает устаревшие записи из кеша"""
    with cache_lock:
        cache = _load_cache()
        current_time = time.time()
        
        initial_count = len(cache)
        cache = {
            k: v for k, v in cache.items()
            if current_time - v.get('timestamp', 0) < CACHE_TTL
        }
        
        removed = initial_count - len(cache)
        if removed > 0:
            _save_cache(cache)
        
        return removed

