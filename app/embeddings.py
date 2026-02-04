from __future__ import annotations

from typing import List

import numpy as np
from openai import OpenAI

from app.config import settings


_EMBED_MODEL = "text-embedding-3-small"


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Returns a list of embedding vectors (list[float]) for each input string.
    """
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY missing. Add it to .env")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    resp = client.embeddings.create(model=_EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Cosine similarity in [-1, 1]. Higher = more similar.
    """
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = (np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)