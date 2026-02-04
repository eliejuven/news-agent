from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.db import Article, SentCluster, SessionLocal


# --- MVP scoring config (simple + adjustable) ---
DEFAULT_COUNTRY_TARGETS: Dict[str, int] = {"US": 5, "UK": 4, "FR": 1}
MAX_PER_SOURCE = 2

# Give a small boost to sources you generally trust more
SOURCE_WEIGHTS: Dict[str, float] = {
    "MIT Technology Review": 1.3,
    "Financial Times - Technology": 1.2,
    "BBC News - Technology": 1.1,
    "The Verge": 1.0,
    "TechCrunch": 1.0,
    "Le Monde - Pixels": 0.9,
    "Les Echos - Tech": 0.9,
}

# Keywords you care about (MVP; we’ll replace with embeddings later)
KEYWORDS: Dict[str, float] = {
    # AI / agents / models
    "agent": 0.4,
    "agents": 0.4,
    "llm": 0.5,
    "transformer": 0.4,
    "inference": 0.4,
    "fine-tune": 0.4,
    "finetune": 0.4,
    "mistral": 0.4,
    "openai": 0.4,
    "anthropic": 0.4,
    "deepmind": 0.4,
    # health / biotech
    "fda": 0.5,
    "clinical": 0.4,
    "trial": 0.4,
    "biotech": 0.4,
    # startups / business
    "funding": 0.4,
    "raised": 0.3,
    "series a": 0.4,
    "series b": 0.4,
    "acquires": 0.4,
    "acquisition": 0.4,
}

RECENCY_HALF_LIFE_HOURS = 48.0  # newer gets higher score


@dataclass
class RankedItem:
    cluster_id: int
    score: float
    country: str
    source: str
    title: str
    url: str
    discovered_at: datetime


def _text_blob(a: Article) -> str:
    t = (a.title or "") + "\n" + (a.text or "")
    return t.lower()


def _recency_score(hours_old: float) -> float:
    # simple decay: score ~ 1.0 when new, ~0.5 at half-life, ~0.25 at 2 half-lives
    if hours_old <= 0:
        return 1.0
    return 0.5 ** (hours_old / RECENCY_HALF_LIFE_HOURS)


def _keyword_score(blob: str) -> float:
    s = 0.0
    for k, w in KEYWORDS.items():
        if k in blob:
            s += w
    return s


def _source_weight(source: str) -> float:
    return SOURCE_WEIGHTS.get(source, 1.0)


def select_top10(
    country_targets: Optional[Dict[str, int]] = None,
    lookback_limit_articles: int = 500,
) -> List[RankedItem]:
    """
    Rank clusters, enforce country quotas (US/UK/FR), avoid repeats (sent_clusters),
    and return 10 ranked items.
    """
    targets = dict(country_targets or DEFAULT_COUNTRY_TARGETS)

    with SessionLocal() as session:
        sent = {cid for (cid,) in session.query(SentCluster.cluster_id).all()}

        # Pull a recent slice of articles, then group by cluster_id in Python
        arts: List[Article] = (
            session.query(Article)
            .order_by(Article.discovered_at.desc())
            .limit(lookback_limit_articles)
            .all()
        )

    # Group articles by cluster_id
    clusters: Dict[int, List[Article]] = {}
    for a in arts:
        if a.cluster_id is None:
            continue
        if a.cluster_id in sent:
            continue
        clusters.setdefault(a.cluster_id, []).append(a)

    now = datetime.utcnow()
    ranked: List[RankedItem] = []

    for cid, items in clusters.items():
        # Representative article: prefer one with extracted text, else newest
        rep = None
        for it in items:
            if it.text:
                rep = it
                break
        if rep is None:
            rep = sorted(items, key=lambda x: x.discovered_at, reverse=True)[0]

        hours_old = (now - rep.discovered_at).total_seconds() / 3600.0
        rec = _recency_score(hours_old) * 2.0  # recency contributes up to ~2 points
        kw = _keyword_score(_text_blob(rep))   # keywords add small boosts
        sw = _source_weight(rep.source or "")  # source multiplier

        base = (rec + kw)
        score = base * sw

        ranked.append(
            RankedItem(
                cluster_id=cid,
                score=score,
                country=(rep.country or "UNK"),
                source=(rep.source or "UNK"),
                title=(rep.title or "(no title)"),
                url=rep.url,
                discovered_at=rep.discovered_at,
            )
        )

    ranked.sort(key=lambda r: r.score, reverse=True)

    # --- Apply constraints: mostly English + max per source ---
    picked: List[RankedItem] = []
    picked_by_country: Dict[str, int] = {"US": 0, "UK": 0, "FR": 0}
    picked_by_source: Dict[str, int] = {}

    def can_pick(x: RankedItem) -> bool:
        if picked_by_source.get(x.source, 0) >= MAX_PER_SOURCE:
            return False
        return True

    # 1) Fill quotas first
    for x in ranked:
        if len(picked) >= 10:
            break
        if x.country in targets and picked_by_country[x.country] < targets[x.country]:
            if can_pick(x):
                picked.append(x)
                picked_by_country[x.country] += 1
                picked_by_source[x.source] = picked_by_source.get(x.source, 0) + 1

    # 2) Fill remaining slots with best remaining (any country), still respecting max/source
    if len(picked) < 10:
        already = {p.cluster_id for p in picked}
        for x in ranked:
            if len(picked) >= 10:
                break
            if x.cluster_id in already:
                continue
            if can_pick(x):
                picked.append(x)
                picked_by_country[x.country] = picked_by_country.get(x.country, 0) + 1
                picked_by_source[x.source] = picked_by_source.get(x.source, 0) + 1

    return picked


def record_sent(cluster_ids: List[int]) -> None:
    if not cluster_ids:
        return
    with SessionLocal() as session:
        for cid in cluster_ids:
            session.add(SentCluster(cluster_id=cid))
        session.commit()