from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from app.candidate_filter import Candidate, filter_candidates_with_embeddings, select_cluster_reps
from app.db import ArticleAnalysis, SentCluster, SessionLocal

from app.db import Article, ArticleAnalysis, SentCluster, SessionLocal

from datetime import datetime, timedelta

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

def _is_recent(published_at, discovered_at, days: int = 7) -> bool:
    cutoff = datetime.utcnow() - timedelta(days=days)
    if published_at is not None:
        return published_at >= cutoff
    return discovered_at >= cutoff

def _passes_relevance_gate(judge_json: str | None) -> bool:
    if not judge_json:
        return True  # unjudged: allow (may be used as fallback)
    try:
        j = json.loads(judge_json)
    except Exception:
        return True
    if not j:
        return True
    return bool(j.get("is_relevant", False)) and float(j.get("your_relevance", 0.0)) >= MIN_YOUR_RELEVANCE


def _apply_constraints(
    ranked: List[RankedLLMItem],
    targets: Dict[str, int],
    max_items: int,
) -> List[RankedLLMItem]:
    picked: List[RankedLLMItem] = []
    picked_by_country: Dict[str, int] = {"US": 0, "UK": 0, "FR": 0}
    picked_by_source: Dict[str, int] = {}

    def can_pick(x: RankedLLMItem) -> bool:
        if picked_by_source.get(x.source, 0) >= MAX_PER_SOURCE:
            return False
        return True

    # 1) Fill quotas first
    for x in ranked:
        if len(picked) >= max_items:
            break
        if x.country in targets and picked_by_country.get(x.country, 0) < targets[x.country]:
            if can_pick(x):
                picked.append(x)
                picked_by_country[x.country] = picked_by_country.get(x.country, 0) + 1
                picked_by_source[x.source] = picked_by_source.get(x.source, 0) + 1

    # 2) Fill remaining (keep FR capped)
    if len(picked) < max_items:
        already = {p.cluster_id for p in picked}
        for x in ranked:
            if len(picked) >= max_items:
                break
            if x.cluster_id in already:
                continue
            if not can_pick(x):
                continue
            if x.country == "FR" and picked_by_country.get("FR", 0) >= targets.get("FR", 1):
                continue

            picked.append(x)
            picked_by_country[x.country] = picked_by_country.get(x.country, 0) + 1
            picked_by_source[x.source] = picked_by_source.get(x.source, 0) + 1

    return picked


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

def select_digest_items(
    min_items: int = 6,
    max_items: int = 10,
    backlog_limit: int = 1500,
    fallback_top_k: int = 120,
    country_targets: Optional[Dict[str, int]] = None,
) -> List[RankedLLMItem]:
    """
    DB-first selection:
    1) Take best judged (judge_score) items that have never been sent.
    2) If < min_items, fill with embedding candidates (similarity fallback).
    Returns between 0 and max_items, aiming for at least min_items when possible.
    """
    targets = dict(country_targets or DEFAULT_COUNTRY_TARGETS)

    # --- Load sent clusters + judged backlog ---
    with SessionLocal() as session:
        sent = {cid for (cid,) in session.query(SentCluster.cluster_id).all()}

        # Join ArticleAnalysis -> Article for metadata and cluster_id
        rows = (
            session.query(Article, ArticleAnalysis)
            .join(ArticleAnalysis, ArticleAnalysis.article_id == Article.id)
            .filter(ArticleAnalysis.judge_score.isnot(None))
            .order_by(ArticleAnalysis.judge_score.desc())
            .limit(backlog_limit)
            .all()
        )

    ranked: List[RankedLLMItem] = []
    for a, an in rows:
        if a.cluster_id is None:
            continue
        if not _is_recent(a.published_at, a.discovered_at, days=7):
            continue
        cid = int(a.cluster_id)
        if cid in sent:
            continue
        if not looks_like_article(a.url):
            continue
        if not _passes_relevance_gate(an.judge_json):
            continue

        ranked.append(
            RankedLLMItem(
                cluster_id=cid,
                score=float(an.judge_score),
                similarity=float(an.profile_similarity or 0.0),
                country=a.country or "UNK",
                source=a.source or "UNK",
                title=a.title or "(no title)",
                url=a.url,
            )
        )

    ranked.sort(key=lambda x: x.score, reverse=True)

    picked = _apply_constraints(ranked, targets=targets, max_items=max_items)

    # --- Fallback: fill with embedding shortlist if we are below min_items ---
    if len(picked) < min_items:
        already = {p.cluster_id for p in picked}

        candidates: List[Candidate] = filter_candidates_with_embeddings(top_k=fallback_top_k)
        reps = select_cluster_reps()

        # Load analysis map once (so we can reuse judge_score if exists)
        with SessionLocal() as session:
            analysis_rows = session.query(ArticleAnalysis).all()
            analysis_by_article_id = {r.article_id: (r.judge_score, r.judge_json) for r in analysis_rows}

        fallback_ranked: List[RankedLLMItem] = []
        for c in candidates:
            if c.cluster_id in sent or c.cluster_id in already:
                continue
            if not looks_like_article(c.url):
                continue

            a = reps.get(c.cluster_id)
            if not _is_recent(a.published_at, a.discovered_at, days=7):
                continue
            if not a:
                continue

            judge_score, judge_json = analysis_by_article_id.get(a.id, (None, None))
            # If judged and fails gate, skip
            if judge_json and not _passes_relevance_gate(judge_json):
                continue

            score = float(judge_score) if judge_score is not None else max(0.0, min(10.0, c.similarity * 20.0))

            fallback_ranked.append(
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

        fallback_ranked.sort(key=lambda x: x.score, reverse=True)

        # Fill remaining slots without breaking constraints too hard
        # We reuse the same constraints function by concatenating: picked first, then fallback ranked.
        combined = picked + [x for x in fallback_ranked if x.cluster_id not in already]
        picked = _apply_constraints(combined, targets=targets, max_items=max_items)

    return picked[:max_items]