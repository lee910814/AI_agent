'use client';

import Link from 'next/link';
import { useDebateStore } from '@/stores/debateStore';
import { Trophy } from 'lucide-react';

export function HighlightBanner() {
  const featuredMatches = useDebateStore((s) => s.featuredMatches);
  if (!featuredMatches.length) return null;

  return (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        <Trophy size={16} className="text-yellow-400" />
        <h2 className="text-sm font-semibold text-text-muted uppercase tracking-wide">
          주간 하이라이트
        </h2>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-hide">
        {featuredMatches.map((match) => (
          <Link
            key={match.id}
            href={`/debate/matches/${match.id}`}
            className="shrink-0 w-72 bg-bg-surface border border-border rounded-xl p-4 hover:border-primary/50 transition-colors"
          >
            <div className="text-xs text-text-muted mb-2 truncate">{match.topic_title}</div>
            <div className="flex items-center gap-2 text-sm font-medium">
              <span className="truncate text-blue-400">{match.agent_a.name}</span>
              <span className="text-text-muted shrink-0">vs</span>
              <span className="truncate text-red-400">{match.agent_b.name}</span>
            </div>
            <div className="flex items-center gap-3 mt-2 text-xs text-text-muted">
              <span>
                {match.score_a} - {match.score_b}
              </span>
              {match.winner_id && (
                <span className="bg-yellow-500/20 text-yellow-400 rounded px-1.5 py-0.5">
                  승부 결정
                </span>
              )}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
