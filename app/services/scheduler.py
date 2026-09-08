# ============================================================
# INTERNSHIP SCHEDULER
# File: app/services/scheduler.py
#
# RESPONSIBILITY:
#
# 1. Wake every 12 hours
# 2. Call the async internship pipeline
# 3. Do NOT perform search/filter/database logic here
# 4. Do NOT send emails here
#
# Pipeline:
#
# Scheduler
#     ↓
# process_all_active_subscriptions()
#     ↓
# Search
#     ↓
# Filter
#     ↓
# Relevance
#     ↓
# Database
#     ↓
# PENDING notifications
#
# Notification dispatcher handles email separately.
# ============================================================

import asyncio
import logging
import os

from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.pipeline_processor import (
    process_all_active_subscriptions,
)


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

CHECK_INTERVAL_MINUTES = 720

TIMEZONE = timezone.utc


# ============================================================
# ASYNC APSCHEDULER
# ============================================================

scheduler = AsyncIOScheduler(
    timezone=TIMEZONE
)


# ============================================================
# SCHEDULER JOB
# ============================================================

async def check_for_new_internships():
    """
    Run one complete internship discovery cycle.

    IMPORTANT:

    This function runs inside ONE asyncio event loop.

    No asyncio.run()
    No ThreadPoolExecutor
    No separate event loops per company.
    """

    logger.info("")
    logger.info("=" * 70)
    logger.info(
        "🔍 Checking for new internships..."
    )
    logger.info("=" * 70)

    start_time = datetime.now(
        timezone.utc
    )

    try:

        # ====================================================
        # RUN LOCKED PIPELINE
        # ====================================================

        result = await (
            process_all_active_subscriptions()
        )

        # ====================================================
        # SUMMARY
        # ====================================================

        elapsed = (
            datetime.now(timezone.utc)
            - start_time
        ).total_seconds()

        logger.info("")
        logger.info(
            "📊 Internship pipeline finished."
        )

        if result:

            logger.info(
                "👥 Subscriptions: %s",
                result.get(
                    "subscriptions",
                    0,
                ),
            )

            logger.info(
                "📦 Groups: %s",
                result.get(
                    "groups",
                    0,
                ),
            )

        logger.info(
            "⏱️ Cycle duration: %.2f seconds",
            elapsed,
        )

        logger.info(
            "🔔 Relevant internships are "
            "queued as PENDING notifications."
        )

        logger.info(
            "📨 Notification dispatcher "
            "will handle email delivery."
        )

        logger.info(
            "✅ Internship check completed."
        )

    except asyncio.CancelledError:

        logger.warning(
            "⚠️ Internship scheduler job cancelled."
        )

        raise

    except Exception as error:

        logger.exception(
            "❌ Internship scheduler cycle failed: %s",
            error,
        )

    finally:

        logger.info("")
        logger.info("=" * 70)


# ============================================================
# START SCHEDULER
# ============================================================

def start_scheduler():
    """
    Start the dedicated internship scheduler.

    IMPORTANT:

    This function must be called from an
    already-running asyncio event loop.
    """

    scheduler_enabled = (
        os.getenv(
            "SCHEDULER_ENABLED",
            "false",
        )
        .strip()
        .lower()
        == "true"
    )

    if not scheduler_enabled:

        logger.info(
            "⏸️ Internship scheduler disabled. "
            "Set SCHEDULER_ENABLED=true "
            "to enable it."
        )

        return

    if scheduler.running:

        logger.warning(
            "⚠️ Scheduler is already running."
        )

        return

    # ========================================================
    # ADD 12-HOUR JOB
    # ========================================================

    scheduler.add_job(

    check_for_new_internships,

    trigger="interval",

    minutes=CHECK_INTERVAL_MINUTES,

    id="internship_checker",

    replace_existing=True,

    max_instances=1,

    coalesce=True,

    next_run_time=datetime.now(timezone.utc),
)
    scheduler.start()

    logger.info("")
    logger.info(
        "⏰ Internship scheduler started."
    )

    logger.info(
        "🔁 Internship search interval: "
        "%d minutes (12 hours).",
        CHECK_INTERVAL_MINUTES,
    )

    logger.info(
        "🔐 Scheduler ownership: "
        "DEDICATED PROCESS"
    )


# ============================================================
# STOP SCHEDULER
# ============================================================


    
# ============================================================
# STOP SCHEDULER
# ============================================================

# ============================================================
# STOP SCHEDULER
# ============================================================

def stop_scheduler():
    """
    Stop the dedicated internship scheduler safely.
    """

    if not scheduler.running:

        logger.info(
            "⏹️ Internship scheduler is not running."
        )

        return

    scheduler.shutdown(
        wait=True
    )

    logger.info(
        "🔹 Internship scheduler stopped."
    )
# ============================================================
# DIRECT TEST
# ============================================================

async def main():

    logging.basicConfig(

        level=logging.INFO,

        format=(
            "%(asctime)s "
            "[%(levelname)s] "
            "%(name)s: "
            "%(message)s"
        ),
    )

    logger.info(
        "🧪 Running internship scheduler directly..."
    )

    # --------------------------------------------------------
    # Run exactly ONE cycle.
    # --------------------------------------------------------

    await check_for_new_internships()


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )