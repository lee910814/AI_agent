import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import PasswordChange, UserCreate, UserLogin, UserUpdate


class UserService:
    """사용자 계정 관리 서비스.

    사용자 생성, 인증, 프로필 수정, 비밀번호 변경 등 사용자 도메인 비즈니스 로직을 담당한다.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, data: UserCreate) -> User:
        """새 사용자를 생성하여 DB에 저장한다.

        이메일은 SHA-256 해시로 저장한다 (개인정보 최소화).
        login_id/nickname 중복은 DB unique 제약으로 방어한다.

        Args:
            data: 사용자 생성 입력 데이터 (UserCreate 스키마).

        Returns:
            DB에 저장된 User 인스턴스.

        Raises:
            IntegrityError: login_id 또는 nickname이 이미 존재하는 경우.
        """
        email_hash = None
        if data.email:
            email_hash = hashlib.sha256(data.email.lower().encode()).hexdigest()

        user = User(
            login_id=data.login_id,
            nickname=data.nickname,
            email_hash=email_hash,
            password_hash=get_password_hash(data.password),
            role="user",
            age_group="unverified",
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate(self, data: UserLogin) -> User | None:
        """login_id와 비밀번호를 검증하여 사용자를 반환한다.

        Args:
            data: 로그인 입력 데이터 (UserLogin 스키마).

        Returns:
            인증 성공 시 User 인스턴스, 실패 시 None.
        """
        result = await self.db.execute(select(User).where(User.login_id == data.login_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        if not verify_password(data.password, user.password_hash):
            return None
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """UUID로 사용자를 조회한다.

        Args:
            user_id: 조회할 사용자 UUID.

        Returns:
            User 인스턴스, 존재하지 않으면 None.
        """
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def check_nickname_available(self, nickname: str) -> bool:
        """닉네임 사용 가능 여부를 확인한다.

        Args:
            nickname: 확인할 닉네임 문자열.

        Returns:
            사용 가능하면 True, 이미 사용 중이면 False.
        """
        result = await self.db.execute(select(User).where(User.nickname == nickname))
        return result.scalar_one_or_none() is None

    async def check_login_id_available(self, login_id: str) -> bool:
        """로그인 아이디 사용 가능 여부를 확인한다.

        Args:
            login_id: 확인할 로그인 아이디 문자열.

        Returns:
            사용 가능하면 True, 이미 사용 중이면 False.
        """
        result = await self.db.execute(select(User).where(User.login_id == login_id))
        return result.scalar_one_or_none() is None

    async def update_profile(self, user: User, data: UserUpdate) -> User:
        """사용자 프로필 정보를 수정한다.

        nickname 중복은 DB unique 제약으로 방어한다.

        Args:
            user: 수정할 User 인스턴스.
            data: 수정할 프로필 데이터 (UserUpdate 스키마). None인 필드는 변경하지 않는다.

        Returns:
            수정된 User 인스턴스.

        Raises:
            IntegrityError: nickname이 이미 다른 사용자에 의해 사용 중인 경우.
        """
        if data.nickname is not None:
            user.nickname = data.nickname
        if data.preferred_themes is not None:
            user.preferred_themes = data.preferred_themes
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def change_password(self, user: User, data: PasswordChange) -> bool:
        """현재 비밀번호를 검증하고 새 비밀번호로 변경한다.

        Args:
            user: 비밀번호를 변경할 User 인스턴스.
            data: 현재/새 비밀번호 데이터 (PasswordChange 스키마).

        Returns:
            변경 성공 시 True, 현재 비밀번호 불일치 시 False.
        """
        if not verify_password(data.current_password, user.password_hash):
            return False
        user.password_hash = get_password_hash(data.new_password)
        await self.db.commit()
        return True
