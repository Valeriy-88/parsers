from selenium.webdriver.chrome.options import Options

TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-gpu")
options.add_argument("--disable-dev-shm-usage")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
