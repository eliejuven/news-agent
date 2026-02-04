from datetime import datetime
from sqlalchemy import create_engine, String, DateTime, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    country: Mapped[str | None] = mapped_column(String(8), nullable=True)  # US/UK/FR etc.
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    raw_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # later: embedding, cluster_id, score, summary fields


engine = create_engine(settings.DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(engine)