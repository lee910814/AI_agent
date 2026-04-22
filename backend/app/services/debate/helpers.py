"""토론 엔진 순수 헬퍼 함수. 외부 I/O 없는 유틸리티 모음."""

import contextlib
import json
import logging
import re

from app.core.config import settings
from app.core.encryption import decrypt_api_key
from app.models.debate_agent import DebateAgent
from app.models.debate_topic import DebateTopic

logger = logging.getLogger(__name__)


# 에이전트 LLM에 주입하는 응답 형식 지시문 — _execute_turn() 내 user 메시지 끝에 추가됨
# 에이전트가 임의 텍스트 대신 구조화 JSON을 반환하도록 강제.
# validate_response_schema()가 이 형식을 검증하며, 불일치 시 파싱 실패로 처리.

RESPONSE_SCHEMA_INSTRUCTION = """⚠️ 중요: 반드시 한국어로만 답변하세요. 영어 사용 금지.

다음 형식의 JSON만 응답하세요 (다른 텍스트 없이):
{
  "action": "argue" | "rebut" | "concede" | "question" | "summarize",
  "claim": "<한국어로 작성한 주요 주장>",
  "evidence": "<한국어로 작성한 근거/데이터/인용>" | null,
  "tool_used": "web_search" (web_search 도구를 사용한 경우) | null,
  "tool_result": "<검색 결과 요약>" (web_search 사용한 경우) | null
}

web_search 도구를 사용한 경우:
- evidence 필드에 검색 결과의 핵심 내용을 반드시 인용하세요
- 출처 URL을 포함하면 논거의 신뢰도가 높아집니다
- 검색 결과와 다른 내용을 인용하면 "허위 인용" 위반으로 감점됩니다

⚠️ 필드 오염 금지: claim 필드 안에 "evidence:", "tool_used:", "tool_result:" 같은 다른 필드 이름을 포함하지 마세요.
각 필드는 반드시 JSON 키로만 분리하세요. 반드시 단일 JSON 객체만 출력하세요."""

# detect_repetition() 제거 — 단어 집합 비교로는 의미적 반복 탐지 불가.
# repetition 탐지를 REVIEW_SYSTEM_PROMPT 기반 LLM 검토로 위임 (orchestrator.py).
# PENALTY_FALSE_SOURCE = 7
# TODO: 허위 출처 탐지 미구현 — WebSocket/LLM tool_use 응답에서 실제 도구 호출 여부를
# 서버 측에서 검증할 방법이 없어 상수만 정의됨. 구현 시 활성화.


def _platform_api_key(provider: str) -> str:
    """플랫폼 환경변수에서 provider별 API 키를 반환한다.

    unknown provider는 빈 문자열을 반환한다 — 의도치 않은 키 노출 방지.

    Args:
        provider: LLM 공급자 식별자 (openai | anthropic | google | runpod).

    Returns:
        해당 provider의 플랫폼 API 키. 미설정이거나 unknown provider면 빈 문자열.
    """
    match provider:
        case "openai":
            return settings.openai_api_key or ""
        case "anthropic":
            return settings.anthropic_api_key or ""
        case "google":
            return settings.google_api_key or ""
        case "runpod":
            return settings.runpod_api_key or ""
        case _:
            return ""


# orchestrator.py / judge.py에서 각각 관리하던 위반 유형 한글 레이블 통합 상수.
# 두 파일의 dict가 diverge하여 judge._format_debate_log()의 .get(k, k) fallback이
# 영문 키를 Judge LLM에 그대로 전달하는 버그가 있었음 — 이 상수로 단일화.
PENALTY_KO_LABELS: dict[str, str] = {
    # 코드 기반 탐지 위반
    "off_topic": "주제 이탈",
    "repetition": "주장 반복",
    "false_source": "허위 출처",
    "prompt_injection": "프롬프트 인젝션",
    # LLM 검토 탐지 위반 (orchestrator review_turn() 결과)
    "ad_hominem": "인신공격(LLM)",
    "straw_man": "허수아비 논증(LLM)",
    "false_claim": "허위 주장(LLM)",
    "no_web_evidence": "웹 근거 미제시(LLM)",
    "false_citation": "허위 인용(LLM)",
    "irrelevant_source": "무관 출처 사용(LLM)",
    # _apply_review_to_turn이 llm_ 접두사로 저장하는 형태
    "llm_off_topic": "주제 이탈(LLM)",
    "llm_false_claim": "허위 주장(LLM)",
    "llm_ad_hominem": "인신공격(LLM)",
    "llm_repetition": "주장 반복(LLM)",
    "llm_no_web_evidence": "웹 근거 미제시(LLM)",
    "llm_false_citation": "허위 인용(LLM)",
    "llm_prompt_injection": "프롬프트 인젝션(LLM)",
}


def validate_response_schema(response_text: str) -> dict | None:
    """에이전트 응답 JSON을 파싱하고 스키마를 검증한다.

    3단계 파싱: 마크다운 코드블록 제거 → 전체 JSON 파싱 시도 → 텍스트 내 JSON 추출.
    action이 유효한 5종 중 하나가 아니거나 claim이 비어 있으면 None을 반환한다.

    Args:
        response_text: LLM이 반환한 원문 응답 텍스트.

    Returns:
        파싱·검증 성공 시 필수 키가 보장된 dict, 실패 시 None.
    """
    text = response_text.strip()

    # 1단계: 마크다운 코드블록 제거
    if "```" in text:
        text = re.sub(r"```(?:json)?\s*", "", text)
        text = re.sub(r"```", "", text).strip()

    # 2단계: JSON 파싱 시도 (전체 텍스트가 JSON인 경우)
    data = None
    with contextlib.suppress(json.JSONDecodeError, ValueError):
        data = json.loads(text)

    # 3단계: 텍스트 중간에 JSON이 포함된 경우 추출
    if data is None:
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            with contextlib.suppress(json.JSONDecodeError, ValueError):
                data = json.loads(json_match.group(0))

    if data is None:
        return None

    required_keys = {"action", "claim"}
    # action과 claim은 에이전트 발언의 필수 필드 — 하나라도 없으면 턴 처리 불가
    if not required_keys.issubset(data.keys()):
        return None

    valid_actions = {"argue", "rebut", "concede", "question", "summarize"}
    # RESPONSE_SCHEMA_INSTRUCTION에 정의된 5개 액션만 허용 — 임의 값 거부
    if data.get("action") not in valid_actions:
        return None

    # claim 필드에 다른 JSON 필드명이 평문으로 혼입된 경우 제거
    # LLM이 JSON 대신 "field: value\n" 형태로 응답하면 validate가 claim에 전부 넣어버리는 버그 방지
    claim_text = str(data.get("claim", ""))
    contamination_pattern = re.compile(r'\n(?:evidence|tool_used|tool_result)\s*:', re.IGNORECASE)
    m = contamination_pattern.search(claim_text)
    if m:
        data["claim"] = claim_text[:m.start()].strip()

    # claim이 비어있으면 실패
    if not str(data.get("claim", "")).strip():
        return None

    # tool_used, tool_result, evidence 기본값 보장
    data.setdefault("evidence", None)
    data.setdefault("tool_used", None)
    data.setdefault("tool_result", None)

    return data


def _resolve_api_key(agent: DebateAgent, force_platform: bool = False) -> str:
    """에이전트 LLM API 키를 반환한다.

    우선순위: BYOK 복호화 → 플랫폼 환경변수 → 빈 문자열.
    플랫폼 키는 force_platform=True 또는 use_platform_credits=True 에이전트에만 사용한다.
    BYOK 복호화 실패 시 플랫폼 키로 자동 폴백하지 않고 빈 문자열 반환 — 명시적 실패 유도.

    Args:
        agent: API 키를 조회할 에이전트.
        force_platform: True이면 BYOK 무시하고 플랫폼 환경변수 키를 사용.

    Returns:
        복호화된 API 키 문자열. 키가 없거나 복호화 실패 시 빈 문자열.
    """
    if agent.provider == "local":
        return ""

    use_platform = force_platform or getattr(agent, "use_platform_credits", False)

    # BYOK 키 복호화 시도 (플랫폼 모드가 아닐 때만)
    if not use_platform:
        if agent.encrypted_api_key:
            try:
                return decrypt_api_key(agent.encrypted_api_key)
            except ValueError:
                # 복호화 실패 시 플랫폼 키로 자동 전환하지 않음 — 운영자가 즉시 인지하도록 명시적 실패
                logger.warning(
                    "Agent %s API key decrypt failed, returning empty key (platform fallback disabled)",
                    agent.id,
                )
        return ""

    # 플랫폼 모드 (force_platform 또는 use_platform_credits=True)
    match agent.provider:
        case "openai":
            key = settings.openai_api_key or ""
        case "anthropic":
            key = settings.anthropic_api_key or ""
        case "google":
            key = settings.google_api_key or ""
        case "runpod":
            key = settings.runpod_api_key or ""
        case _:
            logger.warning(
                "Unknown provider '%s' for agent %s — cannot resolve platform API key",
                agent.provider,
                agent.id,
            )
            return ""
    if not key:
        logger.warning(
            "Platform API key not set for provider '%s' (agent %s) — LLM call will fail",
            agent.provider,
            agent.id,
        )
    return key


def _build_messages(
    system_prompt: str,
    topic: DebateTopic,
    turn_number: int,
    speaker: str,
    my_claims: list[str],
    opponent_claims: list[str],
    prefetch_evidence: str | None = None,
    prev_evidence: str | None = None,
) -> list[dict]:
    """에이전트에게 보낼 LLM 메시지 컨텍스트를 구성한다.

    시스템 메시지에 토론 컨텍스트·RESPONSE_SCHEMA_INSTRUCTION·에이전트 시스템 프롬프트를 합친다.
    이전 발언 이력은 최근 4턴만 포함해 컨텍스트 과부하를 방지한다.
    턴 단계(초반·중반·후반·마지막)에 따라 전략 힌트를 달리 주입한다.

    Args:
        system_prompt: 에이전트 버전 스냅샷의 시스템 프롬프트 (캐릭터·어투 설정).
        topic: 토론 주제 (제목·설명·최대 턴·툴 허용 여부 포함).
        turn_number: 현재 턴 번호 (1-indexed).
        speaker: 발언자 ('agent_a' | 'agent_b').
        my_claims: 본인의 이전 발언 목록.
        opponent_claims: 상대방의 이전 발언 목록.
        prev_evidence: 본인의 이전 턴 evidence 합성 요약. 있으면 발언 힌트로 주입.

    Returns:
        OpenAI/Anthropic 호환 messages 리스트.
    """
    side_label = "A (찬성)" if speaker == "agent_a" else "B (반대)"
    judge_intro = (getattr(topic, "judge_intro", None) or "").strip()
    judge_intro_section = f"[judge_intro]\n{judge_intro}" if judge_intro else "[judge_intro]\n없음"
    tools_line = (
        "툴 사용: 허용됨 (web_search — 현재 주장을 뒷받침하는 웹 근거 검색)\n"
        "web_search 결과를 받은 경우 반드시 한국어로 요약하여 발언에 인용하세요 "
        "(예: '검색 결과에 따르면 ...', '~에 따르면 ...')."
        if topic.tools_enabled
        else "툴 사용: 이 토론에서는 툴 사용이 금지되어 있습니다. tool_used는 반드시 null로 설정하세요."
    )
    context = f"""토론 포지션: {side_label}

토론 주제: {topic.title}
설명: {topic.description or '없음'}
{judge_intro_section}
현재 턴: {turn_number} / {topic.max_turns}
{tools_line}

⚠️ claim 필드에도 에이전트 시스템 프롬프트에서 지정한 어투·말투·캐릭터를 반드시 유지하세요.

{RESPONSE_SCHEMA_INSTRUCTION}"""

    # 시스템 프롬프트를 뒤에 배치해 어투/캐릭터 설정이 context보다 우선 적용되도록 함
    messages = [{"role": "system", "content": context + "\n\n---\n\n" + system_prompt}]

    # 이전 턴 히스토리 (최근 4턴)
    all_turns = []
    for _i, (my_c, opp_c) in enumerate(zip(my_claims, opponent_claims, strict=False)):
        all_turns.append({"role": "assistant", "content": my_c})
        all_turns.append({"role": "user", "content": f"[상대방]: {opp_c}"})

    # 상대방이 더 많이 말한 경우
    if len(opponent_claims) > len(my_claims):
        for opp_c in opponent_claims[len(my_claims) :]:
            all_turns.append({"role": "user", "content": f"[상대방]: {opp_c}"})

    # 최근 4개만 유지
    messages.extend(all_turns[-4:])

    # 턴 단계별 전략 힌트: 초반·중반·후반에 따라 다른 액션을 유도한다
    is_final_turn = turn_number == topic.max_turns
    is_penultimate = topic.max_turns > 2 and turn_number == topic.max_turns - 1
    is_early = turn_number <= 2

    if not my_claims and not opponent_claims:
        messages.append({"role": "user", "content": "먼저 시작하세요. 주제에 대한 첫 번째 주장을 한국어로 제시하세요."})
    elif opponent_claims:
        last_opp = opponent_claims[-1]

        if is_final_turn:
            strategy_hint = (
                "이번이 마지막 발언입니다. 지금까지의 논점을 간결하게 압축하고 핵심 입장을 마무리하세요. "
                "summarize 액션을 적극 활용하세요."
            )
        elif is_penultimate:
            strategy_hint = (
                "클라이맥스 국면입니다. 상대 논거의 핵심 약점에 집중하거나(rebut/question), "
                "인정할 부분은 인정하되 핵심 입장을 굳건히 하세요(concede)."
            )
        elif is_early:
            strategy_hint = (
                "초반 국면입니다. 새로운 논거를 제시(argue)하거나 상대의 전제에 의문을 제기(question)하세요."
            )
        else:
            strategy_hint = (
                "반박(rebut)·새 주장(argue)·질문(question)·인정 후 입장 유지(concede) 중 "
                "지금 상황에서 가장 설득력 있는 전략을 선택하세요."
            )

        base_content = (
            f"[직전 발언]\n{last_opp}\n\n"
            "위 발언을 바탕으로 토론을 이어가세요. "
            "'상대방은'으로 문장을 시작하지 마세요 — 논점이나 근거로 바로 시작하세요. "
            f"{strategy_hint}"
        )
        # Agent B의 첫 발언: 주도적으로 논점을 선점하도록 격려 (A측 편향 보정)
        if speaker == "agent_b" and not my_claims:
            base_content += (
                "\n\n(참고: 상대가 먼저 발언했지만, 당신도 새로운 논거로 주도적으로 쟁점을 선점할 수 있습니다.)"
            )
        # tool-use 미지원 provider용 pre-fetch 검색 결과 주입
        if prefetch_evidence:
            base_content += f"\n\n[참고 출처 (참고용, 직접 인용 권장)]\n{prefetch_evidence}"
        # 이전 턴 evidence 합성 요약 주입 — 연속 논거 구성에 활용
        if prev_evidence:
            base_content += f"\n\n[이전 발언 근거 참고]\n{prev_evidence[:300]}"
        messages.append({"role": "user", "content": base_content})
    else:
        messages.append({"role": "user", "content": "당신의 차례입니다. 주제에 대한 다음 주장을 한국어로 제시하세요."})

    return messages


def calculate_elo(rating_a: int, rating_b: int, result: str, score_diff: int = 0) -> tuple[int, int]:
    """표준 ELO + 판정 점수차 배수.

    result: 'a_win' | 'b_win' | 'draw'
    score_diff: abs(score_a - score_b), 0~100 범위

    공식:
      E_a  = 1 / (1 + 10^((rating_b - rating_a) / 400))   # 기대 승률
      base = K × (실제결과 - E_a)                           # 표준 ELO 변동
      mult = 1.0 + (score_diff / scale) × weight           # 점수차 배수 [1.0 ~ max_mult]
      delta_a = round(base × mult),  delta_b = -delta_a    # 제로섬 유지

    효과:
      - 강자를 이기면 많이 획득, 약자에게 지면 많이 잃음
      - 압도적 승리(score_diff 큼)일수록 최대 max_mult배 변동
    """
    k = settings.debate_elo_k_factor
    scale = settings.debate_elo_score_diff_scale
    weight = settings.debate_elo_score_diff_weight
    max_mult = settings.debate_elo_score_mult_max

    # 기대 승률 (로지스틱 ELO 공식)
    e_a = 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

    # s_a: ELO 공식의 실제 결과 점수 — 승=1.0, 무=0.5, 패=0.0
    if result == "a_win":
        s_a = 1.0
    elif result == "b_win":
        s_a = 0.0
    else:  # draw
        s_a = 0.5

    # 기본 ELO 변동
    base_delta = k * (s_a - e_a)

    # 점수차 배수 (1.0 이상, max_mult 이하)
    mult = 1.0 + (min(abs(score_diff), scale) / scale) * weight
    mult = min(mult, max_mult)

    # 반올림 후 제로섬 보정 (delta_a + delta_b = 0 항상 유지)
    delta_a = round(base_delta * mult)
    delta_b = -delta_a

    return rating_a + delta_a, rating_b + delta_b
