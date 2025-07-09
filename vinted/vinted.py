import asyncio
import logging
import random
import time
import json
from typing import Any
from urllib.parse import urlencode
from collections import deque
from fake_useragent import UserAgent
import websockets
from playwright.async_api import async_playwright
from parameter import (
    api_params_1, api_params_2,
    api_params_3, api_params_4,
    api_params_5, api_params_6,
    web_params_1, web_params_2,
    web_params_3, web_params_4,
    web_params_5, web_params_6,
)
from config import (
    PROXY_USER,
    PROXY_PASS,
    PROXY_PORT,
    LAST_ITEMS_MAX_SIZE,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    USER_AGENT_ROTATION_INTERVAL,
)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('error_code.txt'),
        logging.StreamHandler()
    ]
)


class AntiDetectionSystem:
    """
    Класс для обхода антибот-систем. Содержит методы для:

    - Ротации User-Agent
    - Управления прокси
    - Генерации случайных параметров браузера
    (разрешение, таймзона, локаль)
    """
    def __init__(self):
        self.ua = UserAgent()
        self.request_counter: int = 0
        self.current_user_agent = self.ua.random
        self.proxy_hosts: list[str] = ['',]
        self.proxy_rotation_index: int = 0
        self.common_resolutions: list[dict] = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1440, "height": 900},
            {"width": 1536, "height": 864}
        ]
        self.timezones: list[str] = [
            "America/New_York", "Europe/Paris",
            "Asia/Tokyo", "Australia/Sydney"
        ]
        self.locales: list[str] = [
            "en-US,en;q=0.9",
            "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
        ]

    def get_random_viewport(self):
        """Возвращает случайное разрешение экрана"""
        return random.choice(self.common_resolutions)

    def get_random_timezone(self):
        """Возвращает случайную таймзону"""
        return random.choice(self.timezones)

    def get_random_locale(self):
        """Возвращает случайную локаль"""
        return random.choice(self.locales)

    def rotate_user_agent(self):
        """Меняет User-Agent на случайный"""
        self.current_user_agent = self.ua.random
        self.request_counter: int = 0
        logging.info(
            "Rotated User-Agent to: %s",
            self.current_user_agent
        )

    def get_next_proxy(self):
        """Возвращает следующий прокси из списка (ротация)"""
        proxy: str = self.proxy_hosts[self.proxy_rotation_index]
        self.proxy_rotation_index = (self.proxy_rotation_index + 1) % len(self.proxy_hosts)
        return proxy


class Parser:
    """
    Основной класс парсера Vinted. Обеспечивает:

    - Парсинг данных через API
    - Управление WebSocket-сервером
    - Обработку и фильтрацию URL
    - Распределенную работу через несколько воркеров
    """
    def __init__(self):
        self.ads = AntiDetectionSystem()
        self.urls_set: set = set()
        self.last_items = asyncio.Queue(maxsize=LAST_ITEMS_MAX_SIZE)
        self.urls_queue = deque(maxlen=LAST_ITEMS_MAX_SIZE)
        self.lock = asyncio.Lock()
        self.connected_clients: set = set()
        self.params_list: list[tuple[Any, Any]] = [
            (web_params_1, api_params_1),
            (web_params_2, api_params_2),
            (web_params_3, api_params_3),
            (web_params_4, api_params_4),
            (web_params_5, api_params_5),
            (web_params_6, api_params_6),
        ]

    async def broadcast_link(self, link):
        """Рассылает ссылку всем подключенным WebSocket-клиентам"""
        if self.connected_clients:
            logging.info("Broadcasting link: %s", link)
            await asyncio.gather(
                *(client.send(link) for client in self.connected_clients)
            )

    async def handle_client(self, websocket, path=None):
        """Обрабатывает подключение WebSocket-клиента"""
        self.connected_clients.add(websocket)
        logging.info(
            "Client connected: %s",
            websocket.remote_address
        )
        try:
            async for message in websocket:
                logging.info("Received message: %s", message)
        except Exception as e:
            logging.error("Client connection error: %s", e)
        finally:
            self.connected_clients.remove(websocket)
            logging.info(f"Client disconnected: {websocket.remote_address}")

    async def start_websocket_server(self, host='0.0.0.0', port=3454):
        """Запускает WebSocket-сервер"""
        server = await websockets.serve(self.handle_client, host, port)
        logging.info(
            "WebSocket server started at %s:%s",
            host, port
        )
        await server.wait_closed()

    async def fetch_api_data(self, site_url, api_url):
        """Получает данные через API с защитой от блокировки"""
        for attempt in range(MAX_RETRIES):
            proxy_host: str = self.ads.get_next_proxy()
            proxy: dict = {
                "server": f"http://{proxy_host}:{PROXY_PORT}",
                "username": PROXY_USER,
                "password": PROXY_PASS
            }
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=True,
                        proxy=proxy,
                        timeout=REQUEST_TIMEOUT,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--disable-infobars",
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-dev-shm-usage",
                            f"--user-agent={self.ads.current_user_agent}"
                        ]
                    )

                    try:
                        context = await browser.new_context(
                            user_agent=self.ads.current_user_agent,
                            viewport=self.ads.get_random_viewport(),
                            locale=self.ads.get_random_locale(),
                            timezone_id=self.ads.get_random_timezone(),
                            java_script_enabled=True,
                            permissions=[],
                            geolocation=None,
                            has_touch=False,
                            http_credentials=None,
                            color_scheme="light"
                        )

                        await context.add_init_script("""
                                                Object.defineProperty(navigator, 'webdriver', {
                                                    get: () => false,
                                                });
                                                Object.defineProperty(navigator, 'plugins', {
                                                    get: () => [1, 2, 3],
                                                });
                                                Object.defineProperty(navigator, 'languages', {
                                                    get: () => ['en-US', 'en'],
                                                });
                                                window.chrome = {
                                                    app: {
                                                        isInstalled: false,
                                                    },
                                                    webstore: {
                                                        onInstallStageChanged: {},
                                                        onDownloadProgress: {},
                                                    },
                                                    runtime: {
                                                        PlatformOs: {
                                                            MAC: 'mac',
                                                            WIN: 'win',
                                                            ANDROID: 'android',
                                                            CROS: 'cros',
                                                            LINUX: 'linux',
                                                            OPENBSD: 'openbsd',
                                                        },
                                                        PlatformArch: {
                                                            ARM: 'arm',
                                                            X86_32: 'x86-32',
                                                            X86_64: 'x86-64',
                                                        },
                                                        PlatformNaclArch: {
                                                            ARM: 'arm',
                                                            X86_32: 'x86-32',
                                                            X86_64: 'x86-64',
                                                        },
                                                        RequestUpdateCheckStatus: {
                                                            THROTTLED: 'throttled',
                                                            NO_UPDATE: 'no_update',
                                                            UPDATE_AVAILABLE: 'update_available',
                                                        },
                                                        OnInstalledReason: {
                                                            INSTALL: 'install',
                                                            UPDATE: 'update',
                                                            SHARED_MODULE_UPDATE: 'shared_module_update',
                                                        },
                                                        OnRestartRequiredReason: {
                                                            APP_UPDATE: 'app_update',
                                                            OS_UPDATE: 'os_update',
                                                            PERIODIC: 'periodic',
                                                        },
                                                    },
                                                };
                                            """)

                        page = await context.new_page()
                        await page.goto(site_url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT)
                        await asyncio.sleep(random.uniform(10, 15))

                        async with context.expect_page() as new_page:
                            await page.evaluate("window.open('%s', '_blank')", api_url)
                        api_page = await new_page.value

                        await api_page.bring_to_front()
                        await api_page.wait_for_load_state("domcontentloaded")
                        body_text = await api_page.locator("body").text_content()

                        self.ads.request_counter += 1
                        if self.ads.request_counter >= USER_AGENT_ROTATION_INTERVAL:
                            self.ads.rotate_user_agent()
                        return body_text
                    except Exception as e:
                        logging.warning(
                            "Attempt %s proxy=%s failed: %s",
                            attempt + 1, proxy_host, e
                        )
                    finally:
                        await browser.close()
            except Exception:
                if attempt < MAX_RETRIES - 1:
                    delay = random.uniform(1, 3)
                    await asyncio.sleep(delay)
                else:
                    logging.error(
                        "All attempts failed for %s",
                        api_url
                    )
                    return None

    async def add_url(self, url: str):
        """Добавляет URL в коллекцию с проверкой уникальности"""
        async with self.lock:
            if url not in self.urls_set:
                self.urls_set.add(url)
                self.urls_queue.append(url)
                if len(self.urls_queue) > LAST_ITEMS_MAX_SIZE:
                    old_url = self.urls_queue.popleft()
                    self.urls_set.remove(old_url)
                return True
            return False

    async def worker(self, web_params, api_params):
        """Основной рабочий процесс парсинга"""
        first_iter: bool = True

        while True:
            try:
                ts = str(int(time.time()))
                api_params["time"]: str = ts
                web_params["time"]: str = ts

                web_url: str = f"https://www.vinted.it/catalog?{urlencode(web_params)}"
                api_url: str = f"https://www.vinted.it/api/v2/catalog/items?{urlencode(api_params)}"

                data = await self.fetch_api_data(web_url, api_url)
                if not data:
                    await asyncio.sleep(10)
                    continue

                try:
                    data_json: dict = json.loads(data)
                except json.JSONDecodeError:
                    logging.error("Failed to parse JSON data")
                    await asyncio.sleep(5)
                    continue

                for item in data_json.get("items", [])[:5]:
                    try:
                        url: str = item.get("url")
                        ts_item = (item.get("photo", {})
                                   .get("high_resolution", {})
                                   .get("timestamp", 0))

                        if await self.add_url(url):
                            if self.last_items.full():
                                await self.last_items.get()
                            await self.last_items.put(url)

                            if not first_iter and (time.time() - ts_item) < 1200:
                                await self.broadcast_link(url)
                    except Exception as e:
                        logging.error("Error processing item: %s", e)

                first_iter: bool = False
                await asyncio.sleep(5)

            except Exception as e:
                logging.error("Worker error: %s", e)
                await asyncio.sleep(5)

    async def run(self):
        """
        Главный метод запуска парсера
        (запускает WebSocket и воркеры)
        """
        ws_server_task = asyncio.create_task(self.start_websocket_server())
        worker_tasks: list = [
            asyncio.create_task(self.worker(web_params, api_params))
            for web_params, api_params in self.params_list
        ]

        try:
            await asyncio.gather(ws_server_task, *worker_tasks)
        except Exception as e:
            logging.error("Fatal error: %s", e)
        finally:
            await ws_server_task
            for task in worker_tasks:
                task.cancel()


if __name__ == "__main__":
    parser = Parser()
    asyncio.run(parser.run())
