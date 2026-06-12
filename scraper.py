import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from bs4 import BeautifulSoup
import time
import random
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

FORUM_URL = "https://fashfront.st"

async def get_page_async(page, url, retries=3):
    """Fetch a page using stealth Playwright browser."""
    for attempt in range(retries):
        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(random.uniform(2, 4))
            return await page.content()
        except Exception as e:
            print(f"  Attempt {attempt+1} failed for {url}: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(random.uniform(3, 6))
    print(f"  Giving up on {url}")
    return None

async def scrape_all():
    """Main async scraping function."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/124.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 800},
            locale='en-GB',
        )
        page = await context.new_page()
        await stealth_async(page)

        cutoff = datetime.utcnow() - timedelta(hours=24)
        all_posts = []
        active_threads = []

        print(f"Fetching forum index: {FORUM_URL}")
        html = await get_page_async(page, FORUM_URL)

        if not html:
            print("ERROR: Could not load forum index.")
            await browser.close()
            return [], []

        soup = BeautifulSoup(html, 'lxml')
        board_links = set()

        # Pattern A: Standard forum board links
        for a in soup.select('a.forumtitle, a.forum-name, h3.node-title a, .forumrow a'):
            href = a.get('href', '')
            if href:
                board_links.add(urljoin(FORUM_URL, href))

        # Pattern B: Chan/Lynxchan style short board paths
        if not board_links:
            for a in soup.select('a[href]'):
                href = a.get('href', '').strip('/')
                if re.match(r'^[a-z]{1,5}$', href):
                    board_links.add(urljoin(FORUM_URL, f'/{href}/'))

        # Pattern C: Direct thread links on index page
        if not board_links:
            for a in soup.select('a[href*="/thread/"], a[href*="/t/"], a[href*="/res/"]'):
                href = a.get('href', '')
                if href:
                    active_threads.append({
                        'url': urljoin(FORUM_URL, href),
                        'title': a.get_text(strip=True)
                    })

        print(f"Found {len(board_links)} boards, {len(active_threads)} direct threads")

        # Scrape boards
        for board_url in sorted(board_links):
            threads = await get_board_threads_async(page, board_url, cutoff)
            active_threads.extend(threads)
            await asyncio.sleep(random.uniform(2, 4))

        # Scrape each thread
        for i, thread in enumerate(active_threads, 1):
            print(f"  Thread {i}/{len(active_threads)}: {thread['url']}")
            posts = await scrape_thread_async(page, thread['url'], cutoff)
            print(f"    → {len(posts)} posts")
            all_posts.extend(posts)
            await asyncio.sleep(random.uniform(2, 3))

        await browser.close()
        return all_posts, active_threads

async def get_board_threads_async(page, board_url, cutoff):
    threads = []
    page_num = 1

    while True:
        url = f"{board_url.rstrip('/')}?page={page_num}" if page_num > 1 else board_url
        html = await get_page_async(page, url)
        if not html:
            break

        soup = BeautifulSoup(html, 'lxml')
        found_old = False

        thread_rows = (
            soup.select('.threadbit, .threadrow, tr.thread, .topic-row') or
            soup.select('div[id^="thread_"], li[id^="thread_"]') or
            soup.select('.structItem--thread') or
            soup.select('div[id^="thread"], .thread')
        )

        if not thread_rows:
            break

        for row in thread_rows:
            link_el = row.select_one(
                'a.threadtitle, a.topictitle, h3.threadtitle a, '
                '.structItem-title a, a[href*="/thread/"], a[href*="/t/"], '
                'a[href*="/threads/"], a[href*="/res/"], .subject a'
            )
            if not link_el:
                continue

            thread_url = urljoin(board_url, link_el['href'])
            thread_title = link_el.get_text(strip=True)
            time_el = row.select_one('time, .lastpostdate, span[class*="time"]')
            thread_time = parse_timestamp(time_el)

            if thread_time is None or thread_time >= cutoff:
                threads.append({'url': thread_url, 'title': thread_title})
            else:
                found_old = True

        if found_old:
            break

        next_page = soup.select_one('a.nextlink, a[rel="next"], .pagination-next a')
        if not next_page:
            break

        page_num += 1
        await asyncio.sleep(random.uniform(1, 3))

    print(f"  Board {board_url}: {len(threads)} active threads")
    return threads

async def scrape_thread_async(page, thread_url, cutoff):
    posts = []
    page_num = 1

    while True:
        url = f"{thread_url.rstrip('/')}?page={page_num}" if page_num > 1 else thread_url
        html = await get_page_async(page, url)
        if not html:
            break

        soup = BeautifulSoup(html, 'lxml')
        found_old = False
        page_had_posts = False

        post_els = (
            soup.select('.postcontainer, .post_wrapper, .message-body') or
            soup.select('article.message, .post, div[id^="post_"]') or
            soup.select('blockquote.postMessage, .postMessage') or
            soup.select('.body-block, .post-content')
        )

        for post_el in post_els:
            parent = post_el.find_parent()
            time_el = post_el.select_one('time, .postdate, .post-date, span.date') or \
                      (parent.select_one('time, .postdate') if parent else None)

            post_time = parse_timestamp(time_el)
            content_el = post_el.select_one(
                '.postcontent, .post-body, .message-userContent, '
                'blockquote, .postMessage, .post_body'
            ) or post_el

            text = content_el.get_text(separator=' ', strip=True)
            if not text or len(text) < 5:
                continue

            urls = []
            for a in content_el.select('a[href]'):
                href = a.get('href', '')
                if href.startswith('http'):
 
