import os
import asyncio

os.environ["SCHEDULER_ENABLED"] = "true"

from apscheduler.schedulers.base import STATE_STOPPED

from app.services.scheduler import (
    scheduler,
    start_scheduler,
    stop_scheduler,
)


async def test_scheduler():

    start_scheduler()

    job = scheduler.get_job("internship_checker")

    print("scheduler running:", scheduler.running)
    print("job exists:", job is not None)
    print(
        "interval minutes:",
        job.trigger.interval.total_seconds() / 60
        if job else None,
    )
    print(
        "max_instances:",
        job.max_instances
        if job else None,
    )
    print(
        "coalesce:",
        job.coalesce
        if job else None,
    )

    stop_scheduler()
    await asyncio.sleep(0)

    print("scheduler state:", scheduler.state)
    print("STATE_STOPPED:", STATE_STOPPED)
    print(
        "scheduler stopped:",
        not scheduler.running,
    )


asyncio.run(test_scheduler())