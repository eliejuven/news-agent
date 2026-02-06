from __future__ import annotations

import json
from typing import Any, Dict, List

from openai import OpenAI

from app.config import settings
from app.db import Article, ArticleAnalysis, SessionLocal

BRIEF_MODEL = "gpt-4.1-mini"


def _build_top10_notes(top10_cluster_ids: List[int]) -> List[Dict[str, Any]]:
    """
    Fetches judge_json for the top10 clusters and returns compact notes
    to feed into the brief LLM call.
    """
    notes: List[Dict[str, Any]] = []

    with SessionLocal() as session:
        # Join-ish logic: get the representative Article for each cluster_id
        # (we pick the newest discovered article in that cluster)
        for cid in top10_cluster_ids:
            a = (
                session.query(Article)
                .filter(Article.cluster_id == cid)
                .order_by(Article.discovered_at.desc())
                .first()
            )
            if not a:
                continue

            analysis = session.query(ArticleAnalysis).filter(ArticleAnalysis.article_id == a.id).first()
            if not analysis or not analysis.judge_json:
                # Still allow it, but with minimal info
                notes.append(
                    {
                        "cluster_id": cid,
                        "country": a.country,
                        "source": a.source,
                        "title": a.title,
                        "url": a.url,
                        "takeaway": None,
                        "why_it_matters": [],
                        "topics": [],
                        "judge_score": analysis.judge_score if analysis else None,
                        "tag": f"[{a.country}] ({a.source}) {a.title}",
                    }
                )
                continue

            j = json.loads(analysis.judge_json)

            notes.append(
                {
                    "cluster_id": cid,
                    "country": a.country,
                    "source": a.source,
                    "title": a.title,
                    "url": a.url,
                    "takeaway": j.get("one_sentence_takeaway"),
                    "why_it_matters": j.get("why_it_matters", [])[:3],
                    "topics": j.get("topics", [])[:6],
                    "judge_score": analysis.judge_score,
                    "tag": f"[{a.country}] ({a.source}) {a.title}",
                }
            )

    return notes


def generate_big_news_brief(top10_cluster_ids: List[int]) -> str:
    """
    Returns a short markdown-ish brief:
    - Big news brief: 3–6 bullets
    - What to remember: 2–4 bullets

    Uses only the provided notes (no invention).
    """
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY missing. Add it to .env")

    notes = _build_top10_notes(top10_cluster_ids)

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    prompt = f"""
You are writing a concise "Big news brief" for a personal AI/tech digest.

Rules:
- Use ONLY the provided notes. Do NOT invent facts.
- For each bullet, start with a short theme label like:
  - **Theme: <3-6 words>** — <1-2 sentences>
- Each bullet should clearly map to one or more of the notes (but do NOT mention cluster IDs).
- If details are missing (paywall/empty notes), stay high-level and only use title-level info.

Output format:

BIG NEWS BRIEF
- **Theme: ...** — ...
  Sources: SourceName, SourceName (optional, max 2-3)

WHAT TO REMEMBER
- ...

Notes (Top 10 items):
{json.dumps(notes, ensure_ascii=False, indent=2)}
""".strip()

    resp = client.responses.create(
        model=BRIEF_MODEL,
        input=prompt,
    )

    return resp.output_text.strip()