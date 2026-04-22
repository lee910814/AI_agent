class AppError(Exception):
    """도메인 에러 기반 클래스. FastAPI 전역 핸들러에서 HTTP 응답으로 변환된다."""

    status_code: int = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    """리소스가 존재하지 않음 (HTTP 404)."""

    status_code = 404


class ForbiddenError(AppError):
    """접근 권한 없음 (HTTP 403)."""

    status_code = 403


class ConflictError(AppError):
    """리소스 충돌 (HTTP 409)."""

    status_code = 409


class UnprocessableError(AppError):
    """입력값 검증 실패 (HTTP 422)."""

    status_code = 422


class QueueConflictError(ValueError):
    """큐 충돌 에러. existing_topic_id 포함."""

    def __init__(self, message: str, existing_topic_id: str):
        super().__init__(message)
        self.existing_topic_id = existing_topic_id
