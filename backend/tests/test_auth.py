"""Tests for authentication endpoints."""

from app.auth import hash_password
from app.database import create_user


def test_register(client):
    response = client.post("/auth/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "password": "Password123"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"


def test_register_duplicate_email(client, db_session):
    create_user(db_session, "test@example.com", "testuser", hash_password("Password123"))
    db_session.commit()

    response = client.post("/auth/register", json={
        "email": "test@example.com",
        "username": "testuser2",
        "password": "Password123"
    })
    assert response.status_code == 409


def test_login_success(client, db_session):
    create_user(db_session, "test@example.com", "testuser", hash_password("Password123"))
    db_session.commit()

    response = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "Password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, db_session):
    create_user(db_session, "test@example.com", "testuser", hash_password("Password123"))
    db_session.commit()

    response = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "WrongPassword"
    })
    assert response.status_code == 401


def test_login_lockout(client, db_session):
    create_user(db_session, "test@example.com", "testuser", hash_password("Password123"))
    db_session.commit()

    for _ in range(5):
        response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "WrongPassword"
        })
        assert response.status_code in (401, 429)

    # 5th or 6th attempt should be locked
    response = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "WrongPassword"
    })
    assert response.status_code == 429


def test_me_endpoint(client, db_session):
    user = create_user(db_session, "me@test.com", "meuser", hash_password("Password123"))
    db_session.commit()

    login = client.post("/auth/login", json={
        "email": "me@test.com",
        "password": "Password123"
    })
    token = login.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "me@test.com"
