'use client';

import { useEffect, useState } from 'react';
import { X, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { TierBadge } from '@/components/debate/TierBadge';

type AgentDetail = {
  id: string;
  name: string;
  description: string | null;
  provider: string;
  model_id: string;
  image_url: string | null;
  elo_rating: number;
  tier: string;
  wins: number;
  losses: number;
  draws: number;
  is_active: boolean;
  is_platform: boolean;
  is_profile_public: boolean;
  is_system_prompt_public: boolean;
  created_at: string;
  owner: {
    id: string | null;
    nickname: string;
    created_at: string | null;
    agent_count: number;
  };
  versions: {
    id: string;
    version_number: number;
    version_tag: string | null;
    system_prompt: string;
    parameters: Record<string, unknown> | null;
    wins: number;
    losses: number;
    draws: number;
    created_at: string;
  }[];
  recent_matches: {
    id: string;
    topic_title: string;
    status: string;
    winner_id: string | null;
    score_a: number;
    score_b: number;
    created_at: string;
  }[];
};

const PROVIDER_BADGE: Record<string, string> = {
  openai: 'bg-green-500/20 text-green-400',
  anthropic: 'bg-orange-500/20 text-orange-400',
  google: 'bg-blue-500/20 text-blue-400',
  runpod: 'bg-purple-500/20 text-purple-400',
  local: 'bg-gray-500/20 text-gray-400',
};

function formatDate(iso: string | null) {
  if (!iso) return '-';
  return new Date(iso).toLocaleDateString('ko-KR');
}

type Props = {
  agentId: string | null;
  onClose: () => void;
};

export function AgentDetailModal({ agentId, onClose }: Props) {
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [expandedVersion, setExpandedVersion] = useState<string | null>(null);

  useEffect(() => {
    if (!agentId) {
      setDetail(null);
      return;
    }
    setLoading(true);
    api
      .get<AgentDetail>(`/admin/debate/agents/${agentId}`)
      .then(setDetail)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [agentId]);

  if (!agentId) return null;

  const totalGames = detail ? detail.wins + detail.losses + detail.draws : 0;
  const winRate = totalGames > 0 && detail ? Math.round((detail.wins / totalGames) * 100) : 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
      onClick={onClose}
    >
      <div
        className="bg-bg-surface border border-border rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border sticky top-0 bg-bg-surface z-10">
          <h2 className="font-bold text-text">에이전트 상세</h2>
          <button onClick={onClose} className="text-text-muted hover:text-text transition-colors">
            <X size={20} />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48 text-text-muted text-sm">
            로딩 중...
          </div>
        ) : detail ? (
          <div className="p-6 space-y-6">
            {/* 에이전트 기본 정보 */}
            <div className="flex items-start gap-4">
              <div className="w-16 h-16 rounded-xl border border-border bg-bg overflow-hidden shrink-0 flex items-center justify-center text-3xl">
                {detail.image_url ? (
                  <img
                    src={detail.image_url}
                    alt={detail.name}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  '🤖'
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-lg font-bold text-text">{detail.name}</h3>
                  <TierBadge tier={detail.tier} size="md" />
                  {!detail.is_active && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-400 font-semibold">
                      비활성
                    </span>
                  )}
                  {detail.is_platform && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/20 text-primary font-semibold">
                      플랫폼
                    </span>
                  )}
                </div>
                {detail.description && (
                  <p className="text-sm text-text-muted mt-1 line-clamp-2">{detail.description}</p>
                )}
                <div className="flex items-center gap-2 mt-2 flex-wrap">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-semibold ${PROVIDER_BADGE[detail.provider] ?? 'bg-gray-500/20 text-gray-400'}`}
                  >
                    {detail.provider}
                  </span>
                  <span className="text-xs text-text-muted">{detail.model_id}</span>
                </div>
              </div>
            </div>

            {/* ELO + 전적 */}
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: 'ELO', value: detail.elo_rating, color: 'text-primary' },
                { label: '승', value: detail.wins, color: 'text-green-400' },
                { label: '패', value: detail.losses, color: 'text-red-400' },
                { label: '승률', value: `${winRate}%`, color: 'text-yellow-400' },
              ].map((stat) => (
                <div
                  key={stat.label}
                  className="bg-bg border border-border rounded-xl p-3 text-center"
                >
                  <p className={`text-lg font-bold ${stat.color}`}>{stat.value}</p>
                  <p className="text-[11px] text-text-muted">{stat.label}</p>
                </div>
              ))}
            </div>

            {/* 소유자 정보 */}
            <div className="bg-bg border border-border rounded-xl p-4">
              <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-3">
                소유자
              </h4>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-text">{detail.owner.nickname}</p>
                  <p className="text-xs text-text-muted">ID: {detail.owner.id ?? '-'}</p>
                  <p className="text-xs text-text-muted">
                    가입일: {formatDate(detail.owner.created_at)}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-text">{detail.owner.agent_count}</p>
                  <p className="text-xs text-text-muted">보유 에이전트</p>
                </div>
              </div>
            </div>

            {/* 버전 히스토리 */}
            <div>
              <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-3">
                버전 히스토리
              </h4>
              <div className="space-y-2">
                {detail.versions.map((v) => (
                  <div key={v.id} className="border border-border rounded-lg overflow-hidden">
                    <button
                      className="w-full flex items-center justify-between px-4 py-2.5 bg-bg hover:bg-bg-hover transition-colors text-left"
                      onClick={() => setExpandedVersion(expandedVersion === v.id ? null : v.id)}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-text">
                          {v.version_tag ?? `v${v.version_number}`}
                        </span>
                        <span className="text-xs text-text-muted">{formatDate(v.created_at)}</span>
                        <span className="text-xs text-text-muted">
                          {v.wins}W {v.losses}L {v.draws}D
                        </span>
                      </div>
                      {expandedVersion === v.id ? (
                        <ChevronUp size={14} />
                      ) : (
                        <ChevronDown size={14} />
                      )}
                    </button>
                    {expandedVersion === v.id && (
                      <div className="px-4 py-3 bg-bg border-t border-border">
                        <pre className="text-xs text-text-secondary whitespace-pre-wrap font-mono max-h-48 overflow-y-auto">
                          {v.system_prompt}
                        </pre>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* 최근 매치 */}
            {detail.recent_matches.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-3">
                  최근 매치 5건
                </h4>
                <div className="space-y-2">
                  {detail.recent_matches.map((m) => (
                    <Link
                      key={m.id}
                      href={`/debate/matches/${m.id}`}
                      className="flex items-center justify-between px-3 py-2 bg-bg border border-border rounded-lg hover:border-primary/40 transition-colors no-underline"
                      target="_blank"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <ExternalLink size={12} className="text-text-muted shrink-0" />
                        <span className="text-sm text-text truncate">{m.topic_title}</span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-xs text-text-muted">
                          {m.score_a}:{m.score_b}
                        </span>
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${
                            m.status === 'completed'
                              ? 'bg-green-500/20 text-green-400'
                              : m.status === 'in_progress'
                                ? 'bg-yellow-500/20 text-yellow-400'
                                : 'bg-gray-500/20 text-gray-400'
                          }`}
                        >
                          {m.status === 'completed'
                            ? '완료'
                            : m.status === 'in_progress'
                              ? '진행 중'
                              : m.status}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-48 text-text-muted text-sm">
            에이전트를 찾을 수 없습니다.
          </div>
        )}
      </div>
    </div>
  );
}
