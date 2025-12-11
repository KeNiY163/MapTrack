"""
Сервис для отслеживания контейнеров через Selenium
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from math import radians, sin, cos, sqrt, atan2
import time
import os

# Поддержка запуска как скрипта и как модуля
try:
    from .geocache import geocode
except ImportError:
    # Если запускаем как скрипт
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.geocache import geocode

# Импортируем метрики (с проверкой)
try:
    from .metrics import track_selenium_duration
except ImportError:
    try:
        from src.metrics import track_selenium_duration
    except ImportError:
        def track_selenium_duration(duration): pass

# ===== USER-AGENT =====
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


class ContainerTrackerService:
    """Сервис для отслеживания контейнеров через веб-скрапинг"""
    
    TRACKING_URL = 'https://isales.trcont.com/?tab=tracking&lang=ru'
    
    def __init__(self, enable_screenshots=True):
        """
        Инициализация сервиса
        
        Args:
            enable_screenshots: Включить сохранение скриншотов для отладки
        """
        self.enable_screenshots = enable_screenshots
        if enable_screenshots:
            os.makedirs("screenshots", exist_ok=True)
    
    def _create_driver(self):
        """Создает и настраивает Chrome WebDriver"""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument(f'user-agent={USER_AGENT}')
        
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
        except Exception:
            driver = webdriver.Chrome(options=options)
        
        return driver
    
    def _take_screenshot(self, driver, filename):
        """Сохранить скриншот браузера"""
        if not self.enable_screenshots:
            return None
        
        try:
            screenshot_path = f"screenshots/{filename}"
            driver.save_screenshot(screenshot_path)
            return screenshot_path
        except Exception:
            return None
    
    def _handle_cookie_popup(self, driver):
        """Обработка окна с cookie"""
        try:
            wait = WebDriverWait(driver, 5)
            accept_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Принять')]"))
            )
            accept_btn.click()
            time.sleep(1)
        except Exception:
            pass
    
    def _handle_modal_windows(self, driver):
        """Обработка модальных окон"""
        try:
            wait = WebDriverWait(driver, 3)
            close_btns = driver.find_elements(By.CSS_SELECTOR, '[class*="close"], [class*="Close"]')
            for btn in close_btns:
                try:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        break
                except Exception:
                    pass
        except Exception:
            pass
    
    def _find_input_field(self, driver):
        """Находит поле ввода для трек-номера"""
        wait = WebDriverWait(driver, 10)
        
        try:
            input_fields = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'input[type="text"]'))
            )
            
            if input_fields:
                input_field = input_fields[-1]
                
                # Прокручиваем к элементу в центр экрана
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", input_field)
                time.sleep(1)
                
                wait.until(EC.visibility_of(input_field))
                wait.until(EC.element_to_be_clickable(input_field))
                return input_field
        except Exception as e:
            self._take_screenshot(driver, "03_css_failed.png")
            try:
                input_field = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@type='text']"))
                )
                return input_field
            except Exception as e2:
                self._take_screenshot(driver, "04_xpath_failed.png")
                raise
    
    def _enter_track_number(self, driver, input_field, track_number):
        """Вводит трек-номер в поле"""
        try:
            input_field.clear()
            time.sleep(0.3)
            input_field.send_keys(track_number)
        except Exception as e:
            self._take_screenshot(driver, "06_sendkeys_failed.png")
            # Безопасная передача значения через параметры (защита от инъекций)
            driver.execute_script("arguments[0].value = arguments[1];", input_field, track_number)
    
    def _submit_search(self, driver, input_field):
        """Отправляет форму поиска"""
        try:
            input_field.send_keys(Keys.RETURN)
        except Exception:
            try:
                search_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Поиск')] | //button[@type='submit']")
                driver.execute_script("arguments[0].click();", search_btn)
            except Exception:
                self._take_screenshot(driver, "08_submit_failed.png")
                raise
    
    def _wait_for_results(self, driver):
        """Ожидает загрузки результатов"""
        time.sleep(2)
        
        try:
            wait = WebDriverWait(driver, 10)
            wait.until(lambda d: len(d.find_element(By.TAG_NAME, 'body').text) > 100)
        except Exception:
            self._take_screenshot(driver, "09_results_timeout.png")
            # Продолжаем, так как это не критично
        
        time.sleep(3)
    
    def _parse_results(self, driver, track_number):
        """Парсит результаты со страницы"""
        page_text = driver.find_element(By.TAG_NAME, 'body').text
        lines = [l.strip() for l in page_text.split('\n') if l.strip()]
        
        try:
            location_idx = next(i for i, x in enumerate(lines) if 'Местонахождение' in x)
            action_idx = next(i for i, x in enumerate(lines) if 'Действие' in x)
            country_idx = next(i for i, x in enumerate(lines) if 'Страна' in x)
            date_idx = next(i for i, x in enumerate(lines) if 'Дата и время' in x)
            
            container_number = track_number
            location = lines[location_idx + 1] if location_idx + 1 < len(lines) else "N/A"
            action = lines[action_idx + 1] if action_idx + 1 < len(lines) else "N/A"
            country = lines[country_idx + 1] if country_idx + 1 < len(lines) else "N/A"
            date_time = lines[date_idx + 1] if date_idx + 1 < len(lines) else "N/A"
            
            return {
                'container_number': container_number,
                'location': location,
                'action': action,
                'country': country,
                'date_time': date_time
            }
        except Exception as e:
            raise Exception(
                f"Не найдена информация о контейнере. Проверьте корректность номера или попробуйте позже - "
                f"возможно, информация еще не появилась в системе. Ошибка: {e}"
            )
    
    def _get_coordinates(self, location, destination_city):
        """Получает координаты и рассчитывает расстояние (с кешированием)"""
        try:
            # Используем кеш для получения координат
            coords = geocode(location, 'Russia')
            
            if coords:
                station_lat, station_lon = coords
                
                # Получаем координаты города назначения (тоже через кеш)
                dest_coords = geocode(destination_city, 'Russia')
                
                if dest_coords:
                    dest_lat, dest_lon = dest_coords
                    distance = self._calculate_distance(station_lat, station_lon, dest_lat, dest_lon)
                    return coords, distance
                
                return coords, None
            else:
                return None, None
            
        except Exception:
            return None, None
    
    @staticmethod
    def _calculate_distance(lat1, lon1, lat2, lon2):
        """Рассчитывает расстояние между двумя точками (формула гаверсинуса)"""
        R = 6371  # Радиус Земли в км
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c
    
    def track(self, track_number, destination_city='Москва'):
        """
        Основной метод для отслеживания контейнера
        
        Args:
            track_number: Номер контейнера (например, TKRU4471976)
            destination_city: Город назначения для расчета расстояния
            
        Returns:
            tuple: (message, coords, distance) - сообщение, координаты и расстояние
        """
        start_time = time.time()
        selenium_start = start_time
        driver = None
        
        try:
            # Создаем драйвер
            driver = self._create_driver()
            
            # Загружаем страницу
            driver.get(self.TRACKING_URL)
            time.sleep(4)
            
            # Обрабатываем всплывающие окна
            self._handle_cookie_popup(driver)
            self._handle_modal_windows(driver)
            time.sleep(2)
            
            # Находим и заполняем поле ввода
            input_field = self._find_input_field(driver)
            
            self._enter_track_number(driver, input_field, track_number)
            time.sleep(1)
            
            # Отправляем форму
            self._submit_search(driver, input_field)
            
            # Ждем результаты
            self._wait_for_results(driver)
            
            # Парсим результаты
            result_data = self._parse_results(driver, track_number)
            
            # Формируем сообщение
            message = (
                f"📦 Отслеживание контейнера\n\n"
                f"№ Контейнер: {result_data['container_number']}\n\n"
                f"📍 Местонахождение: {result_data['location']}\n"
                f"⚙️ Действие: {result_data['action']}\n"
                f"🌍 Страна: {result_data['country']}\n"
                f"🕒 Дата и время: {result_data['date_time']}\n"
            )
            
            # Получаем координаты и расстояние
            coords, distance = self._get_coordinates(result_data['location'], destination_city)
            
            if distance is not None:
                message += f"\n   Дистанция до города {destination_city}: ~{distance:.0f} км."
            
            selenium_duration = time.time() - selenium_start
            track_selenium_duration(selenium_duration)
            
            return message, coords, distance
        
        except Exception as e:
            # Делаем скриншот при любой ошибке
            if driver:
                try:
                    self._take_screenshot(driver, "10_error_final.png")
                except Exception:
                    pass
            raise
        
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

