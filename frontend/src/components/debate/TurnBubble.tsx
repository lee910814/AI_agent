'use client';

import { memo, useState } from 'react';
import {
  AlertTriangle,
  ShieldAlert,
  Wrench,
  ChevronDown,
  ChevronRight,
  Ban,
  Loader2,
} from 'lucide-react';
import type { TurnLog, TurnReview } from '@/stores/debateStore';

type Props = {
  turn: TurnLog;
  agentAName: string;
  agentBName: string;
  agentAImageUrl?: string | null;
  agentBImageUrl?: string | null;
  review?: Pick<
    TurnReview,
    'logic_score' | 'violations' | 'feedback' | 'blocked' | 'skipped'
  > | null;
  displayClaim?: string; // 리플레이 스트리밍 시 부분 텍스트 오버라이드
  searching?: { speaker: string; query: string } | null;
};

const ACTION_STYLES: Record<string, string> = {
  argue: 'bg-blue-500/10 text-blue-500',
  rebut: 'bg-orange-500/10 text-orange-500',
  concede: 'bg-green-500/10 text-green-500',
  question: 'bg-purple-500/10 text-purple-500',
  summarize: 'bg-text-muted/10 text-text-muted',
};

const ACTION_LABELS: Record<string, string> = {
  argue: '주장',
  rebut: '반박',
  concede: '인정',
  question: '질문',
  summarize: '요약',
};

/** 벌점 키 → 한국어 레이블 + 설명 */
const PENALTY_INFO: Record<string, { label: string; desc: string }> = {
  schema_violation: { label: 'JSON 형식 위반', desc: '응답이 요구된 JSON 스키마를 따르지 않음' },
  repetition: { label: '주장 반복', desc: '이전 턴과 지나치게 유사한 주장을 반복함' },
  prompt_injection: { label: '프롬프트 인젝션', desc: '시스템 지시를 무력화하려는 패턴이 감지됨' },
  timeout: { label: '응답 시간 초과', desc: '제한 시간 내에 응답하지 못함' },
  false_source: { label: '허위 출처 인용', desc: '존재하지 않는 데이터·인용을 사용함' },
  ad_hominem: { label: '인신공격', desc: '논거 대신 상대방을 직접 비하하는 표현 사용' },
  human_suspicion: { label: '인간 개입 의심', desc: '응답 패턴이 AI가 아닌 인간의 개입을 암시함' },
  // LLM 검토 기반 벌점 (llm_ 접두사)
  llm_prompt_injection: {
    label: '[LLM] 프롬프트 인젝션',
    desc: 'LLM 검토: 시스템 지시를 무력화하려는 시도 감지',
  },
  llm_ad_hominem: {
    label: '[LLM] 인신공격',
    desc: 'LLM 검토: 논거 대신 상대방을 직접 비하하는 표현',
  },
  llm_straw_man: { label: '[LLM] 허수아비 논증', desc: 'LLM 검토: 상대 주장을 왜곡·과장해 반박' },
  llm_circular_reasoning: {
    label: '[LLM] 순환논증',
    desc: 'LLM 검토: 결론을 전제로 반복하는 논증 오류',
  },
  llm_hasty_generalization: {
    label: '[LLM] 성급한 일반화',
    desc: 'LLM 검토: 일부 사례로 전체를 단정하는 일반화 오류',
  },
  llm_accent: {
    label: '[LLM] 강조의 오류',
    desc: 'LLM 검토: 특정 표현만 강조하거나 맥락을 제거해 의미 왜곡',
  },
  llm_genetic_fallacy: {
    label: '[LLM] 유전적 오류',
    desc: 'LLM 검토: 출처·배경만 근거로 현재 가치나 진위를 판단',
  },
  llm_appeal: {
    label: '[LLM] 부적절한 호소',
    desc: 'LLM 검토: 동정·위협 등 감정/힘에 호소해 결론을 유도',
  },
  llm_slippery_slope: {
    label: '[LLM] 미끄러운 경사',
    desc: 'LLM 검토: 근거 없이 연쇄적 파국을 단정하는 오류',
  },
  llm_division: {
    label: '[LLM] 분할의 오류',
    desc: 'LLM 검토: 전체의 성질을 부분에도 그대로 적용',
  },
  llm_composition: {
    label: '[LLM] 합성의 오류',
    desc: 'LLM 검토: 부분의 속성을 전체의 속성으로 일반화',
  },
  llm_off_topic: { label: '[LLM] 주제 이탈', desc: 'LLM 검토: 토론 주제와 무관한 내용이 포함됨' },
  llm_false_claim: {
    label: '[LLM] 허위 주장',
    desc: 'LLM 검토: 사실 확인이 불가능하거나 허위인 주장',
  },
};

/** 툴 이름 → 한국어 */
const TOOL_LABELS: Record<string, string> = {
  calculator: '계산기',
  stance_tracker: '주장 추적',
  opponent_summary: '상대 요약',
  turn_info: '턴 정보',
  web_search: '웹 검색',
};

function LogicScoreBar({ score }: { score: number | null }) {
  if (score == null) return null;
  const pct = (score / 10) * 100;
  const color = score >= 7 ? 'bg-emerald-500' : score >= 4 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-bg rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] font-semibold text-text-muted w-6 text-right">{score}/10</span>
    </div>
  );
}

// SSE 스트리밍 중 매 청크마다 완료된 턴이 불필요하게 재렌더링되는 것을 방지
export const TurnBubble = memo(function TurnBubble({
  turn,
  agentAName,
  agentBName,
  agentAImageUrl,
  agentBImageUrl,
  review,
  displayClaim,
  searching,
}: Props) {
  const isAgentA = turn.speaker === 'agent_a';
  const name = isAgentA ? agentAName : agentBName;
  const imageUrl = isAgentA ? agentAImageUrl : agentBImageUrl;
  const [toolExpanded, setToolExpanded] = useState(false);
  const [reviewExpanded, setReviewExpanded] = useState(false);
  const claimText = displayClaim ?? turn.claim;

  const hasReviewContent =
    (turn.penalty_total > 0 && turn.penalties != null) ||
    turn.human_suspicion_score > 30 ||
    (review != null &&
      !review.skipped &&
      (review.logic_score != null || (review.violations?.length ?? 0) > 0 || review.blocked));

  return (
    <div className={`flex ${isAgentA ? 'justify-start' : 'justify-end'}`}>
      <div
        className={`max-w-[82%] rounded-xl p-3 ${
          isAgentA
            ? 'bg-bg-surface border border-border rounded-tl-none'
            : 'bg-primary/5 border border-primary/20 rounded-tr-none'
        }`}
      >
        {/* 헤더: 아바타 + 이름 + 액션 배지 + 턴 번호 */}
        <div className="flex items-center gap-2 mb-1.5">
          {imageUrl && (
            <img
              src={imageUrl}
              alt={name}
              className="w-5 h-5 rounded-full object-cover flex-shrink-0"
            />
          )}
          <span className="text-xs font-bold text-text">{name}</span>
          <span
            className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
              ACTION_STYLES[turn.action] || ACTION_STYLES.argue
            }`}
          >
            {ACTION_LABELS[turn.action] || turn.action}
          </span>
          <span className="text-[10px] text-text-muted">Turn {turn.turn_number}</span>
          {turn.tool_used && (
            <span className="flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600 font-medium">
              <Wrench size={9} />
              {TOOL_LABELS[turn.tool_used] || turn.tool_used}
            </span>
          )}
        </div>

        {/* 주장 본문 */}
        <p className="text-sm text-text whitespace-pre-wrap break-words">
          {claimText}
          {displayClaim != null && (
            <span className="inline-block w-0.5 h-3.5 bg-primary animate-pulse ml-0.5 align-middle" />
          )}
        </p>

        {/* 근거 검색 중 스피너 */}
        {searching && (
          <div className="flex items-center gap-1.5 mt-1.5 text-[11px] text-text-muted">
            <Loader2 size={11} className="animate-spin text-primary" />
            <span>근거 검색 중: &ldquo;{searching.query}&rdquo;</span>
          </div>
        )}

        {/* 근거 */}
        {turn.evidence &&
          (() => {
            // "[출처: URL1 | URL2]" 패턴 파싱 — DuckDuckGo 검색 결과 출처를 클릭 링크로 렌더링
            const sourceMatch = turn.evidence.match(/\[출처:\s*(.+?)\]$/s);
            const bodyText = sourceMatch
              ? turn.evidence.slice(0, turn.evidence.lastIndexOf('[출처:')).trim()
              : turn.evidence;
            const sourceUrls = sourceMatch
              ? sourceMatch[1]
                  .split('|')
                  .map((u) => u.trim())
                  .filter(Boolean)
              : [];
            return (
              <div className="mt-2 px-2.5 py-1.5 bg-bg rounded border border-border">
                <span className="text-[10px] text-text-muted font-semibold">근거</span>
                <p className="text-xs text-text-secondary mt-0.5 whitespace-pre-wrap">{bodyText}</p>
                {sourceUrls.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5">
                    <span className="text-[10px] text-text-muted">출처:</span>
                    {sourceUrls.map((url) => (
                      <a
                        key={url}
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[10px] text-primary underline break-all"
                      >
                        {url}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            );
          })()}

        {/* 툴 사용 내역 */}
        {turn.tool_used && (
          <div className="mt-2 border border-emerald-500/20 rounded-lg bg-emerald-500/5 overflow-hidden">
            <button
              type="button"
              onClick={() => setToolExpanded(!toolExpanded)}
              className="w-full flex items-center gap-1.5 px-2.5 py-1.5 text-left"
            >
              <Wrench size={11} className="text-emerald-500 shrink-0" />
              <span className="text-[11px] font-semibold text-emerald-600">
                툴 사용: {TOOL_LABELS[turn.tool_used] || turn.tool_used}
              </span>
              {toolExpanded ? (
                <ChevronDown size={11} className="text-emerald-500 ml-auto" />
              ) : (
                <ChevronRight size={11} className="text-emerald-500 ml-auto" />
              )}
            </button>
            {toolExpanded && (
              <div className="px-2.5 pb-2 border-t border-emerald-500/20">
                {turn.tool_result ? (
                  <>
                    <p className="text-[10px] text-text-muted mt-1 mb-0.5">실행 결과</p>
                    <pre className="text-xs text-text-secondary whitespace-pre-wrap font-mono bg-bg rounded p-1.5 overflow-x-auto">
                      {turn.tool_result}
                    </pre>
                  </>
                ) : (
                  <p className="text-[11px] text-text-muted mt-1.5">검색 결과를 가져오지 못했습니다.</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* 검토 결과 토글 버튼 — 검토할 내용이 있을 때만 표시 */}
        {hasReviewContent && (
          <button
            type="button"
            onClick={() => setReviewExpanded(!reviewExpanded)}
            className="mt-2 flex items-center gap-1 text-[11px] text-text-muted hover:text-text transition-colors"
          >
            {reviewExpanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
            {reviewExpanded ? '검토 결과 접기' : '검토 결과 보기'}
            {!reviewExpanded && turn.penalty_total > 0 && (
              <span className="text-red-400 font-semibold ml-1">(-{turn.penalty_total})</span>
            )}
          </button>
        )}

        {/* 벌점 내역 — 접힘 시 숨김 */}
        {reviewExpanded && turn.penalty_total > 0 && turn.penalties && (
          <div className="mt-2 border border-red-500/20 rounded-lg bg-red-500/5 px-2.5 py-2 space-y-1">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-red-400">
              <AlertTriangle size={12} />
              <span>벌점 -{turn.penalty_total}점</span>
            </div>
            {Object.entries(turn.penalties).map(([key, value]) => {
              const info = PENALTY_INFO[key];
              return (
                <div key={key} className="flex items-start gap-2 text-[11px]">
                  <span className="shrink-0 text-red-400 font-semibold mt-0.5">-{value}</span>
                  <div>
                    <span className="text-text font-medium">{info?.label || key}</span>
                    {info?.desc && <span className="text-text-muted ml-1">— {info.desc}</span>}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* 인간 의심 경보 — 접힘 시 숨김 */}
        {reviewExpanded && turn.human_suspicion_score > 30 && (
          <div
            className={`mt-2 flex items-center gap-1.5 text-xs ${
              turn.human_suspicion_score > 60 ? 'text-red-500' : 'text-yellow-500'
            }`}
          >
            <ShieldAlert size={12} />
            <span>인간 개입 {turn.human_suspicion_score > 60 ? '강한 의심' : '의심'}</span>
            <span className="text-text-muted text-[10px]">
              (점수: {turn.human_suspicion_score})
            </span>
          </div>
        )}

        {/* fast path 통과 — 규칙 위반 없음 라벨 */}
        {review && review.skipped && (
          <div className="mt-2 flex items-center gap-1.5 text-[11px] text-text-muted">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500" />
            <span>빠른 통과 — 규칙 위반 없음</span>
          </div>
        )}

        {/* LLM 검토 결과 — 접힘 시 숨김 */}
        {reviewExpanded &&
          review &&
          !review.skipped &&
          (review.logic_score != null ||
            (review.violations?.length ?? 0) > 0 ||
            review.blocked) && (
            <div className="mt-2 border border-border rounded-lg bg-bg px-2.5 py-2 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-semibold text-text-muted">논증 품질</span>
                {review.blocked && (
                  <div className="flex items-center gap-1 text-[10px] font-bold text-red-500">
                    <Ban size={10} />
                    <span>차단됨</span>
                  </div>
                )}
              </div>
              <LogicScoreBar score={review.logic_score} />
              {review.feedback && (
                <p className="text-[11px] text-text-secondary italic">{review.feedback}</p>
              )}
            </div>
          )}

        {/* 메타 정보 */}
        <div className="mt-1.5 flex items-center gap-3 text-[10px] text-text-muted">
          <span>{turn.input_tokens + turn.output_tokens} 토큰</span>
          {turn.response_time_ms != null && (
            <span>{(turn.response_time_ms / 1000).toFixed(1)}s</span>
          )}
        </div>
      </div>
    </div>
  );
});

TurnBubble.displayName = 'TurnBubble';
