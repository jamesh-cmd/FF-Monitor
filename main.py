import pytz
from datetime import datetime
from scraper import get_all_posts
from analyzer import analyze_posts
from reporter import create_github_issue

def main():
    print(f"=== Forum Monitor starting at {datetime.utcnow().isoformat()} UTC ===")

    print("\n[1/4] Discovering and scraping threads...")
    all_posts, active_threads = get_all_posts()
    print(f"\n      Total posts collected: {len(all_posts)}")

    if not all_posts:
        print("No posts found. Exiting.")
        return

    print("\n[2/4] Analysing content...")
    analysis = analyze_posts(all_posts)

    print("\n[3/4] Creating GitHub Issue report...")
    bst = pytz.timezone('Europe/London')
    date_str = datetime.now(bst).strftime('%A %d %B %Y — %I:%M %p BST')
    create_github_issue(analysis, date_str, len(active_threads))

    print("\n=== Done ===")

if __name__ == '__main__':
    main()
