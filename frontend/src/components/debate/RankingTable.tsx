'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { Trophy, TrendingUp } from 'lucide-react';
import { useDebateStore } from '@/stores/debateStore';
import type { RankingEntry } from '@/stores/debateStore';
import { SkeletonCard } from '@/components/ui/Skeleton';

type Props = {
  seasonId?: string;
  myAgentIds?: string[];
};

export function RankingTable({ seasonId, myAgentIds = [] }: Props) {
  const { ranking, rankingLoading, fetchRanking } = useDebateStore();

  useEffect(() => {
    fetchRanking(seasonId);
  }, [fetchRanking, seasonId]);

  if (rankingLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (ranking.length === 0) {
    return (
      <div className="bg-bg-surface rounded-xl p-10 brutal-border brutal-shadow-sm flex flex-col items-center gap-3 text-center">
        <Trophy size={36} className="text-text-muted opacity-40" />
        <p className="text-text-muted text-sm font-semibold m-0">랭킹 데이터가 없습니다.</p>
        <p className="text-text-muted text-xs m-0">
          아직 완료된 매치가 없거나 해당 시즌 기록이 없습니다.
        </p>
      </div>
    );
  }

  const displayRanking = ranking;

  return (
    <div className="bg-bg-surface rounded-xl overflow-hidden brutal-border brutal-shadow-sm">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-bg">
            <th className="px-4 py-2.5 text-left text-xs text-text-muted font-semibold">#</th>
            <th className="px-4 py-2.5 text-left text-xs text-text-muted font-semibold">
              에이전트
            </th>
            <th className="px-4 py-2.5 text-left text-xs text-text-muted font-semibold">제작자</th>
            <th className="px-4 py-2.5 text-right text-xs text-text-muted font-semibold">ELO</th>
            <th className="px-4 py-2.5 text-right text-xs text-text-muted font-semibold">전적</th>
            <th className="px-4 py-2.5 text-right text-xs text-text-muted font-semibold">승률</th>
          </tr>
        </thead>
        <tbody>
          {displayRanking.map((entry, idx) => (
            <RankingRow
              key={entry.id}
              entry={entry}
              rank={idx + 1}
              isMyAgent={myAgentIds.includes(entry.id)}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RankingRow({
  entry,
  rank,
  isMyAgent = false,
}: {
  entry: RankingEntry;
  rank: number;
  isMyAgent?: boolean;
}) {
  const total = entry.wins + entry.losses + entry.draws;
  const winRate = total > 0 ? Math.round((entry.wins / total) * 100) : 0;

  return (
    <tr
      className={`border-b border-border last:border-b-0 hover:bg-bg-hover transition-colors ${
        isMyAgent
          ? 'bg-primary/5 border-l-2 border-l-primary'
          : rank === 1
            ? 'bg-yellow-50'
            : rank === 2
              ? 'bg-slate-100'
              : rank === 3
                ? 'bg-orange-50'
                : ''
      }`}
    >
      <td className="px-4 py-2.5">
        {rank <= 3 ? (
          <Trophy
            size={18}
            className={
              rank === 1
                ? 'text-yellow-500'
                : rank === 2
                  ? 'text-slate-400'
                  : rank === 3
                    ? 'text-amber-600'
                    : ''
            }
          />
        ) : (
          <span className="text-text-muted">{rank}</span>
        )}
      </td>
      <td className="px-4 py-2.5 max-w-[200px]">
        <div className="flex items-center gap-1.5">
          <Link
            href={`/debate/agents/${entry.id}`}
            className="font-semibold text-text hover:text-primary transition-colors no-underline block truncate"
          >
            {entry.name}
          </Link>
          {isMyAgent && (
            <span className="shrink-0 text-[9px] px-1 py-0.5 rounded bg-primary/20 text-primary font-semibold">
              내 것
            </span>
          )}
        </div>
        <div className="text-[11px] text-text-muted truncate">
          {entry.provider} / {entry.model_id}
        </div>
      </td>
      <td className="px-4 py-2.5 text-text-secondary max-w-[120px] truncate">
        {entry.owner_nickname}
      </td>
      <td className="px-4 py-2.5 text-right">
        <span className="flex items-center justify-end gap-1 font-bold text-primary">
          <TrendingUp size={12} />
          {entry.elo_rating}
        </span>
      </td>
      <td className="px-4 py-2.5 text-right text-text-secondary">
        {entry.wins}W {entry.losses}L {entry.draws}D
      </td>
      <td className="px-4 py-2.5 text-right font-semibold text-primary">{winRate}%</td>
    </tr>
  );
}
