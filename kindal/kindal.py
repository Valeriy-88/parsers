import logging
import os
import random
import resource
import signal
import subprocess
import time

import requests
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from config import (
    MAX_TXT_LOG_SIZE_MB,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    sent_products,
    urls_queue,
)
from param import URLS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("error_code.txt"), logging.StreamHandler()],
)
ua = UserAgent()


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


def add_url(url: str) -> bool:
    """
    URL добавляется во множество sent_products и
    в очередь urls_queue (если URL нет в sent_products)
    или возвращает False.

    Примечания:
    - Если длина очереди превышает максимальное значение,
    то последний элемент из очереди и из множества удаляется.

    Args:
        - 'url' (str): URL ссылка на товар
        - 'sent_products' (set): множество найденных объявлений на товар
        - 'urls_queue' (deque): список найденных объявлений

    Returns:
        Bool: Функция возвращает Истина или Лож
        в зависимости от выполнения условия
    """
    if url not in sent_products:
        sent_products.add(url)
        urls_queue.append(url)
        if len(urls_queue) > urls_queue.maxlen:
            old_url = urls_queue.popleft()
            sent_products.remove(old_url)
        return True
    return False


def send_product_to_telegram(product: dict) -> None:
    """
    Отправляет информацию о товаре в Telegram-чат,
    используя метод sendPhoto (если есть изображение)
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
            - 'image' (str, optional): URL изображения товара. Если отсутствует
            или пустой - используется текстовое сообщение
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


def kill_chromedriver() -> None:
    """
    Отчищает систему от всех процессов
    chromedriver, chrome, chromedriver_co, undetected_chromedriver

    Returns:
        None: Функция ничего не возвращает
    """
    try:
        subprocess.run(["pkill", "-9", "-f", "chromedriver"], check=False)
        subprocess.run(["pkill", "-9", "-f", "chrome"], check=False)
        subprocess.run(["pkill", "-9", "-f", "chromedriver_co"], check=False)
        subprocess.run(["pkill", "-9", "-f", "undetected_chromedriver"], check=False)
    except Exception as e:
        logging.error("Произошла ошибка при завершении процессов: %s", e)


def close_open_file_descriptors(min_fd=3, max_fd=None) -> None:
    """
    Закрывает все открытые файловые дескрипторы в диапазоне [min_fd, max_fd).
    Если max_fd не указан, берём лимит открытых дескрипторов системы.

    Returns:
        None: Функция ничего не возвращает
    """
    try:
        if max_fd is None:
            max_fd = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
        logging.info("Closing file descriptors from %s to %s", min_fd, max_fd - 1)
        os.closerange(min_fd, max_fd)
    except Exception as e:
        logging.error("Error closing file descriptors: %s", e)


def quit_driver_and_reap_children(signum=None, frame=None) -> None:
    """
    Обработчик SIGCHLD: забирать всех завершённых дочерних процессов

    Returns:
        None: Функция ничего не возвращает
    """
    try:
        while True:
            pid, status = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break
            logging.info("Reaped zombie process PID %s with status %s", pid, status)
    except ChildProcessError:
        pass


def cleanup_old_chromedriver_processes(max_age_seconds=3600):
    """
    Очищает зависшие процессы chromedriver и chrome,
    работающие дольше указанного времени.

    Функция выполняет:
    1. Поиск всех процессов через команду 'ps' (Linux/MacOS)
    2. Фильтрацию процессов chromedriver/chrome
    3. Завершение процессов, работающих дольше max_age_seconds

    Особенности:
    - Игнорирует свежие процессы (моложе max_age_seconds)
    - Логирует все действия и ошибки
    - Обрабатывает процессы с именами: chromedriver, chromedriver_co, chrome
    - Использует SIGTERM для корректного завершения процессов

    Args:
        max_age_seconds (int, optional): Максимальное время жизни процесса в секундах.
                                      По умолчанию 3600 (1 час).

    Returns:
        None: Функция ничего не возвращает

    Raises:
        Не пробрасывает исключения, но логирует ошибки:
        - Если не удается выполнить команду 'ps'
        - Если не удается завершить процесс
        - При других неожиданных ошибках
    """
    try:
        ps_output = subprocess.check_output(
            ["ps", "-eo", "pid,etimes,comm,cmd"]
        ).decode()
        for line in ps_output.splitlines():
            if line.strip().startswith("PID"):
                continue
            parts = line.split(None, 3)
            if len(parts) < 4:
                continue
            pid = int(parts[0])
            etimes = int(parts[1])
            comm = parts[2]
            cmd = parts[3]
            if comm in ("chromedriver", "chromedriver_co", "chrome"):
                if etimes > max_age_seconds:
                    logging.info(
                        "Убиваем процесс %s PID %s, время работы %s сек: %s",
                        comm, pid, etimes, cmd,
                    )
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except Exception as e:
                        logging.error("Не удалось убить PID %s: %s", pid, e)
    except Exception as e:
        logging.error("Ошибка при очистке процессов: %s", e)


def fetch_data_sync(full_url):
    """
    Заходит, на указанный в url, сайт. Парсит страницу сайта. Ищет нужные параметры.
    Сохраняет их словарем в список.

    Примечания:
    - Если в html или в container ничего нет, то возвращает пустой список.

    Args:
        - 'html' (none): html код страницы сайта
        - 'user_agent' (str): рандомно сгенерированный user agent
        - 'driver' (BaseCase): драйвер undetected chromedriver
        - 'soup' (BeautifulSoup): создает объект BeautifulSoup,
        который парсит (разбирает) HTML-документ для дальнейшего извлечения данных
        - 'container': найденные данные из HTML-документа
        - 'link' (str): ссылка на товар
        - 'image' (str): изображение товара
        - 'price' (str): цена товара

    Returns:
        List: Функция возвращает список найденных объявлений

    Raises:
        При исключении возвращает пустой список.
        Логирует ошибки в следующих случаях:
        - Ошибка сети или таймаут при открытии сайта
        - Неожиданная ошибка при формировании запроса
    """
    driver = None
    html = None
    try:
        options = uc.ChromeOptions()
        options.headless = True

        options.add_argument(f"--user-agent={ua.random}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = uc.Chrome(options=options)
        driver.get(full_url)
        time.sleep(random.uniform(5, 10))

        driver.execute_script("window.scrollBy(0, 600);")
        time.sleep(random.uniform(8.0, 13.0))
        driver.execute_script("window.scrollBy(0, 600);")
        time.sleep(random.uniform(8.0, 13.0))
        driver.execute_script("window.scrollBy(0, 600);")
        time.sleep(random.uniform(8.0, 13.0))

        html = driver.page_source
    except Exception as e:
        logging.error("Error in fetch_data_sync: %s", e)
        quit_driver_and_reap_children()
        close_open_file_descriptors()
        kill_chromedriver()
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    soup = BeautifulSoup(html, "html.parser")
    product_elements = soup.select("div.boost-sd__product-item")
    if not product_elements:
        logging.info(
            "Товары не найдены для %s по известным селекторам.",
            full_url
        )
        return []

    products: list = []
    for element in product_elements[:4]:
        a_tag = element.find("a", class_="boost-sd__product-link", href=True)
        if a_tag:
            link: str = a_tag["href"]
            if not link.startswith("http"):
                link: str = "https://shop.kind.co.jp" + link
        else:
            link: str = full_url

        img_tag = element.find(
            "img",
            class_="boost-sd__product-image-img--main"
        )
        if img_tag:
            image = img_tag.get("src")
            if image and image.startswith("//"):
                image: str = "https:" + image
        else:
            image: None = None

        price_container = element.find("div", class_="boost-sd__product-price")
        if price_container:
            price: str = price_container.get_text(strip=True)
        else:
            price: str = "Цена не найдена"

        products.append({"link": link, "image": image, "price": price})

    return products


def main():
    """
    В цикле с каждым url заходит в parse_page
    и получает из него список объектов.
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
            products: list = fetch_data_sync(url)
            for product in products:
                if not add_url(product["link"]):
                    continue
                if not first_iter:
                    send_product_to_telegram(product)
                    time.sleep(random.uniform(1.0, 3.0))

            time.sleep(random.uniform(60.0, 120.0))
            quit_driver_and_reap_children()
            kill_chromedriver()

        first_iter: bool = False
        rotate_txt_log()
        time.sleep(random.uniform(1800.0, 2300.0))


if __name__ == "__main__":
    signal.signal(signal.SIGCHLD, quit_driver_and_reap_children)
    main()
