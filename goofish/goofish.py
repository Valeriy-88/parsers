import logging
import os
import random
import subprocess
import time
from collections import deque
from typing import Any

import requests
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium_stealth import stealth
from telebot import TeleBot
from urllib3.exceptions import MaxRetryError, NewConnectionError

from parameters import (
    LAST_ITEMS_MAX_SIZE,
    MAX_TXT_LOG_SIZE_MB,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    params_list,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("error_code.txt"), logging.StreamHandler()],
)

ua = UserAgent()
bot = TeleBot(token=TELEGRAM_BOT_TOKEN)
urls_set: set = set()
urls_queue = deque(maxlen=LAST_ITEMS_MAX_SIZE)


def send_product_to_telegram(product: dict) -> None:
    """
    Отправляет информацию о товаре в Telegram-чат, используя метод sendPhoto (если есть изображение)
    или sendMessage (если изображения нет).

    Формат сообщения:
    - Цена: {цена}
    - Ссылка: {ссылка на товар}

    Примечания:
    - Если подпись (caption) превышает 1024 символа,
    она обрезается до 1020 символов с добавлением "..."
    - В случае ошибки при отправке сообщения ошибка логируется,
    но исключение не пробрасывается

    Args:
        product (dict): Словарь с информацией о товаре, должен содержать ключи:
            - 'image' (str, optional): URL изображения товара. Если отсутствует или пустой -
                                      используется текстовое сообщение
            - 'price' (str): Цена товара
            - 'link' (str): Ссылка на товар

    Returns:
        None: Функция ничего не возвращает

    Raises:
        Не пробрасывает исключения, но логирует ошибки в следующих случаях:
        - Ошибка сети или таймаут при обращении к API Telegram
        - Неожиданная ошибка при формировании запроса
    """
    if product["image"]:
        telegram_url: str = (
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        )
        caption: str = f"Цена: {product['price']}\nСсылка: {product['link']}"
        if len(caption) > 1024:
            caption: str = caption[:1020] + "..."
        data: dict = {
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": caption,
            "photo": product["image"],
        }
        try:
            logging.info("send message")
            send_message = requests.post(telegram_url, data=data, timeout=10)
            send_message.raise_for_status()
        except Exception as e:
            logging.error("Ошибка при отправке фото в Telegram: %s", e)
    else:
        telegram_url: str = (
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        )
        text: str = f"Цена: {product['price']}\nСсылка: {product['link']}"
        data: dict = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        try:
            send_message = requests.post(telegram_url, data=data, timeout=10)
            send_message.raise_for_status()
        except Exception as e:
            logging.error("Ошибка при отправке сообщения в Telegram: %s", e)


def add_url(url: str) -> bool:
    """
    URL добавляется во множество sent_products
    и в очередь urls_queue (если URL нет в sent_products)
    или возвращает False.

    Примечания:
    - Если длина очереди превышает максимальное значение,
    то последний элемент из очереди и из множества удаляется.

    Args:
        - 'url' (str): URL ссылка на товар
        - 'sent_products' (set): множество найденных объявлений на товар
        - 'urls_queue' (deque): список найденных объявлений

    Returns:
        Bool: Функция возвращает Истина или Лож в зависимости от выполнения условия
    """
    if url not in urls_set:
        urls_set.add(url)
        urls_queue.append(url)
        if len(urls_queue) > urls_queue.maxlen:
            old_url = urls_queue.popleft()
            urls_set.remove(old_url)
        return True
    return False


def get_ads_by_url(html: Any, first_iter: bool) -> Any:
    """
    Парсит страницу сайта. Ищет нужные параметры.
    При найденном новом объявлении заходит в send_product_to_telegram()

    Основные функции:
    1. выполняет поиск url ссылки
    2. выполняет поиск фото товара
    3. Проверяет поиск цены товары

    Примечания:
    - Если в html или в container ничего нет, то возвращает пустой список.

    Args:
        - 'html' (none): html код страницы сайта
        - 'soup' (BeautifulSoup): создает объект BeautifulSoup,
        который парсит (разбирает) HTML-документ для дальнейшего извлечения данных
        - 'container': найденные данные из HTML-документа
        - 'link' (str): ссылка на товар
        - 'image' (str): изображение товара
        - 'price' (str): цена товара

    Returns:
        List|None: Функция возвращает пустой список или ничего

    Raises:
        При исключении возвращает None.
        Логирует ошибки в следующих случаях:
        - Неожиданная ошибка при формировании запроса
    """
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("div", class_="feeds-list-container--UkIMBPNk")

    if not container:
        return []

    try:
        links = container.find_all("a", class_="feeds-item-wrap--rGdH_KoF", href=True)
        for a_tag in links[:4]:
            link: str = a_tag["href"]
            if not link.startswith("http"):
                link: str = "https://www.goofish.com/" + link

            img_tag = a_tag.find("img")
            if img_tag and img_tag.get("src"):
                image: str = img_tag["src"]
                if image.startswith("//"):
                    image: str = "https:" + image
                elif image.startswith("/"):
                    image: str = "https://www.goofish.com/" + image
            else:
                image: None = None

            price_container = a_tag.find(class_="price-wrap--YzmU5cUl")
            if price_container:
                currency: str = price_container.find(
                    class_="sign--x6uVdG3X"
                ).text.strip()
                number: str = price_container.find(
                    class_="number--NKh1vXWM"
                ).text.strip()
                price: str = number + currency
            else:
                price: None = None

            if add_url(link):
                if not first_iter:
                    send_product_to_telegram(
                        {"link": link, "image": image, "price": price}
                    )

    except Exception as e:
        logging.error("Error add new ad %s", e)


def random_scroll(driver) -> None:
    """
    Рандомно делает скролл вверх или вниз по странице сайта

    Returns:
        None: Функция ничего не возвращает
    """
    driver.execute_script(f"window.scrollBy(0, {random.uniform(500.0, 700.0)});")
    time.sleep(random.uniform(8.0, 13.0))
    for _ in range(2):
        random.choice(
            [
                driver.execute_script(
                    f"window.scrollBy(0, {random.uniform(500.0, 700.0)});"
                ),
                driver.execute_script(
                    f"window.scrollBy(0, -{random.uniform(500.0, 700.0)});"
                ),
            ]
        )
        time.sleep(random.uniform(8.0, 13.0))


def process_url(first_iter: bool) -> None:
    """
    Обрабатывает список URL через headless-браузер с эмуляцией человеческого поведения.

    Основной функционал:
    - Открывает Chrome в режиме без графического интерфейса (headless=True)
    - Настраивает параметры stealth-режима для обхода антибот-систем
    - Последовательно обрабатывает каждый URL из params_list
    - Выполняет сортировку результатов по дате ("最新" - новейшие)
    - Эмулирует человеческое поведение (случайные скроллы, задержки)
    - Извлекает HTML-контент страницы и передает в get_ads_by_url()
    - Управляет вкладками браузера для улучшения маскировки

    Обрабатываемые исключения:
        - MaxRetryError: Проблемы с подключением
        - NewConnectionError: Ошибки сети
        - Общие исключения (Exception)
    """
    html_page = None
    browser = None
    try:
        options = uc.ChromeOptions()
        options.headless = False
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-popup-blocking")
        browser = uc.Chrome(options=options)
        stealth(
            browser,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=False,
            run_on_insecure_origins=False,
        )
        for url in params_list:
            browser.get(url)
            time.sleep(random.uniform(8.0, 13.0))
            sort_by = browser.find_element(By.CSS_SELECTOR, '[class="item--m9jSTUup"]')
            sort_by.click()
            time.sleep(random.uniform(8.0, 13.0))
            try:
                sort_by = browser.find_element(
                    By.CSS_SELECTOR, "[span.search-select-title--zzthyzLG]"
                )
                sort_by.click()
                time.sleep(random.uniform(2.0, 4.0))
            except Exception as e:
                logging.error("Error click sort_by %s", e)
                continue

            sort_by_date = browser.find_element(
                By.XPATH,
                "//div[@class='search-select-item--H_AJBURX' and text()='最新']",
            )
            sort_by_date.click()
            time.sleep(random.uniform(2.0, 4.0))

            actions = ActionChains(browser)
            actions.move_by_offset(100, 0).perform()
            time.sleep(random.uniform(8.0, 13.0))

            random_scroll(browser)

            try:
                html_page = browser.page_source
            except Exception as e:
                logging.error("Error get page source %s", e)

            if not html_page:
                logging.error("HTML страницы не получен")
                continue

            get_ads_by_url(html_page, first_iter)
            time.sleep(random.uniform(13.0, 20.0))
            random_scroll(browser)
            time.sleep(random.uniform(13.0, 20.0))

            browser.execute_script("window.open();")
            browser.switch_to.window(browser.window_handles[-1])
            time.sleep(random.uniform(1.5, 3.0))

        if browser:
            try:
                browser.close()
                browser.quit()
            except Exception as e:
                logging.error("Error close browser %s", e)

    except (MaxRetryError, NewConnectionError, Exception) as e:
        logging.error("General Error on: %s", e)
        if browser:
            try:
                browser.close()
                browser.quit()
            except Exception as e:
                logging.error("Error close browser %s", e)


def rotate_txt_log() -> None:
    """
    Удаляет файл если он превышает заданный объем мегабайт

    Примечания:
    - Если файла нет, то ничего не делает

    Args:
        - 'size_mb' (float): размер файла

    Returns:
        None: Функция ничего не возвращает
    """
    if os.path.exists("error_code.txt"):
        size_mb: float = os.path.getsize("error_code.txt") / (1024 * 1024)
        if size_mb > MAX_TXT_LOG_SIZE_MB:
            os.remove("error_cod.txt")
            logging.info(
                "Deleted error_cod.txt due to size > %s MB.",
                MAX_TXT_LOG_SIZE_MB
            )


def kill_chromedriver() -> None:
    """
    Отчищает систему от всех процессов chromedriver и chrome

    Returns:
        None: Функция ничего не возвращает
    """
    try:
        subprocess.run(["pkill", "-9", "-f", "chromedriver"], check=False)
        subprocess.run(["pkill", "-9", "-f", "chrome"], check=False)
    except Exception as e:
        logging.error("Произошла ошибка при завершении процессов: %s", e)


def quit_driver_and_reap_children() -> None:
    """
    Отчищает систему от зависших зомби-процессов

    Примечания:
    - Если процессов нет,
    то завершает цикл и выходит из функции

    Args:
        - 'pid' (int): pid процесса в системе

    Returns:
        None: Функция ничего не возвращает
    """
    try:
        while True:
            pid, _ = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break
    except ChildProcessError:
        pass
    except Exception as e:
        logging.error("Ошибка при очистке зомби-процессов: %s", e)


def main() -> None:
    """
    Основной цикл работы парсера Goofish с бесконечным выполнением.

    Логика работы:
    1. Запускает бесконечный цикл парсинга
    2. На первой итерации устанавливает флаг first_iter=True
    3. Для каждой итерации:
        - Логирует начало работы
        - Запускает процесс парсинга URL (process_url)
        - Выполняет ротацию лог-файлов (rotate_txt_log)
        - Устанавливает паузу между итерациями (30-45 минут)
    """
    first_iter: bool = True
    while True:
        logging.info("Goofish started")
        process_url(first_iter)
        rotate_txt_log()
        first_iter: bool = False
        time.sleep(random.uniform(1800.0, 2700.0))


if __name__ == "__main__":
    main()
