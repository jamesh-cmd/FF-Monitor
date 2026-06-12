import os
import requests

def create_github_issue(analysis, date_str, thread_count):
    token   = os.environ['GITHUB_TOKEN']
    repo    = os.environ['GITHUB_REPOSITORY']
    body    = format_report(analysis, date_str, thread_count)

    resp = requests.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers={
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        },
        json={
            'title': f'📋 Daily Report — {date_str}',
            'body': body,
            'labels': ['daily-report']
        }
    )
    if resp.status_code == 201:
        print(f"✅ Issue created: {resp.json()['html_url']}")
    else:
        print(f"❌ Failed: {resp.status_code} — {resp.text}")

def format_report(analysis, date_str, thread_count):
    lines = []
    lines += [
        f"# 📋 Daily Monitoring Report — {date_str}",
        f"",
        f"**Threads active (24hrs):** {thread_count} &nbsp;|&nbsp; "
        f"**Posts analysed:** {analysis['thread_stats']['total_posts']}",
        f"",
        "---",
        ""
    ]

    # --- Keyword hits by category ---
    lines += ["## 🔴 Keyword Hits by Category", ""]
    lines += ["| Category | Hits |", "|---|---|"]
    for cat, count in sorted(analysis['keyword_hits'].items(), key=lambda x: x[1], reverse=True):
        marker = " ⚠️" if count > 20 else ""
        lines.append(f"| {cat} | **{count}**{marker} |")
    lines += [""]

    # --- Top 100 keywords ---
    lines += ["## 📊 Top 100 Most Frequent Keywords", ""]
    lines += ["| # | Keyword | Count |", "|---|---|---|"]
    for i, (word, count) in enumerate(analysis['top_100_words'], 1):
        lines.append(f"| {i} | `{word}` | {count} |")
    lines += [""]

    # --- Google Drive URLs (highlighted first) ---
    lines += ["## 🚨 Google Drive / Google Docs URLs", ""]
    gdrive = analysis['gdrive_urls']
    if gdrive:
        lines.append(f"**{len(gdrive)} Google Drive link(s) found:**")
        lines.append("")
        for item in gdrive:
            lines += [
                f"**URL:** {item['url']}",
                f"- Thread: {item['thread']}",
                f"- Posted: {item['timestamp'] or '_unknown_'}",
                f"- Context: _{item['context'][:200]}_",
                ""
            ]
    else:
        lines.append("_No Google Drive links found today._")
    lines.append("")

    # --- All URLs ---
    all_urls = analysis['all_urls']
    lines += [f"## 🌐 All URLs Shared ({len(all_urls)} total)", ""]
    if all_urls:
        for item in all_urls:
            lines.append(f"- `{item['url']}` — _{item['thread']}_")
    else:
        lines.append("_No URLs shared today._")
    lines.append("")

    # --- AI mentions (full messages) ---
    ai = analysis['ai_mentions']
    lines += [f"## 🤖 AI Mentions — Full Messages ({len(ai)} posts)", ""]
    if ai:
        for i, mention in enumerate(ai, 1):
            lines += [
                f"### Mention {i}",
                f"**Keywords matched:** {', '.join(f'`{k}`' for k in mention['matched_keywords'])}",
                f"**Thread:** {mention['thread']}",
                f"**Posted:** {mention['timestamp'] or '_unknown_'}",
                f"",
                f"**Full message:**",
                f"> {mention['full_text'].replace(chr(10), '  ')}",
                ""
            ]
    else:
        lines.append("_No AI mentions found today._")
    lines.append("")

    # --- Thread activity ---
    stats = analysis['thread_stats']
    lines += [
        "## 📈 Thread Activity", "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Active threads (24hrs) | {stats['active_threads']} |",
        f"| Total posts analysed | {stats['total_posts']} |",
        ""
    ]
    lines.append("**Most active threads:**")
    for url, count in stats['most_active']:
        lines.append(f"- {url} — **{count} posts**")
    lines.append("")

    # --- Trend signals ---
    lines += ["## ⚠️ Trend Signals", ""]
    for signal in analysis['trend_signals']:
        lines.append(f"- {signal}")

    return '\n'.join(lines)
