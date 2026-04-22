"""애플리케이션 설정 모듈.

환경 변수와 .env 파일을 통해 모든 설정값을 관리한다.
BaseSettings를 상속하므로 환경 변수가 .env 파일보다 우선 적용된다.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """전체 애플리케이션 설정.

    pydantic-settings BaseSettings를 통해 .env 파일과 환경 변수에서
    설정값을 자동으로 로드한다. 환경 변수가 .env 파일보다 우선 적용된다.

    Attributes:
        app_env: 실행 환경 식별자 (development | production).
        debug: FastAPI 디버그 모드 활성화 여부.
        database_url: 비동기 ORM용 asyncpg 데이터베이스 URL.
        database_sync_url: Alembic 마이그레이션용 동기 psycopg URL.
        redis_url: Redis 연결 URL.
        secret_key: JWT 서명 키. 프로덕션에서는 반드시 강한 랜덤값으로 설정.
        access_token_expire_minutes: 액세스 토큰 만료 시간 (기본 7일).
        encryption_key: API 키 암호화용 Fernet 키. 미설정 시 secret_key에서 파생.
        cors_origins: CORS 허용 출처 목록.
        runpod_api_key: RunPod Serverless API 키.
        runpod_endpoint_id: RunPod 기본 엔드포인트 ID.
        openai_api_key: OpenAI 플랫폼 API 키.
        anthropic_api_key: Anthropic 플랫폼 API 키.
        google_api_key: Google AI 플랫폼 API 키.
        langfuse_public_key: Langfuse LLM 추적 퍼블릭 키.
        langfuse_secret_key: Langfuse LLM 추적 시크릿 키.
        langfuse_host: Langfuse 서버 주소.
        sentry_dsn: Sentry 에러 수집 DSN. 빈 문자열이면 비활성.
        credit_system_enabled: 크레딧 차감 기능 전체 ON/OFF.
        upload_dir: 업로드 파일 저장 디렉토리.
        max_upload_size: 단일 파일 최대 크기 (바이트).
        allowed_image_types: 허용 이미지 MIME 타입 목록.
        debate_enabled: 토론 기능 전체 ON/OFF.
    """
    app_env: str = "development"        # 실행 환경 (development | production)
    debug: bool = True                  # FastAPI 디버그 모드

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://chatbot:chatbot@localhost:5432/chatbot"   # 비동기 ORM용
    database_sync_url: str = "postgresql+psycopg://chatbot:chatbot@localhost:5432/chatbot"  # Alembic용
    redis_url: str = "redis://localhost:6379/0"

    # ── Auth ──────────────────────────────────────────────────────────────────
    secret_key: str = ""                        # JWT 서명 키 — .env에서 반드시 설정
    access_token_expire_minutes: int = 10080    # 액세스 토큰 만료 (7일, 프로토타입 편의)

    # JWT 서명 키와 분리 — SECRET_KEY 교체가 암호화된 API 키에 영향 없도록
    # 이미 암호화된 데이터가 있으면 ENCRYPTION_KEY 변경 전 전체 API 키 재암호화 필요
    encryption_key: str = ""            # API 키 암호화 키 — 미설정 시 secret_key에서 파생

    cors_origins: list[str] = ["http://localhost:3000"]     # CORS 허용 출처

    # ── External APIs ─────────────────────────────────────────────────────────
    runpod_api_key: str = ""            # RunPod Serverless API 키
    runpod_endpoint_id: str = ""        # RunPod 기본 엔드포인트 ID
    openai_api_key: str = ""            # OpenAI 플랫폼 키 (에이전트 LLM 호출용)
    anthropic_api_key: str = ""         # Anthropic 플랫폼 키
    google_api_key: str = ""            # Google AI 플랫폼 키

    # ── Observability ─────────────────────────────────────────────────────────
    langfuse_public_key: str = ""       # Langfuse LLM 추적 퍼블릭 키
    langfuse_secret_key: str = ""       # Langfuse LLM 추적 시크릿 키
    langfuse_host: str = "http://localhost:3001"     # Langfuse 서버 주소
    sentry_dsn: str = ""                # Sentry 에러 수집 DSN — 빈 문자열이면 비활성

    # ── Credits ───────────────────────────────────────────────────────────────
    credit_system_enabled: bool = True  # 크레딧 차감 기능 전체 ON/OFF

    # ── Uploads ───────────────────────────────────────────────────────────────
    upload_dir: str = "uploads"         # 업로드 파일 저장 디렉토리
    max_upload_size: int = 5_242_880    # 단일 파일 최대 크기 (5 MB)
    allowed_image_types: list[str] = [  # 허용 이미지 MIME 타입
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    ]

    # ── Debate Platform ───────────────────────────────────────────────────────
    debate_enabled: bool = False        # 토론 기능 전체 ON/OFF (비활성 시 403 반환)

    # ELO 레이팅
    debate_elo_k_factor: int = 32                   # ELO K 팩터 — 클수록 변동 폭 큼
    debate_elo_score_diff_scale: int = 100          # 판정 점수차 정규화 기준 (0~100 범위)
    debate_elo_score_diff_weight: float = 1.0       # 점수차 배수 가중치 (0=미사용, 1=최대 2배)
    debate_elo_score_mult_max: float = 2.0          # 점수차 ELO 배수 상한
    debate_elo_forfeit_score_diff: int = 100        # 몰수패 시 점수차 (최대 패널티)

    # 매치 타이밍
    debate_turn_timeout_seconds: int = 60           # 에이전트 발언 생성 최대 대기 시간
    debate_turn_delay_seconds: float = 1.5          # 턴 간 인위적 딜레이 — 관전 UX 개선용
    debate_queue_timeout_seconds: int = 120         # 매칭 큐 최대 대기 시간
    debate_pending_timeout_seconds: int = 600        # pending/waiting_agent 상태 자동 error 처리
    debate_inprogress_timeout_seconds: int = 3600   # in_progress 상태 자동 error 처리 (최대 1시간)
    debate_auto_match_check_interval: int = 10      # 자동 매칭 루프 실행 주기 (초)
    debate_agent_connect_timeout: int = 30          # 로컬 에이전트 WebSocket 접속 대기 (회당)
    debate_agent_connect_timeout_tool: int = 120    # 툴 사용 모드 에이전트 접속 대기 (회당, 외부 데이터 페치 시간 고려)
    debate_agent_connect_retries: int = 3           # 로컬 에이전트 접속 재시도 횟수
    debate_ws_heartbeat_interval: int = 15          # WebSocket 핑 전송 간격 (초)

    # 제한
    debate_daily_topic_limit: int = 5               # 사용자 일일 토픽 등록 최대 건수
    debate_credit_cost: int = 5                     # 매치 참가 시 차감 크레딧
    debate_credit_buffer_ratio: float = 1.5         # 크레딧 선차감 버퍼 비율 (예상 토큰 × 배수)

    # LLM 모델
    debate_orchestrator_model: str = "gpt-4o"       # 기본 오케스트레이터 모델 (폴백용)
    debate_review_model: str = "gpt-4o-mini"           # 턴 검토 모델 — 경량·저비용
    debate_judge_model: str = "gpt-4.1"             # 최종 판정 모델 — 고정밀
    debate_summary_model: str = "gpt-4o-mini"       # 요약 리포트 생성 모델

    # 턴 검토
    debate_turn_review_enabled: bool = True         # 턴 검토 기능 ON/OFF
    debate_turn_review_timeout: int = 25            # 검토 LLM 응답 최대 대기 시간 (초, gpt-5-nano 추론 포함)
    debate_turn_review_model: str = ""              # 검토 모델 오버라이드 (optimized=False 롤백 경로 전용) — 빈 문자열이면 debate_review_model 사용
    debate_forfeit_on_severe_streak: int = 3        # 연속 severe 위반 이 수에 도달 시 부전패 (0이면 비활성)

    # 최적화
    debate_orchestrator_optimized: bool = True      # 최적화 오케스트레이터 활성화 (모델 분리 + 병렬 실행)
    debate_turn_max_retries: int = 2                # 발언 실패(타임아웃·에러) 시 재시도 횟수
    debate_series_max_draws: int = 3                # 시리즈 무승부 최대 허용 횟수 (초과 시 자동 만료)
    debate_orchestration_mode: str = "balanced"     # 오케스트레이션 모드 라벨 (speed|balanced|quality)
    debate_trace_events_enabled: bool = True        # SSE payload trace_id/orchestration_mode 부착 여부

    # 판정 규칙
    debate_draw_threshold: int = 1                  # 승패 판정 최소 점수차 (미만이면 무승부)
    debate_review_max_tokens: int = 2000            # 턴 검토 LLM max_tokens (gpt-5-nano reasoning 포함)
    debate_judge_timeout_seconds: int = 120         # 판정 LLM 전체 응답 최대 대기 시간 (stage1+stage2 합산)
    debate_judge_max_tokens: int = 1024             # 최종 판정 LLM max_tokens
    debate_judge_temperature: float = 0.2           # 최종 판정 LLM temperature
    debate_prediction_cutoff_turns: int = 2         # 예측투표 가능 최대 턴 수 (초과 시 마감)
    debate_ready_countdown_seconds: int = 10        # 첫 준비 완료 후 자동매치 카운트다운 (초)
    debate_review_model_candidate: str = ""         # 검토 모델 실험군 후보 (빈 문자열이면 비활성)
    debate_judge_model_candidate: str = ""          # 판정 모델 실험군 후보 (빈 문자열이면 비활성)
    debate_model_rollout_ratio: float = 0.0         # 실험군 비율(0.0~1.0), match_id 해시 기반 결정

    # 시즌 보상 크레딧
    debate_season_reward_top3: list[int] = [500, 300, 200]  # 1~3위 보상 (인덱스=순위-1)
    debate_season_reward_rank4_10: int = 50         # 4~10위 보상

    # 에이전트 제약
    agent_name_change_cooldown_days: int = 7        # 에이전트 이름 변경 쿨다운 (일)

    # 요약 리포트
    debate_summary_enabled: bool = True             # 매치 종료 후 요약 리포트 자동 생성

    # Tool-Use (LLM Function Calling)
    debate_tool_use_enabled: bool = True      # API 에이전트 tool-use(web_search) 전체 ON/OFF

    # 근거 검색 (DuckDuckGo)
    debate_evidence_search_enabled: bool = True     # 턴 발언 후 웹 근거 자동 검색
    debate_evidence_search_timeout: int = 20        # 근거 검색 전체 타임아웃 (초)
    debate_evidence_search_max_results: int = 5     # 키워드당 DuckDuckGo 최대 결과 수
    debate_evidence_keyword_model: str = "gpt-4o-mini"  # 키워드 추출 LLM 모델
    debate_evidence_synthesis_model: str = "gpt-4o-mini"    # evidence 합성 LLM 모델
    debate_evidence_synthesis_max_tokens: int = 200          # evidence 합성 최대 토큰

    # 커뮤니티 피드
    community_post_enabled: bool = True             # 매치 완료 후 에이전트 포스트 자동 생성
    community_post_model: str = "gpt-4o-mini"       # 포스트 생성 LLM 모델

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_auth: int = 20           # 인증 엔드포인트 최대 요청 수
    rate_limit_api: int = 300           # 일반 API 최대 요청 수 (페이지 로드 시 5~10개 동시 요청 고려)
    rate_limit_debate: int = 120        # 토론 엔드포인트 최대 요청 수 (SSE 포함)
    rate_limit_admin: int = 120         # 관리자 API 최대 요청 수
    rate_limit_window: int = 60         # 요청 수 집계 윈도우 (초)
    rate_limit_enabled: bool = True     # Rate Limiting 전체 ON/OFF

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()

# 프로덕션 안전 검증: 약한 시크릿 키로 기동 방지
if not settings.secret_key or settings.secret_key == "change-me-in-production":
    if settings.app_env != "development":
        raise RuntimeError(
            "SECRET_KEY must be set to a strong random value in production. "
            "Use: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    else:
        import warnings

        warnings.warn(
            "SECRET_KEY is not set. Using empty key for development only.",
            stacklevel=1,
        )
