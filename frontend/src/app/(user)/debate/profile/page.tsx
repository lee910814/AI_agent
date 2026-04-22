'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { FileText, ChevronRight } from 'lucide-react';
import { useUserStore } from '@/stores/userStore';
import { useDebateAgentStore } from '@/stores/debateAgentStore';
import { api } from '@/lib/api';

type MatchItem = {
  id: string;
  topic_id: string;
  topic_title: string;
  agent_a: { id: string; name: string };
  agent_b: { id: string; name: string };
  status: string;
  winner_id: string | null;
  score_a: number;
  score_b: number;
  created_at: string;
};


function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
  });
}

export default function ProfilePage() {
  const { user } = useUserStore();
  const { agents, fetchMyAgents } = useDebateAgentStore();
  const [matches, setMatches] = useState<MatchItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMyAgents();
  }, [fetchMyAgents]);

  useEffect(() => {
    async function loadMatches() {
      if (agents.length === 0) {
        setLoading(false);
        return;
      }
      try {
        // 내 첫번째 에이전트의 매치 히스토리 조회
        const data = await api.get<{ items: MatchItem[]; total: number }>(
          `/matches?agent_id=${agents[0].id}&limit=10`,
        );
        setMatches(data.items);
      } catch {
        console.error('Failed to load matches');
      } finally {
        setLoading(false);
      }
    }
    if (agents.length > 0) loadMatches();
  }, [agents]);

  const primaryAgent = agents[0];
  const totalWins = agents.reduce((sum, a) => sum + a.wins, 0);
  const totalElo = primaryAgent?.elo_rating ?? 1500;

  return (
    <div className="max-w-[800px] mx-auto">
      {/* ─── Profile Card ─── */}
      <div className="nemo-gradient-card mb-6 text-center">
        <div className="w-16 h-16 rounded-2xl bg-white/20 flex items-center justify-center text-white text-2xl font-bold mx-auto mb-3">
          {user?.nickname?.charAt(0)?.toUpperCase() ?? 'U'}
        </div>
        <h2 className="text-xl font-bold mb-1">{user?.nickname ?? '사용자'}</h2>
        <p className="text-white/70 text-sm mb-6">가입일: 2025년 8월</p>

        <div className="grid grid-cols-3 gap-3">
          <div className="bg-white/15 rounded-xl py-3 px-2 text-center">
            <p className="text-2xl font-bold">{totalWins}</p>
            <p className="text-white/60 text-xs">승리</p>
          </div>
          <div className="bg-white/15 rounded-xl py-3 px-2 text-center">
            <p className="text-2xl font-bold">{totalElo.toLocaleString()}</p>
            <p className="text-white/60 text-xs">ELO</p>
          </div>
          <div className="bg-white/15 rounded-xl py-3 px-2 text-center">
            <p className="text-2xl font-bold">S3</p>
            <p className="text-white/60 text-xs">시즌</p>
          </div>
        </div>
      </div>

      {/* ─── Recent Matches ─── */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-text flex items-center gap-2">
          <FileText size={18} className="text-nemo" />
          최근 매치
        </h3>
        <Link
          href="/debate"
          className="text-xs text-text-muted hover:text-nemo no-underline flex items-center gap-1"
        >
          전체보기 <ChevronRight size={14} />
        </Link>
      </div>

      <div className="flex flex-col gap-3">
        {loading ? (
          <div className="text-center py-8 text-text-muted text-sm">로딩 중...</div>
        ) : matches.length === 0 ? (
          <div className="text-center py-8 text-text-muted text-sm">매치 기록이 없습니다.</div>
        ) : (
          matches.map((match) => {
            const myAgent = agents.find(
              (a) => a.id === match.agent_a.id || a.id === match.agent_b.id,
            );
            const isWinner = myAgent && match.winner_id === myAgent.id;
            const isError = match.status === 'error';
            const opponent = match.agent_a.id === myAgent?.id ? match.agent_b : match.agent_a;
            const score =
              match.agent_a.id === myAgent?.id
                ? `${match.score_a}:${match.score_b}`
                : `${match.score_b}:${match.score_a}`;

            return (
              <Link
                key={match.id}
                href={`/debate/matches/${match.id}`}
                className="nemo-rank-card no-underline"
              >
                {/* Result badge */}
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center text-xs font-bold shrink-0 ${
                    isError
                      ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                      : isWinner
                        ? 'bg-nemo/10 text-nemo border border-nemo/20'
                        : 'bg-gray-500/10 text-gray-400 border border-gray-500/20'
                  }`}
                >
                  {isError ? '오류' : isWinner ? '승' : '패'}
                </div>

                {/* Match info */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-text truncate">{match.topic_title}</p>
                  <p className="text-xs text-text-muted">
                    vs {opponent.name} · {score} · {formatDate(match.created_at)}
                  </p>
                </div>

                <ChevronRight size={16} className="text-text-muted shrink-0" />
              </Link>
            );
          })
        )}
      </div>
    </div>
  );
}
