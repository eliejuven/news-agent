from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz

from app.db import Article, SessionLocal


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def assign_clusters(limit: int = 200, threshold: int = 92) -> Tuple[int, int]:
    """
    Assign cluster_id based on fuzzy title similarity.

    - limit: how many newest articles to consider
    - threshold: 0-100; higher = stricter matching

    Returns: (num_articles_clustered, num_clusters_created)
    """
    with SessionLocal() as session:
        articles: List[Article] = (
            session.query(Article)
            .order_by(Article.discovered_at.desc())
            .limit(limit)
            .all()
        )

        # Only cluster things that have a title
        articles = [a for a in articles if a.title]

        next_cluster_id = 1
        clustered = 0
        clusters_created = 0

        for i, a in enumerate(articles):
            if a.cluster_id is not None:
                continue

            # Start a new cluster with article a as the "seed"
            a.cluster_id = next_cluster_id
            clusters_created += 1
            clustered += 1

            title_a = _norm(a.title)

            # Compare to later articles, assign same cluster if similar
            for b in articles[i + 1 :]:
                if b.cluster_id is not None or not b.title:
                    continue
                title_b = _norm(b.title)

                score = fuzz.token_set_ratio(title_a, title_b)
                if score >= threshold:
                    b.cluster_id = next_cluster_id
                    clustered += 1

            next_cluster_id += 1

        session.commit()

        return clustered, clusters_created