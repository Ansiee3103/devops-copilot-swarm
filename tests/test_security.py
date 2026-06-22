import pytest
from backend.core.security import hash_password, verify_password, create_access_token, decode_token

def test_password_hash_and_verify():
    password = "securepassword123"
    hashed   = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) == True

def test_password_wrong():
    hashed = hash_password("correct_password")
    assert verify_password("wrong_password", hashed) == False

def test_password_unique_hashes():
    """Same password should produce different hashes (bcrypt salting)"""
    h1 = hash_password("password123")
    h2 = hash_password("password123")
    assert h1 != h2  # Different salts

def test_token_create_and_decode():
    token   = create_access_token({"sub": "testuser", "role": "deployer"})
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"]  == "testuser"
    assert payload["role"] == "deployer"

def test_token_invalid():
    payload = decode_token("invalid.token.here")
    assert payload is None

def test_token_has_expiry():
    token   = create_access_token({"sub": "user"})
    payload = decode_token(token)
    assert "exp" in payload
    assert "iat" in payload
    assert "jti" in payload  # unique token ID