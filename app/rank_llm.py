from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from app.candidate_filter import Candidate, filter_candidates_with_embeddings, select_cluster_reps
from app.db import ArticleAnalysis, SentCluster, SessionLocal

DEFAULT_COUNTRY_TARGETS: Dict[str, int] = {"US": 5, "UK": 4, "FR": 1}
MAX_PER_SOURCE = 2

MIN_YOUR_RELEVANCE = 6.0  # hard quality gate


@dataclass
class RankedLLMItem:
    cluster_id: int
    score: float
    similarity: float
    country: str
    source: str
    title: str
    url: str


def looks_like_article(url: str) -> bool:
    """
    Quick heuristic to avoid hub pages / newsletters / tags.
    Tweak this list as you observe bad URLs.
    """
    u = (url or "").lower()
    bad = [
        "#comments",
        "/tag/",
        "/category/",
        "/topics/",
        "/topic/",
        "/section/",
        "/newsletter",
        "/rss",
        "/tech-exchange",
    ]
    return not any(b in u for b in bad)


def select_top10_llm(
    top_k: int = 60,
    country_targets: Optional[Dict[str, int]] = None,
) -> List[RankedLLMItem]:
    targets = dict(country_targets or DEFAULT_COUNTRY_TARGETS)

    # Embedding shortlist (cheap)
    candidates: List[Candidate] = filter_candidates_with_embeddings(top_k=top_k)

    # Representative articles per cluster
    reps = select_cluster_reps()

    # Load judge scores from DB + "sent" clusters
    with SessionLocal() as session:
        sent = {cid for (cid,) in session.query(SentCluster.cluster_id).all()}
        analysis_rows = session.query(ArticleAnalysis).all()
        analysis_by_article_id = {r.article_id: (r.judge_score, r.judge_json) for r in analysis_rows}

    ranked: List[RankedLLMItem] = []

    for c in candidates:
        # URL guard (avoid hub pages)
        if not looks_like_article(c.url):
            continue

        # avoid repeats
        if c.cluster_id in sent:
            continue

        a = reps.get(c.cluster_id)
        if a is None:
            continue

        judge_score, judge_json = analysis_by_article_id.get(a.id, (None, None))

        # If we have judged JSON, enforce relevance gate
        if judge_json:
            try:
                j = json.loads(judge_json)
            except Exception:
                # malformed JSON shouldn't break ranking; treat as unjudged
                j = None

            if j:
                if (not j.get("is_relevant", False)) or float(j.get("your_relevance", 0.0)) < MIN_YOUR_RELEVANCE:
                    continue

        # Score: prefer judge_score; fallback to similarity
        if judge_score is None:
            score = max(0.0, min(10.0, c.similarity * 20.0))
        else:
            score = float(judge_score)

        ranked.append(
            RankedLLMItem(
                cluster_id=c.cluster_id,
                score=score,
                similarity=c.similarity,
                country=c.country,
                source=c.source,
                title=c.title,
                url=c.url,
            )
        )

    ranked.sort(key=lambda x: x.score, reverse=True)

    # Apply constraints: country quotas + max per source
    picked: List[RankedLLMItem] = []
    picked_by_country: Dict[str, int] = {"US": 0, "UK": 0, "FR": 0}
    picked_by_source: Dict[str, int] = {}

    def can_pick(x: RankedLLMItem) -> bool:
        # max per source
        if picked_by_source.get(x.source, 0) >= MAX_PER_SOURCE:
            return False
        return True

    # 1) Fill quotas first (US/UK/FR targets)
    for x in ranked:
        if len(picked) >= 10:
            break
        if x.country in targets and picked_by_country.get(x.country, 0) < targets[x.country]:
            if can_pick(x):
                picked.append(x)
                picked_by_country[x.country] = picked_by_country.get(x.country, 0) + 1
                picked_by_source[x.source] = picked_by_source.get(x.source, 0) + 1

    # 2) Fill remaining slots with best remaining BUT keep FR capped at 1
    # (Practical: US/UK dominate; FR stays at 1 max.)
    if len(picked) < 10:
        already = {p.cluster_id for p in picked}
        for x in ranked:
            if len(picked) >= 10:
                break
            if x.cluster_id in already:
                continue
            if not can_pick(x):
                continue

            # hard cap FR at target (prevents 2 FR items)
            if x.country == "FR" and picked_by_country.get("FR", 0) >= targets.get("FR", 1):
                continue

            picked.append(x)
            picked_by_country[x.country] = picked_by_country.get(x.country, 0) + 1
            picked_by_source[x.source] = picked_by_source.get(x.source, 0) + 1

    return picked