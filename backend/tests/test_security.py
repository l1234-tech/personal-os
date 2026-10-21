from app.security import (
    generate_opaque_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_password_is_hashed_and_verified() -> None:
    password = "example-strong-password-123"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("different-password-123", hashed)


def test_opaque_tokens_are_unique_and_only_stored_as_hashes() -> None:
    token_a = generate_opaque_token()
    token_b = generate_opaque_token()

    assert token_a != token_b
    assert len(token_a) >= 32
    assert hash_token(token_a) != token_a
    assert len(hash_token(token_a)) == 64
