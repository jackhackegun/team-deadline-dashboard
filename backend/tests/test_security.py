from app.security import hash_password, verify_password, create_access_token, decode_access_token


def test_password_hash_roundtrip():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip():
    token = create_access_token(user_id=42)
    assert decode_access_token(token) == 42
