#!/usr/bin/env python3
"""Pull the latest articles from Medium into data/medium.yaml.

    python generator/sync_medium.py

Medium's RSS feed only returns the ~10 most recent posts, so this script merges:
new articles are added, existing ones are updated, and anything you edited by hand
(excerpt, topic, featured, hidden) is kept. Safe to run on every deploy — if Medium
can't be reached, the existing file is left untouched.
"""
from __future__ import annotations

import datetime as dt
import email.utils
import html
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "medium.yaml"
FEED = "https://medium.com/feed/@imrohitkushwaha2001"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"
WORDS_PER_MINUTE = 230

TOPICS = [
    ("Cloud", {"aws", "aws-lambda", "cloud", "cloud-computing", "gcp", "azure", "devops"}),
    ("Engineering", {"distributed-systems", "software-engineering", "system-design-interview", "system-design", "backend"}),
    ("AI", {"ai", "artificial-intelligence", "machine-learning", "llm", "llm-quantization", "model-quantization",
            "generative-ai-use-cases", "generative-ai", "rag"}),
]
KEEP_FIELDS = ("excerpt", "topic", "featured", "hidden", "image", "image_alt", "takeaways")


def text_of(fragment: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))).strip()


def excerpt_from(body: str, title: str, limit: int = 180) -> str:
    for para in re.findall(r"<p>(.*?)</p>", body, flags=re.S):
        text = text_of(para)
        if text and not text.startswith(title[:30]):
            if len(text) <= limit:
                return text
            return text[:limit].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"
    return ""


def full_title(title: str, body: str) -> str:
    """The feed cuts long titles with '…'; the article body starts with the full one."""
    if not title.endswith("…"):
        return title
    stem = title[:-1].strip()
    for heading in re.findall(r"<h[1-4][^>]*>(.*?)</h[1-4]>", body, flags=re.S):
        text = text_of(heading)
        if text.startswith(stem):
            return text
    return title


def topic_for(tags: list[str]) -> str:
    for topic, names in TOPICS:
        if names & set(tags):
            return topic
    return "Writing"


def fetch() -> list[dict]:
    req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0 (site-builder)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        root = ET.fromstring(resp.read())

    items = []
    for item in root.iter("item"):
        body = item.findtext(CONTENT_NS, "")
        title = full_title(html.unescape(item.findtext("title", "")).strip(), body)
        tags = [c.text for c in item.findall("category") if c.text]
        published = email.utils.parsedate_to_datetime(item.findtext("pubDate"))
        items.append({
            "title": title,
            "url": item.findtext("link", "").split("?")[0],
            "date": published.date(),
            "excerpt": excerpt_from(body, title),
            "topic": topic_for(tags),
            "tags": tags,
            "reading_time": max(1, round(len(text_of(body).split()) / WORDS_PER_MINUTE)),
        })
    return items


def main() -> int:
    try:
        fresh = fetch()
    except Exception as exc:  # network down, feed changed — keep what we have
        print(f"Medium sync skipped: {exc}", file=sys.stderr)
        return 0

    existing = []
    if OUT.exists():
        existing = yaml.safe_load(OUT.read_text(encoding="utf-8")) or []
    by_url = {a["url"]: a for a in existing}

    for article in fresh:
        old = by_url.get(article["url"], {})
        for field in KEEP_FIELDS:
            if field in old:
                article[field] = old[field]
        by_url[article["url"]] = {**old, **article}

    merged = sorted(by_url.values(), key=lambda a: str(a["date"]), reverse=True)
    header = "# Synced from Medium by generator/sync_medium.py — hand edits to excerpt/topic/featured/hidden are kept.\n"
    OUT.write_text(header + yaml.safe_dump(merged, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    added = len(merged) - len(existing)
    print(f"Medium: {len(merged)} articles ({added} new) → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
