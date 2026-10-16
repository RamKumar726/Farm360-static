def test_public_api_hides_internal_fields(client):
    response = client.get("/api/v1/services")
    assert response.status_code == 200
    assert b"password" not in response.data and b"payment" not in response.data


def test_api_admin_requires_login(client):
    assert client.get("/api/v1/admin/leads").status_code == 401


def test_openapi_documented(client):
    assert client.get("/api/v1/openapi.json").status_code == 200
