"""Tests for document upload endpoint."""

import io
from app.auth import hash_password
from app.database import create_user


def _login_user(client, db_session, email, password):
    create_user(db_session, email, email.split("@")[0], hash_password(password))
    db_session.commit()
    resp = client.post("/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_upload_valid_pdf(client, db_session):
    token = _login_user(client, db_session, "upload@test.com", "Password123")
    pdf_bytes = b"%PDF-1.4 test content for pdf validation"

    response = client.post(
        "/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert response.status_code == 200
    data = response.json()
    assert "document_id" in data
    assert "filename" in data


def test_upload_wrong_mime(client, db_session):
    token = _login_user(client, db_session, "badmime@test.com", "Password123")
    txt_bytes = b"not a pdf"

    response = client.post(
        "/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test.txt", io.BytesIO(txt_bytes), "text/plain")}
    )
    assert response.status_code == 415


def test_upload_no_auth(client):
    pdf_bytes = b"%PDF-1.4 test"
    response = client.post(
        "/upload",
        files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert response.status_code == 403


def test_list_documents_isolation(client, db_session):
    token1 = _login_user(client, db_session, "d1@test.com", "Password123")
    token2 = _login_user(client, db_session, "d2@test.com", "Password123")

    pdf = b"%PDF-1.4 doc"
    client.post(
        "/upload",
        headers={"Authorization": f"Bearer {token1}"},
        files={"file": ("doc.pdf", io.BytesIO(pdf), "application/pdf")}
    )

    docs1 = client.get("/documents", headers={"Authorization": f"Bearer {token1}"}).json()
    docs2 = client.get("/documents", headers={"Authorization": f"Bearer {token2}"}).json()

    assert len(docs1["documents"]) == 1
    assert len(docs2["documents"]) == 0
