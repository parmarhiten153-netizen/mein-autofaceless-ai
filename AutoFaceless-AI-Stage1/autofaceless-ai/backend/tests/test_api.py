import os
os.environ["DATABASE_URL"] = "sqlite:///./test_autofaceless.db"
# Importing app reads environment through settings at module import; this test is a basic API smoke suite.
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)

def register_and_login(email="demo@example.com"):
    r = client.post("/api/auth/register", json={"email": email, "password": "strong-password-123", "timezone": "Asia/Kolkata"})
    assert r.status_code == 201, r.text
    r = client.post("/api/auth/login", json={"email": email, "password": "strong-password-123"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}

def payload(key):
    return {"idempotency_key": key, "niche": "Science facts", "language": "Hindi", "format": "shorts", "target_duration_seconds": 45, "tone": "educational", "topic_keywords": "space", "target_audience": "general"}

def test_auth_and_dashboard():
    headers = register_and_login()
    r = client.get("/api/dashboard", headers=headers)
    assert r.status_code == 200
    assert r.json()["daily_limit"] == 2
    assert r.json()["remaining_today"] == 2

def test_quota_and_idempotency():
    headers = register_and_login("quota@example.com")
    first = client.post("/api/jobs", json=payload("request-key-0001"), headers=headers)
    assert first.status_code == 202
    duplicate = client.post("/api/jobs", json=payload("request-key-0001"), headers=headers)
    assert duplicate.status_code == 202
    assert duplicate.json()["id"] == first.json()["id"]
    second = client.post("/api/jobs", json=payload("request-key-0002"), headers=headers)
    assert second.status_code == 202
    third = client.post("/api/jobs", json=payload("request-key-0003"), headers=headers)
    assert third.status_code == 429

def test_invalid_timezone():
    r = client.post("/api/auth/register", json={"email": "bad-tz@example.com", "password": "strong-password-123", "timezone": "Not/AZone"})
    assert r.status_code == 422
