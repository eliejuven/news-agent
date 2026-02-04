from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import feedparser
import yaml

from app.db import Article, SessionLocal

SOURCES_PATH = Path("data/sources.yaml")


def _parse_datetime(entry: dict[str, Any]) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc).replace(tzinfo=None)
    return None


def ingest_rss() -> tuple[int, int]:
    """
    Fetch RSS feeds listed in data/sources.yaml and insert unseen items into DB.
    Returns (added_count, seen_count).
    """
    cfg = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8")) or {}
    rss_sources = cfg.get("rss_sources", [])

    added = 0
    seen = 0

    with SessionLocal() as session:
        for src in rss_sources:
            name = (src.get("name") or "").strip()
            country = (src.get("country") or "").strip()
            url = (src.get("url") or "").strip()

            if not (name and country and url):
                print(f"⚠️ Skipping invalid source entry: {src}")
                continue

            feed = feedparser.parse(url)
            if getattr(feed, "bozo", False):
                err = getattr(feed, "bozo_exception", None)
                print(f"⚠️ Feed parse issue for {name}: {err}")

            for entry in feed.entries:
                link = (entry.get("link") or "").strip()
                title = (entry.get("title") or "").strip() or None
                published_at = _parse_datetime(entry)

                if not link:
                    continue

                exists = session.query(Article.id).filter(Article.url == link).first()
                if exists:
                    seen += 1
                    continue

                session.add(
                    Article(
                        url=link,
                        title=title,
                        source=name,
                        country=country,
                        published_at=published_at,
                    )
                )
                added += 1

        session.commit()

    return added, seen