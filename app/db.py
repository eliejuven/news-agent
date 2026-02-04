from typing import Optional
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
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    raw_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    fetch_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)   # ok / failed
    fetch_error: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    extract_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # ok / failed
    extract_error: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    xtracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    cluster_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # later: embedding, cluster_id, score, summary fields

class SentCluster(Base):
    __tablename__ = "sent_clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cluster_id: Mapped[int] = mapped_column(Integer, index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    

engine = create_engine(settings.DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(engine)