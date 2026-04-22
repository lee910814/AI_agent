"""에러 핸들링 계층 단위 테스트."""
import pytest
from app.core.exceptions import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    QueueConflictError,
    UnprocessableError,
)


class TestAppErrorHierarchy:
    def test_not_found_is_app_error(self):
        err = NotFoundError("리소스를 찾을 수 없습니다")
        assert isinstance(err, AppError)
        assert err.status_code == 404
        assert err.message == "리소스를 찾을 수 없습니다"

    def test_forbidden_status_code(self):
        err = ForbiddenError("접근 권한이 없습니다")
        assert err.status_code == 403

    def test_conflict_status_code(self):
        err = ConflictError("이미 존재합니다")
        assert err.status_code == 409

    def test_unprocessable_status_code(self):
        err = UnprocessableError("입력값이 잘못되었습니다")
        assert err.status_code == 422

    def test_app_error_default_status(self):
        err = AppError("서버 오류")
        assert err.status_code == 500

    def test_queue_conflict_backward_compatibility(self):
        """기존 QueueConflictError는 영향받지 않아야 한다."""
        err = QueueConflictError("이미 대기 중", "topic-123")
        assert err.existing_topic_id == "topic-123"
        assert isinstance(err, ValueError)

    def test_app_error_str_representation(self):
        err = NotFoundError("에이전트를 찾을 수 없습니다")
        assert str(err) == "에이전트를 찾을 수 없습니다"
