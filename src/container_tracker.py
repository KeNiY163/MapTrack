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
import json
from typing import Optional, Dict, Any

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
    
    def _create_driver(self, enable_network_logging=False):
        """Создает и настраивает Chrome WebDriver с оптимизацией для снижения нагрузки
        
        Args:
            enable_network_logging: Включить логирование сетевых запросов для перехвата AJAX
        """
        options = Options()
        
        # Базовые опции для headless режима
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        # Отключение GPU и графики
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-background-networking')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-backgrounding-occluded-windows')
        
        # Отключение функций, которые нагружают систему
        options.add_argument('--disable-features=TranslateUI')
        options.add_argument('--disable-ipc-flooding-protection')
        options.add_argument('--disable-hang-monitor')
        options.add_argument('--disable-prompt-on-repost')
        options.add_argument('--disable-sync')
        options.add_argument('--disable-web-resources')
        options.add_argument('--disable-client-side-phishing-detection')
        options.add_argument('--disable-component-update')
        options.add_argument('--disable-default-apps')
        options.add_argument('--disable-domain-reliability')
        options.add_argument('--disable-features=AudioServiceOutOfProcess')
        
        # Отключение изображений и медиа для экономии ресурсов
        prefs = {
            'profile.managed_default_content_settings.images': 2,  # Блокировать изображения
            'profile.default_content_setting_values.notifications': 2,  # Блокировать уведомления
            'profile.managed_default_content_settings.media_stream': 2,  # Блокировать медиа
        }
        options.add_experimental_option('prefs', prefs)
        
        # Отключение логирования (кроме случаев когда нужно логирование сети)
        if not enable_network_logging:
            options.add_experimental_option('excludeSwitches', ['enable-logging'])
        else:
            # Для перехвата сетевых запросов включаем performance logging
            options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        
        options.add_experimental_option('useAutomationExtension', False)
        
        # User agent
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
            track_number: Номер контейнера (например, TKRU1234567)
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
    
    def track_contract(self, contract_number: str) -> Optional[Dict[str, Any]]:
        """
        Получает данные по договору через Selenium с перехватом AJAX ответа
        
        Args:
            contract_number: Номер договора (например, 123456АБ7890)
            
        Returns:
            dict с данными по договору или None если ошибка
        """
        start_time = time.time()
        driver = None
        ajax_response = None
        
        # Функция для безопасного вывода (локальная, чтобы избежать циклических импортов)
        def safe_print(text: str):
            try:
                print(text)
                import sys
                sys.stdout.flush()
            except UnicodeEncodeError:
                safe_text = text.encode('ascii', 'ignore').decode('ascii')
                print(safe_text if safe_text.strip() else str(text))
                import sys
                sys.stdout.flush()
        
        try:
            safe_print(f"🔍 [SELENIUM] Начало получения данных по договору {contract_number} через Selenium")
            
            # Создаем драйвер с логированием сети
            driver = self._create_driver(enable_network_logging=True)
            
            # Включаем перехват сетевых запросов через Chrome DevTools Protocol ДО загрузки страницы
            driver.execute_cdp_cmd('Network.enable', {})
            safe_print(f"✅ [SELENIUM] Включен перехват сетевых запросов")
            
            # Загружаем страницу
            contract_url = 'https://gs25.ru/status/'
            safe_print(f"🌐 [SELENIUM] Загрузка страницы для поиска по договору")
            driver.get(contract_url)
            time.sleep(4)
            
            # Обрабатываем всплывающие окна
            self._handle_cookie_popup(driver)
            self._handle_modal_windows(driver)
            time.sleep(2)
            
            # Находим поле ввода для номера договора
            safe_print(f"🔍 [SELENIUM] Поиск поля ввода для договора {contract_number}")
            wait = WebDriverWait(driver, 10)
            
            # Ищем поле ввода (может быть input[type="text"] или другой селектор)
            try:
                input_fields = wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'input[type="text"]'))
                )
                if input_fields:
                    input_field = input_fields[0]  # Берем первое поле
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", input_field)
                    time.sleep(1)
                    wait.until(EC.visibility_of(input_field))
                    wait.until(EC.element_to_be_clickable(input_field))
                    safe_print(f"✅ [SELENIUM] Поле ввода найдено")
                else:
                    raise Exception("Поле ввода не найдено")
            except Exception as e:
                self._take_screenshot(driver, "contract_input_not_found.png")
                safe_print(f"⚠️ [SELENIUM] Ошибка поиска поля ввода: {e}")
                # Попробуем другой селектор
                input_field = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@type='text'] | //input[contains(@placeholder, 'договор') or contains(@placeholder, 'Договор')]"))
                )
                safe_print(f"✅ [SELENIUM] Поле ввода найдено через XPath")
            
            # Вводим номер договора
            safe_print(f"⌨️ [SELENIUM] Ввод номера договора: {contract_number}")
            input_field.clear()
            time.sleep(0.3)
            input_field.send_keys(contract_number)
            time.sleep(1)
            
            # Отправляем форму (ENTER или поиск кнопки)
            safe_print(f"📤 [SELENIUM] Отправка формы поиска")
            try:
                input_field.send_keys(Keys.RETURN)
            except Exception:
                try:
                    search_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Поиск')] | //button[@type='submit'] | //input[@type='submit']")
                    driver.execute_script("arguments[0].click();", search_btn)
                except Exception:
                    safe_print(f"⚠️ [SELENIUM] Не удалось найти кнопку поиска, пробуем через JS")
                    driver.execute_script("arguments[0].form.submit();", input_field)
            
            # Ждем AJAX запроса и перехватываем ответ
            safe_print(f"⏳ [SELENIUM] Ожидание AJAX ответа...")
            time.sleep(5)  # Даем время на выполнение AJAX запроса
            
            # Получаем логи производительности для перехвата сетевых запросов
            logs = driver.get_log('performance')
            safe_print(f"📋 [SELENIUM] Получено {len(logs)} записей логов производительности")
            
            # Хранилище для request_id для получения тела ответа
            ajax_request_id = None
            
            # Ищем ответ от admin-ajax.php в логах
            for log in logs:
                try:
                    log_data = json.loads(log['message'])
                    message = log_data.get('message', {})
                    method = message.get('method', '')
                    params = message.get('params', {})
                    
                    # Ищем ответ от admin-ajax.php
                    if method == 'Network.responseReceived':
                        response = params.get('response', {})
                        url = response.get('url', '')
                        
                        if 'admin-ajax.php' in url:
                            safe_print(f"✅ [SELENIUM] Найден ответ от admin-ajax.php: {url}")
                            ajax_request_id = params.get('requestId', '')
                            safe_print(f"🆔 [SELENIUM] Request ID: {ajax_request_id}")
                            break
                    
                except (json.JSONDecodeError, KeyError, Exception) as e:
                    continue
            
            # Если нашли request_id, получаем тело ответа через CDP
            if ajax_request_id:
                try:
                    # Ждем завершения запроса
                    time.sleep(2)
                    response_body = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': ajax_request_id})
                    body = response_body.get('body', '')
                    base64_encoded = response_body.get('base64Encoded', False)
                    
                    safe_print(f"📄 [SELENIUM] Получено тело ответа, длина: {len(body)} символов, base64: {base64_encoded}")
                    
                    # Если ответ в base64, декодируем
                    if base64_encoded:
                        import base64
                        body = base64.b64decode(body).decode('utf-8', errors='ignore')
                    
                    safe_print(f"📄 [SELENIUM] Первые 1000 символов ответа:\n{body[:1000]}")
                    safe_print(f"📄 [SELENIUM] Полный ответ:\n{body}")
                    
                    # Пытаемся распарсить JSON
                    try:
                        ajax_response = json.loads(body)
                        safe_print(f"✅ [SELENIUM] JSON успешно распарсен")
                        safe_print(f"📦 [SELENIUM] Структура ответа: {type(ajax_response)}, ключи: {list(ajax_response.keys()) if isinstance(ajax_response, dict) else 'не словарь'}")
                        import json as json_module
                        safe_print(f"📦 [SELENIUM] Полное содержимое JSON ответа:\n{json_module.dumps(ajax_response, ensure_ascii=False, indent=2)}")
                    except json.JSONDecodeError as e:
                        safe_print(f"⚠️ [SELENIUM] Ошибка парсинга JSON: {e}")
                        safe_print(f"📄 [SELENIUM] Ответ не является JSON, возвращаем текст")
                        ajax_response = {'raw': body, 'error': 'not_json'}
                        
                except Exception as e:
                    safe_print(f"❌ [SELENIUM] Ошибка получения тела ответа через CDP: {e}")
                    import traceback
                    safe_print(f"📋 [SELENIUM] Traceback:\n{traceback.format_exc()}")
            
            # Если не нашли через логи, пробуем получить через выполнение JS на странице
            if not ajax_response:
                safe_print(f"⚠️ [SELENIUM] AJAX ответ не найден в логах, пробуем через выполнение JS на странице")
                time.sleep(2)  # Даем еще немного времени
                
                # Пробуем найти результат на странице напрямую
                try:
                    page_text = driver.find_element(By.TAG_NAME, 'body').text
                    safe_print(f"📄 [SELENIUM] Текст страницы получен, длина: {len(page_text)} символов")
                    safe_print(f"📄 [SELENIUM] Первые 1000 символов страницы:\n{page_text[:1000]}")
                    # Здесь можно попробовать распарсить данные со страницы если AJAX не сработал
                except Exception as e:
                    safe_print(f"⚠️ [SELENIUM] Ошибка получения текста страницы: {e}")
            
            selenium_duration = time.time() - start_time
            track_selenium_duration(selenium_duration)
            safe_print(f"⏱️ [SELENIUM] Время выполнения: {selenium_duration:.2f} секунд")
            
            return ajax_response
            
        except Exception as e:
            safe_print(f"❌ [SELENIUM] Ошибка при получении данных по договору {contract_number}: {e}")
            import traceback
            safe_print(f"📋 [SELENIUM] Traceback:\n{traceback.format_exc()}")
            
            # Делаем скриншот при ошибке
            if driver:
                try:
                    self._take_screenshot(driver, f"contract_error_{contract_number.replace('/', '_')}.png")
                except Exception:
                    pass
            return None
            
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

