"""Скрипт для организации структуры репозитория"""
import os
import shutil
import sys
from pathlib import Path

# Исправление кодировки для Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_DIR = Path(__file__).parent

# Структура папок
STRUCTURE = {
    'src': [
        'bot.py',
        'bot_runner.py',
        'metrics.py',
        'container_tracker.py',
        'view_metrics.py',
    ],
    'docs': [
        '*.md',
        '*.txt',
    ],
    'tests': [
        'test_multithreading.py',
        'quick_thread_test.py',
    ],
    'scripts': [
        'deploy.sh',
        'install.sh',
        'start_bot.bat',
    ],
    'data': [
        'history.json',
        'schedule.json',
        'cities.json',
    ],
    'config': [
        'prometheus.yml',
        'docker-compose.yml',
        'docker-compose.simple.yml',
    ],
    'docker': [
        'Dockerfile',
        'Dockerfile.simple',
    ],
    'trash': [
        'ReqPozition.py',
    ],
}

# Исключения для docs
DOCS_EXCLUDE = ['requirements.txt']

def create_dirs():
    """Создать все необходимые папки"""
    for folder in STRUCTURE.keys():
        folder_path = BASE_DIR / folder
        if folder_path.exists() and not folder_path.is_dir():
            # Если это файл, удаляем его
            folder_path.unlink()
        folder_path.mkdir(exist_ok=True)
        print(f"✅ Создана/проверена папка: {folder}")

def move_files():
    """Переместить файлы в соответствующие папки"""
    moved = 0
    
    # Перемещаем конкретные файлы
    for folder, files in STRUCTURE.items():
        if folder == 'docs':
            continue  # Обработаем отдельно
        
        for file_pattern in files:
            if '*' in file_pattern:
                continue  # Пропускаем паттерны
            
            src_path = BASE_DIR / file_pattern
            if src_path.exists():
                dst_path = BASE_DIR / folder / file_pattern
                try:
                    shutil.move(str(src_path), str(dst_path))
                    print(f"✅ {file_pattern} -> {folder}/")
                    moved += 1
                except Exception as e:
                    print(f"❌ Ошибка перемещения {file_pattern}: {e}")
    
    # Обрабатываем docs отдельно (паттерны)
    docs_dir = BASE_DIR / 'docs'
    for file in BASE_DIR.glob('*.md'):
        if file.name not in DOCS_EXCLUDE:
            try:
                shutil.move(str(file), str(docs_dir / file.name))
                print(f"✅ {file.name} -> docs/")
                moved += 1
            except Exception as e:
                print(f"❌ Ошибка перемещения {file.name}: {e}")
    
    for file in BASE_DIR.glob('*.txt'):
        if file.name not in DOCS_EXCLUDE:
            try:
                shutil.move(str(file), str(docs_dir / file.name))
                print(f"✅ {file.name} -> docs/")
                moved += 1
            except Exception as e:
                print(f"❌ Ошибка перемещения {file.name}: {e}")
    
    return moved

if __name__ == '__main__':
    print("🚀 Организация структуры репозитория...")
    print("=" * 50)
    
    create_dirs()
    print()
    
    moved = move_files()
    print()
    print("=" * 50)
    print(f"✅ Перемещено файлов: {moved}")
    print("✅ Структура репозитория организована!")

