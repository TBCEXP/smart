from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.database import get_session, init_db
from app.middleware.auth import AuthMiddleware
from app.models.entities import Schedule
from app.routers.api import router as api_router
from app.services.config_store import ConfigStore
from app.services.pipeline import PipelineService

STATIC_DIR = Path(__file__).resolve().parent / "app" / "static"
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
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
        from app.services.catalog import seed_catalog_documents
        from app.services.files import seed_file_transfers
        from app.services.prepress import seed_prepress_reviews
        from app.services.phase1 import seed_factories
        from app.services.share import seed_portal_demo
        from app.services.pipeline import seed_geo_data

        auth = AuthService()
        await auth.ensure_default_whitelist(db)
        await seed_geo_data(db)
        await seed_factories(db)
        await seed_portal_demo(db)
        await seed_catalog_documents(db)
        await seed_file_transfers(db)
        await seed_prepress_reviews(db)
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


@app.get("/admin/leads")
async def admin_leads():
    return FileResponse(STATIC_DIR / "admin_dashboard.html")


@app.get("/admin/dashboard")
async def admin_dashboard():
    return FileResponse(STATIC_DIR / "admin_dashboard.html")


@app.get("/portal")
async def customer_portal():
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/portal/dashboard")
async def portal_dashboard_page():
    return FileResponse(STATIC_DIR / "portal_dashboard.html")


@app.get("/s/{token}")
async def share_page(token: str):
    return FileResponse(STATIC_DIR / "share.html")


@app.get("/auth/callback")
async def auth_callback():
    return FileResponse(STATIC_DIR / "auth_callback.html")


@app.get("/docs/feishu-fields")
async def feishu_fields_doc():
    """Serve Feishu column mapping for Tab2 configuration."""
    path = DOCS_DIR / "FEISHU_FIELDS.md"
    if not path.exists():
        return PlainTextResponse("FEISHU_FIELDS.md not found", status_code=404)
    return PlainTextResponse(
        path.read_text(encoding="utf-8"),
        media_type="text/markdown; charset=utf-8",
    )
