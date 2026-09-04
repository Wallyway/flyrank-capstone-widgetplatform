import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.ids import hash_key, new_api_key
from app.main import app
from app.services.ratelimit import RateLimiter

# TestClient is used without its context manager on purpose: that skips the
# lifespan, so the notification worker never starts and no background task can
# make a test flaky. The pool is built at import time, so the database works.


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def fresh_limits():
    """Every test starts with an empty rate-limit table.

    Without this, the order tests run in would decide whether they pass.
    """
    app.state.limiter.by_ip.counters.clear()
    app.state.limiter.by_widget.counters.clear()
    yield


def make_tenant(name: str) -> tuple[int, str]:
    tenant = app.state.tenants.create_tenant(name)
    key = new_api_key()
    app.state.tenants.add_api_key(tenant["id"], hash_key(key), label="test")
    return tenant["id"], key


def drop_tenant(tenant_id: int):
    # Widgets, submissions and jobs all cascade from here.
    with app.state.pool.connection() as conn:
        conn.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))


@pytest.fixture
def tenant():
    tenant_id, key = make_tenant(f"test-{uuid.uuid4().hex[:8]}")
    yield {"id": tenant_id, "key": key, "auth": {"Authorization": f"Bearer {key}"}}
    drop_tenant(tenant_id)


@pytest.fixture
def other_tenant():
    tenant_id, key = make_tenant(f"test-other-{uuid.uuid4().hex[:8]}")
    yield {"id": tenant_id, "key": key, "auth": {"Authorization": f"Bearer {key}"}}
    drop_tenant(tenant_id)


WIDGET_BODY = {
    "type": "signup_form",
    "title": "Test widget",
    "description": "for the suite",
    "button_text": "Send",
    "fields": [
        {"name": "email", "label": "Email", "type": "email", "required": True},
        {"name": "name", "label": "Name", "type": "text", "required": False, "max_length": 20},
        {"name": "role", "label": "Role", "type": "select", "required": False, "options": ["A", "B"]},
    ],
}


@pytest.fixture
def widget(client, tenant):
    response = client.post("/api/widgets", json=WIDGET_BODY, headers=tenant["auth"])
    assert response.status_code == 201
    return response.json()
