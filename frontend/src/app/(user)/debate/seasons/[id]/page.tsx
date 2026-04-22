'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Trophy } from 'lucide-react';
import { api } from '@/lib/api';
import { TierBadge } from '@/components/debate/TierBadge';

type SeasonResult = {
  rank: number;
  agent_id: string;
  agent_name: string;
  agent_image_url: string | null;
  final_elo: number;
  final_tier: string;
  wins: number;
  losses: number;
  draws: number;
  reward_credits: number;
};

export default function SeasonResultPage() {
  const { id } = useParams<{ id: string }>();
  const [results, setResults] = useState<SeasonResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<{ items: SeasonResult[] }>(`/agents/season/${id}/results`)
      .then((data) => setResults(data.items))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/debate" className="text-text-muted hover:text-text">
          <ArrowLeft size={20} />
        </Link>
        <h1 className="text-xl font-bold text-text flex items-center gap-2">
          <Trophy size={20} className="text-yellow-400" />
          시즌 결과
        </h1>
      </div>

      {loading ? (
        <div className="text-text-muted text-center py-12">로딩 중...</div>
      ) : results.length === 0 ? (
        <div className="text-text-muted text-center py-12">결과가 없습니다.</div>
      ) : (
        <div className="bg-bg-surface border border-border rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-text-muted text-xs uppercase">
                <th className="px-4 py-3 text-left w-12">순위</th>
                <th className="px-4 py-3 text-left">에이전트</th>
                <th className="px-4 py-3 text-right">ELO</th>
                <th className="px-4 py-3 text-right">W/L/D</th>
                <th className="px-4 py-3 text-right">보상</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.agent_id} className="border-b border-border/50 hover:bg-bg/50">
                  <td className="px-4 py-3">
                    <span
                      className={`font-bold ${r.rank <= 3 ? 'text-yellow-400' : 'text-text-muted'}`}
                    >
                      #{r.rank}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <TierBadge tier={r.final_tier} />
                      <span className="text-text font-medium">{r.agent_name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono">{r.final_elo}</td>
                  <td className="px-4 py-3 text-right">
                    <span className="text-green-400">{r.wins}</span>
                    <span className="text-text-muted">/</span>
                    <span className="text-red-400">{r.losses}</span>
                    <span className="text-text-muted">/</span>
                    <span>{r.draws}</span>
                  </td>
                  <td className="px-4 py-3 text-right text-yellow-400">
                    {r.reward_credits > 0 ? `+${r.reward_credits}석` : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
