'use client';

import { useState } from 'react';
import {
  X,
  Ban,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Shield,
  Clock,
  Cpu,
  Wrench,
  Award,
} from 'lucide-react';

// ─── 타입 ───────────────────────────────────────────────────────────────────

type DebugTurn = {
  id: string;
  turn_number: number;
  speaker: string;
  action: string;
  claim: string;
  evidence: string | null;
  raw_response: Record<string, unknown> | null;
  review_result: {
    logic_score: number;
    violations: { type: string; severity: string; detail: string }[];
    feedback: string;
    block: boolean;
  } | null;
  penalties: Record<string, number> | null;
  penalty_total: number;
  is_blocked: boolean;
  human_suspicion_score: number;
  response_time_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  tool_used: string | null;
  tool_result: string | null;
  created_at: string;
};

type DebugMatchAgent = {
  id: string;
  name: string;
  provider: string;
  model_id: string;
};

type DebugMatch = {
  id: string;
  topic_title: string;
  agent_a: DebugMatchAgent;
  agent_b: DebugMatchAgent;
  status: string;
  winner_id: string | null;
  score_a: number;
  score_b: number;
  penalty_a: number;
  penalty_b: number;
  scorecard: {
    agent_a: Record<string, number>;
    agent_b: Record<string, number>;
    reasoning: string;
  } | null;
  started_at: string | null;
  finished_at: string | null;
};

export type DebugData = {
  match: DebugMatch;
  turns: DebugTurn[];
};

type Props = {
  data: DebugData;
  onClose: () => void;
};

// ─── 상수 ───────────────────────────────────────────────────────────────────

const ACTION_LABELS: Record<string, string> = {
  argue: '주장',
  rebut: '반박',
  concede: '인정',
  question: '질문',
  summarize: '요약',
};

const PENALTY_LABELS: Record<string, string> = {
  schema_violation: 'JSON 형식 위반',
  repetition: '주장 반복',
  prompt_injection: '프롬프트 인젝션',
  timeout: '응답 시간 초과',
  false_source: '허위 출처 인용',
  ad_hominem: '인신공격',
  straw_man: '허수아비 논증',
  circular_reasoning: '순환논증',
  hasty_generalization: '성급한 일반화',
  accent: '강조의 오류',
  genetic_fallacy: '유전적 오류',
  appeal: '부적절한 호소',
  slippery_slope: '미끄러운 경사',
  division: '분할의 오류',
  composition: '합성의 오류',
  off_topic: '주제 이탈',
  false_claim: '허위 주장',
  human_suspicion: '인간 개입 의심',
  llm_prompt_injection: '[LLM] 프롬프트 인젝션',
  llm_ad_hominem: '[LLM] 인신공격',
  llm_straw_man: '[LLM] 허수아비 논증',
  llm_circular_reasoning: '[LLM] 순환논증',
  llm_hasty_generalization: '[LLM] 성급한 일반화',
  llm_accent: '[LLM] 강조의 오류',
  llm_genetic_fallacy: '[LLM] 유전적 오류',
  llm_appeal: '[LLM] 부적절한 호소',
  llm_slippery_slope: '[LLM] 미끄러운 경사',
  llm_division: '[LLM] 분할의 오류',
  llm_composition: '[LLM] 합성의 오류',
  llm_off_topic: '[LLM] 주제 이탈',
  llm_false_claim: '[LLM] 허위 주장',
};

const MATCH_STATUS_LABELS: Record<string, string> = {
  pending: '대기',
  in_progress: '진행 중',
  completed: '완료',
  error: '오류',
  waiting_agent: '에이전트 대기',
  forfeit: '몰수패',
};

type Filter = 'all' | 'blocked' | 'penalized';

// ─── 논증 점수 바 ────────────────────────────────────────────────────────────

function LogicBar({ score }: { score: number }) {
  const pct = (score / 10) * 100;
  const color = score >= 7 ? 'bg-emerald-500' : score >= 4 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-bg rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[11px] font-semibold text-text-muted w-8 text-right">{score}/10</span>
    </div>
  );
}

// ─── 개별 턴 카드 ────────────────────────────────────────────────────────────

function TurnDebugCard({
  turn,
  agentAName,
  agentBName,
}: {
  turn: DebugTurn;
  agentAName: string;
  agentBName: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [rawOpen, setRawOpen] = useState(false);

  const isAgentA = turn.speaker === 'agent_a';
  const name = isAgentA ? agentAName : agentBName;

  return (
    <div
      className={`border rounded-lg overflow-hidden ${
        turn.is_blocked
          ? 'border-red-500/40 bg-red-500/5'
          : turn.penalty_total > 0
            ? 'border-orange-500/30 bg-orange-500/5'
            : 'border-border bg-bg-surface'
      }`}
    >
      {/* 헤더 — 항상 표시 */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-black/5 transition-colors"
      >
        {/* 턴 번호 */}
        <span className="text-[11px] font-mono text-text-muted w-8 shrink-0">
          T{turn.turn_number}
        </span>

        {/* 발화자 배지 */}
        <span
          className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold shrink-0 ${
            isAgentA ? 'bg-blue-500/15 text-blue-400' : 'bg-violet-500/15 text-violet-400'
          }`}
        >
          {name}
        </span>

        {/* 액션 배지 */}
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-bg text-text-muted border border-border font-medium shrink-0">
          {ACTION_LABELS[turn.action] ?? turn.action}
        </span>

        {/* 차단 배지 */}
        {turn.is_blocked && (
          <span className="flex items-center gap-0.5 text-[10px] font-bold text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded shrink-0">
            <Ban size={9} />
            차단
          </span>
        )}

        {/* 벌점 배지 */}
        {turn.penalty_total > 0 && (
          <span className="flex items-center gap-0.5 text-[10px] font-bold text-orange-400 bg-orange-500/10 px-1.5 py-0.5 rounded shrink-0">
            <AlertTriangle size={9} />-{turn.penalty_total}
          </span>
        )}

        {/* 인간 의심 배지 */}
        {turn.human_suspicion_score > 30 && (
          <span
            className={`flex items-center gap-0.5 text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0 ${
              turn.human_suspicion_score > 60
                ? 'text-red-400 bg-red-500/10'
                : 'text-yellow-500 bg-yellow-500/10'
            }`}
          >
            <Shield size={9} />
            {turn.human_suspicion_score}
          </span>
        )}

        {/* 주장 미리보기 */}
        <span className="flex-1 text-xs text-text-muted truncate min-w-0">
          {turn.claim.slice(0, 80)}
          {turn.claim.length > 80 ? '...' : ''}
        </span>

        {/* 토큰 수 */}
        <span className="text-[10px] text-text-muted shrink-0 font-mono">
          {turn.input_tokens + turn.output_tokens}tok
        </span>

        {expanded ? (
          <ChevronDown size={14} className="text-text-muted shrink-0" />
        ) : (
          <ChevronRight size={14} className="text-text-muted shrink-0" />
        )}
      </button>

      {/* 펼친 상세 내용 */}
      {expanded && (
        <div className="px-3 pb-3 pt-2 space-y-3 border-t border-border/60">
          {/* 주장 전문 */}
          <div>
            <p className="text-[10px] text-text-muted font-semibold mb-1 flex items-center gap-1">
              주장 (claim)
              {turn.is_blocked && (
                <span className="text-red-400 flex items-center gap-0.5">
                  <Ban size={9} />
                  차단됨
                </span>
              )}
            </p>
            <p
              className={`text-sm whitespace-pre-wrap leading-relaxed rounded p-2.5 bg-bg border border-border ${
                turn.is_blocked ? 'text-red-400' : 'text-text'
              }`}
            >
              {turn.claim}
            </p>
          </div>

          {/* 근거 */}
          {turn.evidence && (
            <div>
              <p className="text-[10px] text-text-muted font-semibold mb-1">근거 (evidence)</p>
              <p className="text-xs text-text-secondary whitespace-pre-wrap bg-bg rounded px-2.5 py-2 border border-border">
                {turn.evidence}
              </p>
            </div>
          )}

          {/* LLM 검토 결과 */}
          {turn.review_result && (
            <div className="bg-bg rounded-lg p-2.5 border border-border space-y-2">
              <p className="text-[10px] font-semibold text-text-muted">LLM 검토 결과</p>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-text-muted w-16 shrink-0">논증 점수</span>
                <LogicBar score={turn.review_result.logic_score} />
              </div>
              {turn.review_result.feedback && (
                <p className="text-[11px] italic text-text-secondary">
                  &ldquo;{turn.review_result.feedback}&rdquo;
                </p>
              )}
              {turn.review_result.violations && turn.review_result.violations.length > 0 && (
                <div className="space-y-1 pt-1 border-t border-border/60">
                  <p className="text-[10px] text-text-muted font-semibold">위반 항목</p>
                  {turn.review_result.violations.map((v, i) => (
                    <div key={i} className="flex items-start gap-1.5 text-[11px]">
                      <span
                        className={`font-bold shrink-0 ${
                          v.severity === 'severe' ? 'text-red-400' : 'text-orange-400'
                        }`}
                      >
                        [{v.severity}]
                      </span>
                      <span className="text-text font-medium">
                        {PENALTY_LABELS[v.type] ?? v.type}
                      </span>
                      {v.detail && <span className="text-text-muted"> — {v.detail}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 벌점 내역 */}
          {turn.penalty_total > 0 && turn.penalties && (
            <div className="bg-orange-500/5 rounded-lg p-2.5 border border-orange-500/20">
              <p className="text-[10px] font-semibold text-orange-400 mb-1.5">
                벌점 합계: -{turn.penalty_total}
              </p>
              <div className="space-y-1">
                {Object.entries(turn.penalties).map(([key, val]) => (
                  <div key={key} className="flex items-center gap-2 text-[11px]">
                    <span className="text-orange-400 font-semibold w-6 text-right shrink-0">
                      -{val}
                    </span>
                    <span className="text-text">{PENALTY_LABELS[key] ?? key}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 툴 사용 */}
          {turn.tool_used && (
            <div className="bg-emerald-500/5 rounded-lg p-2.5 border border-emerald-500/20">
              <p className="text-[10px] font-semibold text-emerald-500 mb-1 flex items-center gap-1">
                <Wrench size={10} />툴 사용: {turn.tool_used}
              </p>
              {turn.tool_result && (
                <pre className="text-[11px] text-text-secondary font-mono whitespace-pre-wrap break-all">
                  {turn.tool_result}
                </pre>
              )}
            </div>
          )}

          {/* 원본 LLM 응답 (raw_response) */}
          {turn.raw_response && (
            <div>
              <button
                type="button"
                onClick={() => setRawOpen(!rawOpen)}
                className="flex items-center gap-1.5 text-[11px] text-text-muted hover:text-text transition-colors mb-1"
              >
                {rawOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                <span className="font-semibold">원본 LLM 응답 (raw_response)</span>
              </button>
              {rawOpen && (
                <pre className="text-[11px] font-mono text-text-secondary bg-bg border border-border rounded-lg p-2.5 overflow-x-auto whitespace-pre-wrap break-all max-h-64">
                  {JSON.stringify(turn.raw_response, null, 2)}
                </pre>
              )}
            </div>
          )}

          {/* 메타 정보 */}
          <div className="flex flex-wrap items-center gap-4 text-[10px] text-text-muted pt-1 border-t border-border/60">
            <span className="flex items-center gap-1">
              <Cpu size={10} />
              in {turn.input_tokens} / out {turn.output_tokens}
            </span>
            {turn.response_time_ms != null && (
              <span className="flex items-center gap-1">
                <Clock size={10} />
                {(turn.response_time_ms / 1000).toFixed(2)}s
              </span>
            )}
            {turn.human_suspicion_score > 0 && (
              <span className="flex items-center gap-1">
                <Shield size={10} />
                인간의심 {turn.human_suspicion_score}
              </span>
            )}
            <span className="text-text-muted/60">
              {new Date(turn.created_at).toLocaleTimeString('ko-KR')}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── 메인 모달 ───────────────────────────────────────────────────────────────

export function DebateDebugModal({ data, onClose }: Props) {
  const { match, turns } = data;
  const [filter, setFilter] = useState<Filter>('all');
  const [scorecardOpen, setScorecardOpen] = useState(false);

  const blockedCount = turns.filter((t) => t.is_blocked).length;
  const penalizedCount = turns.filter((t) => t.penalty_total > 0).length;

  const filteredTurns = turns.filter((t) => {
    if (filter === 'blocked') return t.is_blocked;
    if (filter === 'penalized') return t.penalty_total > 0;
    return true;
  });

  const aIsWinner = match.winner_id === match.agent_a.id;
  const bIsWinner = match.winner_id === match.agent_b.id;

  const durationSec =
    match.started_at && match.finished_at
      ? Math.round(
          (new Date(match.finished_at).getTime() - new Date(match.started_at).getTime()) / 1000,
        )
      : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.65)' }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-bg border border-border rounded-xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl">
        {/* ── 헤더 ── */}
        <div className="flex items-start justify-between px-5 py-4 border-b border-border shrink-0">
          <div className="min-w-0 flex-1 pr-4">
            <p className="text-[10px] text-text-muted uppercase tracking-wide mb-0.5">
              매치 디버그 로그
            </p>
            <h2 className="font-semibold text-text text-sm leading-snug line-clamp-1">
              {match.topic_title}
            </h2>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              <span className="text-xs font-semibold text-blue-400">{match.agent_a.name}</span>
              <span className="text-[11px] text-text-muted">
                {match.agent_a.provider} · {match.agent_a.model_id}
              </span>
              <span className="text-xs text-text-muted font-bold">vs</span>
              <span className="text-xs font-semibold text-violet-400">{match.agent_b.name}</span>
              <span className="text-[11px] text-text-muted">
                {match.agent_b.provider} · {match.agent_b.model_id}
              </span>
              <span className="text-[10px] border border-border rounded px-1.5 py-0.5 text-text-muted">
                {MATCH_STATUS_LABELS[match.status] ?? match.status}
              </span>
              {durationSec != null && (
                <span className="text-[10px] text-text-muted flex items-center gap-0.5">
                  <Clock size={9} />
                  {durationSec}s
                </span>
              )}
            </div>
          </div>

          {/* 점수 요약 */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="text-right">
              <p className="text-[10px] text-text-muted">{match.agent_a.name}</p>
              <p
                className={`text-xl font-bold font-mono leading-none ${aIsWinner ? 'text-blue-400' : 'text-text'}`}
              >
                {match.score_a}
                {match.penalty_a > 0 && (
                  <span className="text-xs text-orange-400 ml-1">(-{match.penalty_a})</span>
                )}
              </p>
            </div>
            <span className="text-text-muted font-bold text-sm">:</span>
            <div className="text-left">
              <p className="text-[10px] text-text-muted">{match.agent_b.name}</p>
              <p
                className={`text-xl font-bold font-mono leading-none ${bIsWinner ? 'text-violet-400' : 'text-text'}`}
              >
                {match.score_b}
                {match.penalty_b > 0 && (
                  <span className="text-xs text-orange-400 ml-1">(-{match.penalty_b})</span>
                )}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="ml-3 p-1.5 rounded-lg hover:bg-bg-surface text-text-muted hover:text-text transition-colors"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* ── 필터 바 ── */}
        <div className="flex items-center gap-2 px-5 py-2.5 border-b border-border shrink-0 flex-wrap">
          <p className="text-[11px] text-text-muted">필터:</p>
          {(
            [
              ['all', `전체 (${turns.length})`],
              ['blocked', `차단됨 (${blockedCount})`],
              ['penalized', `벌점 있음 (${penalizedCount})`],
            ] as [Filter, string][]
          ).map(([f, label]) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={`text-xs px-2.5 py-1 rounded-lg transition-colors ${
                filter === f
                  ? f === 'blocked'
                    ? 'bg-red-500/20 text-red-400 font-semibold'
                    : f === 'penalized'
                      ? 'bg-orange-500/20 text-orange-400 font-semibold'
                      : 'bg-primary/20 text-primary font-semibold'
                  : 'bg-bg-surface text-text-muted hover:text-text border border-border'
              }`}
            >
              {label}
            </button>
          ))}
          <span className="ml-auto text-[10px] text-text-muted">
            {turns.length}턴 · 차단 {blockedCount} · 벌점 {penalizedCount}
          </span>
        </div>

        {/* ── 턴 목록 ── */}
        <div className="flex-1 overflow-y-auto px-5 py-3 space-y-2">
          {filteredTurns.length === 0 ? (
            <p className="text-sm text-text-muted text-center py-10">해당 조건의 턴이 없습니다.</p>
          ) : (
            filteredTurns.map((turn) => (
              <TurnDebugCard
                key={turn.id}
                turn={turn}
                agentAName={match.agent_a.name}
                agentBName={match.agent_b.name}
              />
            ))
          )}
        </div>

        {/* ── 스코어카드 (접을 수 있음) ── */}
        {match.scorecard && (
          <div className="border-t border-border px-5 py-3 shrink-0">
            <button
              type="button"
              onClick={() => setScorecardOpen(!scorecardOpen)}
              className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text transition-colors w-full"
            >
              {scorecardOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              <Award size={13} className="text-yellow-500" />
              <span className="font-semibold">스코어카드 & 판정 근거</span>
            </button>

            {scorecardOpen && (
              <div className="mt-2.5 space-y-2">
                <div className="grid grid-cols-2 gap-3">
                  {(['agent_a', 'agent_b'] as const).map((side) => {
                    const scores = match.scorecard![side];
                    const agentName = side === 'agent_a' ? match.agent_a.name : match.agent_b.name;
                    const total = Object.values(scores).reduce((a, b) => a + b, 0);
                    const isWinner =
                      side === 'agent_a'
                        ? match.winner_id === match.agent_a.id
                        : match.winner_id === match.agent_b.id;
                    return (
                      <div
                        key={side}
                        className={`bg-bg rounded-lg p-2.5 border ${
                          isWinner ? 'border-primary/40' : 'border-border'
                        }`}
                      >
                        <p
                          className={`text-xs font-semibold mb-2 ${
                            side === 'agent_a' ? 'text-blue-400' : 'text-violet-400'
                          }`}
                        >
                          {agentName}
                          {isWinner && (
                            <span className="ml-1.5 text-[10px] text-yellow-500 font-bold">
                              ★ 승리
                            </span>
                          )}
                          <span className="ml-1 text-text-muted font-normal">— {total}점</span>
                        </p>
                        {Object.entries(scores).map(([k, v]) => (
                          <div
                            key={k}
                            className="flex justify-between items-center text-[11px] text-text-muted py-0.5"
                          >
                            <span>{k}</span>
                            <span className="font-mono font-semibold text-text">{v}</span>
                          </div>
                        ))}
                      </div>
                    );
                  })}
                </div>
                {match.scorecard.reasoning && (
                  <div className="bg-bg rounded-lg p-2.5 border border-border">
                    <p className="text-[10px] text-text-muted font-semibold mb-1">판정 근거</p>
                    <p className="text-xs text-text-secondary whitespace-pre-wrap leading-relaxed">
                      {match.scorecard.reasoning}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
