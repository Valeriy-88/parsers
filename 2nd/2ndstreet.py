import logging
import os
import random
import subprocess
import time
from collections import deque
from typing import Set

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from selenium.common.exceptions import *
from seleniumbase import SB

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from param import URLS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("error_code.txt"), logging.StreamHandler()],
)
LAST_ITEMS_MAX_SIZE: int = 2000
sent_products: Set[str] = set()
urls_queue: deque = deque(maxlen=LAST_ITEMS_MAX_SIZE)
ua = UserAgent()
MAX_TXT_LOG_SIZE_MB: int = 5


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
                f"Deleted error_cod.txt due to size > {MAX_TXT_LOG_SIZE_MB} MB."
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


def send_product_to_telegram(product: dict) -> None:
    """
    Отправляет информацию о товаре в Telegram-чат, используя метод sendPhoto (если есть изображение)
    или sendMessage (если изображения нет).

    Формат сообщения:
    - Цена: {цена}
    - Ссылка: {ссылка на товар}

    Примечания:
    - Если подпись (caption) превышает 1024 символа, она обрезается до 1020 символов с добавлением "..."
    - В случае ошибки при отправке сообщения ошибка логируется, но исключение не пробрасывается

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
            logging.error(f"Ошибка при отправке фото в Telegram: {e}")
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
            logging.error(f"Ошибка при отправке сообщения в Telegram: {e}")


def add_url(url: str) -> bool:
    """
    URL добавляется во множество sent_products и в очередь urls_queue (если URL нет в sent_products)
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
    if url not in sent_products:
        sent_products.add(url)
        urls_queue.append(url)
        if len(urls_queue) > urls_queue.maxlen:
            old_url = urls_queue.popleft()
            sent_products.remove(old_url)
        return True
    return False


def parse_page(url: str) -> list:
    """
    Заходит, на указанный в url, сайт. Парсит страницу сайта. Ищет нужные параметры.
    Сохраняет их словарем в список.

    Примечания:
    - Если в html или в container ничего нет, то возвращает пустой список.

    Args:
        - 'html' (none): html код страницы сайта
        - 'user_agent' (str): рандомно сгенерированный user agent
        - 'driver' (BaseCase): драйвер seleniumbase
        - 'soup' (BeautifulSoup): создает объект BeautifulSoup,
        который парсит (разбирает) HTML-документ для дальнейшего извлечения данных
        - 'container': найденные данные из HTML-документа
        - 'link' (str): ссылка на товар
        - 'image' (str): изображение товара
        - 'price' (str): цена товара

    Returns:
        List: Функция возвращает список найденных объявлений

    Raises:
        При исключении возвращает пустой список. Логирует ошибки в следующих случаях:
        - Ошибка сети или таймаут при открытии сайта
        - Неожиданная ошибка при формировании запроса
    """
    html = None
    user_agent: str = ua.random
    try:
        with SB(
            browser="chrome",
            headless=False,
            incognito=True,
            uc_cdp=True,
            agent=user_agent,
        ) as driver:
            try:
                driver.open(url)
                time.sleep(random.uniform(4.0, 6.0))
            except Exception as e:
                logging.error("Error driver open %s", e)
                return []

            try:
                driver.click('button[class*="spg-tour02-end"]')
            except Exception:
                pass

            time.sleep(random.uniform(8.0, 12.0))
            try:
                html = driver.get_page_source()
            except Exception as e:
                logging.error("Error get page source %s", e)

    except Exception as e:
        logging.error("Error initial driver %s", e)
        return []

    if not html:
        logging.error("HTML страницы не получен")
        return []

    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("div", id="searchResultListWrapper")

    if not container:
        logging.info(f"Товары не найдены для {url}")
        return []

    products: list = []
    try:
        links = container.find_all("a", class_="itemCard_inner", href=True)
        for a_tag in links[:4]:
            link: str = a_tag["href"]
            if not link.startswith("http"):
                link: str = "https://www.2ndstreet.jp" + link
            else:
                link: str = url

            img_tag = a_tag.find("img")
            if img_tag and img_tag.get("src"):
                image = img_tag["src"]
                if image.startswith("//"):
                    image = "https:" + image
                elif image.startswith("/"):
                    image = "https://www.2ndstreet.jp" + image
            else:
                image = None

            price_container = a_tag.find(class_="itemCard_price")
            if price_container:
                price: str = price_container.text
            else:
                price: None = None

            products.append({"link": link, "image": image, "price": price})

        return products
    except Exception as e:
        logging.error("Error add new ad %s", e)


def main() -> None:
    """
    В цикле с каждым url заходит в parse_page и получает из него список объектов.
    Во вложенном цикле проходит по данному списку
    заходит в send_product_to_telegram (если не первая итерация)
    чтобы отправить сообщение.

    В kill_chromedriver, удаляет все лишние процессы
    В quit_driver_and_reap_children завершает все зомби процессы
    В rotate_txt_log проверяет размер файла логов.

    Примечания:
    - Если add_url вернул False, то идет на следующую итерацию
    - После каждой итерации цикла products
    функция засыпает на какое-то время
    - После всех итераций цикла URLS
    функция засыпает на какое-то время

    Args:
        - 'first_iter' (bool): html код страницы сайта
        - 'products' (list): рандомно сгенерированный user agent

    Returns:
        None: Функция ничего не возвращает
    """
    first_iter: bool = True
    while True:
        logging.info("start search ads by url")
        for url in URLS:
            products: list = parse_page(url)
            for product in products:
                if not add_url(product["link"]):
                    continue
                if not first_iter:
                    send_product_to_telegram(product)

            kill_chromedriver()
            quit_driver_and_reap_children()
            time.sleep(random.uniform(50.0, 60.0))

        first_iter: bool = False
        rotate_txt_log()
        time.sleep(random.uniform(170.0, 190.0))


if __name__ == "__main__":
    main()
