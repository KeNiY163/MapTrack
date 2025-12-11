import subprocess
import sys
import os
import time
from datetime import datetime

def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

def run_bot():
    restart_count = 0
    max_restarts_per_hour = 10
    restart_times = []
    
    while True:
        try:
            log("🚀 Запуск бота...")
            # Путь к bot.py - он в той же папке
            bot_path = os.path.join(os.path.dirname(__file__), "bot.py")
            # Устанавливаем рабочую директорию на корень проекта для правильных путей
            project_root = os.path.dirname(os.path.dirname(__file__))
            process = subprocess.Popen(
                [sys.executable, bot_path],
                cwd=project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            for line in process.stdout:
                print(line, end='')
            
            process.wait()
            
            log(f"⚠️ Бот остановлен с кодом: {process.returncode}")
            
            current_time = time.time()
            restart_times = [t for t in restart_times if current_time - t < 3600]
            
            if len(restart_times) >= max_restarts_per_hour:
                log(f"❌ Превышен лимит перезапусков ({max_restarts_per_hour}/час). Ожидание 1 час...")
                time.sleep(3600)
                restart_times.clear()
            
            restart_times.append(current_time)
            restart_count += 1
            
            log(f"🔄 Перезапуск #{restart_count} через 5 секунд...")
            time.sleep(5)
            
        except KeyboardInterrupt:
            log("⛔ Остановка по Ctrl+C")
            if 'process' in locals():
                process.terminate()
            break
        except Exception as e:
            log(f"❌ Критическая ошибка: {e}")
            time.sleep(10)

if __name__ == "__main__":
    log("🤖 Запуск системы автоперезапуска бота")
    run_bot()
