from typing import Set
from collections import deque


TELEGRAM_BOT_TOKEN: str = ""
TELEGRAM_CHAT_ID: str = ""
LAST_ITEMS_MAX_SIZE: int = 2000
sent_products: Set[str] = set()
urls_queue: deque = deque(maxlen=LAST_ITEMS_MAX_SIZE)
MAX_TXT_LOG_SIZE_MB: int = 5
