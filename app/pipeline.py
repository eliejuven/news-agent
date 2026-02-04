from app.db import init_db
from app.ingest_rss import ingest_rss


def run_pipeline() -> None:
    init_db()
    print("✅ DB initialized.")

    added, seen = ingest_rss()
    print(f"📰 RSS ingest: added {added} new articles ({seen} already seen).")

    print("✅ Pipeline finished.")