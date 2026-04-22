'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Swords,
  Users,
  Lock,
  Shield,
  MessageSquare,
  Trophy,
  Zap,
} from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { useDebateStore } from '@/stores/debateStore';
import { useDebateAgentStore } from '@/stores/debateAgentStore';
import { useToastStore } from '@/stores/toastStore';
import { SkeletonCard } from '@/components/ui/Skeleton';
import type { DebateTopic, DebateMatch } from '@/stores/debateStore';

type ConflictInfo = { existingTopicId: string; existingTopicTitle: string };
type QueueStatusResponse = {
  status: 'not_in_queue' | 'queued' | 'matched';
  joined_at?: string;
  is_ready?: boolean;
  opponent_agent_id?: string | null;
  match_id?: string;
};

const MODE_LABELS: Record<string, string> = {
  debate: '찬반 토론',
  persuasion: '설득',
  cross_exam: '교차 심문',
};

const STATUS_CONFIG: Record<string, { bg: string; text: string; dot?: string; label: string }> = {
  open: { bg: 'bg-green-500/10', text: 'text-green-500', dot: 'bg-green-500', label: '참가 가능' },
  in_progress: {
    bg: 'bg-yellow-500/10',
    text: 'text-yellow-500',
    dot: 'bg-yellow-500',
    label: '진행 중',
  },
  scheduled: { bg: 'bg-blue-500/10', text: 'text-blue-400', label: '예정' },
  closed: { bg: 'bg-text-muted/10', text: 'text-text-muted', label: '종료' },
};

const MATCH_STATUS_CONFIG: Record<string, { bg: string; text: string; label: string }> = {
  completed: { bg: 'bg-green-500/10', text: 'text-green-500', label: '완료' },
  in_progress: { bg: 'bg-yellow-500/10', text: 'text-yellow-500', label: '진행 중' },
  scheduled: { bg: 'bg-blue-500/10', text: 'text-blue-400', label: '예정' },
  cancelled: { bg: 'bg-text-muted/10', text: 'text-text-muted', label: '취소' },
};

export default function TopicDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { joinQueue } = useDebateStore();
  const { agents, fetchMyAgents } = useDebateAgentStore();
  const addToast = useToastStore((s) => s.addToast);

  const [topic, setTopic] = useState<DebateTopic | null>(null);
  const [matches, setMatches] = useState<DebateMatch[]>([]);
  const [selectedAgent, setSelectedAgent] = useState('');
  const [password, setPassword] = useState('');
  const [joining, setJoining] = useState(false);
  const [conflictInfo, setConflictInfo] = useState<ConflictInfo | null>(null);
  const [forceJoining, setForceJoining] = useState(false);
  const [agentQueueStatus, setAgentQueueStatus] = useState<QueueStatusResponse | null>(null);

  useEffect(() => {
    api
      .get<DebateTopic>(`/topics/${id}`)
      .then(setTopic)
      .catch(() => {});
    api
      .get<{ items: DebateMatch[] }>(`/matches?topic_id=${id}`)
      .then((r) => setMatches(r.items))
      .catch(() => {});
    fetchMyAgents();
  }, [id, fetchMyAgents]);

  const handleAgentSelect = async (agentId: string) => {
    const next = agentId === selectedAgent ? '' : agentId;
    setSelectedAgent(next);
    setConflictInfo(null);
    setAgentQueueStatus(null);
    if (!next) return;
    try {
      const status = await api.get<QueueStatusResponse>(
        `/topics/${id}/queue/status?agent_id=${next}`,
      );
      setAgentQueueStatus(status);
    } catch {
      // 상태 조회 실패는 참가 시점에 처리
    }
  };

  const handleForceJoin = async () => {
    if (!conflictInfo || !selectedAgent) return;
    setForceJoining(true);
    try {
      const { leaveQueue } = useDebateStore.getState();
      await leaveQueue(conflictInfo.existingTopicId, selectedAgent);
      setConflictInfo(null);
      await handleJoin();
    } catch {
      addToast('error', '대기 취소 중 오류가 발생했습니다.');
    } finally {
      setForceJoining(false);
    }
  };

  const handleJoin = async () => {
    if (!selectedAgent) return;
    setJoining(true);
    try {
      const result = await joinQueue(id, selectedAgent, password || undefined);
      if (result.status === 'matched' && result.match_id) {
        router.push(`/debate/matches/${result.match_id}`);
      } else {
        router.push(`/debate/waiting/${id}?agent=${selectedAgent}`);
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const detail = e.body as { message: string; existing_topic_id: string } | null;
        const existingTopicId = detail?.existing_topic_id ?? '';
        let existingTopicTitle = '다른 토픽';
        if (existingTopicId) {
          try {
            const t = await api.get<{ title: string }>(`/topics/${existingTopicId}`);
            existingTopicTitle = t.title;
          } catch {}
        }
        setConflictInfo({ existingTopicId, existingTopicTitle });
      } else {
        addToast('error', e instanceof ApiError ? e.message : '참가에 실패했습니다.');
      }
      setJoining(false);
    }
  };

  if (!topic) {
    return (
      <div className="max-w-[1200px] mx-auto py-12 px-4 xl:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 flex flex-col gap-4">
            <SkeletonCard />
            <SkeletonCard />
          </div>
          <div className="lg:col-span-1">
            <SkeletonCard />
          </div>
        </div>
      </div>
    );
  }

  const statusCfg = STATUS_CONFIG[topic.status] ?? STATUS_CONFIG.closed;
  const canJoin = topic.status === 'open';

  return (
    <div className="max-w-[1200px] mx-auto py-12 px-4 xl:px-8">
      {/* 뒤로 가기 */}
      <div className="flex flex-col gap-2 mb-10">
        <Link
          href="/debate"
          className="flex items-center gap-1.5 text-xs font-bold text-text-muted no-underline hover:text-text transition-colors w-fit"
        >
          <ArrowLeft size={13} />
          토론 목록으로
        </Link>
        <h1 className="text-lg font-black text-text flex items-center gap-3 m-0">
          <Swords size={20} className="text-primary" />
          토픽 상세
        </h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* ── 왼쪽: 토픽 정보 + 매치 기록 ───────────────────────────── */}
        <div className="lg:col-span-2 flex flex-col gap-5">
          {/* 토픽 카드 */}
          <div className="bg-bg-surface brutal-border brutal-shadow-sm rounded-2xl p-6">
            {/* 상태·모드 뱃지 */}
            <div className="flex items-center gap-2 mb-4">
              <span
                className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-black tracking-tight ${statusCfg.bg} ${statusCfg.text} border border-black/5`}
              >
                {statusCfg.dot && (
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${statusCfg.dot} ${topic.status === 'open' ? 'animate-pulse' : ''}`}
                  />
                )}
                {statusCfg.label}
              </span>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-[10px] font-black bg-primary/10 text-primary">
                {MODE_LABELS[topic.mode] ?? topic.mode}
              </span>
              {topic.is_admin_topic && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[10px] font-black bg-primary/5 text-primary/70">
                  <Shield size={10} />
                  공식
                </span>
              )}
              {topic.is_password_protected && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[10px] font-black bg-yellow-500/10 text-yellow-500">
                  <Lock size={10} />
                  비공개
                </span>
              )}
            </div>

            <h2 className="text-xl font-black text-text m-0 mb-3 leading-snug">{topic.title}</h2>
            {topic.description && (
              <p className="text-sm text-text-secondary leading-relaxed mb-4">
                {topic.description}
              </p>
            )}

            {/* 스탯 그리드 */}
            <div className="grid grid-cols-3 gap-3 pt-4 border-t border-border">
              <div className="flex flex-col items-center gap-0.5 py-2">
                <span className="text-lg font-black text-text">{topic.max_turns}</span>
                <span className="text-[10px] font-bold text-text-muted">최대 라운드</span>
              </div>
              <div className="flex flex-col items-center gap-0.5 py-2 border-x border-border">
                <span className="text-lg font-black text-text">{topic.queue_count}</span>
                <span className="text-[10px] font-bold text-text-muted">대기 중</span>
              </div>
              <div className="flex flex-col items-center gap-0.5 py-2">
                <span className="text-lg font-black text-text">{topic.match_count}</span>
                <span className="text-[10px] font-bold text-text-muted">총 매치</span>
              </div>
            </div>

            {topic.creator_nickname && (
              <p className="text-[11px] text-text-muted mt-3 pt-3 border-t border-border m-0">
                제안자:{' '}
                <span className="font-bold text-text-secondary">@{topic.creator_nickname}</span>
              </p>
            )}
          </div>

          {/* 매치 기록 */}
          <div className="bg-bg-surface brutal-border brutal-shadow-sm rounded-2xl p-6">
            <h3 className="text-sm font-black text-text m-0 mb-4 flex items-center gap-2">
              <MessageSquare size={15} className="text-primary" />
              매치 기록
              {matches.length > 0 && (
                <span className="text-xs font-bold text-text-muted">({matches.length})</span>
              )}
            </h3>

            {matches.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-text-muted">
                <Trophy size={28} className="mb-2 opacity-40" />
                <p className="text-xs font-medium m-0">아직 매치가 없습니다</p>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {matches.map((m) => {
                  const ms = MATCH_STATUS_CONFIG[m.status] ?? MATCH_STATUS_CONFIG.cancelled;
                  return (
                    <Link
                      key={m.id}
                      href={`/debate/matches/${m.id}`}
                      className="flex items-center justify-between bg-bg brutal-border rounded-xl p-3.5 no-underline hover:border-primary/40 hover:translate-y-[-1px] transition-all group"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                          <Swords size={13} className="text-primary" />
                        </div>
                        <span className="text-sm font-black text-text group-hover:text-primary transition-colors">
                          {m.agent_a.name}
                          <span className="mx-1.5 text-text-muted font-normal">vs</span>
                          {m.agent_b.name}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {m.status === 'completed' && (
                          <span className="text-xs font-black text-text">
                            {m.score_a} : {m.score_b}
                          </span>
                        )}
                        <span
                          className={`text-[10px] font-black px-2 py-0.5 rounded-full ${ms.bg} ${ms.text}`}
                        >
                          {ms.label}
                        </span>
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* ── 오른쪽: 참가 패널 ─────────────────────────────────────── */}
        <div className="lg:col-span-1 sticky top-4">
          {canJoin ? (
            <div className="bg-bg-surface brutal-border brutal-shadow-sm rounded-2xl p-5">
              <h3 className="text-sm font-black text-text m-0 mb-4 flex items-center gap-2">
                <Zap size={15} className="text-primary" />
                토론 참가
              </h3>

              {agents.length === 0 ? (
                <div className="text-center py-4">
                  <Users size={28} className="mx-auto mb-2 text-text-muted opacity-40" />
                  <p className="text-xs text-text-muted mb-3">
                    참가하려면 에이전트를 먼저 만드세요.
                  </p>
                  <Link
                    href="/debate/agents/create"
                    className="inline-block px-4 py-2 bg-primary text-white text-xs font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-1px] transition-all no-underline"
                  >
                    에이전트 만들기
                  </Link>
                </div>
              ) : (
                <>
                  {/* 에이전트 선택 카드 리스트 */}
                  <div className="flex flex-col gap-2 mb-4">
                    {agents.map((agent) => {
                      const isSelected = selectedAgent === agent.id;
                      return (
                        <button
                          key={agent.id}
                          onClick={() => handleAgentSelect(agent.id)}
                          className={`w-full flex items-center justify-between p-3 rounded-xl border-2 transition-all cursor-pointer text-left ${
                            isSelected
                              ? 'border-primary bg-primary/5 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]'
                              : 'border-border bg-bg hover:border-primary/40 hover:translate-y-[-1px]'
                          }`}
                        >
                          <div className="flex flex-col gap-0.5 min-w-0">
                            <span className="text-sm font-black text-text truncate">
                              {agent.name}
                            </span>
                            <span className="text-[10px] font-bold text-text-muted">
                              {agent.provider} · {agent.model_id}
                            </span>
                          </div>
                          <div className="flex flex-col items-end gap-0.5 shrink-0 ml-2">
                            <span className="text-sm font-black text-primary">
                              {agent.elo_rating}
                            </span>
                            <span className="text-[10px] font-bold text-text-muted">ELO</span>
                          </div>
                        </button>
                      );
                    })}
                  </div>

                  {/* 대기 상태 안내 */}
                  {agentQueueStatus?.status === 'queued' && (
                    <p className="text-xs font-bold text-yellow-500 bg-yellow-500/10 rounded-lg px-3 py-2 mb-3">
                      이 에이전트는 이미 대기 중입니다.
                    </p>
                  )}
                  {agentQueueStatus?.status === 'matched' && agentQueueStatus.match_id && (
                    <p className="text-xs font-bold text-blue-400 bg-blue-500/10 rounded-lg px-3 py-2 mb-3">
                      진행 중인 매치가 있습니다.{' '}
                      <button
                        onClick={() => router.push(`/debate/matches/${agentQueueStatus.match_id}`)}
                        className="underline bg-transparent border-none cursor-pointer text-blue-400 font-bold"
                      >
                        매치 보기
                      </button>
                    </p>
                  )}

                  {/* 충돌(다른 토픽 대기 중) */}
                  {conflictInfo && (
                    <div className="mb-3 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-xl text-xs">
                      <p className="text-text font-bold mb-2 m-0">
                        &ldquo;{conflictInfo.existingTopicTitle}&rdquo; 에 이미 대기 중입니다.
                        <br />
                        <span className="font-normal text-text-muted">
                          기존 대기를 취소하고 여기에 참가할까요?
                        </span>
                      </p>
                      <div className="flex gap-2 mt-2">
                        <button
                          onClick={() => setConflictInfo(null)}
                          className="flex-1 py-1.5 text-text-muted border border-border rounded-lg bg-transparent cursor-pointer text-xs font-bold"
                        >
                          취소
                        </button>
                        <button
                          onClick={handleForceJoin}
                          disabled={forceJoining}
                          className="flex-1 py-1.5 bg-primary text-white rounded-lg border-none cursor-pointer text-xs font-black disabled:opacity-50"
                        >
                          {forceJoining ? '처리 중...' : '대기 취소 후 참가'}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* 비밀번호 입력 */}
                  {topic.is_password_protected && (
                    <input
                      type="password"
                      placeholder="방 비밀번호 입력"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full mb-3 px-3 py-2.5 bg-bg border-2 border-border rounded-xl text-sm text-text placeholder-text-muted focus:outline-none focus:border-primary font-medium"
                    />
                  )}

                  {/* 참가 버튼 */}
                  <button
                    onClick={handleJoin}
                    disabled={
                      !selectedAgent ||
                      joining ||
                      agentQueueStatus?.status === 'queued'
                    }
                    className="w-full py-3 bg-primary text-white text-sm font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-1px] transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:translate-y-0 cursor-pointer border-none"
                  >
                    {joining
                      ? '참가 중...'
                      : agentQueueStatus?.status === 'queued'
                        ? '대기 중'
                        : selectedAgent
                          ? '참가하기'
                          : '에이전트를 선택하세요'}
                  </button>
                </>
              )}
            </div>
          ) : (
            /* 참가 불가 상태 */
            <div className="bg-bg-surface brutal-border brutal-shadow-sm rounded-2xl p-5">
              <div className="flex flex-col items-center justify-center py-6 text-center">
                <div
                  className={`px-3 py-1 rounded-full text-xs font-black mb-3 ${statusCfg.bg} ${statusCfg.text}`}
                >
                  {statusCfg.label}
                </div>
                <p className="text-sm font-bold text-text-muted m-0">
                  {topic.status === 'closed'
                    ? '이 토픽은 종료되었습니다.'
                    : topic.status === 'scheduled'
                      ? '아직 시작되지 않은 토픽입니다.'
                      : '현재 참가할 수 없습니다.'}
                </p>
              </div>
            </div>
          )}

          {/* 토픽 메타 정보 */}
          <div className="mt-4 bg-bg-surface brutal-border brutal-shadow-sm rounded-2xl p-5">
            <h3 className="text-xs font-black text-text-muted uppercase tracking-wider m-0 mb-3">
              토픽 정보
            </h3>
            <div className="flex flex-col gap-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted font-bold">턴당 토큰</span>
                <span className="font-black text-text">{topic.turn_token_limit.toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted font-bold">발언 횟수</span>
                <span className="font-black text-text">{topic.max_turns * 2}회 (각 {topic.max_turns}턴)</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted font-bold">보조 툴</span>
                <span className={`font-black ${topic.tools_enabled ? 'text-green-500' : 'text-text-muted'}`}>
                  {topic.tools_enabled ? '허용' : '비허용'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
