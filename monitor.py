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
import time
import urllib.request
from html import unescape
from pathlib import Path
from urllib.error import URLError, HTTPError

USER_AGENT = (
    "Mozilla/5.0 (compatible; TelegramChannelMonitor/1.0; +https://github.com/openclawromanaibot/telegram-channel-monitor)"
)


def fetch_channel(channel: str) -> str:
    url = f"https://t.me/s/{channel.lstrip('@')}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_posts(html: str, channel: str) -> list[dict]:
    """Extract posts from t.me/s/ HTML. Returns list of {id, text, url, date}."""
    posts = []
    # Each message block roughly: data-post="channel/123" ... <div class="tgme_widget_message_text">...</div>
    pattern = re.compile(
        r'data-post="(?P<channel>[^"]+)/(?P<id>\d+)"'
        r'.*?class="tgme_widget_message_date".*?datetime="(?P<date>[^"]+)"'
        r'.*?class="tgme_widget_message_text[^"]*"[^>]*>(?P<body>.*?)</div>',
        re.DOTALL | re.IGNORECASE,
    )
    for m in pattern.finditer(html):
        body = m.group("body")
        # Strip HTML tags
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
    # Newest first usually; keep order as found
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
        # Support simple phrases; case-insensitive substring
        if kw.lower() in lower:
            found.append(kw)
    return found


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
    # Support both | and , as separators for keywords
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
    seen = state.setdefault("seen", {})  # channel -> set of post ids (as list in json)

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
            # Always mark as seen so we don't re-process after the window moves
            channel_seen.add(pid)

        # Keep only recent IDs to avoid unbounded growth (last ~50)
        seen[channel] = sorted(channel_seen, key=int, reverse=True)[:50]

    if matches:
        # Newest first roughly
        for post, found in matches:
            kw_str = ", ".join(found)
            # Compact one-block message for Telegram
            print(f"🔔 {post['channel']} · {post['date']}")
            print(f"Keywords: {kw_str}")
            print(post["text"][:800] + ("…" if len(post["text"]) > 800 else ""))
            print(post["url"])
            print("---")

    if not args.dry_run:
        save_state(state_path, state)

    # Exit 0 always; empty stdout = no notification from Hermes
    return 0


if __name__ == "__main__":
    sys.exit(main())
