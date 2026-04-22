'use client';

import { useEffect, useLayoutEffect, useRef } from 'react';
import type { StreamingTurn } from '@/stores/debateStore';

type Props = {
  turn: StreamingTurn;
  agentAName: string;
  agentBName: string;
  agentAImageUrl?: string | null;
  agentBImageUrl?: string | null;
  // 타이핑이 완전히 끝난 시점에 1회 호출 — TurnBubble로 교체할 타이밍을 상위에 알림
  onTypingDone?: () => void;
  // turn SSE 이벤트가 도착한 경우 true — 모든 청크 수신 완료를 의미
  turnComplete?: boolean;
};

/**
 * 부분 JSON에서 "claim" 필드 텍스트를 추출.
 * LLM이 {"action":"...", "claim": "여기 내용..."} 형식으로 출력하므로
 * claim이 시작된 이후 텍스트만 표시해 자연스러운 타이핑 효과를 제공한다.
 */
function extractPartialClaim(raw: string): string {
  const match = raw.match(/"claim"\s*:\s*"((?:[^"\\]|\\.)*)(?:"|$)/s);
  if (match) return match[1].replace(/\\n/g, '\n').replace(/\\"/g, '"').replace(/\\\\/g, '\\');
  // JSON 형식이 아닌 평문 출력 (스키마 미준수 LLM 또는 local 에이전트) — raw 텍스트 직접 표시
  if (!raw.trim().startsWith('{')) return raw.trim();
  return '';
}

export function StreamingTurnBubble({
  turn,
  agentAName,
  agentBName,
  agentAImageUrl,
  agentBImageUrl,
  onTypingDone,
  turnComplete,
}: Props) {
  const isAgentA = turn.speaker === 'agent_a';
  const name = isAgentA ? agentAName : agentBName;
  const imageUrl = isAgentA ? agentAImageUrl : agentBImageUrl;

  // SSE 청크를 직접 표시 — 가짜 타이핑 interval 없이 실시간 반영
  // turn.raw는 appendChunk 호출마다 Zustand에서 새 객체로 교체되므로 re-render 자동 발생
  const claim = extractPartialClaim(turn.raw);

  const onDoneRef = useRef(onTypingDone);
  onDoneRef.current = onTypingDone;
  const doneFiredRef = useRef(false);

  // 턴이 바뀌면 완료 플래그 초기화
  useEffect(() => {
    doneFiredRef.current = false;
  }, [turn.turn_number, turn.speaker]);

  // turn SSE 이벤트 도착(= 모든 청크 수신 완료) → 즉시 TurnBubble 교체 신호
  useEffect(() => {
    if (turnComplete && !doneFiredRef.current) {
      doneFiredRef.current = true;
      setTimeout(() => onDoneRef.current?.(), 0);
    }
  }, [turnComplete]);

  // DOM 커밋 직후(페인트 전) 스크롤 — claim 변경마다 새 scrollHeight 기준으로 정확히 이동
  useLayoutEffect(() => {
    if (!claim) return;
    const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
    if (maxScroll <= 0 || window.scrollY >= maxScroll - 150) {
      window.scrollTo(0, document.documentElement.scrollHeight);
    }
  }, [claim]);

  return (
    <div className={`flex ${isAgentA ? 'justify-start' : 'justify-end'}`}>
      <div
        className={`max-w-[82%] rounded-xl p-3 ${
          isAgentA
            ? 'bg-bg-surface border border-border rounded-tl-none'
            : 'bg-primary/5 border border-primary/20 rounded-tr-none'
        }`}
      >
        {/* 헤더 */}
        <div className="flex items-center gap-2 mb-1.5">
          {imageUrl && (
            <img
              src={imageUrl}
              alt={name}
              className="w-5 h-5 rounded-full object-cover flex-shrink-0"
            />
          )}
          <span className="text-xs font-bold text-text">{name}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-medium animate-pulse">
            생성 중...
          </span>
          <span className="text-[10px] text-text-muted">Turn {turn.turn_number}</span>
        </div>

        {/* 실시간 SSE 텍스트 또는 대기 점 */}
        {claim ? (
          <p className="text-sm text-text whitespace-pre-wrap">
            {claim}
            {!turnComplete && (
              <span className="inline-block w-0.5 h-3.5 bg-primary animate-pulse ml-0.5 align-middle" />
            )}
          </p>
        ) : (
          <div className="flex items-center gap-1 py-1">
            <span
              className="w-1.5 h-1.5 rounded-full bg-text-muted/60 animate-bounce"
              style={{ animationDelay: '0ms' }}
            />
            <span
              className="w-1.5 h-1.5 rounded-full bg-text-muted/60 animate-bounce"
              style={{ animationDelay: '150ms' }}
            />
            <span
              className="w-1.5 h-1.5 rounded-full bg-text-muted/60 animate-bounce"
              style={{ animationDelay: '300ms' }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
