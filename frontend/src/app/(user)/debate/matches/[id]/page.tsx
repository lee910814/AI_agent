'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Swords } from 'lucide-react';
import { useDebateStore } from '@/stores/debateStore';
import type { PromotionSeries } from '@/stores/debateStore';
import { DebateViewer } from '@/components/debate/DebateViewer';
import { FightingHPBar } from '@/components/debate/FightingHPBar';
import { PromotionBadge } from '@/components/debate/PromotionBadge';
import { PromotionSeriesProgress } from '@/components/debate/PromotionSeriesProgress';
import { Scorecard } from '@/components/debate/Scorecard';
import { SummaryReport } from '@/components/debate/SummaryReport';
import { MatchActionBar } from '@/components/debate/MatchActionBar';
import { SkeletonCard } from '@/components/ui/Skeleton';

const STATUS_LABELS: Record<string, string> = {
  pending: '대기',
  in_progress: '진행 중',
  completed: '종료',
  error: '오류',
  waiting_agent: '에이전트 대기',
  forfeit: '몰수패',
};

const STATUS_CLASSES: Record<string, string> = {
  pending: 'bg-bg-hover text-text-muted',
  in_progress: 'bg-yellow-500/20 text-yellow-400',
  completed: 'bg-green-500/20 text-green-400',
  error: 'bg-red-500/20 text-red-400',
  waiting_agent: 'bg-blue-500/20 text-blue-400',
  forfeit: 'bg-red-500/20 text-red-400',
};

export default function MatchPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const autoReplay = searchParams.get('replay') === '1';
  const {
    currentMatch,
    turns,
    fetchMatch,
    fetchTurns,
    setDebateShowAll,
    debateShowAll,
    waitingAgent,
    creditInsufficient,
    matchVoidReason,
    startReplay,
  } = useDebateStore();
  const scorecardRef = useRef<HTMLDivElement>(null);
  const prevStatusRef = useRef<string | undefined>(undefined);
  const replayStartedRef = useRef(false);
  // 승급전/강등전 시리즈 상태 (SSE series_update 이벤트로 업데이트)
  const [seriesUpdate, setSeriesUpdate] = useState<PromotionSeries | null>(null);

  useEffect(() => {
    fetchMatch(id);
  }, [id, fetchMatch]);

  // pending/waiting_agent 상태일 때 폴링 — in_progress 전환을 감지해 SSE를 자동 연결
  useEffect(() => {
    if (!currentMatch) return;
    if (!['pending', 'waiting_agent'].includes(currentMatch.status)) return;

    const interval = setInterval(() => fetchMatch(id), 3000);
    return () => clearInterval(interval);
  }, [currentMatch?.status, id, fetchMatch]);

  // ?replay=1 파라미터로 진입 시 turns 로드 완료 후 자동 리플레이 시작
  useEffect(() => {
    if (autoReplay && turns.length > 0 && !replayStartedRef.current) {
      replayStartedRef.current = true;
      startReplay();
    }
  }, [autoReplay, turns.length, startReplay]);

  // 완료된 매치에 직접 접근 시 턴 로그 로드 + 결과창 표시
  // (SSE를 통한 live 관전 없이 페이지에 진입한 경우 처리)
  useEffect(() => {
    if (
      currentMatch?.id === id &&
      (currentMatch.status === 'completed' || currentMatch.status === 'forfeit') &&
      !debateShowAll
    ) {
      fetchTurns(id);
      setDebateShowAll(true);
    }
  }, [currentMatch?.id, currentMatch?.status, id, debateShowAll, fetchTurns, setDebateShowAll]);

  // 토론 완료 시 스코어카드로 스크롤 (in_progress → completed 전환 감지)
  useEffect(() => {
    if (prevStatusRef.current === 'in_progress' && currentMatch?.status === 'completed') {
      setTimeout(() => {
        scorecardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 600);
    }
    prevStatusRef.current = currentMatch?.status;
  }, [currentMatch?.status]);

  if (!currentMatch) {
    return (
      <div className="max-w-[700px] mx-auto py-6 px-4">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  const isCompleted = currentMatch.status === 'completed';
  const isForfeit = currentMatch.status === 'forfeit';

  // ELO 필드 접근을 위한 타입 확장
  const match = currentMatch as typeof currentMatch & {
    elo_a_before?: number | null;
    elo_b_before?: number | null;
    elo_a_after?: number | null;
    elo_b_after?: number | null;
  };

  // HP 계산: 진행 중엔 패널티+턴 진행도 기반, 완료 시엔 최종 점수 사용
  const penaltiesA = turns
    .filter((t) => t.speaker === 'agent_a')
    .reduce((s, t) => s + t.penalty_total, 0);
  const penaltiesB = turns
    .filter((t) => t.speaker === 'agent_b')
    .reduce((s, t) => s + t.penalty_total, 0);
  const attrition = turns.length; // 완료된 턴당 1 HP 자연 감소 (긴장감 연출)

  const hpA = isCompleted ? currentMatch.score_a : Math.max(20, 100 - attrition - penaltiesA);
  const hpB = isCompleted ? currentMatch.score_b : Math.max(20, 100 - attrition - penaltiesB);

  const isWinnerA =
    (isCompleted || isForfeit) && currentMatch.winner_id === currentMatch.agent_a.id;
  const isWinnerB =
    (isCompleted || isForfeit) && currentMatch.winner_id === currentMatch.agent_b.id;

  // 종료 배너 결정
  const showBanner = isCompleted || isForfeit;
  let bannerText = '';
  let bannerClass = '';
  if (showBanner) {
    if (isForfeit) {
      const winnerName = isWinnerA ? currentMatch.agent_a.name : currentMatch.agent_b.name;
      bannerText = `토론 종료 — ${winnerName} 부전승`;
      bannerClass = 'bg-red-500/20 border-b border-red-500/30';
    } else if (currentMatch.winner_id === currentMatch.agent_a.id) {
      bannerText = `토론 종료 — ${currentMatch.agent_a.name} 승리!`;
      bannerClass = 'bg-yellow-500/20 border-b border-yellow-500/30';
    } else if (currentMatch.winner_id === currentMatch.agent_b.id) {
      bannerText = `토론 종료 — ${currentMatch.agent_b.name} 승리!`;
      bannerClass = 'bg-yellow-500/20 border-b border-yellow-500/30';
    } else {
      bannerText = '토론 종료 — 무승부';
      bannerClass = 'bg-bg-hover border-b border-border';
    }
  }

  // ELO 변동 계산
  const eloDeltaA =
    match.elo_a_after != null && match.elo_a_before != null
      ? match.elo_a_after - match.elo_a_before
      : null;
  const eloDeltaB =
    match.elo_b_after != null && match.elo_b_before != null
      ? match.elo_b_after - match.elo_b_before
      : null;

  return (
    // -m-4 md:-m-6: main의 padding을 상쇄해 sticky 헤더가 화면 최상단에 정확히 고정되도록 함
    <div className="-m-4 md:-m-6">
      {/* 종료 배너 — 최상단 고정 (배틀 헤더보다 위) */}
      {showBanner && (
        <div
          className={`sticky top-0 z-40 px-4 py-2 text-center text-sm font-semibold ${bannerClass}`}
        >
          <span>{bannerText}</span>
          {match.elo_a_after != null && (
            <span className="ml-4 inline-flex items-center gap-3 text-xs font-mono">
              <span>
                {currentMatch.agent_a.name}{' '}
                {eloDeltaA != null && (
                  <span className={eloDeltaA >= 0 ? 'text-green-400' : 'text-red-400'}>
                    {eloDeltaA >= 0 ? '+' : ''}
                    {eloDeltaA}
                  </span>
                )}
              </span>
              <span className="text-text-muted">|</span>
              <span>
                {currentMatch.agent_b.name}{' '}
                {eloDeltaB != null && (
                  <span className={eloDeltaB >= 0 ? 'text-green-400' : 'text-red-400'}>
                    {eloDeltaB >= 0 ? '+' : ''}
                    {eloDeltaB}
                  </span>
                )}
              </span>
            </span>
          )}
        </div>
      )}

      {/* 배틀 헤더 — 항상 화면 상단 고정 (sticky top-0) */}
      <div
        className={`sticky top-0 z-30 bg-gradient-to-b from-bg via-bg-surface to-bg
          border-b shadow-lg shadow-black/40 ${
            currentMatch.match_type === 'promotion'
              ? 'border-yellow-400/60 shadow-yellow-400/10'
              : currentMatch.match_type === 'demotion'
                ? 'border-red-500/60 shadow-red-500/20'
                : 'border-border'
          }`}
      >
        <div className="max-w-[700px] mx-auto px-5 pt-4 pb-4">
          {/* HP 게이지 영역 */}
          <div className="flex items-start gap-3">
            <FightingHPBar
              agentId={currentMatch.agent_a.id}
              agentName={currentMatch.agent_a.name}
              provider={currentMatch.agent_a.provider}
              hp={hpA}
              side="left"
              isWinner={isWinnerA}
              isCompleted={isCompleted || isForfeit}
              agentImageUrl={currentMatch.agent_a.image_url}
            />

            {/* 중앙: 아이콘 + 상태 + 점수 + 승급전/강등전 배지 */}
            <div className="flex flex-col items-center gap-1.5 shrink-0 pt-1">
              <Swords size={18} className="text-primary" />
              <span
                className={`text-[11px] px-2 py-0.5 rounded-full font-semibold whitespace-nowrap
                  ${STATUS_CLASSES[currentMatch.status] ?? 'bg-bg-hover text-text-muted'}`}
              >
                {STATUS_LABELS[currentMatch.status] ?? currentMatch.status}
              </span>
              {currentMatch.match_type && currentMatch.match_type !== 'ranked' && (
                <PromotionBadge
                  type={currentMatch.match_type as 'promotion' | 'demotion'}
                  size="sm"
                />
              )}
              {isCompleted && (
                <span className="text-sm font-mono font-bold text-text mt-0.5">
                  {hpA} <span className="text-text-muted font-normal">:</span> {hpB}
                </span>
              )}
              {!isCompleted && turns.length > 0 && (
                <span className="text-[11px] font-mono text-text-muted">{turns.length}턴</span>
              )}
            </div>

            <FightingHPBar
              agentId={currentMatch.agent_b.id}
              agentName={currentMatch.agent_b.name}
              provider={currentMatch.agent_b.provider}
              hp={hpB}
              side="right"
              isWinner={isWinnerB}
              isCompleted={isCompleted || isForfeit}
              agentImageUrl={currentMatch.agent_b.image_url}
            />
          </div>

          {/* 토론 주제 */}
          <div className="mt-3 pt-3 border-t border-border text-center">
            <p className="text-[10px] text-text-muted uppercase tracking-widest mb-1">토론 주제</p>
            <h1 className="text-sm font-bold text-white leading-snug">
              「{currentMatch.topic_title}」
            </h1>
          </div>

          {/* 승급전/강등전 시리즈 진행도 */}
          {(seriesUpdate || currentMatch.match_type !== 'ranked') &&
            (() => {
              const activeSeries =
                seriesUpdate ??
                (currentMatch.match_type && currentMatch.match_type !== 'ranked'
                  ? {
                      id: currentMatch.series_id ?? '',
                      agent_id: '',
                      series_type: currentMatch.match_type as 'promotion' | 'demotion',
                      from_tier: '',
                      to_tier: '',
                      required_wins: currentMatch.match_type === 'promotion' ? 2 : 1,
                      current_wins: 0,
                      current_losses: 0,
                      status: 'active' as const,
                      created_at: '',
                      completed_at: null,
                    }
                  : null);
              if (!activeSeries || !activeSeries.from_tier) return null;
              return (
                <div className="mt-2 pt-2 border-t border-border flex justify-center">
                  <PromotionSeriesProgress series={activeSeries} />
                </div>
              );
            })()}
        </div>
      </div>

      {/* 스크롤 콘텐츠 영역 */}
      <div className="max-w-[700px] mx-auto px-4 pt-4 pb-20">
        {/* 뒤로가기 — 스크롤 시 사라지는 내비게이션 */}
        <Link
          href="/debate"
          className="flex items-center gap-1 text-sm text-text-muted no-underline hover:text-text mb-4"
        >
          <ArrowLeft size={14} />
          토론 목록
        </Link>

        {/* SSE 특수 이벤트 배너 */}
        {waitingAgent && (
          <div className="rounded-lg bg-yellow-50 border border-yellow-200 px-4 py-3 text-sm text-yellow-800 mb-4">
            에이전트 연결 대기 중...
          </div>
        )}
        {creditInsufficient && (
          <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-800 mb-4">
            크레딧이 부족하여 토론이 중단됐습니다.
          </div>
        )}
        {matchVoidReason && (
          <div className="rounded-lg bg-gray-50 border border-gray-200 px-4 py-3 text-sm text-gray-700 mb-4">
            매치가 무효화되었습니다: {matchVoidReason}
          </div>
        )}

        {/* 토론 뷰어 */}
        <div className="mb-4">
          <DebateViewer match={currentMatch} onSeriesUpdate={setSeriesUpdate} />
        </div>

        {/* 스코어카드 (완료된 매치, 전체 보기/리플레이 종료 후에만 표시) */}
        {currentMatch.status === 'completed' && debateShowAll && (
          <div ref={scorecardRef}>
            <Scorecard
              matchId={currentMatch.id}
              agentA={currentMatch.agent_a}
              agentB={currentMatch.agent_b}
              penaltyA={currentMatch.penalty_a}
              penaltyB={currentMatch.penalty_b}
            />
            <SummaryReport
              matchId={currentMatch.id}
              agentAName={currentMatch.agent_a.name}
              agentBName={currentMatch.agent_b.name}
            />
          </div>
        )}
      </div>

      {/* 하단 액션바 — sticky bottom-0 */}
      <MatchActionBar
        matchId={currentMatch.id}
        matchStatus={currentMatch.status}
        agentAName={currentMatch.agent_a.name}
        agentBName={currentMatch.agent_b.name}
        topicTitle={currentMatch.topic_title}
      />
    </div>
  );
}
