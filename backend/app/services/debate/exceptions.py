"""토론 도메인 전용 예외 클래스."""


class MatchVoidError(Exception):
    """에이전트 귀책 없는 기술적 장애로 매치를 무효화해야 할 때."""
    pass
