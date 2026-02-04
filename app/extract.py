from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx
import trafilatura

from app.db import Article, SessionLocal


def fetch_and_extract(limit: int = 20, timeout_s: float = 20.0) -> tuple[int, int]:
    """
    Fetch HTML + extract main text for up to `limit` articles that don't have text yet.
    Returns (ok_count, fail_count).
    """
    ok = 0
    fail = 0

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    }

    with SessionLocal() as session:
        # Pick articles we haven't extracted yet
        rows = (
            session.query(Article)
            .filter(Article.text.is_(None))
            .order_by(Article.discovered_at.desc())
            .limit(limit)
            .all()
        )

        if not rows:
            return (0, 0)

        with httpx.Client(follow_redirects=True, headers=headers, timeout=timeout_s) as client:
            for a in rows:
                try:
                    r = client.get(a.url)
                    a.raw_html = r.text
                    a.fetched_at = datetime.utcnow()
                    if r.status_code >= 400:
                        a.fetch_status = "failed"
                        a.fetch_error = f"HTTP {r.status_code}"
                        fail += 1
                        continue
                    a.fetch_status = "ok"
                except Exception as e:
                    a.fetch_status = "failed"
                    a.fetch_error = str(e)[:500]
                    a.fetched_at = datetime.utcnow()
                    fail += 1
                    continue

                try:
                    # Extract text
                    text = trafilatura.extract(
                        a.raw_html,
                        url=a.url,
                        include_comments=False,
                        include_tables=False,
                    )
                    a.extracted_at = datetime.utcnow()
                    if text and len(text.strip()) > 200:
                        a.text = text.strip()
                        a.extract_status = "ok"
                        ok += 1
                    else:
                        a.extract_status = "failed"
                        a.extract_error = "empty_or_too_short"
                        fail += 1
                except Exception as e:
                    a.extract_status = "failed"
                    a.extract_error = str(e)[:500]
                    a.extracted_at = datetime.utcnow()
                    fail += 1

        session.commit()

    return ok, fail