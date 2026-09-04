import json
import uuid

from app import config
from app.main import app


def post(client, widget_id, data, **extra):
    body = {"widget_id": widget_id, "data": data}
    body.update(extra.pop("body", {}))
    return client.post("/public/submissions", json=body, **extra)


def test_a_valid_submission_is_stored(client, widget, tenant):
    response = post(client, widget["id"], {"email": "ada@example.com", "name": "Ada"})
    assert response.status_code == 201
    assert response.json()["status"] == "received"

    page = client.get("/api/submissions", headers=tenant["auth"]).json()
    assert page["total"] == 1
    assert page["items"][0]["data"]["email"] == "ada@example.com"
    assert page["items"][0]["widget_id"] == widget["id"]


def test_malformed_json_is_a_400_not_a_500(client):
    response = client.post(
        "/public/submissions", content=b'{"widget_id":', headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert response.json() == {"error": "body: not valid JSON"}


def test_a_json_body_that_is_not_an_object_is_refused(client):
    response = client.post(
        "/public/submissions", content=b'"hello"', headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400


def test_an_oversized_payload_is_a_413(client, widget):
    body = json.dumps({"widget_id": widget["id"], "data": {"email": "a@b.co", "name": "x" * 50000}})
    response = client.post(
        "/public/submissions", content=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413
    assert str(config.MAX_BODY_BYTES) in response.json()["error"]


def test_field_level_validation(client, widget):
    response = post(client, widget["id"], {"email": "not-an-email"})
    assert response.status_code == 400
    assert "not a valid email address" in response.json()["error"]

    response = post(client, widget["id"], {"name": "no email here"})
    assert response.status_code == 400
    assert "email: required" in response.json()["error"]

    response = post(client, widget["id"], {"email": "a@b.co", "surprise": "x"})
    assert response.status_code == 400
    assert "unknown field" in response.json()["error"]

    response = post(client, widget["id"], {"email": "a@b.co", "role": "Z"})
    assert response.status_code == 400
    assert "must be one of" in response.json()["error"]

    # The widget declared max_length 20 for name.
    response = post(client, widget["id"], {"email": "a@b.co", "name": "y" * 40})
    assert response.status_code == 400
    assert "at most 20 characters" in response.json()["error"]


def test_an_unknown_widget_is_a_404(client):
    response = post(client, "wgt_does_not_exist", {"email": "a@b.co"})
    assert response.status_code == 404


def test_a_replayed_request_stores_one_row(client, widget, tenant):
    key = f"test-{uuid.uuid4().hex}"
    headers = {"Idempotency-Key": key}
    data = {"email": "grace@example.com"}

    first = client.post("/public/submissions", json={"widget_id": widget["id"], "data": data}, headers=headers)
    second = client.post("/public/submissions", json={"widget_id": widget["id"], "data": data}, headers=headers)
    third = client.post("/public/submissions", json={"widget_id": widget["id"], "data": data}, headers=headers)

    assert first.status_code == 201
    assert (second.status_code, third.status_code) == (200, 200)
    assert second.json()["status"] == "replayed"
    assert first.json()["id"] == second.json()["id"] == third.json()["id"]

    assert client.get("/api/submissions", headers=tenant["auth"]).json()["total"] == 1


def test_the_burst_gets_429_and_the_service_keeps_serving(client, widget, monkeypatch):
    limit = config.RATE_LIMIT_PER_IP
    codes = []
    for _ in range(limit + 5):
        codes.append(post(client, widget["id"], {"email": "flood@example.com"}).status_code)

    assert codes.count(201) == limit
    assert codes.count(429) == 5

    refused = post(client, widget["id"], {"email": "flood@example.com"})
    assert refused.status_code == 429
    assert int(refused.headers["retry-after"]) > 0

    # The API is limiting one client, not falling over.
    assert client.get("/health").status_code == 200
    assert client.get(f"/public/widgets/{widget['id']}/config").status_code == 200


def test_a_filled_honeypot_is_accepted_and_quietly_flagged(client, widget, tenant):
    response = client.post(
        "/public/submissions",
        json={
            "widget_id": widget["id"],
            "data": {"email": "bot@spam.example"},
            config.HONEYPOT_FIELD: "http://spam.example",
        },
    )
    # The bot is told the same thing a person is.
    assert response.status_code == 202
    assert response.json()["status"] == "received"

    # But it never reaches the owner's dashboard.
    assert client.get("/api/submissions", headers=tenant["auth"]).json()["total"] == 0
    with_spam = client.get("/api/submissions?include_spam=true", headers=tenant["auth"]).json()
    assert with_spam["total"] == 1
    assert with_spam["items"][0]["is_spam"] is True


def test_a_submission_queues_exactly_one_notification(client, widget):
    response = post(client, widget["id"], {"email": "notify@example.com"})
    submission_id = response.json()["id"]
    with app.state.pool.connection() as conn:
        row = conn.execute(
            "SELECT status, attempts FROM notification_jobs WHERE submission_id = %s", (submission_id,)
        ).fetchone()
    assert row is not None
    assert row["status"] == "pending"
    assert row["attempts"] == 0


def test_spam_does_not_queue_a_notification(client, widget):
    response = client.post(
        "/public/submissions",
        json={
            "widget_id": widget["id"],
            "data": {"email": "bot@spam.example"},
            config.HONEYPOT_FIELD: "filled",
        },
    )
    with app.state.pool.connection() as conn:
        row = conn.execute(
            "SELECT id FROM notification_jobs WHERE submission_id = %s", (response.json()["id"],)
        ).fetchone()
    assert row is None
