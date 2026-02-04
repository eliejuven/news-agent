# News Agent — Personal AI News Digest (MVP)

A personal agentic AI system that scans multiple news sources (US / UK / FR),
deduplicates similar stories, ranks the most relevant ones, and sends a
**Top-10 must-read email digest** three times a week.

Built as an MVP by an MIT data science / ML student to stay on top of:
- AI & agentic systems
- Technology & startups
- Business & innovation
- Health & biotech (early support)

---

## What this agent does today

When the pipeline runs, the agent:

1. **Ingests RSS feeds** from trusted US, UK, and French news sources
2. **Fetches and extracts article text** from the web
3. **Deduplicates similar stories** into clusters
4. **Scores and ranks stories** using recency, keywords, and source quality
5. **Selects a Top 10** with a mostly-English balance (US=5, UK=4, FR=1)
6. **Emails the Top 10** as a clean HTML digest
7. **Remembers what was sent** to avoid repeating stories

This is a working end-to-end MVP.

---

## Example output

- A daily/tri-weekly email titled:  
  **“Top 10 must-reads — YYYY-MM-DD”**
- Each item includes:
  - country & source
  - title
  - link to the original article
  - internal relevance score

---

## Project structure

The project is organized as a simple, modular pipeline:

news-agent/
│
├── app/
│   ├── config.py        # Environment-based configuration
│   ├── db.py            # Database models and session
│   ├── ingest_rss.py    # RSS ingestion
│   ├── extract.py       # HTML fetching & text extraction
│   ├── dedupe.py        # Duplicate clustering
│   ├── rank.py          # Scoring & Top-10 selection
│   ├── emailer.py       # HTML email rendering & SMTP sending
│   └── pipeline.py     # Orchestrates the full agent routine
│
├── scripts/
│   └── run_pipeline.py  # Entry point
│
├── data/
│   └── sources.yaml     # RSS feed configuration
│
├── .env                 # Local secrets (ignored by git)
├── .gitignore
├── README.md
└── news_agent.db        # Local SQLite DB (ignored by git)

---

## How to run (local)

### 1. Create and activate a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependecies
```bash
python -m pip install --upgrade pip
python -m pip install \
  sqlalchemy pydantic-settings httpx feedparser trafilatura rapidfuzz
```

### 3. Configure environment variables

Create a `.env` file in the project root (this file is ignored by git).

```env
DATABASE_URL=sqlite:///news_agent.db

EMAIL_TO=your_email@gmail.com
EMAIL_FROM=your_email@gmail.com

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=YOUR_GMAIL_APP_PASSWORD
```

### 4. Run the agent
```bash
python -m scripts.run_pipeline
```
