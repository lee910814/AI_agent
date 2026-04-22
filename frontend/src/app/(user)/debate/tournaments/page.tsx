'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { Trophy, Users } from 'lucide-react';
import { useTournamentStore } from '@/stores/debateTournamentStore';

const STATUS_LABELS: Record<string, string> = {
  registration: '참가 신청',
  in_progress: '진행 중',
  completed: '완료',
  cancelled: '취소',
};

const STATUS_COLORS: Record<string, string> = {
  registration: 'bg-blue-500/20 text-blue-400',
  in_progress: 'bg-yellow-500/20 text-yellow-400',
  completed: 'bg-green-500/20 text-green-400',
  cancelled: 'bg-bg-hover text-text-muted',
};

export default function TournamentsPage() {
  const { tournaments, tournamentsTotal, loading, fetchTournaments } = useTournamentStore();

  useEffect(() => {
    fetchTournaments();
  }, [fetchTournaments]);

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <div className="flex items-center gap-3 mb-6">
        <Trophy size={22} className="text-yellow-400" />
        <h1 className="text-xl font-bold text-text">토너먼트</h1>
        <span className="text-xs text-text-muted ml-auto">총 {tournamentsTotal}개</span>
      </div>

      {loading ? (
        <div className="text-text-muted text-center py-12">로딩 중...</div>
      ) : tournaments.length === 0 ? (
        <div className="text-text-muted text-center py-12">진행 중인 토너먼트가 없습니다.</div>
      ) : (
        <div className="space-y-3">
          {tournaments.map((t) => (
            <Link
              key={t.id}
              href={`/debate/tournaments/${t.id}`}
              className="flex items-center gap-4 bg-bg-surface border border-border rounded-xl p-4 hover:border-primary/50 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-text truncate">{t.title}</div>
                <div className="text-xs text-text-muted flex items-center gap-2 mt-1">
                  <Users size={12} />
                  {t.bracket_size}강 · 라운드 {t.current_round}
                </div>
              </div>
              <span
                className={`text-xs px-2 py-1 rounded-full shrink-0 ${STATUS_COLORS[t.status] ?? 'bg-bg-hover text-text-muted'}`}
              >
                {STATUS_LABELS[t.status] ?? t.status}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
