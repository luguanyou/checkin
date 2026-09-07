import argparse
import getpass
from collections.abc import Sequence

from sqlalchemy import select

from attendance_api.db import SessionFactory
from attendance_api.models import User
from attendance_api.security.passwords import hash_password, password_meets_policy


def _create_admin(username: str, display_name: str, password: str) -> int:
    normalized_username = username.strip().lower()
    normalized_display_name = display_name.strip()
    if not normalized_username or not normalized_display_name:
        print("用户名和显示名称不能为空")
        return 1
    if not password_meets_policy(password):
        print("密码长度必须为 12 至 128 个字符")
        return 1

    with SessionFactory() as db:
        if db.scalar(select(User.id).where(User.username == normalized_username)) is not None:
            print("用户名已存在")
            return 1
        db.add(
            User(
                username=normalized_username,
                password_hash=hash_password(password),
                display_name=normalized_display_name,
                role="ADMIN",
                status="ACTIVE",
                must_change_password=False,
            )
        )
        db.commit()
    print(f"管理员 {normalized_username} 已创建")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="attendance-api")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_admin = subparsers.add_parser("create-admin")
    create_admin.add_argument("--username", required=True)
    create_admin.add_argument("--display-name", required=True)
    args = parser.parse_args(argv)

    if args.command == "create-admin":
        password = getpass.getpass("密码：")
        confirmation = getpass.getpass("再次输入密码：")
        if password != confirmation:
            print("两次输入的密码不一致")
            return 1
        return _create_admin(args.username, args.display_name, password)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
