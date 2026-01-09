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
            # Устанавливаем рабочую директорию на корень проекта для правильных путей
            project_root = os.path.dirname(os.path.dirname(__file__))
            # Запускаем бот как модуль
            process = subprocess.Popen(
                [sys.executable, "-m", "src.bot"],
                cwd=project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False,  # Читаем как байты, чтобы контролировать декодирование
                bufsize=1
            )
            
            for line_bytes in process.stdout:
                try:
                    # Декодируем с UTF-8 и обработкой ошибок
                    line = line_bytes.decode('utf-8', errors='replace')
                    print(line, end='')
                except (UnicodeEncodeError, UnicodeDecodeError) as e:
                    # Безопасный вывод при проблемах с кодировкой
                    try:
                        safe_line = line_bytes.decode('utf-8', errors='replace').encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                        print(safe_line, end='')
                    except Exception:
                        # Если и это не помогло, пропускаем строку
                        pass
            
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
