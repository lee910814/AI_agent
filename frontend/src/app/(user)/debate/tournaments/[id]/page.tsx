'use client';

import { useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Trophy } from 'lucide-react';
import { useTournamentStore } from '@/stores/debateTournamentStore';
import { TournamentBracket } from '@/components/debate/TournamentBracket';

export default function TournamentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { currentTournament, loading, fetchTournament } = useTournamentStore();

  useEffect(() => {
    fetchTournament(id);
  }, [id, fetchTournament]);

  if (loading) return <div className="text-text-muted text-center py-20">로딩 중...</div>;
  if (!currentTournament)
    return <div className="text-text-muted text-center py-20">토너먼트를 찾을 수 없습니다.</div>;

  const t = currentTournament;
  const rounds = Math.ceil(Math.log2(t.bracket_size));

  return (
    <div className="max-w-5xl mx-auto px-4 py-6">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/debate/tournaments" className="text-text-muted hover:text-text">
          <ArrowLeft size={20} />
        </Link>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-text flex items-center gap-2">
            <Trophy size={20} className="text-yellow-400" />
            {t.title}
          </h1>
          <div className="text-xs text-text-muted mt-1">
            {t.bracket_size}강 · 라운드 {t.current_round}/{rounds}
          </div>
        </div>
      </div>

      {t.winner_agent_id && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4 mb-6 text-center">
          <span className="text-yellow-400 font-semibold">
            🏆 우승자:{' '}
            {t.entries.find((e) => e.agent_id === t.winner_agent_id)?.agent_name ?? '알 수 없음'}
          </span>
        </div>
      )}

      <div className="bg-bg-surface border border-border rounded-2xl p-6">
        <TournamentBracket entries={t.entries} matches={[]} rounds={rounds} />
      </div>
    </div>
  );
}
