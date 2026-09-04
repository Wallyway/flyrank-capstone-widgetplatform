from app import config


def send(client, widget_id, email, **extra):
    body = {"widget_id": widget_id, "data": {"email": email}}
    body.update(extra)
    return client.post("/public/submissions", json=body)


def test_the_stats_add_up_and_exclude_spam(client, widget, tenant):
    send(client, widget["id"], "one@example.com")
    send(client, widget["id"], "two@example.com")
    send(client, widget["id"], "bot@example.com", **{config.HONEYPOT_FIELD: "filled"})

    overview = client.get("/api/stats/overview", headers=tenant["auth"]).json()
    assert overview["total"] == 2
    assert overview["spam_blocked"] == 1

    # The list and the headline number use the same filter, so they agree.
    page = client.get("/api/submissions", headers=tenant["auth"]).json()
    assert page["total"] == overview["total"]


def test_a_widget_with_no_submissions_still_appears(client, tenant, widget):
    rows = client.get("/api/stats/by-widget", headers=tenant["auth"]).json()
    assert [r["widget_id"] for r in rows] == [widget["id"]]
    assert rows[0]["total"] == 0


def test_the_timeseries_fills_quiet_days_with_zero(client, tenant):
    rows = client.get("/api/stats/timeseries?days=7", headers=tenant["auth"]).json()
    assert len(rows) == 7
    assert all(isinstance(r["total"], int) for r in rows)
    assert [r["day"] for r in rows] == sorted(r["day"] for r in rows)


def test_paging_is_bounded(client, tenant):
    response = client.get("/api/submissions?limit=1000", headers=tenant["auth"])
    assert response.status_code == 400


def test_the_dashboard_is_closed_to_anonymous_callers(client):
    for path in [
        "/api/submissions",
        "/api/stats/overview",
        "/api/stats/by-widget",
        "/api/stats/geo",
        "/api/stats/timeseries",
    ]:
        assert client.get(path).status_code == 401, path


def test_one_tenant_never_sees_another_tenants_numbers(client, widget, tenant, other_tenant):
    send(client, widget["id"], "mine@example.com")

    assert client.get("/api/stats/overview", headers=tenant["auth"]).json()["total"] == 1
    assert client.get("/api/stats/overview", headers=other_tenant["auth"]).json()["total"] == 0
    assert client.get("/api/submissions", headers=other_tenant["auth"]).json()["total"] == 0

    # Even naming the other tenant's widget explicitly returns nothing.
    filtered = client.get(f"/api/submissions?widget_id={widget['id']}", headers=other_tenant["auth"]).json()
    assert filtered["total"] == 0


def test_the_api_does_not_hand_back_the_visitors_ip(client, widget, tenant):
    send(client, widget["id"], "someone@example.com")
    row = client.get("/api/submissions", headers=tenant["auth"]).json()["items"][0]
    assert "ip" not in row
    assert "user_agent" not in row
