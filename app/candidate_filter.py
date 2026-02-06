from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import yaml

from app.db import Article, SessionLocal, SentCluster
from app.embeddings import cosine_similarity, embed_texts


PROFILE_PATH = "data/profile.yaml"


@dataclass
class Candidate:
    cluster_id: int
    similarity: float
    country: str
    
    source: str
    title: str
    url: str


def _load_profile_texts() -> List[str]:
    cfg = yaml.safe_load(open(PROFILE_PATH, "r", encoding="utf-8")) or {}
    texts = cfg.get("profile", [])
    if not texts:
        raise ValueError("data/profile.yaml missing 'profile' list")
    return [str(t).strip() for t in texts if str(t).strip()]


def select_cluster_reps(limit_articles: int = 600) -> Dict[int, Article]:
    """
    Pick 1 representative Article per cluster_id.
    Prefer an article with extracted text; otherwise newest.
    Excludes clusters already sent.
    """
    with SessionLocal() as session:
        sent = {cid for (cid,) in session.query(SentCluster.cluster_id).all()}
        arts: List[Article] = (
            session.query(Article)
            .order_by(Article.discovered_at.desc())
            .limit(limit_articles)
            .all()
        )

    by_cluster: Dict[int, List[Article]] = {}
    for a in arts:
        if a.cluster_id is None:
            continue
        if a.cluster_id in sent:
            continue
        by_cluster.setdefault(a.cluster_id, []).append(a)

    reps: Dict[int, Article] = {}
    for cid, items in by_cluster.items():
        # prefer with text
        with_text = [x for x in items if x.text]
        if with_text:
            reps[cid] = with_text[0]
        else:
            reps[cid] = sorted(items, key=lambda x: x.discovered_at, reverse=True)[0]
    return reps


def filter_candidates_with_embeddings(top_k: int = 60) -> List[Candidate]:
    profile_texts = _load_profile_texts()
    profile_vecs = embed_texts(profile_texts)

    reps = select_cluster_reps()
    rep_list = list(reps.values())

    # For cost: only embed title + first chunk of text
    rep_inputs = []
    for a in rep_list:
        blob = (a.title or "") + "\n" + (a.text or "")
        rep_inputs.append(blob[:6000])

    rep_vecs = embed_texts(rep_inputs)

    candidates: List[Candidate] = []
    for a, v in zip(rep_list, rep_vecs):
        sim = max(cosine_similarity(v, pv) for pv in profile_vecs)
        candidates.append(
            Candidate(
                cluster_id=int(a.cluster_id),
                similarity=sim,
                country=a.country or "UNK",
                source=a.source or "UNK",
                title=a.title or "(no title)",
                url=a.url,
            )
        )

    candidates.sort(key=lambda c: c.similarity, reverse=True)
    return candidates[:top_k]