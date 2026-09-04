def test_preflight_is_answered_by_the_middleware(client):
    response = client.options(
        "/public/submissions",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type, idempotency-key",
        },
    )
    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "*"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert response.headers["access-control-allow-headers"] == "content-type, idempotency-key"
    assert response.headers["access-control-max-age"] == "600"


def test_public_get_carries_cors_headers(client, widget):
    response = client.get(
        f"/public/widgets/{widget['id']}/config", headers={"Origin": "https://anywhere.example"}
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


def test_admin_api_is_deliberately_not_cors_enabled(client, tenant):
    response = client.get("/api/widgets", headers={**tenant["auth"], "Origin": "https://evil.example"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
