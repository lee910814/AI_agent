"""토론 판정기. LLM 기반 최종 판정(judge)."""

import asyncio
import json
import logging
import re

from app.core.config import settings
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog
from app.services.debate.helpers import PENALTY_KO_LABELS, _platform_api_key
from app.services.llm.inference_client import InferenceClient
from app.services.llm.utils import infer_provider

logger = logging.getLogger(__name__)

# 채점 기준 (총 100점 만점)
# argumentation: 주장·근거·추론의 일체 (logic + evidence 통합)
# rebuttal: 상대 논거에 대한 직접 대응
# strategy: 쟁점 주도력, 논점 우선순위 설정, 흐름 운영
SCORING_CRITERIA = {
    "argumentation": 40,
    "rebuttal": 35,
    "strategy": 25,
}

def _build_score_format() -> str:
    """SCORING_CRITERIA에서 Judge LLM이 반환할 JSON 출력 스펙을 동적 생성한다.

    scoring criteria 변경 시 자동으로 반영된다.

    Returns:
        Judge LLM 시스템 프롬프트에 삽입할 JSON 형식 문자열.
    """
    fields = ", ".join(f'"{k}": <0-{v}>' for k, v in SCORING_CRITERIA.items())
    return f'{{"agent_a": {{{fields}}}, "agent_b": {{{fields}}}, "reasoning": "<한국어로 작성한 채점 근거>"}}'



# Stage 1: 서술형 분석 프롬프트 — 숫자/점수 언급 금지로 앵커링 편향 차단
JUDGE_ANALYSIS_PROMPT = """당신은 AI 토론 전문 분석가입니다. 아래 토론 전문을 읽고 서술형으로 분석하세요.
숫자나 점수를 절대 언급하지 마세요. 오직 논거, 반박, 전략의 강점과 약점을 서술하세요.

분석 포인트:
1. 각 에이전트의 논거 명확성과 근거 타당성
2. 상대 주장에 대한 반박의 정확성
3. 전체 토론 흐름에서의 전략적 접근
4. 위반 패턴: '경고(벌점 없음)'로 표시된 항목도 포함하여 반복 위반이 논거 품질에 미치는 영향을 평가하세요"""

# Stage 2: 분석 결과 기반 채점 프롬프트
JUDGE_SCORING_PROMPT = (
    "당신은 AI 토론 채점관입니다. 제공된 분석 결과를 바탕으로 채점하세요.\n\n"
    "채점 기준:\n"
    "- argumentation (최대 40점): 논거의 명확성, 근거의 타당성\n"
    "- rebuttal (최대 35점): 상대 주장 반박의 정확성, 논리적 일관성\n"
    "- strategy (최대 25점): 토론 흐름 파악, 전략적 전개\n\n"
    "⚠️ 반드시 아래 JSON 형식만 출력하세요. 설명, 마크다운 코드블록, 추가 텍스트 절대 금지:\n"
    + _build_score_format()
)

JUDGE_INTRO_SYSTEM_PROMPT = (
    "당신은 AI 토론의 judge LLM이며 토론 시작 전 아래의 사항을 지켜야 합니다\n"
    "1) 간단한 인사말\n"
    "2) 토론 주제에 대한 간단한 설명 2-3 문장\n"
    "명확하고 중립적인 언어로 120자 이내로 작성하시고 점수는 아직 매기지 마세요."
)


class DebateJudge:
    """LLM 2-stage 방식으로 토론 전체를 판정하는 심판 클래스.

    Stage 1: 서술형 분석 (점수 언급 금지 — 앵커링 편향 차단)
    Stage 2: 분석 결과 기반 JSON 채점
    """

    def __init__(
        self,
        client: "InferenceClient | None" = None,
        judge_model_override: str | None = None,
    ) -> None:
        self._owns_client = client is None
        self.client = client if client is not None else InferenceClient()
        self.judge_model_override = judge_model_override

    async def aclose(self) -> None:
        """소유한 InferenceClient를 닫는다. 외부 주입 클라이언트는 닫지 않는다."""
        if self._owns_client:
            await self.client.aclose()

    def _resolve_model_id(self) -> str | None:
        """Return configured judge model id if present."""
        return self.judge_model_override or settings.debate_judge_model or settings.debate_orchestrator_model

    @staticmethod
    def _fallback_intro_message(topic: DebateTopic) -> str:
        """Build a safe intro message when LLM intro generation fails."""
        topic_description = (topic.description or "").strip()
        if topic_description:
            return (
                f"토론장에 오신 것을 환영합니다. 오늘의 토론 주제는 '{topic.title}' 입니다. "
                f"{topic_description[:220]} "
                "Agent간 토론이 시작됩니다."
            ).strip()
        return f"'{topic.title}'이 있는지 확인 부탁드립니다."

    async def generate_intro(
        self,
        topic: DebateTopic,
        agent_a_name: str = "Agent A",
        agent_b_name: str = "Agent B",
        trace_id: str | None = None,
        orchestration_mode: str | None = None,
    ) -> dict:
        """Generate pre-debate judge intro (welcome + short topic explanation)."""
        model_id = self._resolve_model_id()
        if not model_id:
            logger.warning(
                "Judge intro fallback(model_unset) | trace_id=%s mode=%s topic=%s",
                trace_id,
                orchestration_mode,
                getattr(topic, "id", None),
            )
            return {
                "message": self._fallback_intro_message(topic),
                "input_tokens": 0,
                "output_tokens": 0,
                "model_id": None,
                "fallback_reason": "model_unset",
            }

        provider = infer_provider(model_id)
        api_key = _platform_api_key(provider)
        intro_timeout = getattr(settings, "debate_judge_timeout_seconds", 120)
        intro_max_tokens = min(getattr(settings, "debate_judge_max_tokens", 600), 220)
        user_prompt = (
            f"토론 주제: {topic.title}\n"
            f"주제 설명: {topic.description or 'N/A'}\n"
            f"참가자: {agent_a_name} vs {agent_b_name}"
        )

        try:
            result = await asyncio.wait_for(
                self.client.generate_byok(
                    provider=provider,
                    model_id=model_id,
                    api_key=api_key,
                    messages=[
                        {"role": "system", "content": JUDGE_INTRO_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=intro_max_tokens,
                    temperature=0.5,
                ),
                timeout=intro_timeout,
            )
            message = (result.get("content") or "").strip()
            if not message:
                raise ValueError("empty_intro")
            return {
                "message": message,
                "input_tokens": result.get("input_tokens", 0),
                "output_tokens": result.get("output_tokens", 0),
                "model_id": model_id,
                "fallback_reason": None,
            }
        except Exception as exc:
            logger.warning(
                "Judge intro fallback(request_error) | trace_id=%s mode=%s topic=%s model=%s err=%s",
                trace_id,
                orchestration_mode,
                getattr(topic, "id", None),
                model_id,
                exc,
            )
            return {
                "message": self._fallback_intro_message(topic),
                "input_tokens": 0,
                "output_tokens": 0,
                "model_id": model_id,
                "fallback_reason": "request_error",
            }

    async def judge(
        self,
        match: DebateMatch,
        turns: list[DebateTurnLog],
        topic: DebateTopic,
        agent_a_name: str = "에이전트 A",
        agent_b_name: str = "에이전트 B",
        trace_id: str | None = None,
        orchestration_mode: str | None = None,
    ) -> dict:
        """LLM으로 토론 판정. 스코어카드 dict 반환."""
        model_id = self._resolve_model_id()
        if not model_id:
            raise ValueError(
                "judge 모델 미설정: DEBATE_JUDGE_MODEL 또는 DEBATE_ORCHESTRATOR_MODEL "
                "환경 변수를 설정하세요. 모델 미설정 시 silent draw가 발생해 ELO 변동이 누락됩니다."
            )
        return await self._judge_with_model(
            match,
            turns,
            topic,
            agent_a_name,
            agent_b_name,
            model_id=model_id,
            trace_id=trace_id,
            orchestration_mode=orchestration_mode,
        )

    async def _judge_with_model(
        self,
        match: DebateMatch,
        turns: list[DebateTurnLog],
        topic: DebateTopic,
        agent_a_name: str,
        agent_b_name: str,
        model_id: str,
        trace_id: str | None = None,
        orchestration_mode: str | None = None,
    ) -> dict:
        """지정된 model_id로 2-stage LLM 판정을 수행하고 스코어카드·점수·승패를 반환한다.

        Stage 1: 서술형 분석 (온도 0.3, 점수 언급 금지 — 앵커링 편향 차단)
        Stage 2: 분석 결과 기반 채점 (JSON 출력)
        """
        debate_log = self._format_debate_log(turns, topic, agent_a_name, agent_b_name)
        provider = infer_provider(model_id)
        api_key = _platform_api_key(provider)

        judge_input_tokens = 0
        judge_output_tokens = 0
        raw_content = ""
        fallback_reason: str | None = None
        try:
            # stage1+stage2 합산 시간을 단일 타임아웃으로 제한
            async with asyncio.timeout(settings.debate_judge_timeout_seconds):
                # Stage 1: 서술형 분석 — 숫자/점수 없이 논거·반박·전략 강약점 서술
                analysis_messages = [
                    {"role": "system", "content": JUDGE_ANALYSIS_PROMPT},
                    {"role": "user", "content": debate_log},
                ]
                analysis_result = await self.client.generate_byok(
                    provider=provider,
                    model_id=model_id,
                    api_key=api_key,
                    messages=analysis_messages,
                    max_tokens=settings.debate_judge_max_tokens,
                    temperature=0.3,
                )
                judge_input_tokens += analysis_result.get("input_tokens", 0)
                judge_output_tokens += analysis_result.get("output_tokens", 0)
                analysis_content = analysis_result.get("content", "")
                if not analysis_content:
                    raise ValueError("Judge Stage 1 returned empty content")

                # Stage 2: 분석 결과 기반 채점 — JSON 출력
                # debate_log 재전송 생략: Stage 1이 이미 전체 대화를 분석했으므로 분석 결과만 전달
                scoring_messages = [
                    {"role": "system", "content": JUDGE_SCORING_PROMPT},
                    {"role": "user", "content": f"[분석 결과]\n{analysis_content}"},
                ]
                scoring_result = await self.client.generate_byok(
                    provider=provider,
                    model_id=model_id,
                    api_key=api_key,
                    messages=scoring_messages,
                    max_tokens=settings.debate_judge_max_tokens,
                    temperature=settings.debate_judge_temperature,
                )
                judge_input_tokens += scoring_result.get("input_tokens", 0)
                judge_output_tokens += scoring_result.get("output_tokens", 0)
                raw_content = scoring_result.get("content", "")
            content = raw_content.strip()
            # LLM이 마크다운 코드블록으로 감싸 반환하는 경우 제거
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.MULTILINE)
                content = re.sub(r"\s*```\s*$", "", content.strip())
            # JSON 오브젝트만 추출 (텍스트 앞뒤 잡동사니 제거)
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                content = json_match.group(0)
            scorecard = json.loads(content)
            if not isinstance(scorecard.get("agent_a"), dict) or not isinstance(scorecard.get("agent_b"), dict):
                raise ValueError("Invalid scorecard structure")
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.error(
                "Judge response parse error | trace_id=%s mode=%s err=%s raw=%.500s",
                trace_id,
                orchestration_mode,
                exc,
                raw_content,
            )
            # 파싱 실패 시 각 항목 최대값의 절반으로 균등 점수 (무승부 폴백)
            # half_scores_a/b 독립 생성 — 공유 dict 참조 시 클램핑 로직이 한 쪽 수정으로 양쪽에 반영되는 버그 방지
            half_scores_a = {k: v // 2 for k, v in SCORING_CRITERIA.items()}
            half_scores_b = {k: v // 2 for k, v in SCORING_CRITERIA.items()}
            scorecard = {
                "agent_a": half_scores_a,
                "agent_b": half_scores_b,
                "reasoning": "심판 채점 오류로 인해 동점 처리되었습니다.",
            }
            fallback_reason = "parse_error"
        except Exception as exc:
            # httpx.HTTPError, ConnectionError, asyncio.TimeoutError 등 네트워크 오류
            # 파싱 오류와 동일하게 무승부 폴백 처리 — 완료된 매치를 error로 전환하지 않음
            logger.error(
                "Judge request error | trace_id=%s mode=%s err=%s",
                trace_id,
                orchestration_mode,
                exc,
                exc_info=True,
            )
            half_scores_a = {k: v // 2 for k, v in SCORING_CRITERIA.items()}
            half_scores_b = {k: v // 2 for k, v in SCORING_CRITERIA.items()}
            scorecard = {
                "agent_a": half_scores_a,
                "agent_b": half_scores_b,
                "reasoning": "판정 요청 오류로 인해 동점 처리되었습니다.",
            }
            fallback_reason = "request_error"
        # Judge 반환 점수를 SCORING_CRITERIA 범위로 클램핑 — LLM 오버슈팅 방어
        for key, max_val in SCORING_CRITERIA.items():
            scorecard["agent_a"][key] = max(0, min(scorecard["agent_a"].get(key, 0), max_val))
            scorecard["agent_b"][key] = max(0, min(scorecard["agent_b"].get(key, 0), max_val))

        # SCORING_CRITERIA 키만 합산 — LLM이 extra key를 추가해도 score overflow 방지
        score_a = sum(scorecard["agent_a"].get(k, 0) for k in SCORING_CRITERIA)
        score_b = sum(scorecard["agent_b"].get(k, 0) for k in SCORING_CRITERIA)

        penalty_a = match.penalty_a or 0
        penalty_b = match.penalty_b or 0
        final_a = max(0, score_a - penalty_a)
        final_b = max(0, score_b - penalty_b)

        # 점수차 >= debate_draw_threshold → 승/패, 미만 → 무승부
        diff = abs(final_a - final_b)
        winner_id = (match.agent_a_id if final_a > final_b else match.agent_b_id) if diff >= settings.debate_draw_threshold else None

        return {
            "scorecard": scorecard,
            "score_a": final_a,
            "score_b": final_b,
            "penalty_a": penalty_a,
            "penalty_b": penalty_b,
            "winner_id": winner_id,
            "input_tokens": judge_input_tokens,
            "output_tokens": judge_output_tokens,
            "model_id": model_id,
            "fallback_reason": fallback_reason,
            # fallback 판정(parse_error/request_error)은 신뢰도가 낮으므로 ELO 변동 억제 권고
            "elo_suppressed": fallback_reason is not None,
        }

    def _format_debate_log(
        self,
        turns: list[DebateTurnLog],
        topic: DebateTopic,
        agent_a_name: str = "에이전트 A",
        agent_b_name: str = "에이전트 B",
    ) -> str:
        """턴 로그를 Judge LLM 입력용 텍스트로 포맷한다.

        벌점 정보와 위반 횟수 요약을 포함하여 Judge가 공정한 채점을 할 수 있도록 한다.

        Args:
            turns: DebateTurnLog 목록.
            topic: 토론 주제.
            agent_a_name: 에이전트 A 이름.
            agent_b_name: 에이전트 B 이름.

        Returns:
            Judge LLM에 전달할 포맷된 토론 전문 문자열.
        """
        lines = [f"토론 주제: {topic.title}", f"설명: {topic.description or '없음'}", ""]

        violation_counts: dict[str, dict[str, int]] = {"agent_a": {}, "agent_b": {}}

        for turn in turns:
            label = f"{agent_a_name} (찬성)" if turn.speaker == "agent_a" else f"{agent_b_name} (반대)"
            penalty_key = turn.speaker
            lines.append(f"[턴 {turn.turn_number}] {label} ({turn.action}):")
            lines.append(f"주장: {turn.claim}")
            if turn.evidence:
                lines.append(f"근거: {turn.evidence}")
            raw = turn.raw_response or {}
            if raw.get("tool_used"):
                lines.append(f"도구 사용: {raw['tool_used']}")
            if turn.penalty_total > 0:
                ko_items = ", ".join(
                    f"{PENALTY_KO_LABELS.get(k, k)} {v}점"
                    for k, v in (turn.penalties or {}).items()
                    if v
                )
                lines.append(f"벌점: -{turn.penalty_total}점 ({ko_items})")
                for violation_key in (turn.penalties or {}):
                    counts = violation_counts.get(penalty_key, {})
                    counts[violation_key] = counts.get(violation_key, 0) + 1
                    violation_counts[penalty_key] = counts
            # minor 위반은 penalty_total에 포함되지 않으나 Judge가 패턴을 인식하도록 별도 표시
            minor_violations = [
                v for v in (turn.review_result or {}).get("violations", [])
                if v.get("severity") == "minor"
            ]
            if minor_violations:
                minor_items = ", ".join(
                    PENALTY_KO_LABELS.get(v.get("type", ""), v.get("type", ""))
                    for v in minor_violations
                )
                lines.append(f"경고(벌점 없음): {minor_items}")
                for v in minor_violations:
                    vtype = v.get("type", "")
                    counts = violation_counts.get(penalty_key, {})
                    counts[vtype] = counts.get(vtype, 0) + 1
                    violation_counts[penalty_key] = counts
            lines.append("")

        lines.append("[벌점 요약]")
        lines.append(self._format_violation_summary(agent_a_name, violation_counts.get("agent_a", {})))
        lines.append(self._format_violation_summary(agent_b_name, violation_counts.get("agent_b", {})))

        return "\n".join(lines)

    def _format_violation_summary(self, name: str, violations: dict[str, int]) -> str:
        """에이전트 이름과 위반 횟수 dict를 받아 Judge용 요약 문자열 반환."""
        if not violations:
            return f"{name}: 위반 없음"
        items = ", ".join(
            f"{PENALTY_KO_LABELS.get(k, k)} {v}회"
            for k, v in violations.items()
            if v
        )
        return f"{name}: {items}"
