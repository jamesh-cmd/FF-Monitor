import re
from collections import Counter, defaultdict
from keywords import KEYWORD_CATEGORIES, AI_KEYWORDS

STOPWORDS = {
    'the','a','an','and','or','but','in','on','at','to','for','of','with',
    'is','it','be','as','by','that','this','from','are','was','were','been',
    'have','has','had','do','does','did','will','would','could','should',
    'may','might','can','not','no','so','if','then','than','their','they',
    'them','we','you','he','she','his','her','its','our','my','your','i',
    'me','him','us','who','what','which','when','where','how','all','just',
    'about','up','out','more','also','like','get','got','go','going','said',
    'one','two','three','new','also','even','still','back','only','very',
    'much','well','good','know','think','right','here','see','now','want',
    'way','make','come','look','take','use','into','over','after','time',
    'some','would','there','than','been','has','its','been','were','had'
}

def analyze_posts(posts):
    return {
        'keyword_hits':        count_keyword_hits(posts),
        'top_100_words':       get_top_keywords(posts, n=100),
        'uncategorised_words': get_uncategorised_words(posts, min_count=10),
        'all_urls':            extract_all_urls(posts),
        'gdrive_urls':         extract_gdrive_urls(posts),
        'ai_mentions':         find_ai_mentions(posts),
        'thread_stats':        get_thread_stats(posts),
        'trend_signals':       get_trend_signals(posts),
    }

def count_keyword_hits(posts):
    hits = {cat: 0 for cat in KEYWORD_CATEGORIES}
    all_text = ' '.join(p['text'].lower() for p in posts)
    for category, keywords in KEYWORD_CATEGORIES.items():
        for kw in keywords:
            hits[category] += len(re.findall(re.escape(kw.lower()), all_text))
    return hits

def get_top_keywords(posts, n=100):
    all_words = []
    for post in posts:
        words = re.findall(r"\b[a-z]{3,}\b", post['text'].lower())
        all_words.extend(w for w in words if w not in STOPWORDS)
    return Counter(all_words).most_common(n)

def get_uncategorised_words(posts, min_count=10):
    """
    Find high-frequency words that don't match any existing keyword category.
    These are candidates for new keywords — your daily discovery feed.
    """
    # Build a flat set of all tracked keyword fragments
    all_tracked = set()
    for keywords in KEYWORD_CATEGORIES.values():
        for kw in keywords:
            # Add each word within the keyword phrase too
            for word in kw.lower().split():
                all_tracked.add(word.strip())

    # Count all words across posts
    all_words = []
    for post in posts:
        words = re.findall(r"\b[a-z]{3,}\b", post['text'].lower())
        all_words.extend(w for w in words if w not in STOPWORDS)

    word_counts = Counter(all_words)

    # Filter: only words above threshold that aren't already tracked
    uncategorised = [
        (word, count)
        for word, count in word_counts.most_common(200)
        if count >= min_count
        and not any(word in kw.lower() or kw.lower() in word
                    for kws in KEYWORD_CATEGORIES.values()
                    for kw in kws)
        and word not in all_tracked
    ]

    return uncategorised[:50]  # top 50 uncategorised terms

def extract_all_urls(posts):
    seen = set()
    urls = []
    for post in posts:
        for url in post.get('urls', []):
            if url not in seen:
                seen.add(url)
                urls.append({
                    'url': url,
                    'thread': post['thread_url'],
                    'timestamp': post.get('timestamp')
                })
    return urls

def extract_gdrive_urls(posts):
    gdrive_domains = [
        'drive.google.com', 'docs.google.com',
        'sheets.google.com', 'slides.google.com', 'forms.google.com'
    ]
    results = []
    for post in posts:
        for url in post.get('urls', []):
            if any(d in url for d in gdrive_domains):
                results.append({
                    'url': url,
                    'thread': post['thread_url'],
                    'timestamp': post.get('timestamp'),
                    'context': post['text'][:300]
                })
    return results

def find_ai_mentions(posts):
    mentions = []
    for post in posts:
        text_lower = post['text'].lower()
        matched = [kw for kw in AI_KEYWORDS if kw in text_lower]
        if matched:
            mentions.append({
                'full_text': post['text'],
                'matched_keywords': matched,
                'thread': post['thread_url'],
                'timestamp': post.get('timestamp')
            })
    return mentions

def get_thread_stats(posts):
    thread_counts = defaultdict(int)
    for post in posts:
        thread_counts[post['thread_url']] += 1
    sorted_threads = sorted(thread_counts.items(), key=lambda x: x[1], reverse=True)
    return {
        'total_posts': len(posts),
        'active_threads': len(thread_counts),
        'most_active': sorted_threads[:5]
    }

def get_trend_signals(posts):
    hits = count_keyword_hits(posts)
    signals = []
    for cat, count in sorted(hits.items(), key=lambda x: x[1], reverse=True):
        if count > 50:
            signals.append(f"🔴 VERY HIGH: {cat} — {count} hits")
        elif count > 20:
            signals.append(f"🟠 HIGH: {cat} — {count} hits")
        elif count > 10:
            signals.append(f"🟡 ELEVATED: {cat} — {count} hits")
    return signals if signals else ["🟢 No elevated signals today."]
