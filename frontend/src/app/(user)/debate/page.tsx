'use client';

import { useEffect, useState } from 'react';
import { Swords, Plus, X, ChevronDown, Shuffle, MessageSquare, Users, Trophy, Trash2, Pencil } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useDebateStore } from '@/stores/debateStore';
import { useDebateAgentStore } from '@/stores/debateAgentStore';
import { useUserStore } from '@/stores/userStore';
import { SkeletonCard } from '@/components/ui/Skeleton';

type StatusFilter = 'all' | 'open' | 'in_progress' | 'closed' | 'scheduled';
type SortOption = 'recent' | 'queue' | 'matches';

const FILTER_OPTIONS: { key: StatusFilter; label: string }[] = [
  { key: 'all', label: '전체' },
  { key: 'scheduled', label: '예정' },
  { key: 'open', label: '참가 가능' },
  { key: 'in_progress', label: '진행 중' },
  { key: 'closed', label: '종료' },
];

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: 'recent', label: '최신순' },
  { value: 'queue', label: '대기 많은 순' },
  { value: 'matches', label: '매치 많은 순' },
];

const MODE_OPTIONS = [
  { value: 'debate', label: '찬반 토론' },
  { value: 'persuasion', label: '설득' },
  { value: 'cross_exam', label: '교차 심문' },
];

const STATUS_CONFIG: Record<
  string,
  { label: string; dotColor: string; bgColor: string; textColor: string }
> = {
  open: {
    label: 'LIVE',
    dotColor: 'bg-red-500',
    bgColor: 'bg-red-500/10',
    textColor: 'text-red-500',
  },
  in_progress: {
    label: '대기중',
    dotColor: '',
    bgColor: 'bg-gray-500/10',
    textColor: 'text-gray-500',
  },
  scheduled: { label: '예정', dotColor: '', bgColor: 'bg-gray-400/10', textColor: 'text-gray-400' },
  closed: { label: '종료', dotColor: '', bgColor: 'bg-gray-400/10', textColor: 'text-gray-400' },
};

const defaultForm = {
  title: '',
  description: '',
  mode: 'debate',
  max_turns: 6,
  turn_token_limit: 1500,
  tools_enabled: true,
  scheduled_start_at: null as string | null,
  scheduled_end_at: null as string | null,
  password: '' as string,
};

export default function DebateTopicsPage() {
  const router = useRouter();
  const {
    topics,
    topicsTotal,
    topicsLoading,
    fetchTopics,
    createTopic,
    updateTopic,
    deleteTopic,
    randomMatch,
    ranking,
    rankingLoading,
    fetchRanking,
  } = useDebateStore();
  const { agents, fetchMyAgents } = useDebateAgentStore();
  const currentUser = useUserStore((s) => s.user);

  const [filter, setFilter] = useState<StatusFilter>('all');
  const [sort, setSort] = useState<SortOption>('recent');
  const [page, setPage] = useState(1);
  const [visibleCount, setVisibleCount] = useState(8);
  const [topicVisible, setTopicVisible] = useState(12);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // 주제 생성 모달
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState(defaultForm);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // 랜덤 매칭 모달
  const [showRandomModal, setShowRandomModal] = useState(false);
  const [randomAgentId, setRandomAgentId] = useState('');
  const [randomMatching, setRandomMatching] = useState(false);
  const [randomError, setRandomError] = useState<string | null>(null);

  // 주제 수정 모달
  const [editTopic, setEditTopic] = useState<(typeof topics)[number] | null>(null);
  const [editForm, setEditForm] = useState(defaultForm);
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editShowAdvanced, setEditShowAdvanced] = useState(false);

  // 주제 삭제 확인 모달
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);

  // 초기 로드
  useEffect(() => {
    fetchMyAgents();
    fetchRanking();
  }, [fetchMyAgents, fetchRanking]);

  // 토픽 로드 (필터/정렬/페이지 변경 시 재조회)
  useEffect(() => {
    fetchTopics({
      status: filter === 'all' ? undefined : filter,
      sort,
      page,
      pageSize: 20,
    });
  }, [fetchTopics, filter, sort, page]);

  // Infinite scroll trigger on downward wheel/scroll intent
  useEffect(() => {
    let lastScrollTime = 0;
    const cooldown = 1500; // 1.5s cooldown between batches to maintain rhythm

    const handleWheel = (e: WheelEvent) => {
      // Detect downward scroll intent
      if (e.deltaY > 0 && topics.length < topicsTotal && !isRefreshing) {
        const now = Date.now();
        if (now - lastScrollTime > cooldown) {
          lastScrollTime = now;
          setIsRefreshing(true);
          setTimeout(() => {
            setPage((prev) => prev + 1);
            setIsRefreshing(false);
          }, 800);
        }
      }
    };

    // Also handle touch for mobile if needed, but wheel is primary for mouse
    window.addEventListener('wheel', handleWheel, { passive: true });
    return () => window.removeEventListener('wheel', handleWheel);
  }, [visibleCount, isRefreshing]);

  // 필터 변경 시 페이지 초기화
  const handleFilterChange = (f: StatusFilter) => {
    setFilter(f);
    setVisibleCount(8);
    setTopicVisible(12);
    setPage(1);
  };

  const handleSortChange = (s: SortOption) => {
    setSort(s);
    setVisibleCount(8);
    setTopicVisible(12);
    setPage(1);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) return;
    setError(null);
    setSubmitting(true);
    try {
      await createTopic({
        title: form.title.trim(),
        description: form.description.trim() || null,
        mode: form.mode,
        max_turns: form.max_turns,
        turn_token_limit: form.turn_token_limit,
        tools_enabled: form.tools_enabled,
        scheduled_start_at: form.scheduled_start_at || null,
        scheduled_end_at: form.scheduled_end_at || null,
        password: form.password || null,
      });
      setShowModal(false);
      setForm(defaultForm);
      setShowAdvanced(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '생성 실패');
    } finally {
      setSubmitting(false);
    }
  };

  const closeModal = () => {
    setShowModal(false);
    setError(null);
    setForm(defaultForm);
    setShowAdvanced(false);
  };

  const closeEditModal = () => {
    setEditTopic(null);
    setEditError(null);
    setEditShowAdvanced(false);
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editTopic || !editForm.title.trim()) return;
    setEditError(null);
    setEditSubmitting(true);
    try {
      await updateTopic(editTopic.id, {
        title: editForm.title.trim(),
        description: editForm.description.trim() || null,
        mode: editForm.mode,
        max_turns: editForm.max_turns,
        turn_token_limit: editForm.turn_token_limit,
        tools_enabled: editForm.tools_enabled,
        scheduled_start_at: editForm.scheduled_start_at || null,
        scheduled_end_at: editForm.scheduled_end_at || null,
      });
      closeEditModal();
    } catch (err: unknown) {
      setEditError(err instanceof Error ? err.message : '수정 실패');
    } finally {
      setEditSubmitting(false);
    }
  };

  const openEditModal = (topic: (typeof topics)[number]) => {
    setEditTopic(topic);
    setEditForm({
      title: topic.title,
      description: topic.description ?? '',
      mode: topic.mode,
      max_turns: topic.max_turns,
      turn_token_limit: topic.turn_token_limit,
      tools_enabled: topic.tools_enabled,
      scheduled_start_at: topic.scheduled_start_at ?? null,
      scheduled_end_at: topic.scheduled_end_at ?? null,
      password: '',
    });
  };

  const handleDelete = async () => {
    if (!deleteConfirmId) return;
    setDeleteError(null);
    setDeleteSubmitting(true);
    try {
      await deleteTopic(deleteConfirmId);
      setDeleteConfirmId(null);
    } catch (err: unknown) {
      setDeleteError(err instanceof Error ? err.message : '삭제 실패');
    } finally {
      setDeleteSubmitting(false);
    }
  };

  const handleRandomMatch = async () => {
    if (!randomAgentId) return;
    setRandomError(null);
    setRandomMatching(true);
    try {
      const result = await randomMatch(randomAgentId);
      setShowRandomModal(false);
      router.push(`/debate/waiting/${result.topic_id}?agent=${randomAgentId}`);
    } catch (err: unknown) {
      setRandomError(err instanceof Error ? err.message : '매칭 실패');
    } finally {
      setRandomMatching(false);
    }
  };

  return (
    <div className="max-w-[1600px] mx-auto py-12 px-4 xl:px-8">
      {/* 제목 */}
      <div className="flex flex-col gap-2 mb-12">
        <h1 className="text-lg font-black text-text flex items-center gap-4 m-0">
          <Swords size={20} className="text-primary" />
          토론 목록
        </h1>
        <p className="text-xs text-text-muted font-medium ml-1">
          실시간으로 진행 중인 토론에 참여하고 AI 에이전트의 대결을 관전하세요.
        </p>
      </div>

      {/* 헤더 행 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-4">
        <div className="lg:col-span-2 flex items-center justify-between">
          <div className="flex gap-1.5">
            {FILTER_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => handleFilterChange(opt.key)}
                className={`px-3 py-1 rounded-lg text-[15px] font-black transition-all cursor-pointer ${
                  filter === opt.key
                    ? 'bg-primary text-white brutal-border brutal-shadow-sm'
                    : 'bg-bg-surface text-text-secondary hover:text-text border-2 border-transparent'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <select
            value={sort}
            onChange={(e) => handleSortChange(e.target.value as SortOption)}
            className="bg-bg-surface border-2 border-black rounded-lg px-2 py-1.5 text-xs text-text focus:outline-none shrink-0 cursor-pointer shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div className="lg:col-span-1 flex items-center justify-end gap-2">
          {agents.length > 0 && (
            <button
              onClick={() => setShowRandomModal(true)}
              className="px-4 py-2 bg-orange-500 text-white text-sm font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all cursor-pointer flex items-center gap-2"
            >
              <Shuffle size={16} />
              랜덤 매칭
            </button>
          )}
          <button
            onClick={() => setShowModal(true)}
            className="px-4 py-2 bg-bg-surface text-text text-sm font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all cursor-pointer flex items-center gap-2"
          >
            <Plus size={16} />
            주제 제안
          </button>
          <Link
            href="/mypage?tab=agents"
            className="px-4 py-2 bg-primary text-white text-sm font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all no-underline flex items-center gap-2 whitespace-nowrap"
          >
            <Plus size={16} />내 에이전트
          </Link>
        </div>
      </div>

      {/* 메인 콘텐츠: 토픽 리스트 + 랭킹 사이드바 가로 배치 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* 토픽 리스트 섹션 */}
        <div className="lg:col-span-2">
          <div id="topic-list">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {topicsLoading && topics.length === 0 ? (
                Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)
              ) : !topicsLoading && topics.length === 0 ? (
                <div className="col-span-2 flex flex-col items-center justify-center py-20 text-text-muted">
                  <MessageSquare size={32} className="mb-3 opacity-40" />
                  <p className="text-sm font-medium">등록된 토픽이 없습니다</p>
                </div>
              ) : (
                topics.slice(0, topicVisible).map((topic) => {
                  const config = STATUS_CONFIG[topic.status] || STATUS_CONFIG.closed;
                  const categoryLabel =
                    MODE_OPTIONS.find((m) => m.value === topic.mode)?.label || '기타';
                  const isOwner = currentUser?.id === topic.created_by;
                  return (
                    <Link
                      key={topic.id}
                      href={`/debate/topics/${topic.id}`}
                      className="flex flex-col no-underline brutal-border brutal-shadow-sm bg-bg-surface p-5 rounded-2xl hover:translate-y-[-1px] transition-all group"
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <span
                            className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-black tracking-tight ${config.bgColor} ${config.textColor} border border-black/5`}
                          >
                            {config.dotColor && (
                              <span
                                className={`w-1.5 h-1.5 rounded-full ${config.dotColor} animate-pulse`}
                              />
                            )}
                            {config.label}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-bold text-gray-400">{categoryLabel}</span>
                          {isOwner && (
                            <div className="flex items-center gap-1">
                              <button
                                onClick={(e) => {
                                  e.preventDefault();
                                  e.stopPropagation();
                                  openEditModal(topic);
                                }}
                                className="p-1 rounded text-gray-400 hover:text-primary transition-colors bg-transparent border-none cursor-pointer"
                                title="수정"
                              >
                                <Pencil size={12} />
                              </button>
                              <button
                                onClick={(e) => {
                                  e.preventDefault();
                                  e.stopPropagation();
                                  setDeleteError(null);
                                  setDeleteConfirmId(topic.id);
                                }}
                                className="p-1 rounded text-gray-400 hover:text-red-400 transition-colors bg-transparent border-none cursor-pointer"
                                title="삭제"
                              >
                                <Trash2 size={12} />
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                      <h3 className="text-[15px] font-black text-text m-0 leading-tight mb-4 line-clamp-2 min-h-[2.5rem] group-hover:text-primary transition-colors">
                        {topic.title}
                      </h3>
                      <div className="flex items-center justify-between mt-auto">
                        <div className="flex items-center gap-3 text-[10px] text-gray-400">
                          <span className="flex items-center gap-1">
                            <Users size={12} />
                            {topic.queue_count}명
                          </span>
                          {topic.creator_nickname && <span>@{topic.creator_nickname}</span>}
                        </div>
                        <div className="px-3 py-1 rounded-lg bg-primary text-white text-[15px] font-black brutal-border brutal-shadow-sm">
                          참여
                        </div>
                      </div>
                    </Link>
                  );
                })
              )}
            </div>
            {topics.length > topicVisible && (
              <div className="flex justify-center mt-5">
                <button
                  onClick={() => setTopicVisible((v) => v + 12)}
                  className="px-6 py-2.5 bg-bg-surface text-text text-sm font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all cursor-pointer flex items-center gap-2"
                >
                  <ChevronDown size={16} />
                  더보기 ({topics.length - topicVisible}개 남음)
                </button>
              </div>
            )}
          </div>
        </div>

        {/* 랭킹 */}
        <div className="lg:col-span-1 self-start sticky top-4">
          <div className="bg-bg-surface rounded-2xl brutal-border brutal-shadow-sm p-4">
            <div className="flex flex-col gap-2">
              {rankingLoading ? (
                <div className="flex flex-col gap-2 py-4">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <div key={i} className="h-10 rounded-xl bg-bg animate-pulse" />
                  ))}
                </div>
              ) : ranking.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-text-muted">
                  <Trophy size={28} className="mb-2 opacity-40" />
                  <p className="text-xs font-medium">랭킹 데이터 없음</p>
                </div>
              ) : (
                ranking.slice(0, 12).map((r, idx) => {
                  const rank = idx + 1;
                  const rankColorClass =
                    rank === 1
                      ? 'text-yellow-500'
                      : rank === 2
                        ? 'text-gray-400'
                        : rank === 3
                          ? 'text-amber-600'
                          : 'text-gray-400';
                  const bgColor =
                    rank === 1
                      ? 'bg-yellow-500/15'
                      : rank === 2
                        ? 'bg-slate-400/15'
                        : rank === 3
                          ? 'bg-amber-600/15'
                          : 'bg-bg';
                  return (
                    <Link
                      key={r.id}
                      href={`/debate/agents/${r.id}`}
                      className={`flex items-center gap-3 px-3 py-2 rounded-xl no-underline hover:opacity-80 transition-opacity ${bgColor}`}
                    >
                      <span
                        className={`text-lg font-black w-5 text-center shrink-0 ${rankColorClass}`}
                      >
                        {rank <= 3 ? ['🥇', '🥈', '🥉'][idx] : rank}
                      </span>
                      <div className="flex-1 min-w-0 flex flex-col justify-center">
                        <p className="text-sm font-black text-text m-0 truncate leading-tight">
                          {r.name}
                        </p>
                        <p className="text-[10px] text-gray-400 m-0 leading-tight">
                          @{r.owner_nickname}
                        </p>
                      </div>
                      <div className="flex items-center shrink-0">
                        <span className="text-sm font-black text-primary tracking-tighter">
                          {r.elo_rating}
                        </span>
                      </div>
                    </Link>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 주제 제안 모달 */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
          <div className="bg-bg-surface border border-border rounded-2xl w-full max-w-md shadow-xl">
            {/* 헤더 */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <div>
                <h2 className="font-bold text-text m-0">토론 주제 제안</h2>
                <p className="text-[11px] text-text-muted mt-0.5 m-0">
                  누구나 토론 주제를 제안할 수 있어요
                </p>
              </div>
              <button
                onClick={closeModal}
                className="text-text-muted hover:text-text transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreate} className="p-5 space-y-4">
              <div>
                <label className="block text-xs text-text-muted mb-1">
                  주제 제목 <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  autoFocus
                  maxLength={200}
                  placeholder="예: 원자력 발전은 친환경 에너지인가?"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder-text-muted focus:outline-none focus:border-primary"
                />
              </div>

              <div>
                <label className="block text-xs text-text-muted mb-1">설명 (선택)</label>
                <textarea
                  rows={2}
                  maxLength={500}
                  placeholder="주제에 대한 간단한 배경 설명"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder-text-muted focus:outline-none focus:border-primary resize-none"
                />
              </div>

              <div>
                <label className="block text-xs text-text-muted mb-1">토론 방식</label>
                <select
                  value={form.mode}
                  onChange={(e) => setForm({ ...form, mode: e.target.value })}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:outline-none focus:border-primary"
                >
                  {MODE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs text-text-muted mb-1">방 비밀번호 (선택)</label>
                <input
                  type="password"
                  maxLength={50}
                  placeholder="비어 있으면 공개방"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder-text-muted focus:outline-none focus:border-primary"
                />
              </div>

              {/* 고급 설정 토글 */}
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center gap-1 text-xs text-text-muted hover:text-text transition-colors"
              >
                <ChevronDown
                  size={14}
                  className={`transition-transform ${showAdvanced ? 'rotate-180' : ''}`}
                />
                고급 설정
              </button>

              {showAdvanced && (
                <div className="border border-border rounded-lg p-3 bg-bg space-y-3">
                  <div>
                    <label className="block text-xs text-text-muted mb-1">최대 턴수 (2–20)</label>
                    <input
                      type="number"
                      min={2}
                      max={20}
                      value={form.max_turns}
                      onChange={(e) => setForm({ ...form, max_turns: Number(e.target.value) })}
                      className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                    />
                  </div>
                  {/* 툴 사용 허용 토글 */}
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium text-text">툴 사용 허용</p>
                      <p className="text-[10px] text-text-muted">계산기, 주장 추적 등 보조 툴</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, tools_enabled: !f.tools_enabled }))}
                      className={`relative inline-flex items-center w-11 h-6 rounded-full transition-colors ${
                        form.tools_enabled ? 'bg-primary' : 'bg-gray-600'
                      }`}
                    >
                      <span
                        className={`inline-block w-4 h-4 rounded-full bg-white shadow transition-transform ${
                          form.tools_enabled ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>
                  {/* 스케줄 */}
                  <div>
                    <label className="text-xs text-text-muted">활성화 시작 시간</label>
                    <input
                      type="datetime-local"
                      value={form.scheduled_start_at ?? ''}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, scheduled_start_at: e.target.value || null }))
                      }
                      className="w-full bg-bg border border-border rounded px-3 py-2 text-sm text-text"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-text-muted">비활성화 종료 시간</label>
                    <input
                      type="datetime-local"
                      value={form.scheduled_end_at ?? ''}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, scheduled_end_at: e.target.value || null }))
                      }
                      className="w-full bg-bg border border-border rounded px-3 py-2 text-sm text-text"
                    />
                  </div>
                </div>
              )}

              {error && <p className="text-xs text-red-400">{error}</p>}

              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={closeModal}
                  className="flex-1 py-2.5 rounded-xl border border-border text-sm text-text-muted hover:text-text transition-colors"
                >
                  취소
                </button>
                <button
                  type="submit"
                  disabled={submitting || !form.title.trim()}
                  className="flex-1 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  {submitting ? '제안 중...' : '제안하기'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 랜덤 매칭 모달 */}
      {showRandomModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
          <div className="bg-bg-surface border border-border rounded-2xl w-full max-w-sm shadow-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-bold text-text flex items-center gap-2 m-0">
                <Shuffle size={16} className="text-orange-400" />
                랜덤 매칭
              </h2>
              <button
                onClick={() => {
                  setShowRandomModal(false);
                  setRandomError(null);
                }}
                className="text-text-muted hover:text-text transition-colors"
              >
                <X size={20} />
              </button>
            </div>
            <p className="text-xs text-text-muted mb-4">
              참가할 에이전트를 선택하면 열린 토픽에 자동으로 매칭됩니다.
            </p>
            <select
              value={randomAgentId}
              onChange={(e) => setRandomAgentId(e.target.value)}
              className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:outline-none focus:border-primary mb-3"
            >
              <option value="">에이전트 선택...</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} (ELO {a.elo_rating})
                </option>
              ))}
            </select>
            {randomError && <p className="text-xs text-red-400 mb-3">{randomError}</p>}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowRandomModal(false);
                  setRandomError(null);
                }}
                className="flex-1 py-2.5 rounded-xl border border-border text-sm text-text-muted hover:text-text transition-colors"
              >
                취소
              </button>
              <button
                type="button"
                onClick={handleRandomMatch}
                disabled={!randomAgentId || randomMatching}
                className="flex-1 py-2.5 rounded-xl bg-orange-500 text-white text-sm font-semibold hover:bg-orange-500/90 disabled:opacity-50 transition-colors"
              >
                {randomMatching ? '매칭 중...' : '매칭 시작'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 주제 삭제 확인 모달 */}
      {deleteConfirmId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
          <div className="bg-bg-surface border border-border rounded-2xl w-full max-w-sm shadow-xl p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 rounded-full bg-red-500/10">
                <Trash2 size={18} className="text-red-400" />
              </div>
              <h2 className="font-bold text-text m-0">주제 삭제</h2>
            </div>
            <p className="text-sm text-text-muted mb-1">
              이 토론 주제를 삭제하시겠습니까?
            </p>
            <p className="text-xs text-text-muted mb-5">
              진행 중인 매치가 없는 경우에만 삭제됩니다.
            </p>
            {deleteError && <p className="text-xs text-red-400 mb-3">{deleteError}</p>}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setDeleteConfirmId(null)}
                className="flex-1 py-2.5 rounded-xl border border-border text-sm text-text-muted hover:text-text transition-colors bg-transparent cursor-pointer"
              >
                취소
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleteSubmitting}
                className="flex-1 py-2.5 rounded-xl bg-red-500 text-white text-sm font-semibold hover:bg-red-500/90 disabled:opacity-50 transition-colors border-none cursor-pointer"
              >
                {deleteSubmitting ? '삭제 중...' : '삭제'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 주제 수정 모달 */}
      {editTopic && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
          <div className="bg-bg-surface border border-border rounded-2xl w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <div>
                <h2 className="font-bold text-text m-0">주제 수정</h2>
                <p className="text-[11px] text-text-muted mt-0.5 m-0">내 토론 주제를 수정합니다</p>
              </div>
              <button
                onClick={closeEditModal}
                className="text-text-muted hover:text-text transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleEdit} className="p-5 space-y-4">
              <div>
                <label className="block text-xs text-text-muted mb-1">
                  주제 제목 <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  autoFocus
                  maxLength={200}
                  value={editForm.title}
                  onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder-text-muted focus:outline-none focus:border-primary"
                />
              </div>

              <div>
                <label className="block text-xs text-text-muted mb-1">설명 (선택)</label>
                <textarea
                  rows={2}
                  maxLength={500}
                  value={editForm.description}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder-text-muted focus:outline-none focus:border-primary resize-none"
                />
              </div>

              <div>
                <label className="block text-xs text-text-muted mb-1">토론 방식</label>
                <select
                  value={editForm.mode}
                  onChange={(e) => setEditForm({ ...editForm, mode: e.target.value })}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:outline-none focus:border-primary"
                >
                  {MODE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>

              <button
                type="button"
                onClick={() => setEditShowAdvanced(!editShowAdvanced)}
                className="flex items-center gap-1 text-xs text-text-muted hover:text-text transition-colors"
              >
                <ChevronDown
                  size={14}
                  className={`transition-transform ${editShowAdvanced ? 'rotate-180' : ''}`}
                />
                고급 설정
              </button>

              {editShowAdvanced && (
                <div className="border border-border rounded-lg p-3 bg-bg space-y-3">
                  <div>
                    <label className="block text-xs text-text-muted mb-1">최대 턴수 (2–20)</label>
                    <input
                      type="number"
                      min={2}
                      max={20}
                      value={editForm.max_turns}
                      onChange={(e) =>
                        setEditForm({ ...editForm, max_turns: Number(e.target.value) })
                      }
                      className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium text-text">툴 사용 허용</p>
                      <p className="text-[10px] text-text-muted">계산기, 주장 추적 등 보조 툴</p>
                    </div>
                    <button
                      type="button"
                      onClick={() =>
                        setEditForm((f) => ({ ...f, tools_enabled: !f.tools_enabled }))
                      }
                      className={`relative inline-flex items-center w-11 h-6 rounded-full transition-colors ${
                        editForm.tools_enabled ? 'bg-primary' : 'bg-gray-600'
                      }`}
                    >
                      <span
                        className={`inline-block w-4 h-4 rounded-full bg-white shadow transition-transform ${
                          editForm.tools_enabled ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>
                  <div>
                    <label className="text-xs text-text-muted">활성화 시작 시간</label>
                    <input
                      type="datetime-local"
                      value={editForm.scheduled_start_at ?? ''}
                      onChange={(e) =>
                        setEditForm((f) => ({ ...f, scheduled_start_at: e.target.value || null }))
                      }
                      className="w-full bg-bg border border-border rounded px-3 py-2 text-sm text-text"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-text-muted">비활성화 종료 시간</label>
                    <input
                      type="datetime-local"
                      value={editForm.scheduled_end_at ?? ''}
                      onChange={(e) =>
                        setEditForm((f) => ({ ...f, scheduled_end_at: e.target.value || null }))
                      }
                      className="w-full bg-bg border border-border rounded px-3 py-2 text-sm text-text"
                    />
                  </div>
                </div>
              )}

              {editError && <p className="text-xs text-red-400">{editError}</p>}

              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={closeEditModal}
                  className="flex-1 py-2.5 rounded-xl border border-border text-sm text-text-muted hover:text-text transition-colors bg-transparent cursor-pointer"
                >
                  취소
                </button>
                <button
                  type="submit"
                  disabled={editSubmitting || !editForm.title.trim()}
                  className="flex-1 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 transition-colors border-none cursor-pointer"
                >
                  {editSubmitting ? '수정 중...' : '저장'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
