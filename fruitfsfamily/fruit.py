import logging
import os
import random
import time
import urllib.parse
from datetime import datetime
from typing import Any

import requests
import telebot

from settings import (
    MAX_SEEN_FILE_SIZE_MB,
    MAX_TXT_LOG_SIZE_MB,
    SEARCH_BRAND,
    SEARCH_TERMS,
    SEEN_FILE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("error_code.txt"), logging.StreamHandler()],
)


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


def load_seen_items() -> set:
    """
    Берет данные из файла и записывает их во множество

    Примечания:
    - Если файла нет, то возвращает пустое множество

    Returns:
        None: Функция возвращает множество
    """
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f)
    except FileNotFoundError:
        return set()


def save_seen_items(items: set) -> None:
    """
    Записывает товары в файл

    Returns:
        None: Функция ничего не возвращает
    """
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for item in items:
            f.write(f"{item}\n")


def clean_seen_file() -> None:
    """
    Удаляет половину данных из файла

    Примечания:
    - Если файла нет, то ничего не делает
    - Если объем файла ниже заданного, то ничего не делает

    Args:
        - 'size_mb' (float): размер файла

    Returns:
        None: Функция ничего не возвращает
    """
    if not os.path.exists(SEEN_FILE):
        return

    size_mb: float = os.path.getsize(SEEN_FILE) / (1024 * 1024)
    if size_mb <= MAX_SEEN_FILE_SIZE_MB:
        return

    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        lines: list[str] = f.readlines()

    half: int = len(lines) // 2
    new_lines: list[str] = lines[half:]

    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


seen_items: set = load_seen_items()


def search_products(query: str) -> Any:
    """
    Отправляет пост запрос с заданными параметрами.

    Args:
        - 'url' (str): URL GraphQL API сервера Pikil (production среда)
        - 'headers' (dict): заголовки запроса
        - 'payload' (dict): тело запроса
        - 'response' : результат запроса

    Returns:
        None: Функция возвращает json данные

    Raises:
        При исключении возвращает пустой список.
        Логирует ошибки в следующих случаях:
        - Ошибка сети или таймаут при открытии сайта
        - Неожиданная ошибка при формировании запроса
    """
    url: str = "https://pikil-server.production.fruitsfamily.com/graphql"

    headers: dict = {
        "Host": "pikil-server.production.fruitsfamily.com",
        "Connection": "keep-alive",
        "Accept": "*/*",
        "User-Agent": "FruitsFamily/9.4.1 (1)"
        " com.fruitsFamily.fruitsFamily/20250206024932 iOS/18.1.1",
        "Accept-Language": "ru",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "operationName": "searchProducts",
        "variables": {
            "filter": {"query": query, "colorIds": [], "size_filter": []},
            "sort": "NEW",
            "offset": 0,
            "limit": 40,
        },
        "query": """
        query searchProducts($filter: ProductFilter!, $offset: Int, $limit: Int, $sort: String) {
          searchProducts(filter: $filter, offset: $offset, limit: $limit, sort: $sort) {
            ...ProductFragment
            seller {
              id
              user {
                id
                nickname
                __typename
              }
              __typename
            }
            __typename
          }
        }

        fragment ProductFragment on ProductNotMine {
          id
          resizedSmallImages
          title
          price
          brand
          size
          condition
          status
          like_count
          inquire_count
          discount_rate
          external_url
          __typename
        }
        """,
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error("Error searching for %s: %s", query, e)
        return None


def search_brands(query: str) -> Any:
    """
    Отправляет пост запрос с заданными параметрами.

    Args:
        - 'url' (str): URL GraphQL API сервера Pikil (production среда)
        - 'headers' (dict): заголовки запроса
        - 'payload' (dict): тело запроса
        - 'response' : результат запроса

    Returns:
        None: Функция возвращает json данные

    Raises:
        При исключении возвращает пустой список.
        Логирует ошибки в следующих случаях:
        - Ошибка сети или таймаут при открытии сайта
        - Неожиданная ошибка при формировании запроса
    """
    url: str = "https://pikil-server.production.fruitsfamily.com/graphql"

    headers: dict = {
        "Host": "pikil-server.production.fruitsfamily.com",
        "Connection": "keep-alive",
        "Accept": "*/*",
        "User-Agent": "FruitsFamily/9.4.1 (1) "
        "com.fruitsFamily.fruitsFamily/20250206024932 iOS/18.1.1",
        "Accept-Language": "ru",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "operationName": "SeeProducts",
        "variables": {
            "filter": {"brand": query, "colorIds": [], "size_filter": []},
            "sort": "NEW",
            "offset": 0,
            "limit": 40,
        },
        "query": """
                query SeeProducts($filter: ProductFilter!, $offset: Int, $limit: Int, $sort: String) {
                  searchProducts(filter: $filter, offset: $offset, limit: $limit, sort: $sort) {
                      ...ProductFragment
                          ...ProductDetailsPreloadFragment
                              price
                              __typename
                  }
                }

                fragment ProductFragment on ProductNotMine {
                  id
                  title
                  brand
                  status
                  external_url
                  resizedSmallImages
                  __typename
                }

                fragment ProductDetailsPreloadFragment on ProductNotMine {
                  id
                  createdAt
                  category
                  title
                  description
                  brand
                  price
                  status
                  external_url
                  resizedSmallImages
                  is_visible
                  size
                  condition
                  discount_rate
                  like_count
                  __typename
                }
                """,
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error("Error searching for %s: %s", query, e)
        return None


def get_product_details(product_id: int) -> Any:
    """
    Отправляет пост запрос с заданными параметрами.

    Args:
        - 'url' (str): URL GraphQL API сервера Pikil (production среда)
        - 'headers' (dict): заголовки запроса
        - 'payload' (dict): тело запроса
        - 'response' : результат запроса

    Returns:
        None: Функция возвращает json данные

    Raises:
        При исключении возвращает пустой список.
        Логирует ошибки в следующих случаях:
        - Ошибка сети или таймаут при открытии сайта
        - Неожиданная ошибка при формировании запроса
    """
    url: str = "https://pikil-server.production.fruitsfamily.com/graphql"

    headers: dict = {
        "Host": "pikil-server.production.fruitsfamily.com",
        "Connection": "keep-alive",
        "Accept": "*/*",
        "User-Agent": "FruitsFamily/9.4.1 (1) "
        "com.fruitsFamily.fruitsFamily/20250206024932 iOS/18.1.1",
        "Accept-Language": "ru",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "operationName": "seeProduct",
        "variables": {"productID": product_id},
        "query": """
        query seeProduct($productID: Int!) {
          seeProduct(id: $productID) {
            id
            title
            description
            brand
            size
            condition
            price
            status
            shipping_fee
            shipping_fee_island
            external_url
            resizedSmallImages
            createdAt
            seller {
              user {
                nickname
                dangdo_rate
              }
            }
          }
        }
        """,
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(
            "Error getting product details for ID %s: %s",
            product_id, e
        )
        return None


def get_product_link(product_id: str) -> Any:
    """
    Берет название продукта и формирует URL для запроса

    Примечания:
    - Если получение продукта ничего не вернуло,
    то ничего не делает и возвращает None
    - Если у продукта нет заголовка,
    то ничего не делает и возвращает None

    Args:
        - 'product_details' (Any): детальное описание продукта словарем
        - 'product' (Any): сам продукт
        - 'title' (Any): заголовок продукта (имя)
        - 'encoded_title' (str): декапированное имя продукта
        - 'url' (str): ссылка на продукт

    Returns:
        None: Функция возвращает ссылку на продукт

    Raises:
        При исключении возвращает None.
        Логирует ошибки в следующих случаях:
        - Неожиданная ошибка при формировании запроса
    """
    try:
        product_details: Any = get_product_details(int(product_id))
        if (
            not product_details
            or "data" not in product_details
            or "seeProduct" not in product_details["data"]
        ):
            return None

        product: Any = product_details["data"]["seeProduct"]
        title: Any = product.get("title", "")
        if not title:
            return None

        encoded_title: str = urllib.parse.quote(title)
        return f"@https://fruitsfamily.com/search/{encoded_title}"
    except Exception as e:
        logging.error("Error: %s", e)
        return None


def send_to_telegram(product: dict, photo_url: str, product_url: str) -> None:
    """
    Отправляет информацию о товаре в Telegram-чат

    Примечания:
    - Если фото нет, то отправляет сообщение без него
    - Если фото есть, то отправляет с ним

    Args:
        - 'bot_token' (str): секретный ключ телеграм бота
        - 'chat_id' (int): идентификатор чата
        - 'bot' (bot): Телеграм бот
        - 'price' (str): цена товара
        - 'clean_url' (str): ссылка на товар
        - 'message' (str): отправляемое сообщение в телеграм чат

    Returns:
        None: Функция ничего не возвращает

    Raises:
        При исключении ничего не возвращает
        Логирует ошибки в следующих случаях:
        - Неожиданная ошибка при формировании запроса
    """
    try:
        bot_token: str = ""
        chat_id: str = ""
        bot = telebot.TeleBot(bot_token)

        price: str = format(int(product["price"]), ",") + "원"
        clean_url: str = product_url.replace("@", "") if product_url else "None"

        message: str = (
            f"Title: {product['title']}\n"
            f"Size: {product['size']}\n"
            f"Condition: {product['condition']}\n"
            f"Price: {price}\n"
            f"URL: {clean_url}"
        )

        time.sleep(random.randint(0, 1))
        if photo_url:
            bot.send_photo(chat_id=chat_id, photo=photo_url, caption=message)
        else:
            bot.send_message(chat_id=chat_id, text=message)

    except Exception as e:
        logging.error("Error sending to Telegram: %s", e)


def save_to_log(product: dict) -> None:
    """
    Отправляет полученные данные в функцию для отправки в телеграм чат

    Примечания:
    - Если получение продукта ничего не вернуло,
    то ничего не делает и возвращает None

    Args:
        - 'product_details' (Any): детальное описание продукта
        - 'product_link' (Any): ссылка на продукт
        - 'photo_link' (str): фото продукта

    Returns:
        None: Функция ничего не возвращает

    Raises:
        При исключении возвращает None
        Логирует ошибки в следующих случаях:
        - Неожиданная ошибка при формировании запроса
    """
    product_details: Any = get_product_details(int(product["id"]))
    product_link: Any = get_product_link(str(product["id"]))
    photo_link: str = ""
    try:
        if (
            product_details
            and "data" in product_details
            and "seeProduct" in product_details["data"]
        ):
            details = product_details["data"]["seeProduct"]
            if (
                details.get("resizedSmallImages")
                and len(details["resizedSmallImages"]) > 0
            ):
                photo_link = details["resizedSmallImages"][0]

            send_to_telegram(product, photo_link, product_link)
    except Exception as e:
        logging.error("Error: %s", e)
        return


def view_products() -> bool:
    """
    Поиск и отображение новых товаров по списку поисковых запросов.

    Основные функции:
    1. Поочередно выполняет поиск товаров для каждого термина из SEARCH_TERMS
    2. Фильтрует новые товары (не присутствующие в seen_items)
    3. Форматирует и выводит информацию о новых товарах в консоль
    4. Сохраняет новые товары в лог-файл через save_to_log()

    Returns:
        bool: Флаг обнаружения новых товаров
            - True: Найдены новые товары
            - False: Новых товаров не обнаружено
    """
    new_items_found: bool = False

    for search_term in SEARCH_TERMS:
        print(f"\nSearching for: {search_term}")

        result = search_products(search_term)
        if (not result or "data" not in result
                or "searchProducts" not in result["data"]):
            print(f"No results for {search_term}")
            continue

        products: dict = result["data"]["searchProducts"]
        for product in products:
            item_id: Any = product["id"]
            if item_id not in seen_items:
                new_items_found: bool = True
                seen_items.add(item_id)
                price: str = format(int(product["price"]), ",") + "원"

                print("\nNEW ITEM FOUND!")
                print(f"Brand: {product['brand']}")
                print(f"Title: {product['title']}")
                print(f"Price: {price}")
                print(f"Size: {product['size']}")
                print(f"Condition: {product['condition']}")
                print(f"Status: {product['status']}")
                print(f"URL: {product['external_url']}")
                print("-" * 50)

                save_to_log(product)

    return new_items_found


def view_brand_product() -> bool:
    """
    Поиск и отображение новых товаров по списку поисковых запросов.

    Основные функции:
    1. Поочередно выполняет поиск товаров для каждого термина из SEARCH_TERMS
    2. Фильтрует новые товары (не присутствующие в seen_items)
    3. Форматирует и выводит информацию о новых товарах в консоль
    4. Сохраняет новые товары в лог-файл через save_to_log()

    Returns:
        bool: Флаг обнаружения новых товаров
            - True: Найдены новые товары
            - False: Новых товаров не обнаружено
    """
    new_items_found: bool = False

    for search_term in SEARCH_BRAND:
        print(f"\nSearching for: {search_term}")

        result = search_brands(search_term)
        if (not result or "data" not in result
                or "searchProducts" not in result["data"]):
            print(f"No results for {search_term}")
            continue

        products: dict = result["data"]["searchProducts"]

        for product in products:
            item_id: Any = product["id"]
            if item_id not in seen_items:
                new_items_found: bool = True
                seen_items.add(item_id)
                price: str = format(int(product["price"]), ",") + "원"

                print("\nNEW ITEM FOUND!")
                print(f"Brand: {product['brand']}")
                print(f"Title: {product['title']}")
                print(f"Price: {price}")
                print(f"Size: {product['size']}")
                print(f"Condition: {product['condition']}")
                print(f"Status: {product['status']}")
                print(f"URL: {product['external_url']}")
                print("-" * 50)

                save_to_log(product)

    return new_items_found


def main() -> None:
    """
    Поиск новых товаров и брендов.

    Основные функции:
    1. выполняет поиск товаров
    2. выполняет поиск брендов
    3. Проверяет объем памяти в файле seen file
    4. Сохраняет новые товары в файл через save_seen_items()
    5. Каждые 6 часов сообщает в указанный телеграм чат,
    что сервер работает

    Returns:
        None: Функция ничего не возвращает

    Raises:
        При исключении идет на следующую итерацию
        Логирует ошибки в следующих случаях:
        - Неожиданная ошибка при формировании запроса
    """
    last_print_time: datetime = datetime.now()
    while True:
        try:
            print(
                "\n=== Checking items at " f"%s ===",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )

            new_items_found: bool = view_products()
            new_items_brand_found: bool = view_brand_product()

            if new_items_found or new_items_brand_found:
                clean_seen_file()
                save_seen_items(seen_items)

            print("\nWaiting 40 seconds before next check...")
            current_time: datetime = datetime.now()
            if (current_time - last_print_time).total_seconds() >= 6 * 60 * 60:
                SECRET_KEY = ""
                bot = telebot.TeleBot(SECRET_KEY)
                bot.send_message(123456789, "fruitfamily work")
                last_print_time: datetime = current_time

            rotate_txt_log()
            time.sleep(40)

        except Exception as e:
            logging.error("Error: %s", e)
            continue


if __name__ == "__main__":
    main()
