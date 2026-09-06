
# ============================================================
# SCHEDULER CONTROLLED TEST
# File: app/services/test_scheduler.py
# ============================================================

import asyncio
import os

import app.services.scheduler as scheduler


# ============================================================
# CONTROLLED PIPELINE
# ============================================================

PIPELINE_CALLS = 0


async def fake_process_all_active_subscriptions():
    global PIPELINE_CALLS

    PIPELINE_CALLS += 1

    return {
        "subscriptions": 1,
        "groups": 1,
    }


# ============================================================
# TEST
# ============================================================

async def main():

    print("=" * 60)
    print("SCHEDULER CONTROLLED TEST")
    print("=" * 60)

    # --------------------------------------------------------
    # Replace real pipeline
    # --------------------------------------------------------

    original_pipeline = (
        scheduler.process_all_active_subscriptions
    )

    scheduler.process_all_active_subscriptions = (
        fake_process_all_active_subscriptions
    )

    try:

        # ====================================================
        # TEST 1 — ONE MANUAL CYCLE
        # ====================================================

        print()
        print("TEST 1: MANUAL SCHEDULER CYCLE")
        print("-" * 60)

        await scheduler.check_for_new_internships()

        if PIPELINE_CALLS == 1:
            print(
                "PASS: scheduler called pipeline exactly once"
            )
        else:
            print(
                "FAIL: pipeline call count =",
                PIPELINE_CALLS,
            )

        # ====================================================
        # TEST 2 — SCHEDULER CONFIGURATION
        # ====================================================

        print()
        print("TEST 2: SCHEDULER CONFIGURATION")
        print("-" * 60)

        job = scheduler.scheduler.get_job(
            "internship_checker"
        )

        if job is None:
            print(
                "INFO: scheduler job not installed "
                "until start_scheduler() is called"
            )
        else:
            print(
                "PASS: internship_checker job exists"
            )

        # ====================================================
        # TEST 3 — ENVIRONMENT DISABLED
        # ====================================================

        print()
        print("TEST 3: SCHEDULER DISABLED")
        print("-" * 60)

        os.environ["SCHEDULER_ENABLED"] = "false"

        scheduler.start_scheduler()

        if not scheduler.scheduler.running:
            print(
                "PASS: scheduler remains stopped "
                "when disabled"
            )
        else:
            print(
                "FAIL: scheduler started while disabled"
            )

        # ====================================================
        # TEST 4 — ENABLED SCHEDULER
        # ====================================================

        print()
        print("TEST 4: SCHEDULER ENABLED")
        print("-" * 60)

        os.environ["SCHEDULER_ENABLED"] = "true"

        scheduler.start_scheduler()

        job = scheduler.scheduler.get_job(
            "internship_checker"
        )

        if scheduler.scheduler.running:
            print(
                "PASS: scheduler started"
            )
        else:
            print(
                "FAIL: scheduler did not start"
            )

        if job is not None:
            print(
                "PASS: internship_checker job created"
            )
        else:
            print(
                "FAIL: internship_checker job missing"
            )

        # ====================================================
        # TEST 5 — JOB CONFIGURATION
        # ====================================================

        print()
        print("TEST 5: JOB CONFIGURATION")
        print("-" * 60)

        if job is not None:

            if job.max_instances == 1:
                print(
                    "PASS: max_instances = 1"
                )
            else:
                print(
                    "FAIL: max_instances =",
                    job.max_instances,
                )

            if job.coalesce is True:
                print(
                    "PASS: coalesce = True"
                )
            else:
                print(
                    "FAIL: coalesce =",
                    job.coalesce,
                )

            if (
                job.trigger.interval.total_seconds()
                == 720 * 60
            ):
                print(
                    "PASS: interval = 12 hours"
                )
            else:
                print(
                    "FAIL: incorrect interval =",
                    job.trigger.interval,
                )

        # ====================================================
        # TEST 6 — DUPLICATE START
        # ====================================================

        print()
        print("TEST 6: DUPLICATE START PROTECTION")
        print("-" * 60)

        scheduler.start_scheduler()

        jobs = scheduler.scheduler.get_jobs()

        matching_jobs = [
            job
            for job in jobs
            if job.id == "internship_checker"
        ]

        if len(matching_jobs) == 1:
            print(
                "PASS: only one internship_checker job exists"
            )
        else:
            print(
                "FAIL: duplicate scheduler jobs found:",
                len(matching_jobs),
            )

        # ====================================================
        # STOP
        # ====================================================

        print()
        print("STOPPING SCHEDULER")
        print("-" * 60)

        scheduler.stop_scheduler()

        # AsyncIOScheduler schedules shutdown on the
        # current event loop. Give the callback one
        # event-loop turn to complete.
        await asyncio.sleep(0)

        if not scheduler.scheduler.running:
            print(
                "PASS: scheduler stopped cleanly"
            )
        else:
            print(
                "FAIL: scheduler still running"
            )

        print()
        print("=" * 60)
        print("🎉 SCHEDULER CONTROLLED TEST COMPLETED")
        print("=" * 60)

    finally:

        # ----------------------------------------------------
        # Restore real pipeline
        # ----------------------------------------------------

        scheduler.process_all_active_subscriptions = (
            original_pipeline
        )

        os.environ.pop(
            "SCHEDULER_ENABLED",
            None,
        )

        if scheduler.scheduler.running:
            scheduler.stop_scheduler()
            await asyncio.sleep(0)


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())

