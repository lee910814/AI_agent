'use client';

import { useEffect, useState } from 'react';
import { TrendingUp } from 'lucide-react';
import { api } from '@/lib/api';

type PredictionStats = {
  total: number;
  a_win: number;
  b_win: number;
  draw: number;
  a_win_pct: number;
  b_win_pct: number;
  draw_pct: number;
  my_prediction: string | null;
};

type Props = {
  matchId: string;
  agentAName: string;
  agentBName: string;
  turnCount: number;
};

export function PredictionPanel({ matchId, agentAName, agentBName, turnCount }: Props) {
  const [stats, setStats] = useState<PredictionStats | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canVote = turnCount <= 2;

  useEffect(() => {
    api
      .get<PredictionStats>(`/matches/${matchId}/predictions`)
      .then(setStats)
      .catch(() => {});
  }, [matchId]);

  const vote = async (prediction: 'a_win' | 'b_win' | 'draw') => {
    if (!canVote || submitting || stats?.my_prediction) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await api.post<PredictionStats>(`/matches/${matchId}/predictions`, {
        prediction,
      });
      setStats(updated);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '투표 중 오류가 발생했습니다.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const voted = stats?.my_prediction;

  return (
    <div className="rounded-xl border border-border bg-bg-surface p-4 mb-4">
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp size={16} className="text-primary" />
        <span className="text-sm font-semibold text-text">승자 예측</span>
        {!canVote && (
          <span className="ml-auto text-[11px] text-text-muted">투표 마감 (3턴 이후)</span>
        )}
        {canVote && !voted && (
          <span className="ml-auto text-[11px] text-primary animate-pulse">지금 투표하세요!</span>
        )}
      </div>

      {/* 투표 버튼 */}
      {!voted && canVote && (
        <div className="grid grid-cols-3 gap-2 mb-3">
          <button
            onClick={() => vote('a_win')}
            disabled={submitting}
            className="py-2 rounded-lg text-xs font-semibold bg-blue-500/15 text-blue-400 hover:bg-blue-500/30 disabled:opacity-40 transition-colors"
          >
            {agentAName} 승
          </button>
          <button
            onClick={() => vote('draw')}
            disabled={submitting}
            className="py-2 rounded-lg text-xs font-semibold bg-gray-500/15 text-text-muted hover:bg-gray-500/30 disabled:opacity-40 transition-colors"
          >
            무승부
          </button>
          <button
            onClick={() => vote('b_win')}
            disabled={submitting}
            className="py-2 rounded-lg text-xs font-semibold bg-red-500/15 text-red-400 hover:bg-red-500/30 disabled:opacity-40 transition-colors"
          >
            {agentBName} 승
          </button>
        </div>
      )}

      {/* 투표 완료 메시지 */}
      {voted && (
        <p className="text-xs text-text-muted mb-3">
          투표 완료:{' '}
          <span className="font-semibold text-primary">
            {voted === 'a_win'
              ? `${agentAName} 승`
              : voted === 'b_win'
                ? `${agentBName} 승`
                : '무승부'}
          </span>
        </p>
      )}

      {/* 통계 바 */}
      {stats && stats.total > 0 && (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 text-xs">
            <span className="w-20 truncate text-blue-400">{agentAName}</span>
            <div className="flex-1 h-2 rounded-full bg-bg-hover overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-500"
                style={{ width: `${stats.a_win_pct}%` }}
              />
            </div>
            <span className="w-8 text-right text-text-muted">{stats.a_win_pct}%</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="w-20 truncate text-text-muted">무승부</span>
            <div className="flex-1 h-2 rounded-full bg-bg-hover overflow-hidden">
              <div
                className="h-full bg-gray-500 rounded-full transition-all duration-500"
                style={{ width: `${stats.draw_pct}%` }}
              />
            </div>
            <span className="w-8 text-right text-text-muted">{stats.draw_pct}%</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="w-20 truncate text-red-400">{agentBName}</span>
            <div className="flex-1 h-2 rounded-full bg-bg-hover overflow-hidden">
              <div
                className="h-full bg-red-500 rounded-full transition-all duration-500"
                style={{ width: `${stats.b_win_pct}%` }}
              />
            </div>
            <span className="w-8 text-right text-text-muted">{stats.b_win_pct}%</span>
          </div>
          <p className="text-[11px] text-text-muted text-right mt-1">{stats.total}명 참여</p>
        </div>
      )}

      {stats && stats.total === 0 && (
        <p className="text-xs text-text-muted text-center py-1">아직 투표한 사람이 없습니다.</p>
      )}

      {error && <p className="text-xs text-danger mt-2">{error}</p>}
    </div>
  );
}
