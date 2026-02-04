from app.db import init_db
from app.ingest_rss import ingest_rss
from app.extract import fetch_and_extract
from app.dedupe import assign_clusters
from app.rank import select_top10, record_sent
from datetime import date
from app.emailer import render_html, send_email
from app.analyze_candidates import analyze_top_candidates
from app.rank_llm import select_top10_llm

def run_pipeline() -> None:
    init_db()
    print("✅ DB initialized.")

    added, seen = ingest_rss()
    print(f"📰 RSS ingest: added {added} new articles ({seen} already seen).")

    ok, fail = fetch_and_extract(limit=20)
    print(f"🧾 Extract: ok={ok} failed={fail} (processed up to 20)")

    clustered, clusters = assign_clusters(limit=200, threshold=92)
    print(f"🧩 Dedupe: clustered {clustered} articles into {clusters} clusters")

    new_j = analyze_top_candidates(top_k=60, max_new_judgements=30)
    print(f"🧠 LLM judge: created {new_j} new judgements")

#    top10 = select_top10()
#    print("\n📬 TOP 10 (mostly English: US=5, UK=4, FR=1)\n")
#    for i, item in enumerate(top10, 1):
#       print(f"{i:02d}. [{item.country}] ({item.source}) score={item.score:.2f}")
#       print(f"    {item.title}")
#       print(f"    {item.url}\n")

    top10 = select_top10_llm(top_k=60)
    print("\n📬 TOP 10 (LLM-ranked, mostly English)\n")
    for i, item in enumerate(top10, 1):
        print(f"{i:02d}. [{item.country}] ({item.source}) score={item.score:.2f} sim={item.similarity:.3f}")
        print(f"    {item.title}")
        print(f"    {item.url}\n")

    html = render_html(top10)
    send_email(subject=f"Top 10 must-reads — {date.today().isoformat()}", html=html)
    print("📧 Email sent.")

    record_sent([x.cluster_id for x in top10])
    print("✅ Recorded Top 10 as sent (won't repeat next run).")

    print("✅ Pipeline finished.")