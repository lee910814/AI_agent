"""Observability 통합 모듈: Langfuse + Sentry + Prometheus.

LLM 추적(Langfuse), 에러 수집(Sentry), HTTP/LLM 메트릭(Prometheus)을
단일 모듈에서 초기화하고 관리한다. 각 외부 서비스가 미설정되거나
패키지가 없어도 graceful하게 비활성화된다.
"""

import logging
from contextvars import ContextVar

from app.core.config import settings  # Langfuse/Sentry/메트릭 설정 로드

logger = logging.getLogger(__name__)

# Langfuse 트레이스 컨텍스트를 request 단위로 전파
_current_trace: ContextVar = ContextVar("langfuse_trace", default=None)
_langfuse_client = None


def get_langfuse():
    """Langfuse 클라이언트 싱글턴을 반환한다.

    최초 호출 시 클라이언트를 초기화하고 이후 캐시된 인스턴스를 반환한다.
    키가 미설정되거나 langfuse 패키지가 없으면 None을 반환한다.

    Returns:
        초기화된 Langfuse 인스턴스, 비활성화되어 있으면 None.
    """
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.info("Langfuse keys not configured, tracing disabled.")
        return None

    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        logger.info("Langfuse client initialized (host=%s)", settings.langfuse_host)
        return _langfuse_client
    except Exception:
        logger.warning("Failed to initialize Langfuse", exc_info=True)
        return None


def create_trace(name: str, user_id: str | None = None, session_id: str | None = None, metadata: dict | None = None):
    """새 Langfuse 트레이스를 생성하고 ContextVar에 저장한다.

    요청 단위로 트레이스를 생성하여 해당 요청 내 모든 LLM 호출을 그룹화한다.
    Langfuse가 비활성화된 경우 None을 반환하고 추적을 건너뛴다.

    Args:
        name: 트레이스 식별 이름 (예: "debate_turn", "judge").
        user_id: 트레이스에 연결할 사용자 ID.
        session_id: 트레이스에 연결할 세션 ID.
        metadata: 추가 메타데이터 딕셔너리.

    Returns:
        생성된 Langfuse 트레이스 객체, 비활성화되어 있으면 None.
    """
    langfuse = get_langfuse()
    if langfuse is None:
        return None

    trace = langfuse.trace(
        name=name,
        user_id=user_id,
        session_id=session_id,
        metadata=metadata or {},
    )
    _current_trace.set(trace)
    return trace


def get_current_trace():
    """현재 요청의 Langfuse 트레이스를 반환한다.

    ContextVar에서 현재 asyncio 컨텍스트의 트레이스를 가져온다.
    트레이스가 생성되지 않았거나 Langfuse가 비활성화된 경우 None을 반환한다.

    Returns:
        현재 요청의 Langfuse 트레이스 객체, 없으면 None.
    """
    return _current_trace.get(None)


def create_span(name: str, **kwargs):
    """현재 트레이스에 스팬을 추가한다.

    현재 트레이스가 없으면 아무 작업도 하지 않는다.

    Args:
        name: 스팬 이름.
        **kwargs: Langfuse span() 메서드에 전달할 추가 인자.

    Returns:
        생성된 Langfuse 스팬 객체, 트레이스가 없으면 None.
    """
    trace = get_current_trace()
    if trace is None:
        return None
    return trace.span(name=name, **kwargs)


def create_generation(name: str, model: str, input_messages: list[dict], **kwargs):
    """LLM generation 이벤트를 현재 트레이스에 기록한다.

    InferenceClient에서 각 LLM 호출마다 호출하여 모델·입력·출력 토큰을 추적한다.

    Args:
        name: generation 이름 (예: "turn_review", "judge").
        model: 사용된 LLM 모델 ID.
        input_messages: LLM에 전달된 메시지 목록.
        **kwargs: Langfuse generation() 메서드에 전달할 추가 인자
            (usage, output 등).

    Returns:
        생성된 Langfuse generation 객체, 트레이스가 없으면 None.
    """
    trace = get_current_trace()
    if trace is None:
        return None
    return trace.generation(
        name=name,
        model=model,
        input=input_messages,
        **kwargs,
    )


def flush_langfuse():
    """Langfuse 이벤트 버퍼를 즉시 플러시한다.

    앱 종료 또는 배치 처리 완료 시 버퍼에 남은 이벤트를 강제 전송한다.
    Langfuse가 비활성화된 경우 아무 작업도 하지 않는다.
    """
    langfuse = get_langfuse()
    if langfuse:
        langfuse.flush()


# ── Sentry ──

_sentry_initialized = False


def init_sentry():
    """Sentry SDK를 초기화한다.

    DSN이 설정된 경우에만 초기화하며, 중복 초기화를 방지한다.
    FastAPI와 SQLAlchemy 인테그레이션을 포함하고, 프로덕션에서는
    샘플링 비율을 10%로 제한하여 비용을 절감한다.

    프로덕션: traces_sample_rate=0.1, 개발: 1.0 (모든 트레이스 수집).
    """
    global _sentry_initialized
    if _sentry_initialized:
        return

    if not settings.sentry_dsn:
        logger.info("Sentry DSN not configured, error tracking disabled.")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env,
            traces_sample_rate=0.1 if settings.app_env == "production" else 1.0,
            profiles_sample_rate=0.1 if settings.app_env == "production" else 1.0,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
            send_default_pii=False,  # PII 최소화 원칙
        )
        _sentry_initialized = True
        logger.info("Sentry initialized (env=%s)", settings.app_env)
    except Exception:
        logger.warning("Failed to initialize Sentry", exc_info=True)


def set_sentry_user(user_id: str, role: str):
    """Sentry에 현재 요청의 사용자 컨텍스트를 설정한다.

    에러 발생 시 Sentry 이벤트에 사용자 정보가 포함되어 디버깅을 용이하게 한다.
    PII 최소화 원칙에 따라 ID와 역할만 전송하고 이메일 등은 제외한다.

    Args:
        user_id: 현재 인증된 사용자 ID.
        role: 사용자 역할 (user, admin, superadmin).
    """
    try:
        import sentry_sdk

        sentry_sdk.set_user({"id": user_id, "role": role})
    except Exception:
        pass


def capture_exception(exc: Exception, **context):
    """예외를 Sentry에 전송한다.

    추가 컨텍스트를 extra 필드로 첨부하여 디버깅 정보를 풍부하게 한다.
    Sentry가 비활성화되거나 전송 실패 시 로그로 남기고 예외를 삼킨다.

    Args:
        exc: 전송할 예외 인스턴스.
        **context: Sentry 이벤트의 extra 필드로 첨부할 추가 정보.
    """
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for key, value in context.items():
                scope.set_extra(key, value)
            sentry_sdk.capture_exception(exc)
    except Exception:
        logger.error("Failed to capture exception to Sentry", exc_info=True)


# ── Prometheus ──


def setup_prometheus(app):
    """FastAPI 앱에 Prometheus 메트릭 계측을 설정한다.

    prometheus-fastapi-instrumentator를 사용하여 HTTP 요청 지연/카운트를
    자동으로 수집하고 /metrics 엔드포인트로 노출한다.
    패키지가 없거나 설정 실패 시 로그를 남기고 계속 진행한다.

    Args:
        app: Prometheus 계측을 적용할 FastAPI 앱 인스턴스.
    """
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        instrumentator = Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            excluded_handlers=["/health", "/metrics"],
        )
        instrumentator.instrument(app).expose(app, endpoint="/metrics")

        logger.info("Prometheus instrumentation enabled at /metrics")
    except Exception:
        logger.warning("Failed to setup Prometheus", exc_info=True)


# ── 커스텀 Prometheus 메트릭 ──

_llm_request_duration = None
_llm_token_counter = None


def get_metrics():
    """커스텀 LLM Prometheus 메트릭 싱글턴을 반환한다.

    최초 호출 시 Histogram과 Counter를 생성하고 이후 캐시된 인스턴스를 반환한다.
    prometheus_client 패키지가 없거나 초기화 실패 시 (None, None)을 반환한다.

    Returns:
        (llm_request_duration_histogram, llm_tokens_total_counter) 튜플.
        메트릭 초기화 실패 시 (None, None).
    """
    global _llm_request_duration, _llm_token_counter

    if _llm_request_duration is not None:
        return _llm_request_duration, _llm_token_counter

    try:
        from prometheus_client import Counter, Histogram

        _llm_request_duration = Histogram(
            "llm_request_duration_seconds",
            "LLM API request duration",
            labelnames=["provider", "model"],
            buckets=[0.5, 1, 2, 5, 10, 30, 60],
        )

        _llm_token_counter = Counter(
            "llm_tokens_total",
            "Total LLM tokens processed",
            labelnames=["provider", "model", "direction"],  # direction: input/output
        )

        return _llm_request_duration, _llm_token_counter
    except Exception:
        return None, None


def record_llm_metrics(provider: str, model: str, duration: float, input_tokens: int, output_tokens: int):
    """LLM 호출에 대한 Prometheus 메트릭을 기록한다.

    InferenceClient에서 각 LLM 호출 완료 후 호출하여 지연 시간과
    입출력 토큰 수를 provider·model 레이블로 분류하여 기록한다.

    Args:
        provider: LLM 공급자 이름 (openai, anthropic, google, runpod).
        model: 사용된 모델 ID (예: "gpt-4.1", "claude-3-5-sonnet").
        duration: LLM API 호출 소요 시간 (초).
        input_tokens: 입력 토큰 수.
        output_tokens: 출력 토큰 수.
    """
    duration_hist, token_counter = get_metrics()
    if duration_hist:
        duration_hist.labels(provider=provider, model=model).observe(duration)
    if token_counter:
        token_counter.labels(provider=provider, model=model, direction="input").inc(input_tokens)
        token_counter.labels(provider=provider, model=model, direction="output").inc(output_tokens)
