"""토론 엔진 E2E 테스트.

두 에이전트가 실제 토론 한 사이클(3턴 × 2 에이전트 → 오케스트레이터 판정 → ELO 갱신)을
처음부터 끝까지 실행한다.

실제로 실행되는 것:
- 전체 debate_engine._execute_match 흐름
- 턴 구성 메시지 빌드 (_build_messages)
- 응답 JSON 파싱/검증 (validate_response_schema)
- 벌점 감지 (반복/프롬프트인젝션/인신공격)
- DebateOrchestrator.judge + 스코어카드 파싱
- ELO 계산 (calculate_elo) + DB 반영

Mock 처리 (외부 HTTP 호출만):
- InferenceClient.generate_byok  → 에이전트 턴 응답 (6회)
- InferenceClient._call_openai_byok → 오케스트레이터 판정 (1회)
- publish_event → Redis 없이도 동작 (no-op)
"""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_password_hash
from app.core.encryption import encrypt_api_key
from app.models.debate_agent import DebateAgent, DebateAgentVersion
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog
from app.models.user import User
from app.services.debate.engine import _execute_match
from app.services.debate.orchestrator import calculate_elo

# ---------------------------------------------------------------------------
# 시나리오 정의: 주제 — "AI는 의료 진단을 인간 의사보다 더 잘 수행할 수 있다"
# ---------------------------------------------------------------------------

_TOPIC_TITLE = "AI는 의료 진단을 인간 의사보다 더 잘 수행할 수 있다"
_TOPIC_DESC = (
    "AI 알고리즘이 실제 임상 환경에서 인간 전문의의 진단 정확도를 대체 또는 능가할 수 있는지를 논한다. "
    "기술적 성능, 일반화 능력, 신뢰/윤리 요소를 모두 고려한다."
)

# 6턴 순서: A-B-A-B-A-B (Turn1-A, Turn1-B, Turn2-A, Turn2-B, Turn3-A, Turn3-B)
_AGENT_TURN_SCRIPTS = [
    # ----- Turn 1 -----
    {
        "speaker_label": "Agent A (PRO)",
        "action": "argue",
        "claim": (
            "AI는 의료 영상 분석에서 이미 인간 전문의를 능가합니다. "
            "Google DeepMind 연구(Nature Medicine 2020)에서 AI는 안저 사진 기반 "
            "당뇨망막병증 진단 정확도 94.5%를 달성해 안과 전문의 평균 90.3%를 상회했습니다. "
            "방사선 판독에서도 Stanford CheXNet(2017)은 흉부 X-ray 폐렴 진단 F1 0.435로 "
            "방사선과 전문의 평균 0.387을 초과했습니다."
        ),
        "evidence": "DeepMind - Nature Medicine 2020 (AUC 0.945) / Stanford CheXNet - arXiv 2017",
    },
    {
        "speaker_label": "Agent B (CON)",
        "action": "rebut",
        "claim": (
            "벤치마크 성능은 실제 임상 환경과 다릅니다. "
            "MIT 연구(NEJM 2023)는 동일 AI 모델이 훈련 외 병원 데이터에 적용될 때 "
            "정확도가 최대 23%p 하락함을 입증했습니다. "
            "또한 FDA는 2022년 AI 의료기기 9건을 편향 문제로 리콜했습니다. "
            "제한된 데이터셋에서의 성능이 실제 진단 능력을 대변하지 않습니다."
        ),
        "evidence": "NEJM 2023 - Distribution shift study / FDA Recall Database 2022",
    },
    # ----- Turn 2 -----
    {
        "speaker_label": "Agent A (PRO)",
        "action": "rebut",
        "claim": (
            "분포 이동 문제는 연합 학습(Federated Learning)과 다기관 검증으로 해결되고 있습니다. "
            "2024년 FDA 510(k) 승인을 받은 AI 진단 기기 11건 중 9건이 "
            "멀티센터 외부 검증을 통과했습니다. "
            "규제 프레임워크 자체가 일반화 성능을 요구하도록 진화했으므로, "
            "편향 리콜 사례는 오히려 시스템이 제대로 작동하고 있다는 증거입니다."
        ),
        "evidence": "FDA AI/ML Action Plan 2024 - 11 devices cleared with multicenter validation",
    },
    {
        "speaker_label": "Agent B (CON)",
        "action": "argue",
        "claim": (
            "기술 문제 이전에 신뢰와 책임 귀속 문제가 해결되지 않았습니다. "
            "JAMA Survey 2023에 따르면 환자의 79%가 AI 단독 진단을 수용하지 않으며, "
            "신뢰 없는 치료는 복약 순응도를 약 31% 낮춥니다(Lancet 2022). "
            "또한 AI 오진 발생 시 법적 책임 소재에 대한 국제적 합의가 없습니다."
        ),
        "evidence": "JAMA 2023 - Patient trust survey (n=2,800) / Lancet 2022 - Adherence study",
    },
    # ----- Turn 3 (마무리) -----
    {
        "speaker_label": "Agent A (PRO)",
        "action": "summarize",
        "claim": (
            "AI는 의사를 대체하는 것이 아니라 '증강'합니다. "
            "기술적 정확도에서 AI가 이미 앞서 있고, 신뢰 문제는 임상 통합 경험 축적으로 해결 가능합니다. "
            "더 중요한 것은 지금 이 순간 전문의 접근이 불가능한 45억 명(WHO 2023)의 현실입니다. "
            "AI 진단은 의료 불평등 해소의 결정적 수단입니다."
        ),
        "evidence": "WHO Global Health Access Report 2023 - 4.5B without specialist access",
    },
    {
        "speaker_label": "Agent B (CON)",
        "action": "summarize",
        "claim": (
            "AI의 보조 도구로서의 가치는 인정하나 '더 잘 수행한다'는 주장은 시기상조입니다. "
            "전인적 치료, 예외 상황 판단, 윤리적 의사결정에서 인간 의사는 여전히 필수입니다. "
            "Lancet Digital Health(2024)에 따르면 AI+인간 협업 모델이 단독 AI 대비 34% 더 나은 "
            "환자 결과를 보였습니다. 공동 의사결정 모델이 최선입니다."
        ),
        "evidence": "Lancet Digital Health 2024 - Human-AI collaboration vs AI-alone: +34% outcomes",
    },
]

# 오케스트레이터 판정 스코어카드
_JUDGE_SCORECARD = {
    "agent_a": {"logic": 25, "evidence": 21, "rebuttal": 22, "relevance": 18},
    "agent_b": {"logic": 21, "evidence": 19, "rebuttal": 20, "relevance": 17},
    "reasoning": (
        "Agent A (PRO) provided stronger quantitative evidence and effectively rebutted "
        "the generalization concern with regulatory data. "
        "Agent B (CON) raised valid patient trust and accountability concerns but "
        "lacked specific counter-data to the multicenter validation argument. "
        "Agent A wins by 9-point margin after scoring."
    ),
}
# A: 25+21+22+18=86, B: 21+19+20+17=77 → diff=9 → 무승부(< 10)
# 아래에서 A 점수를 더 높여 승패 판정 확인 가능하도록 조정
_JUDGE_SCORECARD_WIN = {
    "agent_a": {"logic": 26, "evidence": 22, "rebuttal": 22, "relevance": 18},  # 88
    "agent_b": {"logic": 20, "evidence": 18, "rebuttal": 18, "relevance": 17},  # 73  diff=15 → A WIN
    "reasoning": (
        "Agent A (PRO) dominated with concrete regulatory evidence and effectively "
        "neutralized the generalization critique. Agent B's patient trust argument was "
        "philosophically valid but lacked quantitative support. Clear A victory."
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_llm_response(turn: dict) -> dict:
    """에이전트 턴 데이터를 LLM API 응답 포맷으로 변환."""
    body = json.dumps(
        {
            "action": turn["action"],
            "claim": turn["claim"],
            "evidence": turn.get("evidence"),
            "tool_used": None,
            "tool_result": None,
        },
        ensure_ascii=False,
    )
    return {
        "content": body,
        "input_tokens": 200 + len(turn["claim"]) // 5,
        "output_tokens": 60 + len(turn["claim"]) // 10,
        "finish_reason": "stop",
    }


def _divider(char: str = "-", width: int = 72) -> str:
    return char * width


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def two_users(db_session: AsyncSession):
    """에이전트 owner로 쓸 두 사용자 생성."""
    user_a = User(
        id=uuid.uuid4(),
        login_id="pro_debater",
        nickname="pro_debater",
        password_hash=get_password_hash("pass"),
        role="user",
        age_group="unverified",
    )
    user_b = User(
        id=uuid.uuid4(),
        login_id="con_debater",
        nickname="con_debater",
        password_hash=get_password_hash("pass"),
        role="user",
        age_group="unverified",
    )
    db_session.add_all([user_a, user_b])
    await db_session.flush()
    return user_a, user_b


@pytest_asyncio.fixture
async def debate_e2e_setup(db_session: AsyncSession, two_users):
    """E2E 테스트에 필요한 전체 DB 엔티티 생성."""
    user_a, user_b = two_users

    # --- Agent A (PRO) ---
    agent_a = DebateAgent(
        id=uuid.uuid4(),
        owner_id=user_a.id,
        name="Atlas v1 (PRO)",
        description="데이터·연구 기반의 논리형 분석가 에이전트",
        provider="openai",
        model_id="gpt-4o",
        encrypted_api_key=encrypt_api_key("sk-test-atlas-key"),
        elo_rating=1500,
    )
    db_session.add(agent_a)
    await db_session.flush()

    version_a = DebateAgentVersion(
        id=uuid.uuid4(),
        agent_id=agent_a.id,
        version_number=1,
        version_tag="v1.0",
        system_prompt=(
            "당신은 AI 기술의 의료 적용을 적극 지지하는 논리형 분석가입니다. "
            "구체적인 임상 연구와 규제 데이터를 인용하여 주장을 뒷받침하세요. "
            "상대방의 기술적 반박에는 최신 솔루션(연합 학습, 멀티센터 검증)으로 답하세요."
        ),
    )
    db_session.add(version_a)

    # --- Agent B (CON) ---
    agent_b = DebateAgent(
        id=uuid.uuid4(),
        owner_id=user_b.id,
        name="Socrates v1 (CON)",
        description="AI 한계와 인간 요소를 강조하는 균형형 전략가",
        provider="openai",
        model_id="gpt-4o",
        encrypted_api_key=encrypt_api_key("sk-test-socrates-key"),
        elo_rating=1500,
    )
    db_session.add(agent_b)
    await db_session.flush()

    version_b = DebateAgentVersion(
        id=uuid.uuid4(),
        agent_id=agent_b.id,
        version_number=1,
        version_tag="v1.0",
        system_prompt=(
            "당신은 AI 의료 진단의 한계와 위험성을 지적하는 균형형 전략가입니다. "
            "분포 이동, 환자 신뢰, 책임 귀속 문제를 근거로 삼으세요. "
            "상대방의 기술 낙관론에는 실제 사고 사례와 사회적 함의로 반격하세요."
        ),
    )
    db_session.add(version_b)
    await db_session.flush()

    # --- Topic ---
    topic = DebateTopic(
        id=uuid.uuid4(),
        title=_TOPIC_TITLE,
        description=_TOPIC_DESC,
        mode="debate",
        status="in_progress",
        max_turns=3,
        turn_token_limit=500,
    )
    db_session.add(topic)

    # --- Match ---
    match = DebateMatch(
        id=uuid.uuid4(),
        topic_id=topic.id,
        agent_a_id=agent_a.id,
        agent_b_id=agent_b.id,
        agent_a_version_id=version_a.id,
        agent_b_version_id=version_b.id,
        status="pending",
        score_a=0,
        score_b=0,
        penalty_a=0,
        penalty_b=0,
    )
    db_session.add(match)
    await db_session.commit()

    for obj in [agent_a, agent_b, version_a, version_b, topic, match]:
        await db_session.refresh(obj)

    return {
        "agent_a": agent_a,
        "agent_b": agent_b,
        "version_a": version_a,
        "version_b": version_b,
        "topic": topic,
        "match": match,
    }


# ---------------------------------------------------------------------------
# E2E Test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_debate_full_cycle(db_session: AsyncSession, debate_e2e_setup):
    """토론 한 사이클 완전 실행: 3턴 × 2에이전트 → 판정 → ELO 갱신.

    pytest -s 옵션으로 실행 시 전체 토론 트랜스크립트가 콘솔에 출력됩니다:
        backend/.venv/Scripts/python -m pytest tests/integration/test_debate_e2e.py -v -s
    """
    entities = debate_e2e_setup
    match: DebateMatch = entities["match"]
    agent_a: DebateAgent = entities["agent_a"]
    agent_b: DebateAgent = entities["agent_b"]
    topic: DebateTopic = entities["topic"]

    # 에이전트 턴 mock — side_effect로 순서 보장
    turn_responses = [_make_llm_response(t) for t in _AGENT_TURN_SCRIPTS]
    turn_call_index = 0

    async def mock_generate_byok(provider, model_id, api_key, messages, **kwargs):
        nonlocal turn_call_index
        idx = turn_call_index
        turn_call_index += 1
        return turn_responses[idx]

    # 오케스트레이터 판정 mock
    judge_response = {
        "content": json.dumps(_JUDGE_SCORECARD_WIN, ensure_ascii=False),
        "input_tokens": 900,
        "output_tokens": 220,
    }

    # 이벤트 수집 (publish_event mock)
    emitted_events: list[dict] = []

    async def mock_publish_event(match_id: str, event_type: str, data: dict):
        emitted_events.append({"event": event_type, "data": data})

    # ── 실행 ──
    with (
        patch(
            "app.services.llm.inference_client.InferenceClient.generate_byok",
            side_effect=mock_generate_byok,
        ),
        patch(
            "app.services.llm.inference_client.InferenceClient._call_openai_byok",
            new=AsyncMock(return_value=judge_response),
        ),
        patch(
            "app.services.debate.engine.publish_event",
            side_effect=mock_publish_event,
        ),
    ):
        await _execute_match(db_session, str(match.id))

    # ── DB 결과 조회 ──
    # expire_on_commit=False이므로 bulk UPDATE 후 in-memory 객체는 갱신되지 않음.
    # 명시적 refresh()로 최신 DB 값을 로드한다.
    await db_session.refresh(match)
    finished_match = match

    turns = list(
        (
            await db_session.execute(
                select(DebateTurnLog)
                .where(DebateTurnLog.match_id == match.id)
                .order_by(DebateTurnLog.turn_number, DebateTurnLog.speaker)
            )
        ).scalars().all()
    )

    await db_session.refresh(agent_a)
    await db_session.refresh(agent_b)
    updated_a = agent_a
    updated_b = agent_b

    # ── 콘솔 출력 (pytest -s 로 확인) ──
    scorecard = finished_match.scorecard or {}
    a_raw = sum(scorecard.get("agent_a", {}).values()) if scorecard.get("agent_a") else 0
    b_raw = sum(scorecard.get("agent_b", {}).values()) if scorecard.get("agent_b") else 0
    winner_name = (
        agent_a.name
        if finished_match.winner_id == agent_a.id
        else agent_b.name
        if finished_match.winner_id == agent_b.id
        else "무승부 (Draw)"
    )

    print(f"\n\n{_divider('=')}")
    print(f"  [E2E] 토론 E2E 테스트 -- 전체 사이클 실행 결과")
    print(_divider("="))
    print(f"  [TOPIC] 주제: {topic.title}")
    print(f"  [AGENT] Agent A (PRO): {agent_a.name} [{agent_a.provider}/{agent_a.model_id}]")
    print(f"  [AGENT] Agent B (CON): {agent_b.name} [{agent_b.provider}/{agent_b.model_id}]")
    print(f"  [TURNS] 턴 수: {topic.max_turns}턴")
    print(_divider())

    # 턴별 트랜스크립트
    print(f"\n  [TRANSCRIPT] 토론 트랜스크립트\n")
    for _i, turn in enumerate(turns):
        side = "PRO (Agent A)" if turn.speaker == "agent_a" else "CON (Agent B)"
        print(f"  [{turn.turn_number}턴] {side} -- {turn.action.upper()}")
        # 줄 바꿈을 위해 80자 단위로 출력
        claim_lines = [turn.claim[j:j+68] for j in range(0, len(turn.claim), 68)]
        for k, line in enumerate(claim_lines):
            prefix = "  주장: " if k == 0 else "        "
            print(f"  {prefix}{line}")
        if turn.evidence:
            print(f"  근거: {turn.evidence[:80]}")
        if turn.penalty_total > 0:
            print(f"  [PENALTY] 벌점: -{turn.penalty_total} {turn.penalties}")
        print()

    # 판정 결과
    print(_divider())
    print(f"\n  [JUDGE] 오케스트레이터 판정 결과\n")
    if scorecard.get("agent_a") and scorecard.get("agent_b"):
        a_s = scorecard["agent_a"]
        b_s = scorecard["agent_b"]
        print(f"  {'항목':<14} {'Agent A (PRO)':>14} {'Agent B (CON)':>14}")
        print(f"  {_divider('-', 44)}")
        criteria = [("논리성 (logic)", "logic", 30), ("근거 (evidence)", "evidence", 25),
                    ("반박력 (rebuttal)", "rebuttal", 25), ("적합성 (relevance)", "relevance", 20)]
        for label, key, max_score in criteria:
            print(f"  {label:<20} {a_s.get(key,0):>6}/{max_score}  {b_s.get(key,0):>6}/{max_score}")
        print(f"  {_divider('-', 44)}")
        print(f"  {'기본 소계':<20} {a_raw:>9}/100  {b_raw:>9}/100")
        print(f"  {'벌점':<20} {-finished_match.penalty_a:>10}  {-finished_match.penalty_b:>10}")
        print(f"  {'최종 점수':<20} {finished_match.score_a:>10}  {finished_match.score_b:>10}")

    print(f"\n  심판 코멘트:")
    reasoning = scorecard.get("reasoning", "")
    for chunk in [reasoning[i:i+66] for i in range(0, len(reasoning), 66)]:
        print(f"    {chunk}")

    diff = abs(finished_match.score_a - finished_match.score_b)
    verdict = f"점수차 {diff}점 → {'승/패 판정' if diff >= 10 else '무승부 (점수차 < 10)'}"
    print(f"\n  판정: {verdict}")
    print(f"\n  [WINNER] 최종 승자: {winner_name}")
    print(f"\n{_divider()}")

    # ELO 변화
    elo_change_a = updated_a.elo_rating - 1500
    elo_change_b = updated_b.elo_rating - 1500
    print(f"\n  [ELO] ELO 레이팅 갱신 (K={32})")
    print(f"  Agent A: 1500 -> {updated_a.elo_rating:4d}  ({elo_change_a:+d})")
    print(f"  Agent B: 1500 -> {updated_b.elo_rating:4d}  ({elo_change_b:+d})")
    print(f"\n  [EVENTS] 발행된 이벤트 ({len(emitted_events)}건):")
    for ev in emitted_events:
        print(f"    [{ev['event']:15s}] {str(ev['data'])[:60]}")
    print(f"\n{_divider('=')}\n")

    # ── Assertions ──

    # 1) 매치 완료 상태
    assert finished_match.status == "completed", (
        f"매치 상태 오류: expected 'completed', got '{finished_match.status}'"
    )

    # 2) 정확히 6개의 턴 로그
    assert len(turns) == topic.max_turns * 2, (
        f"턴 수 오류: expected {topic.max_turns * 2}, got {len(turns)}"
    )

    # 3) 모든 턴의 action, claim 정상
    valid_actions = {"argue", "rebut", "concede", "question", "summarize"}
    for t in turns:
        assert t.action in valid_actions, f"Turn {t.turn_number}/{t.speaker}: invalid action '{t.action}'"
        assert t.claim, f"Turn {t.turn_number}/{t.speaker}: empty claim"

    # 4) 스코어카드가 DB에 저장됨
    assert finished_match.scorecard is not None, "scorecard가 None"
    assert "agent_a" in finished_match.scorecard
    assert "agent_b" in finished_match.scorecard

    # 5) 점수가 0 이상
    assert finished_match.score_a >= 0
    assert finished_match.score_b >= 0

    # 6) A 점수 > B 점수이므로 A가 승자
    assert finished_match.winner_id == agent_a.id, (
        f"승자 오류: score_a={finished_match.score_a} > score_b={finished_match.score_b}이므로 A가 이겨야 함"
    )

    # 7) ELO 변화: A는 올라가고 B는 내려가야 함
    assert updated_a.elo_rating > 1500, "A의 ELO가 올라야 함"
    assert updated_b.elo_rating < 1500, "B의 ELO가 내려야 함"
    assert updated_a.wins == 1
    assert updated_b.losses == 1

    # 8) 이벤트 발행 순서 확인
    event_types = [e["event"] for e in emitted_events]
    assert "started" in event_types, "started 이벤트 없음"
    assert "finished" in event_types, "finished 이벤트 없음"
    turn_events = [e for e in emitted_events if e["event"] == "turn"]
    assert len(turn_events) == topic.max_turns * 2, (
        f"turn 이벤트 수 오류: expected {topic.max_turns * 2}, got {len(turn_events)}"
    )
    # started가 turn들보다 먼저
    started_idx = event_types.index("started")
    first_turn_idx = event_types.index("turn")
    assert started_idx < first_turn_idx, "started가 첫 turn보다 먼저 발행되어야 함"
    # finished가 마지막
    assert event_types[-1] == "finished", "finished 이벤트가 마지막이어야 함"

    # 9) 토큰 수 기록 (BYOK 에이전트)
    for t in turns:
        assert t.input_tokens > 0, f"Turn {t.turn_number}/{t.speaker}: input_tokens=0"
        assert t.output_tokens > 0, f"Turn {t.turn_number}/{t.speaker}: output_tokens=0"
