#!/usr/bin/env python3
"""
Telegram public channel keyword monitor.
Fetches https://t.me/s/<channel>, extracts recent posts, matches keywords.
Prints matching posts to stdout (for Hermes cron deliver).
Designed for pure-script cron jobs: no_agent=true, deliver=telegram:...

Usage:
  python3 monitor.py --channels channel1,channel2 --keywords "keyword1|keyword2" [--state state.json]

Environment overrides:
  CHANNELS=chan1,chan2
  KEYWORDS=word1|word2
  STATE_FILE=/path/to/state.json
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.error import URLError, HTTPError

USER_AGENT = (
    "Mozilla/5.0 (compatible; TelegramChannelMonitor/1.0; "
    "+https://github.com/openclawromanaibot/telegram-channel-monitor)"
)


def fetch_channel(channel: str) -> str:
    url = f"https://t.me/s/{channel.lstrip('@')}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_posts(html: str, channel: str) -> list[dict]:
    """Extract posts from t.me/s/ HTML. Returns list of {id, text, url, date}."""
    posts = []
    pattern = re.compile(
        r'data-post="(?P<channel>[^"]+)/(?P<id>\d+)"'
        r'.*?class="tgme_widget_message_date".*?datetime="(?P<date>[^"]+)"'
        r'.*?class="tgme_widget_message_text[^"]*"[^>]*>(?P<body>.*?)</div>',
        re.DOTALL | re.IGNORECASE,
    )
    for m in pattern.finditer(html):
        body = m.group("body")
        text = re.sub(r"<[^>]+>", " ", body)
        text = unescape(re.sub(r"\s+", " ", text)).strip()
        if not text:
            continue
        post_id = m.group("id")
        posts.append(
            {
                "id": post_id,
                "channel": m.group("channel"),
                "text": text,
                "url": f"https://t.me/{m.group('channel')}/{post_id}",
                "date": m.group("date"),
            }
        )
    return posts


def load_state(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def match_keywords(text: str, keywords: list[str]) -> list[str]:
    found = []
    lower = text.lower()
    for kw in keywords:
        kw = kw.strip()
        if not kw:
            continue
        if kw.lower() in lower:
            found.append(kw)
    return found


def format_date(iso_date: str) -> str:
    """Make date human-readable."""
    try:
        # Telegram gives something like 2026-11-18T04:12:00+00:00
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%d.%m %H:%M")
    except Exception:
        return iso_date[:16]


def highlight_keywords(text: str, keywords: list[str]) -> str:
    """Simple highlight: wrap matched keywords in *bold* (Telegram markdown)."""
    result = text
    for kw in sorted(keywords, key=len, reverse=True):
        if not kw:
            continue
        # case-insensitive replace, keep original case
        pattern = re.compile(re.escape(kw), re.IGNORECASE)
        result = pattern.sub(lambda m: f"*{m.group(0)}*", result)
    return result


def format_match(post: dict, found: list[str]) -> str:
    """Pretty single notification block for Telegram."""
    channel = post["channel"]
    date_str = format_date(post["date"])
    keywords_str = ", ".join(found)
    text = post["text"]

    # Truncate long texts nicely
    max_len = 650
    if len(text) > max_len:
        text = text[: max_len - 1].rsplit(" ", 1)[0] + "…"

    text = highlight_keywords(text, found)

    lines = [
        f"🔔 *Новое совпадение*",
        f"📢 `{channel}`  ·  🕒 {date_str}",
        f"🔑 {keywords_str}",
        "",
        text,
        "",
        f"→ {post['url']}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor public Telegram channels for keywords")
    parser.add_argument(
        "--channels",
        default=os.environ.get("CHANNELS", ""),
        help="Comma-separated channel usernames (without @)",
    )
    parser.add_argument(
        "--keywords",
        default=os.environ.get("KEYWORDS", ""),
        help="Pipe- or comma-separated keywords (case-insensitive)",
    )
    parser.add_argument(
        "--state",
        default=os.environ.get("STATE_FILE", "state.json"),
        help="Path to state file that remembers last seen post IDs",
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=20,
        help="Max posts to consider per channel (preview usually ~20)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matches but do not update state",
    )
    args = parser.parse_args()

    channels = [c.strip().lstrip("@") for c in re.split(r"[,\s]+", args.channels) if c.strip()]
    raw_kw = args.keywords.replace("|", ",")
    keywords = [k.strip() for k in raw_kw.split(",") if k.strip()]

    if not channels:
        print("ERROR: no channels specified. Use --channels or CHANNELS env.", file=sys.stderr)
        return 1
    if not keywords:
        print("ERROR: no keywords specified. Use --keywords or KEYWORDS env.", file=sys.stderr)
        return 1

    state_path = Path(args.state)
    state = load_state(state_path)
    seen = state.setdefault("seen", {})

    matches = []

    for channel in channels:
        try:
            html = fetch_channel(channel)
        except (URLError, HTTPError, TimeoutError) as e:
            print(f"WARN: failed to fetch {channel}: {e}", file=sys.stderr)
            continue

        posts = extract_posts(html, channel)[: args.max_posts]
        channel_seen = set(seen.get(channel, []))

        for post in posts:
            pid = post["id"]
            if pid in channel_seen:
                continue
            found = match_keywords(post["text"], keywords)
            if found:
                matches.append((post, found))
            channel_seen.add(pid)

        seen[channel] = sorted(channel_seen, key=int, reverse=True)[:50]

    if matches:
        blocks = []
        for post, found in matches:
            blocks.append(format_match(post, found))

        # Join with a clean separator
        print("\n\n──────────────\n\n".join(blocks))

    if not args.dry_run:
        save_state(state_path, state)

    return 0


if __name__ == "__main__":
    sys.exit(main())
