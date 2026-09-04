from tests.conftest import WIDGET_BODY


def test_a_request_without_a_key_is_refused(client):
    response = client.get("/api/widgets")
    assert response.status_code == 401
    assert response.json() == {"error": "API key required"}


def test_an_unknown_key_is_refused(client):
    response = client.get("/api/widgets", headers={"Authorization": "Bearer wpk_not_a_real_key"})
    assert response.status_code == 401


def test_crud_round_trip(client, tenant, widget):
    listed = client.get("/api/widgets", headers=tenant["auth"]).json()
    assert [w["id"] for w in listed] == [widget["id"]]

    patched = client.patch(
        f"/api/widgets/{widget['id']}", json={"button_text": "Changed"}, headers=tenant["auth"]
    ).json()
    assert patched["button_text"] == "Changed"
    # Every edit bumps the version, which is what the config ETag is built from.
    assert patched["config_version"] == widget["config_version"] + 1

    assert client.delete(f"/api/widgets/{widget['id']}", headers=tenant["auth"]).status_code == 204
    assert client.get(f"/api/widgets/{widget['id']}", headers=tenant["auth"]).status_code == 404


def test_another_tenant_gets_404_not_403(client, widget, other_tenant):
    """403 would confirm the id exists. 404 tells them nothing."""
    assert client.get(f"/api/widgets/{widget['id']}", headers=other_tenant["auth"]).status_code == 404
    assert client.patch(
        f"/api/widgets/{widget['id']}", json={"title": "hijacked"}, headers=other_tenant["auth"]
    ).status_code == 404
    assert client.delete(f"/api/widgets/{widget['id']}", headers=other_tenant["auth"]).status_code == 404
    assert client.get("/api/widgets", headers=other_tenant["auth"]).json() == []


def test_a_bad_widget_body_is_a_400_with_the_field_named(client, tenant):
    response = client.post(
        "/api/widgets", json={"type": "newsletter", "title": "", "fields": []}, headers=tenant["auth"]
    )
    assert response.status_code == 400
    assert "type" in response.json()["error"]


def test_a_select_without_options_is_refused(client, tenant):
    body = {**WIDGET_BODY, "fields": [{"name": "pick", "label": "Pick", "type": "select"}]}
    response = client.post("/api/widgets", json=body, headers=tenant["auth"])
    assert response.status_code == 400
    assert "no options" in response.json()["error"]


def test_the_embed_snippet_points_at_the_loader(client, tenant, widget):
    body = client.get(f"/api/widgets/{widget['id']}/embed", headers=tenant["auth"]).json()
    assert body["widget_id"] == widget["id"]
    assert f"/widget.js?id={widget['id']}" in body["snippet"]
    assert body["snippet"].startswith("<script src=")
