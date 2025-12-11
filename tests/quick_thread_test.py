"""
Быстрый тест многопоточности - показывает, работают ли потоки параллельно
"""
import threading
import time
import sys
from datetime import datetime

# Исправление кодировки для Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_threading():
    """Простой тест параллельности потоков"""
    print("="*60)
    print("🧪 БЫСТРЫЙ ТЕСТ МНОГОПОТОЧНОСТИ")
    print("="*60)
    
    results = []
    lock = threading.Lock()
    
    def worker(worker_id, delay=3):
        """Рабочая функция, симулирующая запрос"""
        thread_id = threading.current_thread().ident
        thread_name = threading.current_thread().name
        
        start = time.time()
        timestamp_start = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        
        with lock:
            print(f"[{timestamp_start}] 🚀 Поток #{worker_id} начал работу | "
                  f"Thread ID: {thread_id} | Name: {thread_name}")
        
        # Симулируем работу
        time.sleep(delay)
        
        end = time.time()
        duration = end - start
        timestamp_end = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        
        with lock:
            print(f"[{timestamp_end}] ✅ Поток #{worker_id} завершил работу | "
                  f"Время выполнения: {duration:.2f}с")
        
        results.append({
            'worker_id': worker_id,
            'thread_id': thread_id,
            'start': start,
            'end': end,
            'duration': duration
        })
    
    # Запускаем 5 потоков одновременно
    print("\n📌 Запускаю 5 потоков одновременно (каждый работает 3 секунды)...")
    print("   Если многопоточность работает, все потоки завершатся примерно через 3 секунды")
    print("   Если нет - они завершатся последовательно (около 15 секунд)\n")
    
    threads = []
    overall_start = time.time()
    
    for i in range(1, 6):
        thread = threading.Thread(target=worker, args=(i, 3), daemon=True)
        threads.append(thread)
        thread.start()
        time.sleep(0.1)  # Небольшая задержка для визуализации
    
    # Ждем завершения всех потоков
    for thread in threads:
        thread.join()
    
    overall_duration = time.time() - overall_start
    
    print(f"\n📊 РЕЗУЛЬТАТЫ:")
    print(f"   Всего потоков: 5")
    print(f"   Время работы одного потока: 3 секунды")
    print(f"   Общее время выполнения: {overall_duration:.2f} секунд")
    print(f"   Ожидаемое время (последовательно): 15 секунд")
    
    if overall_duration < 5:
        print(f"\n   ✅ МНОГОПОТОЧНОСТЬ РАБОТАЕТ!")
        print(f"   Потоки выполнялись параллельно (ускорение ~{15/overall_duration:.1f}x)")
    elif overall_duration < 10:
        print(f"\n   ⚠️ Частичная параллельность")
        print(f"   Возможно, ограничение на количество одновременных потоков")
    else:
        print(f"\n   ❌ МНОГОПОТОЧНОСТЬ НЕ РАБОТАЕТ")
        print(f"   Потоки выполнялись последовательно")
    
    # Проверяем параллельность по времени старта
    start_times = [r['start'] for r in results]
    time_diff = max(start_times) - min(start_times)
    print(f"\n   Разница во времени старта потоков: {time_diff:.3f}с")
    
    if time_diff < 1:
        print("   ✅ Потоки запускаются одновременно")
    else:
        print("   ⚠️ Потоки запускаются с задержкой")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    test_threading()

