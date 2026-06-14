from __future__ import annotations

import os
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _resolve_database_urls() -> tuple[str, str]:
    async_url = os.getenv("DATABASE_URL", "")
    sync_url = os.getenv("SYNC_DATABASE_URL", "")
    if not async_url or os.getenv("USE_SQLITE", "").lower() in ("1", "true", "yes"):
        db_path = settings.data_dir / "smartcrm.db"
        async_url = f"sqlite+aiosqlite:///{db_path}"
        sync_url = f"sqlite:///{db_path}"
    return async_url, sync_url


ASYNC_DB_URL, SYNC_DB_URL = _resolve_database_urls()

engine = create_async_engine(ASYNC_DB_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

sync_engine = create_engine(SYNC_DB_URL, pool_pre_ping=True)
SyncSessionLocal = sessionmaker(bind=sync_engine)


async def init_db() -> None:
    from app.models import entities  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if "postgresql" in ASYNC_DB_URL:
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            except Exception:
                pass
        # Lightweight schema patch for existing deployments
        try:
            if "sqlite" in ASYNC_DB_URL:
                cols = await conn.execute(text("PRAGMA table_info(content_drafts)"))
                names = {row[1] for row in cols.fetchall()}
                if "batch_id" not in names:
                    await conn.execute(
                        text("ALTER TABLE content_drafts ADD COLUMN batch_id VARCHAR(36)")
                    )
            elif "postgresql" in ASYNC_DB_URL:
                await conn.execute(
                    text(
                        "ALTER TABLE content_drafts "
                        "ADD COLUMN IF NOT EXISTS batch_id VARCHAR(36)"
                    )
                )
        except Exception:
            pass


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def get_sync_session():
    return SyncSessionLocal()
