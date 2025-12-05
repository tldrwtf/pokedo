"""Tests for authentication module."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from pokedo.core.auth import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    get_password_hash,
    verify_password,
)
from pokedo.server import app, fake_users_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_db():
    """Clear the mock database before each test."""
    fake_users_db.clear()


class TestAuthUtils:
    """Tests for auth utility functions."""

    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "securepassword"
        hashed = get_password_hash(password)
        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("wrongpassword", hashed)

    def test_token_creation(self):
        """Test JWT creation."""
        data = {"sub": "testuser"}
        token = create_access_token(data)
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["sub"] == "testuser"
        assert "exp" in decoded


class TestAuthEndpoints:
    """Tests for authentication API endpoints."""

    def test_register_user(self):
        """Test user registration."""
        response = client.post(
            "/register",
            json={"username": "newuser", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newuser"
        assert "password" not in data  # Should not return password
        assert "newuser" in fake_users_db

    def test_register_duplicate_user(self):
        """Test registering a duplicate username."""
        client.post(
            "/register",
            json={"username": "duplicate", "password": "password123"},
        )
        response = client.post(
            "/register",
            json={"username": "duplicate", "password": "newpassword"},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Username already registered"

    def test_login_success(self):
        """Test successful login."""
        # specific setup for this test
        fake_users_db.clear()
        client.post(
            "/register",
            json={"username": "loginuser", "password": "password123"},
        )
        
        response = client.post(
            "/token",
            data={"username": "loginuser", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_failure(self):
        """Test login with wrong password."""
        client.post(
            "/register",
            json={"username": "failuser", "password": "password123"},
        )
        
        response = client.post(
            "/token",
            data={"username": "failuser", "password": "wrongpassword"},
        )
        assert response.status_code == 401


class TestProtectedEndpoints:
    """Tests for protected endpoints."""

    def test_sync_unauthorized(self):
        """Accessing sync without token fails."""
        response = client.post("/sync", json=[])
        assert response.status_code == 401

    def test_sync_authorized(self):
        """Accessing sync with token succeeds."""
        # Register
        client.post(
            "/register",
            json={"username": "syncuser", "password": "password123"},
        )
        # Login
        login_res = client.post(
            "/token",
            data={"username": "syncuser", "password": "password123"},
        )
        token = login_res.json()["access_token"]
        
        # Sync
        response = client.post(
            "/sync",
            json=[],
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["user"] == "syncuser"
