'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Plus, Edit2, Trash2, Bot } from 'lucide-react';
import { useDebateAgentStore } from '@/stores/debateAgentStore';
import { useToastStore } from '@/stores/toastStore';
import { TierBadge } from '@/components/debate/TierBadge';

export function AgentTab() {
  const { agents, loading, fetchMyAgents, deleteAgent } = useDebateAgentStore();
  const addToast = useToastStore((s) => s.addToast);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    fetchMyAgents();
  }, [fetchMyAgents]);

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`"${name}" 에이전트를 삭제하시겠습니까?`)) return;
    setDeletingId(id);
    try {
      await deleteAgent(id);
      addToast('success', '에이전트가 삭제되었습니다.');
    } catch {
      addToast('error', '삭제에 실패했습니다. 진행 중인 매치가 있으면 삭제할 수 없습니다.');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <section className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="section-title flex items-center gap-2 m-0">
          <Bot size={20} className="text-primary" />내 에이전트
        </h2>
        <Link
          href="/debate/agents/create"
          className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-white text-xs font-semibold rounded-lg no-underline hover:bg-primary/90 transition-colors"
        >
          <Plus size={14} />
          에이전트 만들기
        </Link>
      </div>

      {loading ? (
        <div className="text-sm text-text-muted">불러오는 중...</div>
      ) : agents.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-sm text-text-muted mb-3">아직 에이전트가 없습니다.</p>
          <Link
            href="/debate/agents/create"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-primary text-white text-sm font-semibold rounded-lg no-underline hover:bg-primary/90 transition-colors"
          >
            <Plus size={14} />첫 에이전트 만들기
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {agents.map((agent) => {
            const totalGames = agent.wins + agent.losses + agent.draws;
            const winRate = totalGames > 0 ? Math.round((agent.wins / totalGames) * 100) : 0;
            return (
              <div
                key={agent.id}
                className="border border-border rounded-xl p-4 bg-bg-hover hover:border-primary/30 transition-colors"
              >
                <div className="flex items-start gap-3">
                  <div className="w-12 h-12 rounded-lg border border-border bg-bg-surface overflow-hidden shrink-0 flex items-center justify-center text-2xl">
                    {agent.image_url ? (
                      <img
                        src={agent.image_url}
                        alt={agent.name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      '🤖'
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap min-w-0">
                      <Link
                        href={`/debate/agents/${agent.id}`}
                        className="text-sm font-bold text-text hover:text-primary transition-colors no-underline truncate"
                      >
                        {agent.name}
                      </Link>
                      {'tier' in agent && <TierBadge tier={agent.tier as string} />}
                    </div>
                    <p className="text-xs text-text-muted mt-0.5 truncate">
                      {agent.provider} / {agent.model_id}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs font-mono font-bold text-primary">
                        {agent.elo_rating} ELO
                      </span>
                      <span className="text-xs text-text-muted">
                        {agent.wins}W {agent.losses}L
                      </span>
                      {totalGames > 0 && (
                        <span className="text-xs text-text-muted">{winRate}%</span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border">
                  <Link
                    href={`/debate/agents/${agent.id}/edit`}
                    className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-text-muted border border-border rounded-lg hover:text-text hover:border-primary/40 transition-colors no-underline"
                  >
                    <Edit2 size={12} />
                    편집
                  </Link>
                  <button
                    onClick={() => handleDelete(agent.id, agent.name)}
                    disabled={deletingId === agent.id}
                    className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-text-muted border border-border rounded-lg hover:text-red-400 hover:border-red-400/40 transition-colors disabled:opacity-50"
                  >
                    <Trash2 size={12} />
                    {deletingId === agent.id ? '삭제 중...' : '삭제'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
