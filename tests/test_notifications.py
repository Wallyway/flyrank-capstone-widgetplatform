import asyncio

from app import config
from app.main import app
from app.services.notifications import NotificationWorker


class FailingWorker(NotificationWorker):
    """A worker whose side effect is always broken."""

    async def deliver(self, payload):
        raise RuntimeError("upstream is on fire")


def enqueue(widget_id, tenant_id) -> int:
    """Queue a job the running server will never touch.

    These tests share a database with a live app whose worker polls for due
    jobs every couple of seconds. A job dated an hour out is never due, so it
    cannot be claimed and delivered out from under the assertions here — and
    the tests claim it by name instead of waiting for it to ripen.
    """
    with app.state.pool.connection() as conn:
        submission = conn.execute(
            "INSERT INTO submissions (widget_id, tenant_id, data) VALUES (%s, %s, '{}'::jsonb) RETURNING id",
            (widget_id, tenant_id),
        ).fetchone()
        conn.execute(
            "INSERT INTO notification_jobs (submission_id, next_attempt_at) "
            "VALUES (%s, now() + interval '1 hour')",
            (submission["id"],),
        )
    return submission["id"]


def job_for(submission_id: int) -> dict:
    with app.state.pool.connection() as conn:
        return conn.execute(
            "SELECT id, status, attempts, last_error, next_attempt_at FROM notification_jobs "
            "WHERE submission_id = %s",
            (submission_id,),
        ).fetchone()


def run_one_attempt(worker, submission_id):
    """One claim-and-process cycle, the same pair the worker loop runs."""
    job = worker.repository.claim_one(submission_id)
    assert job is not None, "the job should still have been pending"
    asyncio.run(worker.process(job))


def test_a_broken_side_effect_retries_then_dies_without_touching_the_submission(widget, tenant):
    submission_id = enqueue(widget["id"], tenant["id"])
    worker = FailingWorker(app.state.notifications)

    for _ in range(config.NOTIFY_MAX_ATTEMPTS):
        run_one_attempt(worker, submission_id)

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

    run_one_attempt(NotificationWorker(app.state.notifications), submission_id)

    job = job_for(submission_id)
    assert job["status"] == "delivered"
    assert job["attempts"] == 1


def test_the_backoff_grows(widget, tenant):
    submission_id = enqueue(widget["id"], tenant["id"])
    worker = FailingWorker(app.state.notifications)
    delays = []

    for _ in range(3):
        run_one_attempt(worker, submission_id)
        with app.state.pool.connection() as conn:
            row = conn.execute(
                "SELECT EXTRACT(EPOCH FROM (next_attempt_at - now())) AS wait FROM notification_jobs "
                "WHERE submission_id = %s",
                (submission_id,),
            ).fetchone()
        delays.append(round(row["wait"]))

    assert delays == sorted(delays)
    assert delays[-1] > delays[0]


def test_a_job_can_only_be_claimed_once(widget, tenant):
    """Two workers against one queue must not both get the same row."""
    submission_id = enqueue(widget["id"], tenant["id"])
    repo = app.state.notifications

    first = repo.claim_one(submission_id)
    second = repo.claim_one(submission_id)

    assert first is not None
    assert second is None
