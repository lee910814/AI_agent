#!/usr/bin/env python3
"""테스트/개발 환경 admin 계정 자동 생성.

login_id=admin / password=admin123 (superadmin)
이미 존재하면 스킵.

Usage:
  cd backend && python ../scripts/create_test_admin.py [--env-file .env]
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── --env-file 파싱 ────────────────────────────────────────────
_args = sys.argv[1:]
_env_file = ".env"
for i, a in enumerate(_args):
    if a == "--env-file" and i + 1 < len(_args):
        _env_file = _args[i + 1]

_env_path = Path(_env_file)
if _env_path.exists():
    with open(_env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

# ── DB 연결 ────────────────────────────────────────────────────
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_password_hash
from app.models.user import User

_engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
_Session = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

LOGIN_ID = "admin"
PASSWORD = "admin123"
NICKNAME = "admin"


async def _main() -> None:
    async with _Session() as db:
        existing = (
            await db.execute(select(User).where(User.login_id == LOGIN_ID))
        ).scalar_one_or_none()

        if existing:
            print(f"[SKIP] admin 계정 이미 존재 (id={existing.id})")
            return

        db.add(
            User(
                id=uuid.uuid4(),
                login_id=LOGIN_ID,
                nickname=NICKNAME,
                password_hash=get_password_hash(PASSWORD),
                role="superadmin",
                age_group="adult_verified",
                adult_verified_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
        print(f"[OK] admin 계정 생성 완료 — login_id={LOGIN_ID} / pw={PASSWORD}")


asyncio.run(_main())
