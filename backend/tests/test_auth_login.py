"""'가입은 됐는데 로그인이 안 된다'를 만드는 경로들."""


def test_email_is_case_insensitive(client):
    """가입할 때와 로그인할 때 대소문자가 달라도 같은 계정이어야 한다."""
    r = client.post("/auth/signup", json={"email": "Kim@Test.com", "password": "secret123", "name": "김"})
    assert r.status_code == 200

    assert client.post("/auth/login", json={"email": "Kim@Test.com", "password": "secret123"}).status_code == 200
    assert client.post("/auth/login", json={"email": "kim@test.com", "password": "secret123"}).status_code == 200
    assert client.post("/auth/login", json={"email": "KIM@TEST.COM", "password": "secret123"}).status_code == 200


def test_same_email_different_case_is_not_a_new_account(client):
    client.post("/auth/signup", json={"email": "kim@test.com", "password": "secret123", "name": "김"})
    dup = client.post("/auth/signup", json={"email": "KIM@test.com", "password": "other123", "name": "사칭"})
    assert dup.status_code == 400  # 같은 사람으로 봐야 한다


def test_short_password_gives_a_readable_message(client):
    """검증 실패 메시지가 화면에 그대로 뜬다 — 배열이면 '[object Object]'가 된다."""
    r = client.post("/auth/signup", json={"email": "kim@test.com", "password": "1234", "name": "김"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert isinstance(detail, str), "detail이 문자열이어야 프론트에서 읽을 수 있다"
    assert detail == "비밀번호는 8자 이상이어야 합니다."  # 조사까지 자연스럽게


def test_invalid_email_gives_a_readable_message(client):
    r = client.post("/auth/signup", json={"email": "골뱅이없음", "password": "secret123", "name": "김"})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)
    assert "이메일" in r.json()["detail"]


def test_missing_field_gives_a_readable_message(client):
    r = client.post("/auth/signup", json={"email": "kim@test.com", "password": "secret123"})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)


def test_wrong_password_still_rejected(client):
    client.post("/auth/signup", json={"email": "kim@test.com", "password": "secret123", "name": "김"})
    assert client.post("/auth/login", json={"email": "kim@test.com", "password": "wrongpass"}).status_code == 401
    assert client.post("/auth/login", json={"email": "nobody@test.com", "password": "secret123"}).status_code == 401
