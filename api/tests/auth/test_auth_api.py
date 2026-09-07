from dataclasses import dataclass
from hashlib import sha256
from importlib import import_module
from types import SimpleNamespace

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from attendance_api.models import LoginSession, User

PASSWORD = "correct-password"
NEW_PASSWORD = "new-correct-password"


@dataclass
class Account:
    id: str
    username: str
    plaintext_password: str


@pytest.fixture
def teacher(db_session: Session) -> Account:
    user = User(
        username="teacher01",
        password_hash=PasswordHasher().hash(PASSWORD),
        display_name="王老师",
        role="TEACHER",
        status="ACTIVE",
        must_change_password=False,
    )
    db_session.add(user)
    db_session.commit()
    return Account(id=user.id, username=user.username, plaintext_password=PASSWORD)


def login(client: TestClient, account: Account) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": account.username, "password": account.plaintext_password},
    )
    assert response.status_code == 200
    return response.json()


def test_login_sets_secure_refresh_cookie_and_returns_access_token(
    client: TestClient, teacher: Account
) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": teacher.username, "password": teacher.plaintext_password},
    )

    assert response.status_code == 200
    assert response.json()["expires_in"] == 900
    assert response.json()["user"]["id"] == teacher.id
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    cookie = response.headers["set-cookie"]
    assert "refresh_token=" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/api/v1/auth" in cookie
    assert "Max-Age=604800" in cookie


def test_login_allows_non_secure_refresh_cookie_for_explicit_local_development(
    client: TestClient, teacher: Account, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth_router = import_module("attendance_api.modules.auth.router")
    monkeypatch.setattr(
        auth_router,
        "get_settings",
        lambda: SimpleNamespace(
            access_token_ttl_seconds=900,
            refresh_token_ttl_seconds=604800,
            refresh_cookie_secure=False,
        ),
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"username": teacher.username, "password": teacher.plaintext_password},
    )

    cookie = response.headers["set-cookie"]
    assert "refresh_token=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/api/v1/auth" in cookie
    assert "Secure" not in cookie


def test_login_accepts_valid_legacy_short_password(client: TestClient, db_session: Session) -> None:
    password = "short-pass"
    db_session.add(
        User(
            username="legacy-admin",
            password_hash=PasswordHasher().hash(password),
            display_name="旧管理员",
            role="ADMIN",
            status="ACTIVE",
            must_change_password=False,
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "legacy-admin", "password": password},
    )

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "ADMIN"


@pytest.mark.parametrize(
    ("username", "password", "status"),
    [
        ("missing-user", PASSWORD, None),
        ("teacher01", "incorrect-password", "ACTIVE"),
        ("teacher01", PASSWORD, "DISABLED"),
    ],
)
def test_login_failures_have_identical_response(
    client: TestClient,
    db_session: Session,
    username: str,
    password: str,
    status: str | None,
) -> None:
    if status is not None:
        db_session.add(
            User(
                username="teacher01",
                password_hash=PasswordHasher().hash(PASSWORD),
                display_name="王老师",
                role="TEACHER",
                status=status,
                must_change_password=False,
            )
        )
        db_session.commit()

    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})

    assert response.status_code == 401
    payload = response.json()
    assert payload["code"] == "INVALID_CREDENTIALS"
    assert payload["message"] == "用户名或密码错误"
    assert payload["details"] == {}


def test_refresh_rotates_hash_and_rejects_old_cookie(
    client: TestClient, db_session: Session, teacher: Account
) -> None:
    login(client, teacher)
    old_token = client.cookies["refresh_token"]
    session = db_session.scalar(select(LoginSession))
    assert session is not None
    old_hash = session.refresh_token_hash

    refreshed = client.post("/api/v1/auth/refresh", headers={"Origin": "https://localhost"})

    assert refreshed.status_code == 200
    db_session.refresh(session)
    assert session.refresh_token_hash != old_hash
    current_cookie_hash = sha256(client.cookies["refresh_token"].encode()).hexdigest()
    assert session.refresh_token_hash == current_cookie_hash

    retried = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "https://localhost", "Cookie": f"refresh_token={old_token}"},
    )
    assert retried.status_code == 401
    assert retried.json()["code"] == "AUTHENTICATION_REQUIRED"


def test_refresh_rejects_wrong_origin(client: TestClient, teacher: Account) -> None:
    login(client, teacher)

    response = client.post("/api/v1/auth/refresh", headers={"Origin": "https://attacker.example"})

    assert response.status_code == 403
    assert response.json()["code"] == "INVALID_ORIGIN"


def test_me_omits_sensitive_fields(client: TestClient, teacher: Account) -> None:
    token = str(login(client, teacher)["access_token"])

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["id"] == teacher.id
    assert not {
        "password_hash",
        "refresh_token",
        "refresh_token_hash",
        "failed_login_count",
        "last_failed_login_at",
    }.intersection(response.json())


def test_temporary_password_blocks_business_routes(client: TestClient, db_session: Session) -> None:
    user = User(
        username="temporary",
        password_hash=PasswordHasher().hash(PASSWORD),
        display_name="临时教师",
        role="TEACHER",
        status="ACTIVE",
        must_change_password=True,
    )
    db_session.add(user)
    db_session.commit()
    account = Account(user.id, user.username, PASSWORD)
    token = str(login(client, account)["access_token"])

    response = client.get("/api/v1/courses", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["code"] == "PASSWORD_CHANGE_REQUIRED"


def test_change_password_rotates_current_and_revokes_other_sessions(
    client: TestClient, db_session: Session, teacher: Account
) -> None:
    login(client, teacher)
    login_result = login(client, teacher)
    token = str(login_result["access_token"])
    sessions = list(db_session.scalars(select(LoginSession).order_by(LoginSession.created_at)))
    assert len(sessions) == 2
    current_session = sessions[-1]
    old_current_hash = current_session.refresh_token_hash

    response = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 200
    user = db_session.get(User, teacher.id)
    assert user is not None
    assert user.must_change_password is False
    db_session.refresh(sessions[0])
    db_session.refresh(current_session)
    assert sessions[0].revoked_at is not None
    assert current_session.revoked_at is None
    assert current_session.refresh_token_hash != old_current_hash

    client.cookies.clear()
    relogin = client.post(
        "/api/v1/auth/login", json={"username": teacher.username, "password": NEW_PASSWORD}
    )
    assert relogin.status_code == 200


def test_logout_is_idempotent_and_clears_cookie(client: TestClient, teacher: Account) -> None:
    login(client, teacher)

    first = client.post("/api/v1/auth/logout")
    second = client.post("/api/v1/auth/logout")

    assert first.status_code == 204
    assert second.status_code == 204
    assert "refresh_token" not in client.cookies
    assert "Max-Age=0" in first.headers["set-cookie"]
