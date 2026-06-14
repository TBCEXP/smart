from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.database import get_session, init_db
from app.middleware.auth import AuthMiddleware
from app.models.entities import Schedule
from app.routers.api import router as api_router
from app.services.config_store import ConfigStore
from app.services.pipeline import PipelineService

STATIC_DIR = Path(__file__).resolve().parent / "app" / "static"
pipeline = PipelineService()
config_store = ConfigStore()
_scheduler_running = False


async def scheduler_loop() -> None:
    global _scheduler_running
    _scheduler_running = True
    while _scheduler_running:
        if config_store.get("scheduler_enabled", "false").lower() in ("true", "1", "yes"):
            async with get_session() as db:
                now = datetime.utcnow()
                result = await db.execute(
                    select(Schedule).where(
                        Schedule.enabled.is_(True),
                        (Schedule.next_run_at.is_(None)) | (Schedule.next_run_at <= now),
                    )
                )
                for schedule in result.scalars().all():
                    try:
                        batch_id, stream = await pipeline.run_batch(
                            db,
                            keyword=schedule.keyword,
                            industry=schedule.industry,
                            count=5,
                            country_iso=schedule.country_iso,
                            city=schedule.city,
                            category_l3=schedule.category_l3,
                            language=schedule.language,
                            track=schedule.track,
                        )

                        async def _run_schedule(
                            batch_stream, sid: str, bid: str, run_at: datetime
                        ) -> None:
                            try:
                                async for _ in batch_stream:
                                    pass
                                async with get_session() as sdb:
                                    row = await sdb.get(Schedule, sid)
                                    if row:
                                        row.last_run_at = run_at
                                        row.next_run_at = run_at + timedelta(
                                            hours=row.interval_hours
                                        )
                                        await sdb.commit()
                            except Exception:
                                pass

                        sched_id = schedule.id
                        asyncio.create_task(
                            _run_schedule(stream, sched_id, batch_id, now)
                        )
                    except Exception:
                        pass
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with get_session() as db:
        from app.services.auth import AuthService
        from app.services.geo_track import TradeShowService
        from app.services.pipeline import seed_geo_data

        auth = AuthService()
        await auth.ensure_default_whitelist(db)
        await seed_geo_data(db)
        await TradeShowService().seed_defaults(db)
    task = asyncio.create_task(scheduler_loop())
    yield
    global _scheduler_running
    _scheduler_running = False
    task.cancel()


app = FastAPI(title="SMART CRM", version="1.5.0", lifespan=lifespan)
app.add_middleware(AuthMiddleware)
app.include_router(api_router, prefix="/api")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/admin")
async def admin_portal():
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/portal")
async def customer_portal():
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/auth/callback")
async def auth_callback():
    return FileResponse(STATIC_DIR / "auth_callback.html")
