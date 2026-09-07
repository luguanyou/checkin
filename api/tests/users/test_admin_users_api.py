from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from attendance_api import cli
from attendance_api.models import AuditLog, LoginSession, User
from attendance_api.security.passwords import verify_password

ADMIN_PASSWORD = "admin-password-123"
TEACHER_PASSWORD = "teacher-password-123"


@dataclass
class AdminAccount:
    id: str
    token: str


@pytest.fixture
def admin_account(client: TestClient, db_session: Session) -> AdminAccount:
    admin = User(
        username="admin",
        password_hash=PasswordHasher().hash(ADMIN_PASSWORD),
        display_name="管理员",
        role="ADMIN",
        status="ACTIVE",
        must_change_password=False,
    )
    db_session.add(admin)
    db_session.commit()
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200
    return AdminAccount(id=admin.id, token=response.json()["access_token"])


@pytest.fixture
def admin_client(client: TestClient, admin_account: AdminAccount) -> TestClient:
    client.headers.update({"Authorization": f"Bearer {admin_account.token}"})
    return client


def create_teacher(admin_client: TestClient, username: str = "teacher01") -> dict[str, object]:
    response = admin_client.post(
        "/api/v1/admin/users",
        json={
            "username": username,
            "display_name": "王老师",
            "temporary_password": TEACHER_PASSWORD,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_admin_creates_teacher_without_echoing_password(
    admin_client: TestClient, db_session: Session
) -> None:
    response = admin_client.post(
        "/api/v1/admin/users",
        json={
            "username": "Teacher01 ",
            "display_name": " 王老师 ",
            "temporary_password": TEACHER_PASSWORD,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["username"] == "teacher01"
    assert payload["display_name"] == "王老师"
    assert payload["role"] == "TEACHER"
    assert payload["must_change_password"] is True
    assert "password_hash" not in payload
    audit = db_session.scalar(select(AuditLog).where(AuditLog.action == "USER_CREATED"))
    assert audit is not None
    assert audit.after_value is not None
    assert not {"password", "password_hash", "temporary_password"}.intersection(audit.after_value)


def test_teacher_cannot_use_admin_routes(client: TestClient, db_session: Session) -> None:
    teacher = User(
        username="teacher",
        password_hash=PasswordHasher().hash(TEACHER_PASSWORD),
        display_name="教师",
        role="TEACHER",
        status="ACTIVE",
        must_change_password=False,
    )
    db_session.add(teacher)
    db_session.commit()
    login = client.post(
        "/api/v1/auth/login", json={"username": "teacher", "password": TEACHER_PASSWORD}
    )

    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "RESOURCE_FORBIDDEN"


def test_normalized_duplicate_username_is_rejected(admin_client: TestClient) -> None:
    create_teacher(admin_client)

    response = admin_client.post(
        "/api/v1/admin/users",
        json={
            "username": " TEACHER01",
            "display_name": "另一位老师",
            "temporary_password": TEACHER_PASSWORD,
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "DUPLICATE_RESOURCE"


def test_disabling_user_revokes_all_sessions(
    admin_client: TestClient,
    client: TestClient,
    db_session: Session,
    admin_account: AdminAccount,
) -> None:
    teacher = create_teacher(admin_client)
    client.headers.pop("Authorization")
    for _ in range(2):
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "teacher01", "password": TEACHER_PASSWORD},
        )
        assert login.status_code == 200

    client.headers.update({"Authorization": f"Bearer {admin_account.token}"})
    response = client.patch(
        f"/api/v1/admin/users/{teacher['id']}/status", json={"status": "DISABLED"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "DISABLED"
    sessions = list(
        db_session.scalars(select(LoginSession).where(LoginSession.user_id == teacher["id"]))
    )
    assert len(sessions) == 2
    assert all(item.revoked_at is not None for item in sessions)


def test_reset_password_revokes_sessions_and_requires_change(
    admin_client: TestClient,
    client: TestClient,
    db_session: Session,
    admin_account: AdminAccount,
) -> None:
    teacher = create_teacher(admin_client)
    client.headers.pop("Authorization")
    login = client.post(
        "/api/v1/auth/login", json={"username": "teacher01", "password": TEACHER_PASSWORD}
    )
    assert login.status_code == 200
    client.headers.update({"Authorization": f"Bearer {admin_account.token}"})

    response = client.post(
        f"/api/v1/admin/users/{teacher['id']}/reset-password",
        json={"temporary_password": "replacement-password"},
    )

    assert response.status_code == 204
    user = db_session.get(User, teacher["id"])
    assert user is not None
    assert user.must_change_password is True
    assert verify_password(user.password_hash, "replacement-password")
    session = db_session.scalar(select(LoginSession).where(LoginSession.user_id == teacher["id"]))
    assert session is not None and session.revoked_at is not None


def test_admin_cannot_disable_self(admin_client: TestClient, admin_account: AdminAccount) -> None:
    response = admin_client.patch(
        f"/api/v1/admin/users/{admin_account.id}/status", json={"status": "DISABLED"}
    )

    assert response.status_code == 403
    assert response.json()["code"] == "SELF_ADMIN_ACTION_FORBIDDEN"


def test_user_list_supports_role_status_query_and_pagination(
    admin_client: TestClient, db_session: Session
) -> None:
    for index in range(3):
        db_session.add(
            User(
                username=f"math{index}",
                password_hash=PasswordHasher().hash(TEACHER_PASSWORD),
                display_name=f"数学教师 {index}",
                role="TEACHER",
                status="ACTIVE" if index < 2 else "DISABLED",
                must_change_password=True,
            )
        )
    db_session.commit()

    response = admin_client.get(
        "/api/v1/admin/users",
        params={"role": "TEACHER", "status": "ACTIVE", "q": "数学", "page_size": 1},
    )

    assert response.status_code == 200
    assert response.json()["page"] == 1
    assert response.json()["page_size"] == 1
    assert response.json()["total"] == 2
    assert len(response.json()["items"]) == 1


def test_cli_create_admin_stores_only_argon2_hash(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    passwords = iter([ADMIN_PASSWORD, ADMIN_PASSWORD])

    @contextmanager
    def session_factory() -> Iterator[Session]:
        yield db_session

    monkeypatch.setattr(cli, "SessionFactory", session_factory)
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: next(passwords))

    result = cli.main(["create-admin", "--username", "RootAdmin", "--display-name", "主管理员"])

    assert result == 0
    admin = db_session.scalar(select(User).where(User.username == "rootadmin"))
    assert admin is not None
    assert admin.password_hash != ADMIN_PASSWORD
    assert admin.password_hash.startswith("$argon2id$")
    assert verify_password(admin.password_hash, ADMIN_PASSWORD)
