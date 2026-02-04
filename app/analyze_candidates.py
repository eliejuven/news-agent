from __future__ import annotations

import json
from typing import List

from app.candidate_filter import Candidate, select_cluster_reps, filter_candidates_with_embeddings
from app.db import ArticleAnalysis, SessionLocal
from app.judge import judge_article, JUDGE_MODEL


def analyze_top_candidates(top_k: int = 60, max_new_judgements: int = 30) -> int:
    """
    Runs the LLM judge on up to `max_new_judgements` candidates that haven't been judged yet.
    Returns how many new judgements were created.
    """
    candidates: List[Candidate] = filter_candidates_with_embeddings(top_k=top_k)
    reps = select_cluster_reps()

    created = 0
    with SessionLocal() as session:
        for c in candidates:
            a = reps.get(c.cluster_id)
            if a is None:
                continue

            exists = session.query(ArticleAnalysis).filter(ArticleAnalysis.article_id == a.id).first()
            if exists and exists.judge_score is not None:
                continue

            if created >= max_new_judgements:
                break

            j = judge_article(title=a.title or "", text=a.text or "")
            row = exists or ArticleAnalysis(article_id=a.id, cluster_id=c.cluster_id)

            row.profile_similarity = c.similarity
            row.embed_model = "text-embedding-3-small"
            row.judge_model = JUDGE_MODEL
            row.judge_json = json.dumps(j, ensure_ascii=False)
            row.judge_score = float(j["final_score"])

            session.add(row)
            session.commit()
            created += 1

    return created