"""ORM 모델 패키지.

SQLAlchemy 모델 클래스를 한 곳에서 노출해 다른 모듈이 편리하게 임포트할 수 있도록 한다.
"""

# 커뮤니티 피드 모델
from app.models.community_post import CommunityPost, CommunityPostLike
from app.models.user_community_stats import UserCommunityStats

# 에이전트 관련 모델
from app.models.debate_agent import DebateAgent, DebateAgentSeasonStats, DebateAgentVersion
from app.models.debate_agent_template import DebateAgentTemplate  # 관리자 제공 에이전트 템플릿
from app.models.debate_match import DebateMatch, DebateMatchParticipant, DebateMatchPrediction, DebateMatchQueue  # 매치·참가자·예측투표·큐
from app.models.debate_promotion_series import DebatePromotionSeries  # 승급전/강등전 시리즈
from app.models.debate_season import DebateSeason, DebateSeasonResult  # 시즌·시즌 결과
from app.models.debate_topic import DebateTopic  # 토론 주제
from app.models.debate_tournament import DebateTournament, DebateTournamentEntry  # 토너먼트·참가 에이전트
from app.models.debate_turn_log import DebateTurnLog  # 턴별 발언 기록
from app.models.llm_model import LLMModel  # 등록된 LLM 모델
from app.models.token_usage_log import TokenUsageLog  # LLM 토큰·비용 기록
from app.models.user import User  # 사용자 계정
from app.models.user_follow import UserFollow  # 팔로우 관계
from app.models.user_notification import UserNotification  # 사용자 알림

__all__ = [
    "User",
    "LLMModel",
    "TokenUsageLog",
    "DebateAgent",
    "DebateAgentSeasonStats",
    "DebateAgentTemplate",
    "DebateAgentVersion",
    "DebateMatch",
    "DebateMatchParticipant",
    "DebateMatchPrediction",
    "DebateMatchQueue",
    "DebatePromotionSeries",
    "DebateSeason",
    "DebateSeasonResult",
    "DebateTopic",
    "DebateTournament",
    "DebateTournamentEntry",
    "DebateTurnLog",
    "UserFollow",
    "UserNotification",
    "CommunityPost",
    "CommunityPostLike",
    "UserCommunityStats",
]
