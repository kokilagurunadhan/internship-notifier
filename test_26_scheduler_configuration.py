import pytest

import app.services.scheduler as scheduler_module


# ============================================================
# TEST 26 — SCHEDULER CONFIGURATION
# ============================================================


def test_scheduler_disabled(monkeypatch):
    """
    SCHEDULER_ENABLED=false
    → scheduler must NOT start
    → no job should be registered
    """

    monkeypatch.setenv(
        "SCHEDULER_ENABLED",
        "false",
    )

    added_jobs = []
    started = []

    def fake_add_job(*args, **kwargs):
        added_jobs.append((args, kwargs))

    def fake_start():
        started.append(True)

    monkeypatch.setattr(
        scheduler_module.scheduler,
        "add_job",
        fake_add_job,
    )

    monkeypatch.setattr(
        scheduler_module.scheduler,
        "start",
        fake_start,
    )

    scheduler_module.start_scheduler()

    assert added_jobs == []
    assert started == []

    print("CASE 1 PASSED: Disabled scheduler does not start")


def test_scheduler_enabled_configuration(monkeypatch):
    """
    SCHEDULER_ENABLED=true
    → correct 12-hour job must be registered
    """

    monkeypatch.setenv(
        "SCHEDULER_ENABLED",
        "true",
    )

    added_jobs = []
    started = []

    def fake_add_job(*args, **kwargs):
        added_jobs.append((args, kwargs))

    def fake_start():
        started.append(True)

    monkeypatch.setattr(
        scheduler_module.scheduler,
        "add_job",
        fake_add_job,
    )

    monkeypatch.setattr(
        scheduler_module.scheduler,
        "start",
        fake_start,
    )

    scheduler_module.start_scheduler()

    assert len(added_jobs) == 1
    assert len(started) == 1

    args, kwargs = added_jobs[0]

    # --------------------------------------------------------
    # Correct function
    # --------------------------------------------------------

    assert args[0] is scheduler_module.check_for_new_internships

    print(
        "CASE 2 PASSED: Correct scheduler job function registered"
    )

    # --------------------------------------------------------
    # Correct trigger
    # --------------------------------------------------------

    assert kwargs["trigger"] == "interval"

    print(
        "CASE 3 PASSED: Interval trigger configured"
    )

    # --------------------------------------------------------
    # Correct interval
    # --------------------------------------------------------

    assert kwargs["minutes"] == 720

    print(
        "CASE 4 PASSED: Scheduler interval is exactly 720 minutes"
    )

    # --------------------------------------------------------
    # Correct job ID
    # --------------------------------------------------------

    assert kwargs["id"] == "internship_checker"

    print(
        "CASE 5 PASSED: Correct scheduler job ID"
    )

    # --------------------------------------------------------
    # No overlapping cycles
    # --------------------------------------------------------

    assert kwargs["max_instances"] == 1

    print(
        "CASE 6 PASSED: max_instances=1 prevents overlap"
    )

    # --------------------------------------------------------
    # Missed runs are coalesced
    # --------------------------------------------------------

    assert kwargs["coalesce"] is True

    print(
        "CASE 7 PASSED: coalesce=True configured"
    )

    # --------------------------------------------------------
    # Existing job replaced safely
    # --------------------------------------------------------

    assert kwargs["replace_existing"] is True

    print(
        "CASE 8 PASSED: replace_existing=True configured"
    )


def test_scheduler_does_not_start_twice(monkeypatch):
    """
    If scheduler.running is already True,
    start_scheduler() must not register another job.
    """

    monkeypatch.setenv(
        "SCHEDULER_ENABLED",
        "true",
    )

    # --------------------------------------------------------
    # Mock the read-only running property at the class level.
    # --------------------------------------------------------

    monkeypatch.setattr(
        type(scheduler_module.scheduler),
        "running",
        property(lambda self: True),
    )

    added_jobs = []

    def fake_add_job(*args, **kwargs):
        added_jobs.append((args, kwargs))

    monkeypatch.setattr(
        scheduler_module.scheduler,
        "add_job",
        fake_add_job,
    )

    scheduler_module.start_scheduler()

    assert added_jobs == []

    print(
        "CASE 9 PASSED: Running scheduler cannot be started twice"
    )

def test_scheduler_interval_constant():
    """
    Verify the source-level scheduler constant.
    """

    assert scheduler_module.CHECK_INTERVAL_MINUTES == 720

    print(
        "CASE 10 PASSED: CHECK_INTERVAL_MINUTES = 720"
    )


def test_scheduler_timezone():
    """
    Verify scheduler uses UTC timezone.
    """

    assert scheduler_module.TIMEZONE == scheduler_module.timezone.utc

    print(
        "CASE 11 PASSED: Scheduler timezone is UTC"
    )