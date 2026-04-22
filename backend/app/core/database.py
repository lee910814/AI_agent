"""SQLAlchemy 비동기 데이터베이스 엔진 및 세션 설정.

PostgreSQL과의 비동기 연결 풀을 관리하고, ORM 기본 클래스와
FastAPI Depends에서 사용할 세션 팩토리를 제공한다.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings  # 데이터베이스 URL 및 풀 설정 로드

engine = create_async_engine(
    settings.database_url,
    echo=False,  # 프로덕션에서 SQL 로그 비활성화 (성능)
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # 연결 유효성 사전 확인 (끊어진 커넥션 재연결)
    pool_recycle=1800,   # 30분마다 커넥션 재생성 (장기 연결 누수 방지)
    pool_timeout=5,      # 풀 고갈 시 5초 내 실패 반환 — 기본 30초 대기로 인한 행(hang) 방지
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """모든 SQLAlchemy ORM 모델의 기본 클래스.

    모든 모델은 이 클래스를 상속받아 테이블 매핑을 정의한다.
    Alembic 자동 마이그레이션 감지를 위해 단일 Base 인스턴스를 공유한다.
    """


async def get_db() -> AsyncSession:
    """FastAPI Depends에서 사용할 비동기 DB 세션 제공자.

    컨텍스트 매니저로 세션을 열고, 요청 처리가 끝나면 자동으로 닫는다.
    트랜잭션 커밋/롤백은 호출자의 책임이다.

    Yields:
        AsyncSession: 활성 SQLAlchemy 비동기 세션.
    """
    async with async_session() as session:
        yield session
