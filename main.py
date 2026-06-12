import pytz
from datetime import datetime
from scraper import get_scraper, get_active_threads, scrape_thread
from analyzer import analyze_posts
from reporter import create_github_issue

def main():
    print(f"=== Forum Monitor starting at {datetime.utcnow().isoformat()} UTC ===")

    scraper = get_scraper()

    print("\n[1/4] Discovering active threads...")
    active_threads = get_active_threads(scraper, since_hours=24)
    print(f"      → {len(active_threads)} active threads found")

    if not active_threads:
        print("No active threads found. Exiting.")
        return

    print("\n[2/4] Scraping posts from active threads...")
    all_posts = []
    for i, thread in enumerate(active_threads, 1):
        print(f"      Thread {i}/{len(active_threads)}: {thread['url']}")
        posts = scrape_thread(scraper, thread['url'])
        print(f"        → {len(posts)} posts collected")
        all_posts.extend(posts)

    print(f"\n      Total posts: {len(all_posts)}")

    print("\n[3/4] Analysing content...")
    analysis = analyze_posts(all_posts)

    print("\n[4/4] Creating GitHub Issue report...")
    bst = pytz.timezone('Europe/London')
    date_str = datetime.now(bst).strftime('%A %d %B %Y — %I:%M %p BST')
    create_github_issue(analysis, date_str, len(active_threads))

    print("\n=== Done ===")

if __name__ == '__main__':
    main()
