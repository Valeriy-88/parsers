import concurrent.futures
import logging
import time
import asyncio
import threading
import websockets
import random
import json
from urllib.parse import urlencode
from fake_useragent import UserAgent
from seleniumwire import webdriver
from parameter import (
    api_params_1,
    api_params_2,
    api_params_3,
    api_params_4,
    api_params_5,
    api_params_6,
    web_params_1,
    web_params_2,
    web_params_3,
    web_params_4,
    web_params_5,
    web_params_6,
)
import queue
from selenium_stealth import stealth
from config import (
    PROXY_USER,
    PROXY_PASS,
    PROXY_PORT,
    chrome_options
)
from telebot import TeleBot
from collections import deque
from contextlib import contextmanager


logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(threadName)s %(message)s")
SECRET_KEY = "7566037068:AAESImJZ71r-VLFhj8HlO6bbJ-h3P1MRqO0"
bot = TeleBot(token=SECRET_KEY)

LAST_ITEMS_MAX_SIZE = 2000
last_items = deque(maxlen=LAST_ITEMS_MAX_SIZE)
urls_set = set()
urls_set_lock = threading.Lock()
clients_lock = threading.Lock()
connected_clients = set()
ua = UserAgent()
count = 0
thread_local = threading.local()
links_queue = queue.Queue()
PROXY_HOSTS = [
    '72.9.186.46', '72.9.187.210', '72.9.190.140',
    '72.9.190.104', '72.9.187.217', '72.9.189.252',
    '', '', '',
    '', '', '',
]


def current_date_to_unix():
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ С‚РµРєСѓС‰РµРµ РІСЂРµРјСЏ РІ СЃРµРєСѓРЅРґР°С… РѕС‚ СЌРїРѕС…Рё Unix."""
    return int(time.time())


async def broadcast_link_via_websockets(link):
    """Р Р°СЃСЃС‹Р»Р°РµС‚ СЃСЃС‹Р»РєСѓ РІСЃРµРј РїРѕРґРєР»СЋС‡С‘РЅРЅС‹Рј РєР»РёРµРЅС‚Р°Рј."""
    with clients_lock:
        clients = list(connected_clients)
    if clients:
        logging.info(f"Broadcasting link: {link}")
        tasks = [asyncio.create_task(client.send(link)) for client in clients]
        await asyncio.gather(*tasks)
    else:
        logging.warning("No clients connected to broadcast the link.")


def schedule_broadcast(link, loop):
    """РџР»Р°РЅРёСЂСѓРµС‚ СЂР°СЃСЃС‹Р»РєСѓ СЃСЃС‹Р»РєРё РІ РѕСЃРЅРѕРІРЅРѕРј С†РёРєР»Рµ СЃРѕР±С‹С‚РёР№."""
    asyncio.run_coroutine_threadsafe(broadcast_link_via_websockets(link), loop)


async def handle_client(websocket, path=None):
    with clients_lock:
        connected_clients.add(websocket)
    logging.info(f"Client connected: {websocket.remote_address}")
    try:
        async for message in websocket:
            logging.info(f"Received message from client: {message}")
    except Exception as e:
        logging.error(f"Client connection error: {e}")
    finally:
        with clients_lock:
            connected_clients.remove(websocket)
        logging.info(f"Client disconnected: {websocket.remote_address}")


def start_websocket_server_thread(loop):
    """Р—Р°РїСѓСЃРєР°РµС‚ WebSocket-СЃРµСЂРІРµСЂ РІ РѕС‚РґРµР»СЊРЅРѕРј РїРѕС‚РѕРєРµ."""
    async def run_server():
        server = await websockets.serve(handle_client, '0.0.0.0', 3454)
        await server.wait_closed()

    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_server())


def get_thread_local_random():
    if not hasattr(thread_local, "random"):
        thread_local.random = random.Random()
    return thread_local.random


@contextmanager
def create_driver(HOST):
    driver = None
    try:
        options = {
            'proxy': {
                'http': f'http://{PROXY_USER}:{PROXY_PASS}@{HOST}:{PROXY_PORT}',
                'https': f'https://{PROXY_USER}:{PROXY_PASS}@{HOST}:{PROXY_PORT}',
            },
            'connection_pool_maxsize': 4,
            'connection_timeout': 30,
            'verify_ssl': False,
            'suppress_connection_errors': False,
            'request_storage': 'memory',
            'request_storage_max_size': 100,
            'auto_clear_requests': True,
            'temp_dir': '/var/tmp',
        }
        driver = webdriver.Chrome(
            seleniumwire_options=options,
            options=chrome_options
        )
        stealth(
            driver,
            user_agent=ua.random,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=False,
            run_on_insecure_origins=False,
        )
        yield driver
    except Exception as e:
        logging.error(f"Failed to create driver: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logging.error(f"Error quitting driver: {e}")


def fetch_api(site_url, url_api, proxy_port):
    """
    Р В Р’ВР РЋР С“Р В РЎвЂ”Р В РЎвЂўР В Р’В»Р РЋР Р‰Р В Р’В·Р РЋРЎвЂњР В Р’ВµР РЋРІР‚С™ chromedriver Р В РўвЂР В Р’В»Р РЋР РЏ Р В РЎвЂ”Р В РЎвЂўР В Р’В»Р РЋРЎвЂњР РЋРІР‚РЋР В Р’ВµР В Р вЂ¦Р В РЎвЂР РЋР РЏ API-Р В РЎвЂўР РЋРІР‚С™Р В Р вЂ Р В Р’ВµР РЋРІР‚С™Р В Р’В°.
    Р В РІР‚СњР В Р’В»Р РЋР РЏ Р В РЎвЂќР В Р’В°Р В Р’В¶Р В РўвЂР В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В Р’В·Р В Р’В°Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р В Р’В° Р РЋР С“Р В РЎвЂўР В Р’В·Р В РўвЂР В Р’В°Р РЋРІР‚ВР РЋРІР‚С™Р РЋР С“Р РЋР РЏ headlessР Р†Р вЂљРІР‚ВР В Р’В±Р РЋР вЂљР В Р’В°Р РЋРЎвЂњР В Р’В·Р В Р’ВµР РЋР вЂљ Р РЋР С“ Р В Р’В·Р В Р’В°Р В РўвЂР В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋРІР‚в„–Р В РЎВ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РЎвЂќР РЋР С“Р В РЎвЂ.
    """
    max_retries = 3
    time.sleep(random.randint(1, 3))
    for attempt in range(max_retries):
        try:
            with create_driver(proxy_port) as driver:
                if not driver:
                    logging.warning("Driver is None, retrying...")
                    continue
                driver.get(site_url)
                driver.execute_script(f"window.open('{url_api}', '_blank');")
                driver.switch_to.window(driver.window_handles[1])
                time.sleep(1)
                body_text = driver.find_element("tag name", "body").text
                return json.loads(body_text)

        except Exception as e:
            logging.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            if "Connection refused" in str(e):
                logging.error(f"Connection refused, probably chromedriver issue, restarting chromedriver and retrying...")

            if attempt == max_retries - 1:
                return None


def add_url(url):
    with urls_set_lock:
        if url not in urls_set:
            urls_set.add(url)
            if len(last_items) >= LAST_ITEMS_MAX_SIZE:
                urls_set.remove(last_items.popleft())
            last_items.append(url)
            return True
        return False


def main(web_params, api_params, loop):
    """
    Р С›РЎРѓР Р…Р С•Р Р†Р Р…Р С•Р в„– РЎвЂ Р С‘Р С”Р В» Р В·Р В°Р С—РЎР‚Р С•РЎРѓР В° API РЎвЂЎР ВµРЎР‚Р ВµР В· undetectedРІР‚вЂchromedriver.
    Р вЂќР В»РЎРЏ Р С”Р В°Р В¶Р Т‘Р С•Р С–Р С• Р В·Р В°Р С—РЎР‚Р С•РЎРѓР В°:
      - Р С•Р В±Р Р…Р С•Р Р†Р В»РЎРЏР ВµРЎвЂљРЎРѓРЎРЏ Р С—Р В°РЎР‚Р В°Р СР ВµРЎвЂљРЎР‚ Р Р†РЎР‚Р ВµР СР ВµР Р…Р С‘,
      - РЎвЂћР С•РЎР‚Р СР С‘РЎР‚РЎС“Р ВµРЎвЂљРЎРѓРЎРЏ URL РЎРѓ Р С—Р В°РЎР‚Р В°Р СР ВµРЎвЂљРЎР‚Р В°Р СР С‘,
      - Р Р†РЎвЂ№Р В±Р С‘РЎР‚Р В°Р ВµРЎвЂљРЎРѓРЎРЏ РЎРѓР В»Р ВµР Т‘РЎС“РЎР‹РЎвЂ°Р С‘Р в„– Р С—РЎР‚Р С•Р С”РЎРѓР С‘,
      - Р Р†РЎвЂ№Р С—Р С•Р В»Р Р…РЎРЏР ВµРЎвЂљРЎРѓРЎРЏ Р В·Р В°Р С—РЎР‚Р С•РЎРѓ РЎвЂЎР ВµРЎР‚Р ВµР В· Р В±РЎР‚Р В°РЎС“Р В·Р ВµРЎР‚,
      - Р ВµРЎРѓР В»Р С‘ Р С—Р С•Р В»РЎС“РЎвЂЎР ВµР Р…РЎвЂ№ Р Р…Р С•Р Р†РЎвЂ№Р Вµ Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р Вµ, РЎРѓРЎРѓРЎвЂ№Р В»Р С”Р В° Р С•РЎвЂљР С—РЎР‚Р В°Р Р†Р В»РЎРЏР ВµРЎвЂљРЎРѓРЎРЏ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°Р С.
    """
    first_iter = True

    while True:
        try:
            api_params["time"] = str(current_date_to_unix())
            web_params["time"] = str(current_date_to_unix())

            web_url = "https://www.vinted.it/catalog?" + urlencode(web_params)
            api_site = "https://www.vinted.it/api/v2/catalog/items?" + urlencode(
                api_params
            )

            data = None
            try_count = 0
            max_tries = 3

            while not data and try_count < max_tries:
                try_count += 1
                thread_random = get_thread_local_random()
                proxy_port = thread_random.choice(PROXY_HOSTS)
                data = fetch_api(web_url, api_site, proxy_port)

            if data is None:
                logging.warning("Failed to fetch data, retrying...")
                continue

            for item in data.get("items", [])[:5]:
                try:
                    url = item.get("url")
                    timestamp = (
                        item.get("photo", {}).get("high_resolution", {}).get("timestamp", 0)
                    )
                    if add_url(url):
                        if not first_iter and current_date_to_unix() - timestamp < 1200:
                            bot.send_message(5530555626, 'send server 1')
                            # logging.info(f"РћС‚РєСЂС‹РІР°СЋ URL: {url}")
                            # try:
                            #     loop.call_soon_threadsafe(schedule_broadcast, url, loop)
                            # except Exception as e:
                            #     logging.error(f"Broadcast error: {str(e)}")

                except Exception as e:
                    logging.error(f"Error processing item: {str(e)}")
                    continue

            first_iter = False

        except Exception as e:
            logging.error(f"Unexpected error in main loop: {str(e)}")
            continue


if __name__ == "__main__":
    main_loop = asyncio.new_event_loop()
    websocket_thread = threading.Thread(
        target=start_websocket_server_thread,
        args=(main_loop,),
        daemon=True
    )
    websocket_thread.start()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        futures = [
            executor.submit(main, web_params_1, api_params_1, main_loop),
            executor.submit(main, web_params_2, api_params_2, main_loop),
            executor.submit(main, web_params_3, api_params_3, main_loop),
            executor.submit(main, web_params_4, api_params_4, main_loop),
            executor.submit(main, web_params_5, api_params_5, main_loop),
            executor.submit(main, web_params_6, api_params_6, main_loop),
        ]

