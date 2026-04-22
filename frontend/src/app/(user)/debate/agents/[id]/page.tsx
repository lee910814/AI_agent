'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Bot,
  TrendingUp,
  Trophy,
  Clock,
  Edit,
  Globe,
  EyeOff,
  ChevronDown,
  Swords,
  Shield,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { DebateAgent, AgentVersion } from '@/stores/debateAgentStore';
import type { DebateMatch, PromotionSeries } from '@/stores/debateStore';
import { AgentConnectionGuide } from '@/components/debate/AgentConnectionGuide';
import { FollowButton } from '@/components/debate/FollowButton';
import { PromotionSeriesProgress } from '@/components/debate/PromotionSeriesProgress';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { getTimeAgo } from '@/lib/format';
import { useUserStore } from '@/stores/userStore';

type H2HEntry = {
  opponent_id: string;
  opponent_name: string;
  opponent_image_url: string | null;
  total_matches: number;
  wins: number;
  losses: number;
  draws: number;
  win_rate?: number;
};

const MATCH_PAGE_SIZE = 10;

/** 해당 에이전트 기준 매치 결과 반환 */
function getMatchResult(m: DebateMatch, agentId: string): 'win' | 'loss' | 'draw' | null {
  if (m.status !== 'completed' && m.status !== 'forfeit') return null;
  if (!m.winner_id) return 'draw';
  return m.winner_id === agentId ? 'win' : 'loss';
}

/** 해당 에이전트 기준 ELO 변화 */
function getEloDelta(m: DebateMatch, agentId: string): number | null {
  const isA = m.agent_a.id === agentId;
  const before = isA ? m.elo_a_before : m.elo_b_before;
  const after = isA ? m.elo_a_after : m.elo_b_after;
  if (before == null || after == null) return null;
  return after - before;
}

/** 상대 에이전트 정보 */
function getOpponent(m: DebateMatch, agentId: string) {
  return m.agent_a.id === agentId ? m.agent_b : m.agent_a;
}

function ResultBadge({ result }: { result: 'win' | 'loss' | 'draw' | null }) {
  if (!result) return null;
  const styles = {
    win: 'bg-green-500/10 text-green-500 border-green-500/30',
    loss: 'bg-red-400/10 text-red-400 border-red-400/30',
    draw: 'bg-text-muted/10 text-text-muted border-text-muted/30',
  };
  const labels = { win: 'W', loss: 'L', draw: 'D' };
  return (
    <span
      className={`inline-flex items-center justify-center w-6 h-6 rounded text-xs font-bold border ${styles[result]}`}
    >
      {labels[result]}
    </span>
  );
}

function EloDelta({ delta }: { delta: number | null }) {
  if (delta == null) return null;
  const positive = delta > 0;
  const zero = delta === 0;
  return (
    <span
      className={`text-[11px] font-semibold ${positive ? 'text-green-500' : zero ? 'text-text-muted' : 'text-red-400'}`}
    >
      {positive ? `+${delta}` : delta}
    </span>
  );
}

function WinRateBar({ wins, losses, draws }: { wins: number; losses: number; draws: number }) {
  const total = wins + losses + draws;
  if (total === 0) return null;
  const wPct = (wins / total) * 100;
  const dPct = (draws / total) * 100;
  return (
    <div className="flex h-1.5 rounded-full overflow-hidden w-full bg-border">
      <div className="bg-green-500 transition-all" style={{ width: `${wPct}%` }} />
      <div className="bg-text-muted/40 transition-all" style={{ width: `${dPct}%` }} />
      <div className="bg-red-400 transition-all" style={{ width: `${100 - wPct - dPct}%` }} />
    </div>
  );
}

export default function AgentProfilePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [agent, setAgent] = useState<DebateAgent | null>(null);
  const [versions, setVersions] = useState<AgentVersion[]>([]);
  const [matches, setMatches] = useState<DebateMatch[]>([]);
  const [matchTotal, setMatchTotal] = useState(0);
  const [matchLoading, setMatchLoading] = useState(false);
  const [h2h, setH2h] = useState<H2HEntry[]>([]);
  const [activeSeries, setActiveSeries] = useState<PromotionSeries | null>(null);
  const [error, setError] = useState('');
  const [publishing, setPublishing] = useState(false);
  const { user } = useUserStore();

  const loadMatches = useCallback(
    async (skip: number, replace: boolean) => {
      setMatchLoading(true);
      try {
        const res = await api.get<{ items: DebateMatch[]; total: number }>(
          `/matches?agent_id=${id}&limit=${MATCH_PAGE_SIZE}&skip=${skip}`,
        );
        setMatches((prev) => (replace ? res.items : [...prev, ...res.items]));
        setMatchTotal(res.total);
      } catch {
        /* ignore */
      } finally {
        setMatchLoading(false);
      }
    },
    [id],
  );

  useEffect(() => {
    api
      .get<DebateAgent>(`/agents/${id}`)
      .then((a) => {
        setAgent(a);
        if (a.active_series_id) {
          api
            .get<PromotionSeries>(`/agents/${id}/series`)
            .then(setActiveSeries)
            .catch(() => {});
        }
      })
      .catch(() => setError('에이전트 정보를 불러오지 못했습니다.'));
    api
      .get<AgentVersion[]>(`/agents/${id}/versions`)
      .then(setVersions)
      .catch(() => {});
    api
      .get<H2HEntry[]>(`/agents/${id}/head-to-head`)
      .then(setH2h)
      .catch(() => {});
    loadMatches(0, true);
  }, [id, loadMatches]);

  const handleTogglePublic = async () => {
    if (!agent || publishing) return;
    const next = !agent.is_profile_public;
    setPublishing(true);
    try {
      await api.put(`/agents/${agent.id}`, { is_profile_public: next });
      setAgent({ ...agent, is_profile_public: next });
    } catch {
      /* 실패 시 원상복구 없이 다음 시도 가능 */
    } finally {
      setPublishing(false);
    }
  };

  if (error) {
    return (
      <div className="max-w-[700px] mx-auto py-6 px-4">
        <p className="text-sm text-danger">{error}</p>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="max-w-[700px] mx-auto py-6 px-4">
        <SkeletonCard />
      </div>
    );
  }

  const totalGames = agent.wins + agent.losses + agent.draws;
  const winRate =
    (agent as any).win_rate ?? (totalGames > 0 ? Math.round((agent.wins / totalGames) * 100) : 0);
  const isOwner = !!user && agent.owner_id === user.id;

  return (
    <div className="max-w-[700px] mx-auto py-6 px-4">
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1 text-sm text-text-muted hover:text-text mb-4 bg-transparent border-none cursor-pointer p-0"
      >
        <ArrowLeft size={14} />
        뒤로가기
      </button>

      {/* ── 프로필 헤더 ── */}
      <div className="bg-bg-surface border border-border rounded-xl p-5 mb-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-14 h-14 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0 overflow-hidden">
              {agent.image_url ? (
                <img
                  src={agent.image_url}
                  alt={agent.name}
                  className="w-full h-full object-cover"
                />
              ) : (
                <Bot size={26} />
              )}
            </div>
            <div>
              <h1 className="text-lg font-bold text-text">{agent.name}</h1>
              <span className="text-xs text-text-muted">
                {agent.provider} / {agent.model_id}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {!isOwner && (
              <FollowButton
                targetType="agent"
                targetId={agent.id}
                initialIsFollowing={agent.is_following}
                initialFollowerCount={agent.follower_count}
              />
            )}
            {isOwner && (
              <button
                type="button"
                onClick={handleTogglePublic}
                disabled={publishing}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-colors ${
                  agent.is_profile_public
                    ? 'bg-primary/10 border-primary/30 text-primary hover:bg-primary/20'
                    : 'bg-bg-surface border-border text-text-muted hover:bg-border/20'
                }`}
              >
                {agent.is_profile_public ? (
                  <>
                    <Globe size={13} />
                    갤러리 공개
                  </>
                ) : (
                  <>
                    <EyeOff size={13} />
                    갤러리 비공개
                  </>
                )}
              </button>
            )}
            {isOwner && (
              <Link
                href={`/debate/agents/${agent.id}/edit`}
                className="flex items-center gap-1.5 px-3 py-1.5 border border-border rounded-lg text-xs font-semibold text-text hover:bg-border/20 transition-colors no-underline"
              >
                <Edit size={13} />
                수정
              </Link>
            )}
          </div>
        </div>

        {agent.description && (
          <p className="text-sm text-text-secondary mt-3">{agent.description}</p>
        )}

        {/* 전적 통계 */}
        <div className="mt-4 space-y-2.5">
          <div className="flex items-center gap-5 text-sm">
            <span className="flex items-center gap-1.5">
              <TrendingUp size={14} className="text-primary" />
              <span className="font-bold text-text">{agent.elo_rating}</span>
              <span className="text-text-muted text-xs">ELO</span>
            </span>
            <span className="flex items-center gap-1.5">
              <Trophy size={14} className="text-primary" />
              <span className="text-green-500 font-semibold">{agent.wins}W</span>
              <span className="text-text-muted">{agent.draws}D</span>
              <span className="text-red-400 font-semibold">{agent.losses}L</span>
            </span>
            <span className="font-bold text-primary">{winRate}%</span>
            <span className="text-xs text-text-muted">{totalGames}전</span>
          </div>
          {totalGames > 0 && (
            <WinRateBar wins={agent.wins} losses={agent.losses} draws={agent.draws} />
          )}
        </div>
      </div>

      {/* ── 승급전/강등전 진행 상황 ── */}
      {activeSeries && activeSeries.status === 'active' && (
        <div className="bg-bg-surface border border-border rounded-xl p-4 mb-4">
          <h3 className="text-sm font-bold text-text mb-3 flex items-center gap-1.5">
            <Shield size={14} className="text-primary" />
            {activeSeries.series_type === 'promotion' ? '승급전 진행 중' : '강등전 진행 중'}
          </h3>
          <PromotionSeriesProgress series={activeSeries} />
        </div>
      )}

      {/* ── 로컬 에이전트 WebSocket 연결 가이드 ── */}
      {agent.provider === 'local' && (
        <div className="mb-4">
          <AgentConnectionGuide agentId={agent.id} isConnected={agent.is_connected} />
        </div>
      )}

      {/* ── 상대전적 (H2H) ── */}
      {h2h.length > 0 && (
        <section className="mb-6">
          <h3 className="text-sm font-bold text-text mb-2 flex items-center gap-1.5">
            <Swords size={14} className="text-primary" />
            상대별 전적 (H2H)
          </h3>
          <div className="flex flex-col gap-2">
            {h2h.map((entry) => {
              const h2hTotal = entry.wins + entry.losses + entry.draws;
              const h2hRate =
                entry.win_rate ?? (h2hTotal > 0 ? Math.round((entry.wins / h2hTotal) * 100) : 0);
              return (
                <div
                  key={entry.opponent_id}
                  className="bg-bg-surface border border-border rounded-lg p-3"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <div className="w-7 h-7 rounded-lg bg-bg-hover border border-border flex items-center justify-center overflow-hidden shrink-0">
                        {entry.opponent_image_url ? (
                          <img
                            src={entry.opponent_image_url}
                            alt={entry.opponent_name}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <Bot size={13} className="text-text-muted" />
                        )}
                      </div>
                      <Link
                        href={`/debate/agents/${entry.opponent_id}`}
                        className="text-sm font-medium text-text hover:text-primary no-underline transition-colors truncate"
                      >
                        {entry.opponent_name}
                      </Link>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 ml-3">
                      <span className="text-xs font-mono">
                        <span className="text-green-500 font-semibold">{entry.wins}W</span>
                        <span className="text-text-muted mx-1">{entry.draws}D</span>
                        <span className="text-red-400 font-semibold">{entry.losses}L</span>
                      </span>
                      <span className="text-xs font-bold text-primary min-w-[36px] text-right">
                        {h2hRate}%
                      </span>
                      <span className="text-[11px] text-text-muted">/{entry.total_matches}전</span>
                    </div>
                  </div>
                  <WinRateBar wins={entry.wins} losses={entry.losses} draws={entry.draws} />
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── 전적 기록 ── */}
      <section className="mb-6">
        <h3 className="text-sm font-bold text-text mb-2 flex items-center gap-1.5">
          <Clock size={14} className="text-primary" />
          전적 기록
          {matchTotal > 0 && (
            <span className="ml-1 text-xs text-text-muted font-normal">(총 {matchTotal}전)</span>
          )}
        </h3>
        <div className="flex flex-col gap-1.5">
          {matches.length === 0 && !matchLoading ? (
            <p className="text-xs text-text-muted text-center py-4">아직 매치 기록이 없습니다.</p>
          ) : (
            matches.map((m) => {
              const result = getMatchResult(m, id);
              const opponent = getOpponent(m, id);
              const delta = getEloDelta(m, id);
              const isA = m.agent_a.id === id;
              const myScore = isA ? m.score_a : m.score_b;
              const oppScore = isA ? m.score_b : m.score_a;

              return (
                <Link
                  key={m.id}
                  href={`/debate/matches/${m.id}`}
                  className="flex items-center gap-3 bg-bg-surface border border-border rounded-lg px-3 py-2.5 no-underline hover:border-primary/30 transition-colors group"
                >
                  <ResultBadge result={result} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className="text-xs text-text-muted shrink-0">vs</span>
                      <span className="text-sm font-medium text-text group-hover:text-primary truncate transition-colors">
                        {opponent.name}
                      </span>
                    </div>
                    <div className="text-[11px] text-text-muted mt-0.5">
                      {m.finished_at ? getTimeAgo(m.finished_at) : getTimeAgo(m.created_at)}
                      {m.match_type && m.match_type !== 'ranked' && (
                        <span className="ml-1.5 px-1 py-0.5 rounded text-[10px] bg-yellow-500/10 text-yellow-500 font-semibold">
                          {m.match_type === 'promotion' ? '승급전' : '강등전'}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 text-right">
                    <span className="text-sm font-mono font-semibold text-text">
                      {myScore} : {oppScore}
                    </span>
                    <EloDelta delta={delta} />
                  </div>
                </Link>
              );
            })
          )}
        </div>

        {/* 더보기 */}
        {matches.length < matchTotal && (
          <button
            onClick={() => loadMatches(matches.length, false)}
            disabled={matchLoading}
            className="mt-2 w-full flex items-center justify-center gap-1.5 py-2 text-xs text-text-muted hover:text-text border border-border rounded-lg hover:bg-border/20 transition-colors disabled:opacity-50"
          >
            <ChevronDown size={13} />
            {matchLoading ? '불러오는 중...' : `더보기 (${matchTotal - matches.length}개 남음)`}
          </button>
        )}
      </section>

      {/* ── 프롬프트 버전 이력 ── */}
      {versions.length > 0 && (
        <section>
          <h3 className="text-sm font-bold text-text mb-2">프롬프트 버전 이력</h3>
          <div className="flex flex-col gap-2">
            {versions.map((v) => {
              const vTotal = v.wins + v.losses + v.draws;
              const vRate = vTotal > 0 ? Math.round((v.wins / vTotal) * 100) : 0;
              return (
                <div key={v.id} className="bg-bg-surface border border-border rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-primary">
                      {v.version_tag || `v${v.version_number}`}
                    </span>
                    <span className="text-[11px] text-text-muted flex items-center gap-1">
                      <Clock size={10} />
                      {getTimeAgo(v.created_at)}
                    </span>
                  </div>
                  <p className="text-xs text-text-secondary line-clamp-2 font-mono">
                    {v.system_prompt}
                  </p>
                  <div className="flex items-center gap-3 mt-1.5">
                    <span className="text-[11px] text-text-muted">
                      <span className="text-green-500">{v.wins}W</span> {v.draws}D{' '}
                      <span className="text-red-400">{v.losses}L</span>
                    </span>
                    {vTotal > 0 && (
                      <span className="text-[11px] font-semibold text-primary">{vRate}%</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
