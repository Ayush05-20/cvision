# scraper.py
import logging
import time
import random
from typing import List
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_webdriver() -> webdriver.Chrome:
    options = Options()
    options.headless = True
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"user-agent={random_user_agent()}")
    return webdriver.Chrome(options=options)


def random_user_agent():
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/15.1 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36"
    ]
    return random.choice(agents)


def scrape_website(url: str, timeout: int = 30) -> str:
    try:
        driver = create_webdriver()
        logger.info(f"Opening {url}")
        driver.get(url)

        time.sleep(random.uniform(2, 4))  # Mimic human delay
        html = driver.page_source
        driver.quit()
        logger.info("Scraping successful.")
        return html
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        return ""


def clean_body_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body
    if body:
        return body.get_text(separator="\n", strip=True)
    return soup.get_text(separator="\n", strip=True)


def split_dom_content(content: str, max_chars: int = 2000) -> List[str]:
    # Splits content into LLM-safe chunks
    paragraphs = content.split('\n')
    chunks = []
    current_chunk = ""
    for paragraph in paragraphs:
        if len(current_chunk) + len(paragraph) + 1 > max_chars:
            chunks.append(current_chunk.strip())
            current_chunk = paragraph
        else:
            current_chunk += "\n" + paragraph
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks
