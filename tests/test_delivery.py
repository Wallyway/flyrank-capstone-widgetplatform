from app import config


def test_the_bundle_is_immutable_for_a_year(client):
    response = client.get(f"/static/widget.{config.WIDGET_BUNDLE_VERSION}.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == f"public, max-age={config.BUNDLE_MAX_AGE}, immutable"
    assert response.headers["content-type"].startswith("application/javascript")


def test_an_unknown_bundle_version_is_a_404(client):
    assert client.get("/static/widget.v99.js").status_code == 404
    assert client.get("/static/widget.not-a-version.js").status_code == 404


def test_the_config_is_short_lived_and_revalidates(client, widget):
    first = client.get(f"/public/widgets/{widget['id']}/config")
    assert first.status_code == 200
    assert first.headers["cache-control"] == f"public, max-age={config.CONFIG_MAX_AGE}"

    etag = first.headers["etag"]
    assert str(widget["config_version"]) in etag

    again = client.get(f"/public/widgets/{widget['id']}/config", headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.content == b""


def test_editing_a_widget_changes_its_etag(client, tenant, widget):
    before = client.get(f"/public/widgets/{widget['id']}/config").headers["etag"]
    client.patch(f"/api/widgets/{widget['id']}", json={"title": "New title"}, headers=tenant["auth"])
    after = client.get(f"/public/widgets/{widget['id']}/config").headers["etag"]
    assert before != after


def test_the_config_never_leaks_who_owns_the_widget(client, widget):
    body = client.get(f"/public/widgets/{widget['id']}/config").json()
    assert "tenant_id" not in body
    assert body["honeypot_field"] == config.HONEYPOT_FIELD
    assert body["submit_url"].endswith("/public/submissions")


def test_the_loader_names_the_current_bundle(client, widget):
    body = client.get(f"/widget.js?id={widget['id']}").text
    assert f"widget.{config.WIDGET_BUNDLE_VERSION}.js" in body
    assert widget["id"] in body


def test_an_inactive_widget_stops_being_served(client, tenant, widget):
    client.patch(f"/api/widgets/{widget['id']}", json={"active": False}, headers=tenant["auth"])
    assert client.get(f"/public/widgets/{widget['id']}/config").status_code == 404
    assert client.get(f"/widget.js?id={widget['id']}").status_code == 404
