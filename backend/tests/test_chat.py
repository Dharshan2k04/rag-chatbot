"""Tests for chat endpoints with user isolation."""

from app.auth import hash_password
from app.database import create_user, create_chat


def _login_user(client, db_session, email, password):
    create_user(db_session, email, email.split("@")[0], hash_password(password))
    db_session.commit()
    resp = client.post("/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        print(f"LOGIN FAIL {resp.status_code}: {resp.json()}")
    return resp.json()["access_token"]


def test_create_chat(client, db_session):
    token = _login_user(client, db_session, "u1@test.com", "Password123")
    response = client.post("/chat/new", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert "chat_id" in data


def test_chat_message_no_docs(client, db_session):
    token = _login_user(client, db_session, "u2@test.com", "Password123")
    chat = client.post("/chat/new", headers={"Authorization": f"Bearer {token}"}).json()
    chat_id = chat["chat_id"]

    response = client.post(
        f"/chat/{chat_id}?query=hello",
        headers={"Authorization": f"Bearer {token}"}
    )
    # No documents uploaded => 400
    assert response.status_code == 400


def test_list_chats_isolation(client, db_session):
    token1 = _login_user(client, db_session, "a@test.com", "Password123")
    token2 = _login_user(client, db_session, "b@test.com", "Password123")

    chat1 = client.post("/chat/new", headers={"Authorization": f"Bearer {token1}"}).json()
    chat2 = client.post("/chat/new", headers={"Authorization": f"Bearer {token2}"}).json()

    list1 = client.get("/chat/", headers={"Authorization": f"Bearer {token1}"}).json()
    list2 = client.get("/chat/", headers={"Authorization": f"Bearer {token2}"}).json()

    assert len(list1["chats"]) == 1
    assert list1["chats"][0]["id"] == chat1["chat_id"]

    assert len(list2["chats"]) == 1
    assert list2["chats"][0]["id"] == chat2["chat_id"]


def test_delete_chat(client, db_session):
    token = _login_user(client, db_session, "del@test.com", "Password123")
    chat = client.post("/chat/new", headers={"Authorization": f"Bearer {token}"}).json()
    chat_id = chat["chat_id"]

    resp = client.delete(f"/chat/{chat_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    # Should be gone
    resp = client.get(f"/chat/{chat_id}/messages", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
