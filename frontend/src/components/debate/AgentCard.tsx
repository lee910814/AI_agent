'use client';

import Link from 'next/link';
import { Bot, Trophy, TrendingUp } from 'lucide-react';
import type { DebateAgent } from '@/stores/debateAgentStore';

type Props = { agent: DebateAgent };

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  google: 'Google',
  runpod: 'RunPod',
  local: '로컬',
};

export function AgentCard({ agent }: Props) {
  const totalGames = agent.wins + agent.losses + agent.draws;
  const winRate = totalGames > 0 ? Math.round((agent.wins / totalGames) * 100) : 0;

  return (
    <Link
      href={`/debate/agents/${agent.id}`}
      className="block bg-bg-surface border border-border rounded-xl p-4 hover:border-primary/30 transition-colors no-underline"
    >
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary shrink-0 overflow-hidden">
          {agent.image_url ? (
            <img src={agent.image_url} alt={agent.name} className="w-full h-full object-cover" />
          ) : (
            <Bot size={20} />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <h3 className="text-sm font-bold text-text truncate">{agent.name}</h3>
            {agent.active_series_id && (
              <span className="shrink-0 text-xs px-1.5 py-0.5 rounded-full bg-yellow-500/20 text-yellow-400 font-semibold">
                ⚔️
              </span>
            )}
          </div>
          <span className="text-xs text-text-muted flex items-center gap-1">
            {agent.provider === 'local' && (
              <span
                className={`inline-block w-2 h-2 rounded-full ${
                  agent.is_connected ? 'bg-green-500' : 'bg-gray-400'
                }`}
                title={agent.is_connected ? '접속 중' : '미접속'}
              />
            )}
            {PROVIDER_LABELS[agent.provider] || agent.provider} / {agent.model_id}
          </span>
        </div>
      </div>

      {agent.description && (
        <p className="text-xs text-text-secondary mb-3 line-clamp-2">{agent.description}</p>
      )}

      <div className="flex items-center gap-4 text-xs text-text-muted">
        <span className="flex items-center gap-1">
          <TrendingUp size={12} />
          ELO {agent.elo_rating}
        </span>
        <span className="flex items-center gap-1">
          <Trophy size={12} />
          {agent.wins}W {agent.losses}L {agent.draws}D
        </span>
        {totalGames > 0 && <span className="text-primary font-semibold">{winRate}%</span>}
      </div>
    </Link>
  );
}
