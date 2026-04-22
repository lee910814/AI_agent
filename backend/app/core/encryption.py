"""BYOK API 키 암호화 유틸리티.

Fernet 대칭 암호화로 사용자 BYOK(Bring Your Own Key) API 키를 DB에 안전하게 저장한다.
암호화 키는 ENCRYPTION_KEY 환경 변수에서 직접 공급하거나,
미설정 시 SECRET_KEY를 SHA-256으로 파생하여 사용한다.

주의: 이미 암호화된 데이터가 있는 경우 ENCRYPTION_KEY 변경 전
전체 API 키를 복호화 후 재암호화해야 한다.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings  # 암호화 키 및 폴백 키 로드


def _derive_fernet_key() -> bytes:
    """설정에서 Fernet 호환 32바이트 키를 파생한다.

    ENCRYPTION_KEY가 설정되어 있으면 우선 사용하고, 없으면 SECRET_KEY를
    SHA-256으로 해싱하여 Fernet 키 형식(URL-safe base64)으로 변환한다.

    Returns:
        URL-safe base64 인코딩된 32바이트 Fernet 키.
    """
    # ENCRYPTION_KEY가 설정되면 우선 사용, 없으면 SECRET_KEY에서 파생 (하위 호환)
    source = settings.encryption_key if settings.encryption_key else settings.secret_key
    digest = hashlib.sha256(source.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_api_key(plaintext: str) -> str:
    """API 키를 Fernet으로 암호화하여 base64 문자열로 반환한다.

    Args:
        plaintext: 암호화할 평문 API 키.

    Returns:
        Fernet으로 암호화된 base64 인코딩 문자열.
    """
    f = Fernet(_derive_fernet_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    """암호화된 API 키를 복호화하여 평문으로 반환한다.

    Args:
        ciphertext: encrypt_api_key()가 반환한 암호화된 base64 문자열.

    Returns:
        복호화된 평문 API 키.

    Raises:
        ValueError: 키가 변경되었거나 데이터가 손상된 경우.
    """
    f = Fernet(_derive_fernet_key())
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt API key: invalid key or corrupted data") from exc
