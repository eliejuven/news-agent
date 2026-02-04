from app.db import init_db


def run_pipeline() -> None:
    # Step 1: just initialize DB and prove the pipeline runs.
    init_db()
    print("✅ DB initialized.")
    print("✅ Pipeline finished (Step 1 stub).")