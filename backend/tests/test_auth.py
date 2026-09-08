def test_signup_then_login(client):
    r = client.post("/auth/signup", json={"email": "a@test.com", "password": "secret123", "name": "A"})
    assert r.status_code == 200
    assert "access_token" in r.json()

    r2 = client.post("/auth/login", json={"email": "a@test.com", "password": "secret123"})
    assert r2.status_code == 200


def test_login_wrong_password(client):
    client.post("/auth/signup", json={"email": "b@test.com", "password": "secret123", "name": "B"})
    r = client.post("/auth/login", json={"email": "b@test.com", "password": "wrong"})
    assert r.status_code == 401
