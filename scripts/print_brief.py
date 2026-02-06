from app.rank_llm import select_top10_llm
from app.brief import generate_big_news_brief

if __name__ == "__main__":
    top10 = select_top10_llm(top_k=120)
    cluster_ids = [x.cluster_id for x in top10]

    print("Top10 clusters:", cluster_ids)
    print()
    brief = generate_big_news_brief(cluster_ids)
    print(brief)