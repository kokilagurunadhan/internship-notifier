import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI,Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from app.database.database import (
    Base,
    engine
)
from app.services.pipeline_processor import process_all_active_subscriptions
logger = logging.getLogger(__name__)
from sqlalchemy import text
# ============================================================
# DATABASE MODELS
# ============================================================

from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification
from app.models.historical_job import HistoricalJob

from app.services.notification_dispatcher import (
    run_notification_dispatcher
)
# ============================================================
# API ROUTERS
# ============================================================

from app.api.subscriptions import (
    router as subscription_router
)

from app.api.internships import (
    router as internship_router
)

from app.api.notifications import (
    router as notification_router
)


# ============================================================
# SCHEDULER
# ============================================================

from app.services.scheduler import (
    start_scheduler,
    stop_scheduler
)


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

async def create_tables():

    async with engine.begin() as connection:

        await connection.run_sync(
            Base.metadata.create_all
        )


# ============================================================
# FASTAPI LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    # --------------------------------------------------------
    # STARTUP
    # --------------------------------------------------------

    await create_tables()

    start_scheduler()

    dispatcher_task = asyncio.create_task(
        run_notification_dispatcher()
    )

    logger.info("🚀 Internship Notifier started.")

    try:

        yield

    finally:

        # ----------------------------------------------------
        # SHUTDOWN
        # ----------------------------------------------------

        dispatcher_task.cancel()

        try:
            await dispatcher_task
        except asyncio.CancelledError:
            logger.info(
                "🛑 Notification dispatcher stopped."
            )

        stop_scheduler()

        await engine.dispose()

        logger.info("🛑 Internship Notifier stopped.")

# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(

    title="Internship Notifier",

    description="Automated Internship Tracking Agent",

    version="1.0.0",

    lifespan=lifespan
)
# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/healthz")
async def health_check():

    try:

        async with engine.connect() as connection:

            await connection.execute(
                text("SELECT 1")
            )

        return {
            "status": "healthy",
            "database": "connected",
        }

    except Exception:

        logger.exception(
            "Health check failed"
        )

        return {
            "status": "unhealthy",
            "database": "disconnected",
        }
# ============================================================
# EXTERNAL SCHEDULER TRIGGER
# ============================================================

@app.post("/internal/run-internship-pipeline")
async def run_internship_pipeline(
    x_scheduler_token: str | None = Header(default=None),
):
    expected_token = os.getenv(
        "SCHEDULER_TRIGGER_TOKEN"
    )

    if not expected_token:
        logger.error(
            "SCHEDULER_TRIGGER_TOKEN is not configured."
        )

        return {
            "status": "error",
            "message": "Scheduler trigger is not configured.",
        }

    if x_scheduler_token != expected_token:
        return {
            "status": "unauthorized",
        }

    logger.info(
        "🌐 External scheduler triggered internship pipeline."
    )

    result = await process_all_active_subscriptions()

    return {
        "status": "completed",
        "pipeline": result,
    }
# ============================================================
# CORS
# ============================================================

# ============================================================
# CORS
# ============================================================

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173"
    ).split(",")
    if origin.strip()
]


app.add_middleware(

    CORSMiddleware,

    allow_origins=cors_origins,

    allow_credentials=True,

    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],

    allow_headers=["Content-Type", "Authorization"],
)

# ============================================================
# STATIC FRONTEND FILES
# ============================================================

app.mount(

    "/static",

    StaticFiles(
        directory="frontend"
    ),

    name="static"
)


# ============================================================
# PAGE 1 — TRACKER MANAGEMENT
# ============================================================

@app.get("/")
def home():

    return FileResponse(
        "frontend/index.html"
    )


# ============================================================
# PAGE 2 — INTERNSHIP DASHBOARD
# ============================================================

@app.get("/internships.html")
def internships_page():

    return FileResponse(
        "frontend/internships.html"
    )


# ============================================================
# API ROUTERS
# ============================================================

app.include_router(
    subscription_router
)

app.include_router(
    internship_router
)

app.include_router(
    notification_router
)