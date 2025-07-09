from selenium.webdriver.chrome.options import Options


chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument('--disable-blink-features=AutomationControlled')
chrome_options.add_argument('--disable-extensions')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--ignore-certificate-errors')
chrome_options.add_argument('--allow-running-insecure-content')
chrome_options.add_argument('--disable-web-security')
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)
