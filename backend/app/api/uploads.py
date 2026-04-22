"""파일 업로드 API 라우터 — 이미지 업로드 및 매직 바이트 검증."""

import os
import uuid

import anyio
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()

# 매직 바이트 → 확장자 매핑 (확장자 위변조 방지)
MAGIC_SIGNATURES = {
    b"\xff\xd8\xff": "jpg",
    b"\x89PNG": "png",
    b"GIF8": "gif",
}


def _detect_extension(header: bytes) -> str | None:
    """파일 헤더 매직 바이트로 실제 이미지 포맷 판별.

    Args:
        header: 파일의 처음 12바이트 헤더.

    Returns:
        감지된 확장자 문자열("jpg", "png", "gif", "webp"), 또는 미지원 포맷이면 None.
    """
    for magic, ext in MAGIC_SIGNATURES.items():
        if header.startswith(magic):
            return ext
    # WebP: RIFF....WEBP 패턴
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return None


@router.post("/image")
async def upload_image(
    file: UploadFile,
    user: User = Depends(get_current_user),
):
    """이미지 파일 업로드. 반환된 URL을 배경 이미지 등에 사용."""
    # 1. MIME 타입 검증
    if file.content_type not in settings.allowed_image_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"허용되지 않는 파일 형식입니다. 허용: {', '.join(settings.allowed_image_types)}",
        )

    # 2. 파일 읽기 + 크기 검증
    content = await file.read()
    if len(content) > settings.max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"파일 크기가 {settings.max_upload_size // (1024 * 1024)}MB를 초과합니다.",
        )

    if len(content) < 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 이미지 파일입니다.",
        )

    # 3. 매직 바이트 검증
    ext = _detect_extension(content[:12])
    if ext is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="파일 내용이 이미지 형식과 일치하지 않습니다.",
        )

    # 4. 저장
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = settings.upload_dir
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, filename)
    await anyio.Path(filepath).write_bytes(content)

    return {"url": f"/uploads/{filename}"}
