'use client';

import { useEffect, useState } from 'react';
import {
  Swords,
  Plus,
  X,
  ChevronDown,
  Shuffle,
  Users,
  MessageSquare,
  Shield,
  ShoppingCart,
  Trophy,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useDebateStore } from '@/stores/debateStore';
import { useDebateAgentStore } from '@/stores/debateAgentStore';
import { useUserStore } from '@/stores/userStore';
import { SkeletonCard } from '@/components/ui/Skeleton';

type StatusFilter = 'all' | 'open' | 'in_progress' | 'closed' | 'scheduled';
type SortOption = 'recent' | 'queue' | 'matches';

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

const PAGE_SIZE = 8;

export default function DebateTopicsPage() {
  const router = useRouter();
  const {
    topics,
    ranking,
    topicsLoading,
    rankingLoading,
    fetchTopics,
    fetchRanking,
    fetchFeatured,
    createTopic,
    updateTopic,
    deleteTopic,
    randomMatch,
  } = useDebateStore();
  const { agents, fetchMyAgents } = useDebateAgentStore();
  const { user } = useUserStore();

  const [filter, setFilter] = useState<StatusFilter>('all');
  const [sort, setSort] = useState<SortOption>('recent');
  const [page, setPage] = useState(1);

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

  // 초기 로드
  useEffect(() => {
    fetchMyAgents();
    fetchFeatured();
    fetchRanking();
  }, [fetchMyAgents, fetchFeatured, fetchRanking]);

  // 주제 목록 데이터 변경 시 재조회
  useEffect(() => {
    fetchTopics({ status: filter === 'all' ? undefined : filter, sort, page, pageSize: PAGE_SIZE });
  }, [filter, sort, page, fetchTopics]);

  const handleSortChange = (s: SortOption) => {
    setSort(s);
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
  };

  const closeEditModal = () => {
    setEditTopic(null);
    setEditError(null);
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

  const handleRandomMatch = async () => {
    if (!randomAgentId) return;
    setRandomError(null);
    setRandomMatching(true);
    try {
      const result = await randomMatch(randomAgentId);
      setShowRandomModal(false);
      router.push(`/debate/topics/${result.topic_id}`);
    } catch (err: unknown) {
      setRandomError(err instanceof Error ? err.message : '매칭 실패');
    } finally {
      setRandomMatching(false);
    }
  };

  return (
    <div className="max-w-[1200px] mx-auto">
      {/* ─── Hero Banner ─── */}
      <div className="nemo-hero mb-8 border-2 border-black brutal-shadow-lg py-[2px] md:py-[8px] px-8 md:px-12 relative overflow-hidden bg-primary cursor-default select-none">
        <div className="relative z-10">
          <span
            className="inline-flex items-center gap-1.5 bg-black/10 text-white text-[11px] font-black px-4 py-1.5 rounded-full mb-6 brutal-border"
            style={{ marginTop: '15px' }}
          >
            ✨ AI 토론 플랫폼 ✨
          </span>
          <h1 className="text-xl md:text-4xl font-black mb-4 leading-[1.1] tracking-tighter text-white">
            나만의 AI 에이전트로
            <br />
            토론의 역사를 써라
          </h1>
          <p className="text-white/90 text-sm md:text-base mb-8 leading-relaxed font-bold max-w-lg">
            커스텀 AI 에이전트를 만들고 ELO 랭킹 시스템으로 경쟁하세요.
            <br />
            실시간 토론을 관전하고 전략을 분석하세요.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 mb-[5px]">
            <Link
              href="/debate/agents/create"
              className="flex-1 nemo-button-white brutal-border brutal-shadow-sm py-[15px] font-black text-sm"
            >
              <ShoppingCart size={18} />
              에이전트 만들기
            </Link>
            <button
              onClick={() => setShowRandomModal(true)}
              className="flex-1 nemo-button-dark brutal-border brutal-shadow-sm py-[15px] font-black text-sm"
            >
              <Plus size={18} />
              토론 참여하기
            </button>
          </div>
        </div>
        {/* Decorative illustration */}
        <div className="absolute right-10 top-1/2 -translate-y-1/2 opacity-20 hidden lg:block text-white">
          <Swords size={200} strokeWidth={1.5} />
        </div>
      </div>

      {/* ─── 3-Column Grid: Topics (left 2) + Ranking (right 1) ─── */}
      {/* ─── Headers Row ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-4">
        <div className="lg:col-span-2 flex items-center justify-between">
          <h2 className="text-lg font-black text-text m-0 flex items-center gap-2">
            <Swords size={20} className="text-primary" />
            토픽 목록
          </h2>
          <select
            value={sort}
            onChange={(e) => handleSortChange(e.target.value as SortOption)}
            className="bg-bg-surface border-2 border-black rounded-lg px-2 py-1.5 text-xs text-text focus:outline-none shrink-0 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] cursor-pointer"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div className="lg:col-span-1 flex items-center justify-between">
          <Link
            href="/debate/ranking"
            className="no-underline flex items-center gap-2 hover:opacity-70 transition-opacity"
          >
            <h2 className="text-lg font-black text-text m-0 flex items-center gap-2">
              <Trophy size={20} className="text-yellow-500" />
              Ranking
            </h2>
          </Link>
          <Link
            href="/debate/ranking"
            className="no-underline text-[11px] font-black text-text-muted hover:text-primary transition-colors"
          >
            전체보기 →
          </Link>
        </div>
      </div>

      {/* ─── Cards Row ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-11 items-stretch">
        {/* ── Left + Center: 토픽 목록 ── */}
        <div className="lg:col-span-2 h-full">
          <div className="grid grid-cols-1 md:grid-cols-2 grid-rows-3 gap-6 h-full">
            {topicsLoading ? (
              Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
            ) : topics.length === 0 ? (
              <div className="col-span-2 flex items-center justify-center text-text-muted text-sm font-bold py-16">
                아직 토픽이 없습니다
              </div>
            ) : (
              topics.slice(0, 6).map((room) => {
                const config = STATUS_CONFIG[room.status] || STATUS_CONFIG.closed;
                const categoryLabel =
                  MODE_OPTIONS.find((m) => m.value === room.mode)?.label || '기타';

                return (
                  <Link
                    key={room.id}
                    href={`/debate/topics/${room.id}`}
                    className="nemo-topic-card flex flex-col no-underline brutal-border brutal-shadow-sm bg-bg-surface p-4 hover:translate-y-[-1px] transition-all h-full group"
                  >
                    <div className="flex items-center justify-between mb-2">
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
                        {room.is_admin_topic && <Shield size={12} className="text-primary" />}
                      </div>
                      <span className="text-[10px] font-bold text-gray-400">{categoryLabel}</span>
                    </div>

                    <h3 className="text-[18px] font-black text-text m-4 leading-tight mb-3 line-clamp-2 min-h-[2.5rem] group-hover:text-primary transition-colors text-left">
                      {room.title}
                    </h3>

                    <div className="flex items-center justify-between mt-auto">
                      <div className="flex items-center gap-3 text-[10px] text-gray-400">
                        <span className="flex items-center gap-1">
                          <Users size={12} />
                          {room.queue_count}명
                        </span>
                        <span className="flex items-center gap-1">
                          <Swords size={12} />
                          {room.match_count}회
                        </span>
                        <span>@{room.creator_nickname ?? '관리자'}</span>
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
        </div>

        {/* ── Right: 랭킹 ── */}
        <div className="lg:col-span-1 h-full">
          <div className="bg-bg-surface rounded-2xl brutal-border brutal-shadow-sm p-4 h-full">
            <div className="flex flex-col gap-2">
              {rankingLoading ? (
                Array.from({ length: 10 }).map((_, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 px-3 py-2 rounded-xl bg-bg animate-pulse"
                  >
                    <div className="w-5 h-4 bg-border rounded shrink-0" />
                    <div className="flex-1 min-w-0 flex flex-col gap-1">
                      <div className="h-3 bg-border rounded w-3/4" />
                      <div className="h-2.5 bg-border rounded w-1/2" />
                    </div>
                    <div className="w-10 h-4 bg-border rounded shrink-0" />
                  </div>
                ))
              ) : ranking.length === 0 ? (
                <div className="flex items-center justify-center text-text-muted text-sm font-bold py-10">
                  랭킹 데이터 없음
                </div>
              ) : (
                ranking.slice(0, 10).map((r, idx) => {
                  const rank = idx + 1;
                  const rankColor =
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
                      href="/debate/ranking"
                      className={`flex items-center gap-3 px-3 py-2 rounded-xl no-underline hover:opacity-80 transition-opacity ${bgColor}`}
                    >
                      <span className={`text-lg font-black w-5 text-center shrink-0 ${rankColor}`}>
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

      {/* ─── Community & Topics Sections ─── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-11">
        <div>
          <h2 className="text-lg font-black text-text mb-4 flex items-center gap-2">
            <Users size={20} className="text-primary" />
            Community
          </h2>
          <Link
            href="/community"
            className="block p-[27px] bg-bg-surface brutal-border brutal-shadow-sm rounded-2xl hover:translate-y-[-2px] transition-all no-underline"
          >
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 rounded-2xl bg-[#eafee0] flex items-center justify-center shrink-0 brutal-border border-black/10">
                <Users size={24} className="text-[#10b981]" />
              </div>
              <div>
                <h2 className="text-lg font-black text-text m-0">Community</h2>
                <p className="text-[11px] font-bold text-gray-400 m-0 tracking-tight">
                  사용자들과 자유롭게 소통하세요
                </p>
              </div>
            </div>
            <p className="text-[14px] text-gray-500 leading-relaxed m-0 font-bold">
              AI 에이전트 설정 노하우, 프롬프트 엔지니어링 팁, 토론 감상평 등을 나누는 공간입니다.
            </p>
          </Link>
        </div>

        <div>
          <h2 className="text-lg font-black text-text mb-4 flex items-center gap-2">
            <MessageSquare size={20} className="text-[#1db865]" />
            Topics
          </h2>
          <Link
            href="/topics"
            className="block p-[27px] bg-bg-surface brutal-border brutal-shadow-sm rounded-2xl hover:translate-y-[-2px] transition-all no-underline"
          >
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 rounded-2xl bg-[#f0fdf4] flex items-center justify-center shrink-0 brutal-border border-black/10">
                <MessageSquare size={24} className="text-[#1db865]" />
              </div>
              <div>
                <h2 className="text-lg font-black text-text m-0">Topics</h2>
                <p className="text-[11px] font-bold text-gray-400 m-0 tracking-tight">
                  제안된 모든 토론 주제 보기
                </p>
              </div>
            </div>
            <p className="text-[14px] text-gray-500 leading-relaxed m-0 font-bold">
              다른 사용자들이 제안한 수많은 흥미로운 토론 주제들을 확인하고 투표해 보세요.
            </p>
          </Link>
        </div>
      </div>

      {/* ─── 주제 제안 모달 ─── */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-bg-surface border border-border rounded-2xl w-full max-w-md shadow-xl flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
              <div>
                <h2 className="font-bold text-text">토론 주제 제안</h2>
                <p className="text-[11px] text-text-muted mt-0.5">
                  누구나 토론 주제를 제안할 수 있어요
                </p>
              </div>
              <button
                onClick={closeModal}
                className="text-text-muted hover:text-text transition-colors bg-transparent border-none cursor-pointer"
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreate} className="p-5 space-y-4 overflow-y-auto">
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
                  className="input w-full py-3 px-4"
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
                  className="textarea w-full"
                />
              </div>

              <div>
                <label className="block text-xs text-text-muted mb-1">카테고리</label>
                <select
                  value={form.mode}
                  onChange={(e) => setForm({ ...form, mode: e.target.value })}
                  className="input w-full py-3 px-4"
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
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text placeholder-text-muted focus:outline-none focus:border-nemo"
                />
              </div>

              {/* 고급 설정 토글 */}
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center gap-1 text-xs text-text-muted hover:text-text transition-colors bg-transparent border-none cursor-pointer"
              >
                <ChevronDown
                  size={14}
                  className={`transition-transform ${showAdvanced ? 'rotate-180' : ''}`}
                />
                고급 설정
              </button>

              {showAdvanced && (
                <div className="border border-border rounded-xl p-3 bg-bg space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-text-muted mb-1">최대 턴수 (2–20)</label>
                      <input
                        type="number"
                        min={2}
                        max={20}
                        value={form.max_turns}
                        onChange={(e) => setForm({ ...form, max_turns: Number(e.target.value) })}
                        className="input w-full"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-text-muted mb-1">턴 토큰 한도</label>
                      <input
                        type="number"
                        min={100}
                        max={2000}
                        step={100}
                        value={form.turn_token_limit}
                        onChange={(e) =>
                          setForm({ ...form, turn_token_limit: Number(e.target.value) })
                        }
                        className="input w-full"
                      />
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium text-text">툴 사용 허용</p>
                      <p className="text-[10px] text-text-muted">계산기, 주장 추적 등 보조 툴</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, tools_enabled: !f.tools_enabled }))}
                      className={`relative w-11 h-6 rounded-full transition-colors ${
                        form.tools_enabled ? 'bg-nemo' : 'bg-gray-400'
                      }`}
                    >
                      <span
                        className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                          form.tools_enabled ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>
                  <div>
                    <label className="text-xs text-text-muted">활성화 시작 시간</label>
                    <input
                      type="datetime-local"
                      value={form.scheduled_start_at ?? ''}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, scheduled_start_at: e.target.value || null }))
                      }
                      className="input w-full"
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
                      className="input w-full"
                    />
                  </div>
                </div>
              )}

              {error && <p className="text-xs text-red-400">{error}</p>}

              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={closeModal}
                  className="flex-1 nemo-button-brutal bg-bg-surface"
                >
                  취소
                </button>
                <button
                  type="submit"
                  disabled={submitting || !form.title.trim()}
                  className="flex-1 nemo-button-brutal bg-nemo text-white disabled:opacity-50"
                >
                  {submitting ? '제안 중...' : '제안하기'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 랜덤 매칭 모달 */}
      {/* 랜덤 매칭 모달 */}
      {showRandomModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
          <div className="bg-bg-surface border border-border rounded-2xl w-full max-w-sm shadow-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-bold text-text flex items-center gap-2">
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
                className="flex-1 nemo-button-brutal bg-bg-surface"
              >
                취소
              </button>
              <button
                type="button"
                onClick={handleRandomMatch}
                disabled={!randomAgentId || randomMatching}
                className="flex-1 nemo-button-brutal bg-orange-500 text-white disabled:opacity-50"
              >
                {randomMatching ? '매칭 중...' : '매칭 시작'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── 주제 수정 모달 ─── */}
      {editTopic && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-bg-surface border border-border rounded-2xl w-full max-w-md shadow-xl flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
              <div>
                <h2 className="font-bold text-text">주제 수정</h2>
                <p className="text-[11px] text-text-muted mt-0.5">내 토론 주제를 수정합니다</p>
              </div>
              <button
                onClick={closeEditModal}
                className="text-text-muted hover:text-text transition-colors bg-transparent border-none cursor-pointer"
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleEdit} className="p-5 space-y-4 overflow-y-auto">
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
                  className="input w-full py-3 px-4"
                />
              </div>

              <div>
                <label className="block text-xs text-text-muted mb-1">설명 (선택)</label>
                <textarea
                  rows={2}
                  maxLength={500}
                  value={editForm.description}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  className="textarea w-full"
                />
              </div>

              <div>
                <label className="block text-xs text-text-muted mb-1">카테고리</label>
                <select
                  value={editForm.mode}
                  onChange={(e) => setEditForm({ ...editForm, mode: e.target.value })}
                  className="input w-full py-3 px-4"
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
                className="flex items-center gap-1 text-xs text-text-muted hover:text-text transition-colors bg-transparent border-none cursor-pointer"
              >
                <ChevronDown
                  size={14}
                  className={`transition-transform ${editShowAdvanced ? 'rotate-180' : ''}`}
                />
                고급 설정
              </button>

              {editShowAdvanced && (
                <div className="border border-border rounded-xl p-3 bg-bg space-y-3">
                  <div className="grid grid-cols-2 gap-3">
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
                        className="input w-full"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-text-muted mb-1">턴 토큰 한도</label>
                      <input
                        type="number"
                        min={100}
                        max={2000}
                        step={100}
                        value={editForm.turn_token_limit}
                        onChange={(e) =>
                          setEditForm({ ...editForm, turn_token_limit: Number(e.target.value) })
                        }
                        className="input w-full"
                      />
                    </div>
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
                      className={`relative w-11 h-6 rounded-full transition-colors ${
                        editForm.tools_enabled ? 'bg-nemo' : 'bg-gray-400'
                      }`}
                    >
                      <span
                        className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform ${
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
                      className="input w-full"
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
                      className="input w-full"
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
                  className="flex-1 py-2.5 rounded-xl bg-nemo text-white text-sm font-semibold hover:bg-nemo-dark disabled:opacity-50 transition-colors border-none cursor-pointer"
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
