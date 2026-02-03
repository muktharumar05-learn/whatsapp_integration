import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from bs4.element import Comment
from urllib.parse import urljoin, urlparse
import re
import os
import logging

def tag_visible(element):
    if element.parent.name in ['style', 'script', 'head', 'title', 'meta', '[document]', 'noscript', 'footer', 'nav', 'header', 'form']:
        return False
    if isinstance(element, Comment):
        return False
    return True

def text_from_html(body):
    soup = BeautifulSoup(body, 'html.parser')
    texts = soup.find_all(text=True)
    visible_texts = filter(tag_visible, texts)
    return u" ".join(t.strip() for t in visible_texts if t.strip())

def is_valid_url(url, base_netloc):
    parsed = urlparse(url)
    return (parsed.scheme in ["http", "https"]) and (parsed.netloc == base_netloc)

async def auto_scroll(page):
    distance = 100
    delay = 0.2
    previous_height = await page.evaluate("document.body.scrollHeight")
    while True:
        await page.evaluate(f"window.scrollBy(0, {distance});")
        await asyncio.sleep(delay)
        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == previous_height:
            break
        previous_height = new_height

def safe_filename(url):
    # Remove scheme and replace non-alphanum with underscores
    parsed = urlparse(url)
    path = parsed.netloc + parsed.path
    filename = re.sub(r'[^a-zA-Z0-9]', '_', path)
    if not filename.endswith('.txt'):
        filename += '.txt'
    return filename

async def scrape_page(playwright, phone, url):
    logging.info(f"Scraping (Playwright): {url}")
    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=6000000)
        await asyncio.sleep(2)
        await auto_scroll(page)
        await asyncio.sleep(2)

        content = await page.content()
        visible_text = text_from_html(content)

        # Save full visible text to file

        base_dir = "scrape/scraped_pages"
        customer_dir = os.path.join(base_dir, phone)
        os.makedirs(customer_dir, exist_ok=True)
        filename = safe_filename(url)
        filepath = os.path.join(customer_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(visible_text)
        logging.info(f"Saved {len(visible_text)} chars of visible text to {filepath}")

        base_netloc = urlparse(url).netloc
        soup = BeautifulSoup(content, "html.parser")
        links = set()
        for a in soup.find_all("a", href=True):
            href = a['href']
            full_url = urljoin(url, href)
            if is_valid_url(full_url, base_netloc):
                links.add(full_url)

        await browser.close()
        return visible_text, links
    except Exception as e:
        logging.info(f"Failed to scrape {url}: {e}")
        await browser.close()
        return "", set()

async def crawl_website(start_url, phone, max_pages=1000):
    visited = set()
    to_visit = [start_url]

    async with async_playwright() as playwright:
        while to_visit and len(visited) < max_pages:
            url = to_visit.pop(0)
            if url in visited:
                continue
            content, links = await scrape_page(playwright, phone, url)
            visited.add(url)
            for link in links:
                if link not in visited and link not in to_visit:
                    to_visit.append(link)
            await asyncio.sleep(1)
    logging.info(f"Crawled {len(visited)} pages.")