import cloudscraper
from bs4 import BeautifulSoup
import time
import random
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

FORUM_URL = "https://fashfront.st"

def get_scraper():
    """Create a cloudscraper instance that bypasses Cloudflare JS challenges."""
    return cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'mobile': False
        }
    )

def get_page(scraper, url, retries=3):
    """Fetch a page with retries and polite delays."""
    for attempt in range(retries):
        try:
            response = scraper.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"  Attempt {attempt+1} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(random.uniform(3, 7))
    print(f"  Giving up on {url}")
    return None

def get_active_threads(scraper, since_hours=24):
    """
    Crawl the forum index to find all threads with activity
    in the last N hours. Returns list of {url, title} dicts.
    """
    cutoff = datetime.utcnow() - timedelta(hours=since_hours)
    active_threads = []

    print(f"Fetching forum index: {FORUM_URL}")
    html = get_page(scraper, FORUM_URL)
    if not html:
        print("ERROR: Could not load forum index.")
        return []

    soup = BeautifulSoup(html, 'lxml')

    # --- Collect board/category links ---
    # NOTE: These selectors may need adjusting based on the actual HTML.
    # Run the scraper once and check the output log — we'll tune from there.
    board_links = set()

    # Pattern A: Standard forum (phpBB, MyBB, XenForo style)
    for a in soup.select('a.forumtitle, a.forum-name, h3.node-title a, .forumrow a'):
        href = a.get('href', '')
        if href:
            board_links.add(urljoin(FORUM_URL, href))

    # Pattern B: Chan/Lynxchan style — boards as short paths (/b/, /pol/, etc.)
    if not board_links:
        for a in soup.select('a[href]'):
            href = a.get('href', '').strip('/')
            # Short board codes like "b", "pol", "int" etc.
            if re.match(r'^[a-z]{1,5}$', href):
                board_links.add(urljoin(FORUM_URL, f'/{href}/'))

    print(f"Found {len(board_links)} boards: {board_links}")

    for board_url in sorted(board_links):
        threads = get_board_threads(scraper, board_url, cutoff)
        active_threads.extend(threads)
        time.sleep(random.uniform(2, 4))

    return active_threads

def get_board_threads(scraper, board_url, cutoff):
    """Get all threads in a board that have been active since cutoff."""
    threads = []
    page = 1

    while True:
        # Try common pagination patterns
        if page == 1:
            url = board_url
        else:
            # Try both ?page= and /page-N/ style pagination
            url = f"{board_url.rstrip('/')}?page={page}"

        html = get_page(scraper, url)
        if not html:
            break

        soup = BeautifulSoup(html, 'lxml')
        found_old_thread = False

        # Collect thread rows — try multiple selector patterns
        thread_rows = (
            soup.select('.threadbit, .threadrow, tr.thread, .topic-row') or
            soup.select('div[id^="thread_"], li[id^="thread_"]') or
            soup.select('.structItem--thread')  # XenForo 2
        )

        # Chan-style: threads appear directly on board page
        if not thread_rows:
            thread_rows = soup.select('div[id^="thread"], .thread')

        if not thread_rows:
            print(f"  No thread rows found on {url} — selectors may need updating")
            break

        for row in thread_rows:
            link_el = row.select_one(
                'a.threadtitle, a.topictitle, h3.threadtitle a, '
                '.structItem-title a, a[href*="/thread/"], a[href*="/t/"], '
                'a[href*="/threads/"], .subject a'
            )
            if not link_el:
                continue

            thread_url = urljoin(board_url, link_el['href'])
            thread_title = link_el.get_text(strip=True)

            # Try to get last-post timestamp to filter by 24hrs
            time_el = row.select_one(
                'time, .lastpostdate, .thread-date, '
                'span[class*="time"], .structItem-cell--latest time'
            )
            thread_time = parse_timestamp(time_el)

            if thread_time is None:
                # Can't determine — include it to be safe
                threads.append({'url': thread_url, 'title': thread_title})
            elif thread_time >= cutoff:
                threads.append({'url': thread_url, 'title': thread_title})
            else:
                found_old_thread = True

        # Stop paginating if we've hit threads older than cutoff
        if found_old_thread:
            break

        # Check if there's a next page
        next_page = soup.select_one('a.nextlink, a[rel="next"], .pagination-next a')
        if not next_page:
            break

        page += 1
        time.sleep(random.uniform(1, 3))

    print(f"  Board {board_url}: {len(threads)} active threads")
    return threads

def scrape_thread(scraper, thread_url):
    """
    Scrape all posts from a thread posted in the last 24 hours.
    Returns list of post dicts with text, urls, timestamp, thread_url.
    """
    posts = []
    cutoff = datetime.utcnow() - timedelta(hours=24)
    page = 1

    while True:
        url = f"{thread_url.rstrip('/')}?page={page}" if page > 1 else thread_url
        html = get_page(scraper, url)
        if not html:
            break

        soup = BeautifulSoup(html, 'lxml')
        found_old_post = False
        page_had_posts = False

        # Try multiple post container selectors
        post_els = (
            soup.select('.postcontainer, .post_wrapper, .message-body') or
            soup.select('article.message, .post, div[id^="post_"]') or
            soup.select('blockquote.postMessage, .postMessage') or  # chan style
            soup.select('.body-block, .post-content')
        )

        for post_el in post_els:
            # Get timestamp
            time_el = post_el.select_one(
                'time, .postdate, .post-date, '
                'span.date, .message-date time'
            ) or post_el.find_parent().select_one('time, .postdate') if post_el.find_parent() else None

            post_time = parse_timestamp(time_el)

            # Get post text
            content_el = post_el.select_one(
                '.postcontent, .post-body, .message-userContent, '
                'blockquote, .postMessage, .post_body'
            ) or post_el

            if not content_el:
                continue

            text = content_el.get_text(separator=' ', strip=True)

            if not text or len(text) < 5:
                continue

            # Extract URLs from links
            urls = []
            for a in content_el.select('a[href]'):
                href = a.get('href', '')
                if href.startswith('http'):
                    urls.append(href)

            # Also extract raw URLs typed in text
            raw_urls = re.findall(r'https?://[^\s<>"\'\)]+', text)
            urls = list(set(urls + raw_urls))

            if post_time is None or post_time >= cutoff:
                posts.append({
                    'text': text,
                    'urls': urls,
                    'timestamp': post_time.isoformat() if post_time else None,
                    'thread_url': thread_url
                })
                page_had_posts = True
            else:
                found_old_post = True

        if found_old_post or not page_had_posts:
            break

        next_page = soup.select_one('a.nextlink, a[rel="next"], .pagination-next a')
        if not next_page:
            break

        page += 1
        time.sleep(random.uniform(1, 2))

    return posts

def parse_timestamp(time_el):
    """Try to parse a datetime from a time element. Returns datetime or None."""
    if not time_el:
        return None
    try:
        # Try datetime attribute first (most reliable)
        dt_str = time_el.get('datetime') or time_el.get_text(strip=True)
        dt_str = dt_str.replace('Z', '+00:00').strip()
        dt = datetime.fromisoformat(dt_str)
        return dt.replace(tzinfo=None)
    except Exception:
        return None
