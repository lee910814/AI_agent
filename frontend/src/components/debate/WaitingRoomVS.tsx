'use client';

import { AgentProfilePanel } from './AgentProfilePanel';
import { CountUpTimer } from './CountUpTimer';

type Agent = {
  id: string;
  name: string;
  provider: string;
  model_id: string;
  elo_rating: number;
  wins: number;
  losses: number;
  draws: number;
  image_url?: string | null;
};

type Props = {
  topicTitle: string;
  myAgent: Agent;
  opponent: Agent | null;
  startedAt: Date;
  isMatched: boolean;
  isAutoMatched: boolean;
  isRevealing: boolean;
  isReady: boolean;
  opponentReady: boolean;
  countdown: number | null;
  onReady: () => void;
  readying: boolean;
  onCancel: () => void;
  cancelling: boolean;
};

export function WaitingRoomVS({
  topicTitle,
  myAgent,
  opponent,
  startedAt,
  isMatched,
  isAutoMatched,
  isRevealing,
  isReady,
  opponentReady,
  countdown,
  onReady,
  readying,
  onCancel,
  cancelling,
}: Props) {
  const hasOpponent = opponent !== null;

  return (
    <div className="min-h-screen bg-gradient-to-b from-bg via-bg-surface to-bg flex flex-col items-center justify-center px-4 py-8">
      {/* 토픽 제목 */}
      <div className="mb-8 text-center max-w-[600px]">
        <p className="text-xs text-text-muted uppercase tracking-widest mb-1">토론 주제</p>
        <h1 className="text-lg font-bold text-white break-words">「{topicTitle}」</h1>
      </div>

      {/* VS 레이아웃 */}
      <div className="flex items-center justify-center gap-6 md:gap-12 w-full max-w-[700px]">
        {/* 내 에이전트 (좌) */}
        <div className="flex-1 flex justify-end">
          <AgentProfilePanel agent={myAgent} side="left" />
        </div>

        {/* 중앙 영역 */}
        <div className="flex flex-col items-center gap-4 flex-shrink-0">
          {isMatched ? (
            <div className="flex flex-col items-center gap-2">
              <span
                className="text-5xl font-black text-green-400 drop-shadow-[0_0_20px_rgba(74,222,128,0.8)]
                  animate-bounce"
              >
                MATCH!
              </span>
              {isAutoMatched && (
                <span className="text-xs px-3 py-1 rounded-full bg-yellow-500/20 text-yellow-400 font-semibold border border-yellow-500/30">
                  자동 매칭
                </span>
              )}
              <p className="text-sm text-text-secondary">잠시 후 이동합니다...</p>
            </div>
          ) : (
            <>
              <span
                className="text-5xl font-black text-red-500
                  drop-shadow-[0_0_20px_rgba(239,68,68,0.6)]"
              >
                VS
              </span>
              <CountUpTimer startedAt={startedAt} maxSeconds={120} />
              {!hasOpponent && <p className="text-xs text-text-muted">상대를 찾는 중...</p>}
            </>
          )}
        </div>

        {/* 상대 에이전트 (우) */}
        <div className="flex-1 flex justify-start">
          <AgentProfilePanel agent={opponent} side="right" isRevealing={isRevealing} />
        </div>
      </div>

      {/* 준비 완료 버튼 영역 */}
      {!isMatched && hasOpponent && (
        <div className="mt-10 flex flex-col items-center gap-3">
          {/* 카운트다운 */}
          {countdown !== null && (
            <div className="flex flex-col items-center gap-1">
              <p className="text-xs text-text-secondary">토론 시작까지</p>
              <span
                className={`text-6xl font-black tabular-nums drop-shadow-[0_0_16px_rgba(234,179,8,0.7)] transition-all ${
                  countdown <= 3 ? 'text-red-400 animate-pulse' : 'text-yellow-400'
                }`}
              >
                {countdown}
              </span>
            </div>
          )}

          {/* 준비 상태 표시 */}
          <div className="flex items-center gap-4 text-xs text-text-secondary">
            <span className={isReady ? 'text-green-400 font-semibold' : ''}>
              {isReady ? '✓ 나 준비 완료' : '나 대기 중'}
            </span>
            <span className="text-text-muted">|</span>
            <span className={opponentReady ? 'text-green-400 font-semibold' : ''}>
              {opponentReady ? '✓ 상대 준비 완료' : '상대 대기 중'}
            </span>
          </div>

          {!isReady ? (
            <button
              onClick={onReady}
              disabled={readying}
              className="px-10 py-3 bg-primary text-white font-bold rounded-xl text-sm
                hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed
                transition-all shadow-lg shadow-primary/30 animate-pulse"
            >
              {readying ? '처리 중...' : '준비 완료'}
            </button>
          ) : (
            <div className="px-10 py-3 border border-green-500/40 rounded-xl text-sm text-green-400 font-semibold bg-green-500/10">
              {countdown !== null
                ? '카운트다운 중 — 상대가 준비하면 즉시 시작...'
                : opponentReady
                  ? '양쪽 준비 완료 — 시작 중...'
                  : '상대방 준비를 기다리는 중...'}
            </div>
          )}
        </div>
      )}

      {/* 취소 버튼 */}
      {!isMatched && (
        <button
          onClick={onCancel}
          disabled={cancelling}
          className="mt-6 px-6 py-2 rounded-lg border border-border text-sm text-text-secondary
            hover:border-red-500/50 hover:text-red-400 transition-colors disabled:opacity-50
            disabled:cursor-not-allowed"
        >
          {cancelling ? '취소 중...' : '대기 취소'}
        </button>
      )}
    </div>
  );
}
