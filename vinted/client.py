import asyncio
import websockets
import webbrowser
import logging


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

chrome_path = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
webbrowser.register(''
                    'c',
                    None,
                    webbrowser.BackgroundBrowser(chrome_path)
                    )


async def receive_links(url: str) -> None:
    """
    Подключается к указанному серверу в асинхронном режиме.
    Raises:
        При исключении засыпает на определенное время
        и повторно пытается подключиться. Логирует ошибки в следующих случаях:
        - Неожиданная ошибка при формировании запроса
    :param url: адресная строка сайта
    :return: Ничего не возвращает
    """
    delay: int = 5
    while True:
        try:
            logging.info("Attempting to connect to %s", url)
            async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=60
            ) as websocket:
                logging.info("Connected to %s", url)
                while True:
                    try:
                        link = await websocket.recv()
                        logging.info("Received link from %s: %s", url, link)
                        webbrowser.get('c').open(link)

                    except websockets.exceptions.ConnectionClosed:
                        logging.warning("Connection to %s closed. Reconnecting...", url)
                        break

                    except Exception as e:
                        logging.error(f"Error receiving data: %s", e)
                        break

        except Exception as e:
            logging.error("Connection error to %s: %s", url, e)
            await asyncio.sleep(delay)
            delay: int = min(delay * 2, 60)


async def connect_to_servers(servers: list) -> None:
    """
    Создает задачу на подключение к серверу
    :param servers: Список серверов
    :return: Ничего не возвращает
    """
    tasks: list = []
    for server in servers:
        task = asyncio.create_task(receive_links(server))
        tasks.append(task)
    await asyncio.gather(*tasks, return_exceptions=True)


async def main() -> None:
    """
    Работает в бесконечном цикле.
    Заходит в функцию connect_to_servers().
    Со списком серверов
    :return: Ничего не возвращает
    """
    servers = [
        "",
        "",
        "",
    ]

    while True:
        try:
            await connect_to_servers(servers)
        except Exception as e:
            logging.error("An error occurred: %s", e)
        logging.info("Waiting 5 seconds before attempting to reconnect")
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
