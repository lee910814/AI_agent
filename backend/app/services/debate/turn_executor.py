"""단일 턴 실행 로직. _execute_turn / _execute_turn_with_retry를 클래스로 캡슐화."""

import asyncio
import json
import logging
import re
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.debate_agent import DebateAgent, DebateAgentVersion
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog
from app.schemas.debate_ws import WSTurnRequest
from app.services.debate.broadcast import publish_event
from app.services.debate.evidence_search import EvidenceSearchService
from app.services.debate.exceptions import MatchVoidError
from app.services.debate.helpers import (
    _build_messages,
    validate_response_schema,
)
from app.services.debate.tool_executor import AVAILABLE_TOOLS, DebateToolExecutor, ToolContext
from app.services.debate.ws_manager import WSConnectionManager
from app.services.llm.inference_client import InferenceClient
from app.services.llm.providers.base import APIKeyError

logger = logging.getLogger(__name__)

_evidence_service = EvidenceSearchService()


def _build_web_search_tool(provider: str) -> list[dict]:
    """provider별 web_search tool schema 반환. RunPod/local은 빈 리스트."""
    if not settings.debate_tool_use_enabled:
        return []
    description = "현재 주장을 뒷받침하는 웹 근거 검색. 결과를 claim에 직접 인용하세요."
    query_param = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "검색 쿼리 (영어 권장)"}},
        "required": ["query"],
    }
    match provider:
        case "openai":
            return [
                {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": description,
                        "parameters": query_param,
                    },
                }
            ]
        case "anthropic":
            return [{"name": "web_search", "description": description, "input_schema": query_param}]
        case "google":
            return [
                {
                    "function_declarations": [
                        {
                            "name": "web_search",
                            "description": description,
                            "parameters": query_param,
                        }
                    ]
                }
            ]
        case _:
            return []


class TurnExecutor:
    """단일 턴 실행(LLM 스트리밍 or WebSocket) 및 재시도 로직을 담당하는 클래스."""

    def __init__(self, client: InferenceClient, db: AsyncSession) -> None:
        self.client = client
        self.db = db

    async def execute(
        self,
        match: DebateMatch,
        topic: DebateTopic,
        turn_number: int,
        speaker: str,
        agent: DebateAgent,
        version: DebateAgentVersion | None,
        api_key: str,
        my_claims: list[str],
        opponent_claims: list[str],
        my_accumulated_penalty: int = 0,
        event_meta: dict | None = None,
        prev_evidence: str | None = None,
    ) -> DebateTurnLog:
        """단일 턴을 실행하고 DB에 기록한다.

        로컬 에이전트는 WebSocket 경유, 외부 에이전트는 스트리밍 BYOK 방식으로 처리.
        실패 시 예외를 그대로 전파 — execute_with_retry()가 재시도를 담당한다.

        Args:
            match: 진행 중인 매치.
            topic: 토론 주제.
            turn_number: 현재 턴 번호.
            speaker: 발언자 ('agent_a' | 'agent_b').
            agent: 발언 에이전트.
            version: 에이전트 버전 스냅샷. 없으면 기본 프롬프트 사용.
            api_key: LLM BYOK 또는 플랫폼 API 키.
            my_claims: 본인의 이전 발언 목록.
            opponent_claims: 상대방의 이전 발언 목록.
            my_accumulated_penalty: 이번 턴 이전까지 누적 벌점.

        Returns:
            DB에 저장된 DebateTurnLog 객체.

        Raises:
            TimeoutError: 턴 타임아웃 초과.
            APIKeyError: API 키 인증 실패.
            Exception: 기타 LLM/WebSocket 오류.
        """
        from app.services.debate.debate_formats import _log_orchestrator_usage

        default_prompt = "당신은 한국어 토론 참가자입니다. 반드시 한국어로만 답변하세요."
        system_prompt = version.system_prompt if version else default_prompt

        penalties: dict[str, int] = {}
        penalty_total = 0
        action = "argue"
        claim = ""
        evidence = None
        raw_response = None
        input_tokens = 0
        output_tokens = 0
        response_time_ms: int | None = None

        try:
            if agent.provider == "local":
                # WebSocket 경유 턴 요청 — 응답 시간 측정
                ws_manager = WSConnectionManager.get_instance()
                ws_topic_description = topic.description
                judge_intro = (getattr(topic, "judge_intro", None) or "").strip()
                if judge_intro:
                    base_desc = (topic.description or "").strip()
                    ws_topic_description = (
                        f"{base_desc}\n\n[judge_intro]\n{judge_intro}"
                        if base_desc
                        else f"[judge_intro]\n{judge_intro}"
                    )
                ws_request = WSTurnRequest(
                    match_id=match.id,
                    turn_number=turn_number,
                    speaker=speaker,
                    topic_title=topic.title,
                    topic_description=ws_topic_description,
                    max_turns=topic.max_turns,
                    turn_token_limit=topic.turn_token_limit,
                    my_previous_claims=my_claims,
                    opponent_previous_claims=opponent_claims,
                    time_limit_seconds=settings.debate_turn_timeout_seconds,
                    # tools_enabled=False이면 빈 목록 전달 → 에이전트가 툴 사용 불가
                    available_tools=AVAILABLE_TOOLS if topic.tools_enabled else [],
                )
                tool_ctx = ToolContext(
                    turn_number=turn_number,
                    max_turns=topic.max_turns,
                    speaker=speaker,
                    my_previous_claims=my_claims,
                    opponent_previous_claims=opponent_claims,
                    my_penalty_total=my_accumulated_penalty,
                )
                start_time = time.monotonic()
                ws_response = await asyncio.wait_for(
                    ws_manager.request_turn(
                        match.id,
                        agent.id,
                        ws_request,
                        tool_executor=DebateToolExecutor(),
                        tool_context=tool_ctx,
                    ),
                    timeout=settings.debate_turn_timeout_seconds,
                )
                elapsed = time.monotonic() - start_time
                response_time_ms = int(elapsed * 1000)

                action = ws_response.action
                claim = ws_response.claim
                evidence = ws_response.evidence
                raw_response = {
                    "action": ws_response.action,
                    "claim": ws_response.claim,
                    "evidence": ws_response.evidence,
                    "tool_used": ws_response.tool_used,
                    "tool_result": ws_response.tool_result,
                }

                # local 에이전트도 프론트 타이핑 애니메이션 활성화 — claim 전체를 단일 chunk로 발행
                # event_meta가 turn_number/speaker/chunk를 덮어쓰지 못하도록 역순 병합
                chunk_payload = {
                    **(event_meta or {}),
                    "turn_number": turn_number,
                    "speaker": speaker,
                    "chunk": json.dumps({"action": action, "claim": claim}, ensure_ascii=False),
                }
                try:
                    await publish_event(str(match.id), "turn_chunk", chunk_payload)
                except Exception as pub_exc:
                    logger.warning("SSE 발행 실패 (turn %d %s): %s", turn_number, speaker, pub_exc)

            else:
                # 스트리밍 BYOK — 토큰별로 turn_chunk 이벤트 발행
                # tool-use 미지원 provider: pre-fetch 검색 결과를 메시지에 주입
                prefetch_evidence: str | None = None
                if (
                    settings.debate_tool_use_enabled
                    and topic.tools_enabled
                    and agent.provider not in ("openai", "anthropic", "google")
                ):
                    prefetch_query = topic.title + (" " + opponent_claims[-1] if opponent_claims else "")
                    try:
                        prefetch_result = await asyncio.wait_for(
                            _evidence_service.search(prefetch_query, topic=topic.title),
                            timeout=5.0,
                        )
                        if prefetch_result:
                            prefetch_evidence = prefetch_result.format()
                    except Exception as exc:
                        logger.warning("Pre-fetch evidence failed for %s: %s", speaker, exc)

                messages = _build_messages(
                    system_prompt,
                    topic,
                    turn_number,
                    speaker,
                    my_claims,
                    opponent_claims,
                    prefetch_evidence=prefetch_evidence,
                    prev_evidence=prev_evidence,
                )
                start_time = time.monotonic()
                usage_out: dict = {}
                full_text = ""

                # tool-use 지원 여부 판단
                # topic.tools_enabled가 False이면 provider가 지원하더라도 도구를 제공하지 않음
                web_search_tools = _build_web_search_tool(agent.provider) if topic.tools_enabled else []
                tool_used_flag = False
                tool_result_content = None
                tool_raw_content = None
                # Stage1+Stage2 합산 시간을 전체 debate_turn_timeout_seconds 이하로 제한
                deadline = time.monotonic() + settings.debate_turn_timeout_seconds

                if web_search_tools:
                    # 1단계: 비스트리밍 호출 (tool_call 여부 확인)
                    stage1_timeout = min(settings.debate_turn_timeout_seconds * 0.3, 15.0)
                    try:
                        tool_choice_val = {"type": "auto"} if agent.provider == "anthropic" else "auto"
                        stage1 = await asyncio.wait_for(
                            self.client.generate_byok(
                                provider=agent.provider,
                                model_id=agent.model_id,
                                api_key=api_key,
                                messages=messages,
                                tools=web_search_tools,
                                tool_choice=tool_choice_val,
                                max_tokens=topic.turn_token_limit,
                                temperature=0.7,
                            ),
                            timeout=stage1_timeout,
                        )
                    except Exception as exc:
                        logger.warning("Tool-use stage1 failed (%s), falling back to stream-only: %s", speaker, exc)
                        stage1 = {}

                    tool_calls = stage1.get("tool_calls", [])
                    if tool_calls:
                        try:
                            query = json.loads(tool_calls[0]["function"]["arguments"]).get("query", "")
                        except json.JSONDecodeError:
                            logger.warning("tool_call arguments parse failed, skipping search")
                            query = ""
                        try:
                            await publish_event(
                                str(match.id),
                                "turn_tool_call",
                                {
                                    **(event_meta or {}),
                                    "turn_number": turn_number,
                                    "speaker": speaker,
                                    "tool_name": "web_search",
                                    "query": query,
                                },
                            )
                        except Exception as exc:
                            logger.warning("turn_tool_call SSE failed: %s", exc)
                        # 합성 맥락: 상대 마지막 발언 → 없으면 토픽 제목으로 대체
                        synthesis_claim = opponent_claims[-1] if opponent_claims else topic.title
                        search_result = (
                            await _evidence_service.search_by_query(
                                query, claim=synthesis_claim, topic=topic.title
                            )
                            if query
                            else None
                        )
                        tool_result_content = search_result.format() if search_result else "검색 결과 없음"
                        tool_raw_content = search_result.raw_content if search_result else None
                        tool_used_flag = True
                        messages.append(
                            {
                                "role": "assistant",
                                "content": stage1.get("content") or "",
                                "tool_calls": tool_calls,
                            }
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_calls[0]["id"],
                                # name 포함 — Google _to_gemini_format()이 functionResponse name으로 사용
                                "name": tool_calls[0]["function"]["name"],
                                "content": tool_result_content,
                            }
                        )
                        input_tokens += stage1.get("input_tokens", 0)
                        output_tokens += stage1.get("output_tokens", 0)

                # 2단계: 스트리밍 발언 생성
                stream_kwargs: dict = {}
                if web_search_tools and tool_used_flag:
                    stream_kwargs["tools"] = web_search_tools

                remaining = max(deadline - time.monotonic(), 1.0)
                async with asyncio.timeout(remaining):
                    async for chunk in self.client.generate_stream_byok(
                        provider=agent.provider,
                        model_id=agent.model_id,
                        api_key=api_key,
                        messages=messages,
                        usage_out=usage_out,
                        max_tokens=topic.turn_token_limit,
                        temperature=0.7,
                        **stream_kwargs,
                    ):
                        full_text += chunk
                        # event_meta가 turn_number/speaker/chunk를 덮어쓰지 못하도록 역순 병합
                        chunk_payload = {
                            **(event_meta or {}),
                            "turn_number": turn_number,
                            "speaker": speaker,
                            "chunk": chunk,
                        }
                        try:
                            await publish_event(str(match.id), "turn_chunk", chunk_payload)
                        except Exception as pub_exc:
                            logger.warning("SSE 발행 실패 (turn %d %s): %s", turn_number, speaker, pub_exc)

                elapsed = time.monotonic() - start_time
                response_time_ms = int(elapsed * 1000)

                response_text = full_text
                parsed = validate_response_schema(response_text)
                # 2단계 토큰 합산
                input_tokens += usage_out.get("input_tokens", 0)
                output_tokens += usage_out.get("output_tokens", 0)

                if parsed is None:
                    # JSON 파싱 불가 또는 스키마 불일치 — 원문을 발언으로 사용
                    # 500자 하드코딩 제거 — 토픽 설정과 무관하게 잘리는 문제 방지
                    if usage_out.get("finish_reason") == "length":
                        # max_tokens 초과로 JSON이 중간에 잘린 경우 — claim 필드만 직접 추출
                        m = re.search(r'"claim"\s*:\s*"((?:[^"\\]|\\.)*)', response_text)
                        claim = m.group(1) if m else response_text[:1500]
                    else:
                        claim = response_text[:1500]
                    raw_response = {"raw": response_text}
                else:
                    action = parsed["action"]
                    claim = parsed["claim"]
                    evidence = parsed.get("evidence")
                    raw_response = {
                        "action": parsed["action"],
                        "claim": parsed["claim"],
                        "evidence": parsed.get("evidence"),
                        "tool_used": "web_search" if tool_used_flag else parsed.get("tool_used"),
                        "tool_result": tool_result_content if tool_used_flag else parsed.get("tool_result"),
                        "tool_raw_content": tool_raw_content if tool_used_flag else None,
                    }
                # 토픽 turn_token_limit 초과로 응답이 절삭됨 — 메타 정보만 추가
                if usage_out.get("finish_reason") == "length" and isinstance(raw_response, dict):
                    raw_response["finish_reason"] = "length"

        except Exception:
            # TimeoutError 포함 모든 예외를 그대로 전파 — execute_with_retry가 재시도·부전패 처리
            raise

        # BYOK 에이전트 턴 토큰 사용량 기록 (테스트 매치 포함)
        if agent.provider != "local":
            await _log_orchestrator_usage(
                self.db, agent.owner_id, agent.model_id, input_tokens, output_tokens, match_id=match.id
            )

        _tool_used = raw_response.get("tool_used") if isinstance(raw_response, dict) else None
        _tool_result = raw_response.get("tool_result") if isinstance(raw_response, dict) else None
        turn = DebateTurnLog(
            match_id=match.id,
            turn_number=turn_number,
            speaker=speaker,
            agent_id=agent.id,
            action=action,
            claim=claim,
            evidence=evidence,
            raw_response=raw_response,
            tool_used=_tool_used,
            tool_result=_tool_result,
            penalties=penalties if penalties else None,
            penalty_total=penalty_total,
            response_time_ms=response_time_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        self.db.add(turn)
        await self.db.flush()
        return turn

    async def execute_with_retry(
        self,
        match: DebateMatch,
        topic: DebateTopic,
        turn_number: int,
        speaker: str,
        agent: DebateAgent,
        version: DebateAgentVersion | None,
        api_key: str,
        my_claims: list[str],
        opponent_claims: list[str],
        my_accumulated_penalty: int = 0,
        event_meta: dict | None = None,
        prev_evidence: str | None = None,
    ) -> DebateTurnLog | None:
        """재시도 로직을 포함한 턴 실행. 모든 재시도 실패 시 None을 반환한다.

        APIKeyError는 1회만 재시도 후 MatchVoidError로 변환.
        그 외 예외는 debate_turn_max_retries 횟수까지 재시도 후 None 반환.

        Args:
            match: 진행 중인 매치.
            topic: 토론 주제.
            turn_number: 현재 턴 번호.
            speaker: 발언자 ('agent_a' | 'agent_b').
            agent: 발언 에이전트.
            version: 에이전트 버전 스냅샷.
            api_key: LLM API 키.
            my_claims: 본인의 이전 발언 목록.
            opponent_claims: 상대방의 이전 발언 목록.
            my_accumulated_penalty: 누적 벌점.

        Returns:
            성공 시 DebateTurnLog, 모든 재시도 실패 시 None.

        Raises:
            MatchVoidError: APIKeyError가 2회 연속 발생한 경우 (기술적 장애).
        """
        for attempt in range(settings.debate_turn_max_retries + 1):
            try:
                return await self.execute(
                    match,
                    topic,
                    turn_number,
                    speaker,
                    agent,
                    version,
                    api_key,
                    my_claims,
                    opponent_claims,
                    my_accumulated_penalty=my_accumulated_penalty,
                    event_meta=event_meta,
                    prev_evidence=prev_evidence,
                )
            except APIKeyError as exc:
                if attempt == 0:
                    # 일시적 인증 오류 가능성 — 1회 재시도
                    logger.warning(
                        "API key error on attempt 1 (turn %d %s): %s", turn_number, speaker, type(exc).__name__
                    )
                    await asyncio.sleep(1.0)
                    continue
                # 2회 연속 실패 → 기술적 장애로 매치 무효화
                raise MatchVoidError(
                    f"API key authentication failed after retry for agent {getattr(agent, 'id', 'unknown')}: {exc}"
                ) from exc
            except Exception as exc:
                if attempt < settings.debate_turn_max_retries:
                    logger.warning(
                        "Turn %d %s failed (attempt %d/%d): %s — retrying",
                        turn_number,
                        speaker,
                        attempt + 1,
                        settings.debate_turn_max_retries + 1,
                        exc,
                    )
                else:
                    logger.error(
                        "Turn %d %s failed after %d attempts: %s — forfeit",
                        turn_number,
                        speaker,
                        settings.debate_turn_max_retries + 1,
                        exc,
                    )
                    return None
