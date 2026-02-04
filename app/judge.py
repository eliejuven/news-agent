from __future__ import annotations

import json
from typing import Any, Dict, Optional

from openai import OpenAI

from app.config import settings

JUDGE_MODEL = "gpt-4.1-mini"

# JSON schema for structured outputs (stable keys, easy to store/debug)
JUDGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "is_relevant": {"type": "boolean"},
        "topics": {"type": "array", "items": {"type": "string"}},
        "your_relevance": {"type": "number", "minimum": 0, "maximum": 10},
        "impact": {"type": "number", "minimum": 0, "maximum": 10},
        "novelty": {"type": "number", "minimum": 0, "maximum": 10},
        "credibility": {"type": "number", "minimum": 0, "maximum": 10},
        "depth": {"type": "number", "minimum": 0, "maximum": 10},
        "hype_risk": {"type": "number", "minimum": 0, "maximum": 10},
        "one_sentence_takeaway": {"type": "string"},
        "why_it_matters": {"type": "array", "items": {"type": "string"}, "maxItems": 3}
    },
    "required": [
        "is_relevant", "topics",
        "your_relevance", "impact", "novelty", "credibility", "depth", "hype_risk",
        "one_sentence_takeaway", "why_it_matters"
    ],
}


def compute_final_score(j: Dict[str, Any]) -> float:
    """
    Final score in [0, 10] computed deterministically from the rubric.
    """
    score = (
        0.35 * float(j["your_relevance"]) +
        0.25 * float(j["impact"]) +
        0.20 * float(j["novelty"]) +
        0.15 * float(j["credibility"]) +
        0.10 * float(j["depth"]) -
        0.15 * float(j["hype_risk"])
    )
    # clamp
    return max(0.0, min(10.0, score))


def judge_article(title: str, text: str) -> Dict[str, Any]:
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY missing. Add it to .env")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    content = (title or "") + "\n\n" + (text or "")
    content = content[:8000]  # cost guard

    prompt = f"""
You are scoring news articles for a personal tech/AI digest.
Return JSON matching the provided schema.

Scoring guidance:
- "is_relevant": true if the article is meaningfully about AI, agentic systems, ML, tech startups/venture, developer tools, or health AI.
- Prefer high scores for: concrete new info, real product/technical substance, credible reporting.
- Penalize hype and shallow takes.

Article:
{content}
""".strip()

    resp = client.responses.create(
        model=JUDGE_MODEL,
        input=prompt,
        text={
        "format": {
            "type": "json_schema",
            "name": "article_judge",
            "schema": JUDGE_SCHEMA,
            "strict": True,
        }
    },
)

    # The SDK returns the JSON as text; parse it
    out = resp.output_text
    data = json.loads(out)
    data["final_score"] = compute_final_score(data)
    return data