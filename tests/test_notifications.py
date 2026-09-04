import asyncio

import pytest

from app import config
from app.main import app
from app.services.notifications import NotificationWorker


class FailingWorker(NotificationWorker):
    """A worker whose side effect is always broken."""

    async def deliver(self, payload):
        raise RuntimeError("upstream is on fire")


def enqueue(widget_id, tenant_id) -> int:
    with app.state.pool.connection() as conn:
        submission = conn.execute(
            "INSERT INTO submissions (widget_id, tenant_id, data) VALUES (%s, %s, '{}'::jsonb) RETURNING id",
            (widget_id, tenant_id),
        ).fetchone()
        conn.execute("INSERT INTO notification_jobs (submission_id) VALUES (%s)", (submission["id"],))
    return submission["id"]


def job_for(submission_id: int) -> dict:
    with app.state.pool.connection() as conn:
        return conn.execute(
            "SELECT id, status, attempts, last_error FROM notification_jobs WHERE submission_id = %s",
            (submission_id,),
        ).fetchone()


def test_a_broken_side_effect_retries_then_dies_without_touching_the_submission(widget, tenant):
    submission_id = enqueue(widget["id"], tenant["id"])
    worker = FailingWorker(app.state.notifications)

    # One tick per attempt. next_attempt_at is pushed into the future by the
    # backoff, so each round is stepped back to now to keep the test instant.
    for _ in range(config.NOTIFY_MAX_ATTEMPTS):
        asyncio.run(worker.tick())
        with app.state.pool.connection() as conn:
            conn.execute(
                "UPDATE notification_jobs SET next_attempt_at = now() WHERE submission_id = %s AND status = 'pending'",
                (submission_id,),
            )

    job = job_for(submission_id)
    assert job["status"] == "dead"
    assert job["attempts"] == config.NOTIFY_MAX_ATTEMPTS
    assert "on fire" in job["last_error"]

    # The point of all of it: the submission is untouched.
    with app.state.pool.connection() as conn:
        row = conn.execute("SELECT id FROM submissions WHERE id = %s", (submission_id,)).fetchone()
    assert row is not None


def test_a_working_side_effect_is_marked_delivered(widget, tenant, monkeypatch):
    monkeypatch.setattr(config, "WEBHOOK_URL", "")
    monkeypatch.setattr(config, "NOTIFY_FORCE_FAILURE", False)
    submission_id = enqueue(widget["id"], tenant["id"])

    asyncio.run(NotificationWorker(app.state.notifications).tick())

    job = job_for(submission_id)
    assert job["status"] == "delivered"
    assert job["attempts"] == 1


def test_the_backoff_grows(widget, tenant):
    submission_id = enqueue(widget["id"], tenant["id"])
    worker = FailingWorker(app.state.notifications)
    delays = []

    for _ in range(3):
        asyncio.run(worker.tick())
        with app.state.pool.connection() as conn:
            row = conn.execute(
                "SELECT EXTRACT(EPOCH FROM (next_attempt_at - now())) AS wait FROM notification_jobs "
                "WHERE submission_id = %s",
                (submission_id,),
            ).fetchone()
            delays.append(round(row["wait"]))
            conn.execute(
                "UPDATE notification_jobs SET next_attempt_at = now() WHERE submission_id = %s",
                (submission_id,),
            )

    assert delays == sorted(delays)
    assert delays[-1] > delays[0]
