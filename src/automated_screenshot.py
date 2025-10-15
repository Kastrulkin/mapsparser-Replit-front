#!/usr/bin/env python3
"""
Модуль для автоматического создания скриншотов карточек Яндекс.Карт
"""
import os
import time
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class YandexMapsScreenshotter:
    """Класс для автоматического создания скриншотов карточек Яндекс.Карт"""
    
    def __init__(self, headless=True, window_size=(1920, 1080)):
        self.headless = headless
        self.window_size = window_size
        self.driver = None
        
    def _setup_driver(self):
        """Настройка Chrome WebDriver"""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument("--headless")
        
        # Настройки для стабильной работы
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--ignore-ssl-errors")
        chrome_options.add_argument("--ignore-certificate-errors-spki-list")
        
        # Установка размера окна
        chrome_options.add_argument(f"--window-size={self.window_size[0]},{self.window_size[1]}")
        
        # Отключение уведомлений
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        
        # User-Agent для обхода блокировок
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_window_size(*self.window_size)
            logger.info("Chrome WebDriver успешно инициализирован")
            return True
        except Exception as e:
            logger.error(f"Ошибка инициализации WebDriver: {e}")
            return False
    
    def take_screenshot(self, yandex_maps_url, output_path=None):
        """
        Создание скриншота карточки компании на Яндекс.Картах
        
        Args:
            yandex_maps_url (str): URL карточки на Яндекс.Картах
            output_path (str, optional): Путь для сохранения скриншота
            
        Returns:
            str: Путь к созданному скриншоту или None в случае ошибки
        """
        if not self._setup_driver():
            return None
            
        try:
            logger.info(f"Открываем URL: {yandex_maps_url}")
            self.driver.get(yandex_maps_url)
            
            # Ждем загрузки страницы
            wait = WebDriverWait(self.driver, 20)
            
            # Ждем появления карточки организации
            try:
                # Ищем карточку организации
                card_element = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='card']"))
                )
                logger.info("Карточка организации найдена")
            except:
                # Если карточка не найдена, ищем альтернативные селекторы
                try:
                    card_element = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".card"))
                    )
                    logger.info("Карточка организации найдена (альтернативный селектор)")
                except:
                    logger.warning("Карточка организации не найдена, делаем скриншот всей страницы")
            
            # Дополнительное ожидание для полной загрузки
            time.sleep(3)
            
            # Прокручиваем к началу карточки
            if 'card_element' in locals():
                self.driver.execute_script("arguments[0].scrollIntoView(true);", card_element)
                time.sleep(1)
            
            # Создаем временный файл если путь не указан
            if output_path is None:
                temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                output_path = temp_file.name
                temp_file.close()
            
            # Создаем скриншот
            self.driver.save_screenshot(output_path)
            logger.info(f"Скриншот сохранен: {output_path}")
            
            # Обрезаем скриншот если нужно (убираем лишние элементы)
            self._crop_screenshot(output_path)
            
            return output_path
            
        except Exception as e:
            logger.error(f"Ошибка при создании скриншота: {e}")
            return None
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None
    
    def _crop_screenshot(self, image_path):
        """Обрезка скриншота для удаления лишних элементов"""
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                
                # Определяем область карточки (примерно верхняя треть экрана)
                crop_height = min(height // 2, 800)  # Максимум 800px высоты
                
                # Обрезаем изображение
                cropped = img.crop((0, 0, width, crop_height))
                cropped.save(image_path)
                
                logger.info(f"Скриншот обрезан до размеров: {width}x{crop_height}")
                
        except Exception as e:
            logger.warning(f"Не удалось обрезать скриншот: {e}")
    
    def analyze_card_from_url(self, yandex_maps_url):
        """
        Полный анализ карточки: создание скриншота + анализ через GigaChat
        
        Args:
            yandex_maps_url (str): URL карточки на Яндекс.Картах
            
        Returns:
            dict: Результат анализа или None в случае ошибки
        """
        try:
            # Создаем скриншот
            screenshot_path = self.take_screenshot(yandex_maps_url)
            if not screenshot_path:
                return None
            
            # Анализируем скриншот через GigaChat
            from services.gigachat_client import GigaChatAnalyzer
            
            analyzer = GigaChatAnalyzer()
            result = analyzer.analyze_with_image(screenshot_path)
            
            # Удаляем временный файл
            try:
                os.unlink(screenshot_path)
            except:
                pass
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при анализе карточки: {e}")
            return None

def test_screenshot():
    """Тестовая функция для проверки работы"""
    screenshotter = YandexMapsScreenshotter(headless=False)  # Для тестирования показываем браузер
    
    # Тестовый URL
    test_url = "https://yandex.ru/maps/org/gagarin/180566191872/"
    
    result = screenshotter.take_screenshot(test_url)
    if result:
        print(f"Скриншот создан: {result}")
    else:
        print("Ошибка создания скриншота")

if __name__ == "__main__":
    test_screenshot()
