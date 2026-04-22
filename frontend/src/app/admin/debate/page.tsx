'use client';

import { useEffect, useState } from 'react';
import {
  Swords,
  Bot,
  MessageSquare,
  Trophy,
  Activity,
  Plus,
  X,
  CalendarClock,
  StopCircle,
  Trash2,
  FileSearch,
  Ban,
  AlertTriangle,
  Loader2,
  Search,
  Zap,
  Calendar,
  Play,
  Eraser,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { StatCard } from '@/components/admin/StatCard';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { DebateDebugModal, type DebugData } from '@/components/debate/DebateDebugModal';
import { AgentDetailModal } from '@/components/admin/AgentDetailModal';

type DebateStats = {
  agents_count: number;
  topics_count: number;
  matches_total: number;
  matches_completed: number;
  matches_in_progress: number;
};

type AdminDebateMatch = {
  id: string;
  topic_title: string;
  agent_a: { id: string; name: string; provider: string; model_id: string; elo_rating: number };
  agent_b: { id: string; name: string; provider: string; model_id: string; elo_rating: number };
  status: string;
  winner_id: string | null;
  score_a: number;
  score_b: number;
  penalty_a: number;
  penalty_b: number;
  blocked_turns_count?: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

const MATCH_STATUS_LABELS: Record<string, string> = {
  pending: '대기',
  in_progress: '진행 중',
  completed: '완료',
  error: '오류',
  waiting_agent: '에이전트 대기',
  forfeit: '몰수패',
};

const MATCH_STATUS_COLORS: Record<string, string> = {
  pending: 'text-text-muted',
  in_progress: 'text-yellow-500',
  completed: 'text-green-500',
  error: 'text-danger',
  waiting_agent: 'text-blue-400',
  forfeit: 'text-red-400',
};

type AdminDebateAgent = {
  id: string;
  name: string;
  provider: string;
  model_id: string;
  elo_rating: number;
  image_url: string | null;
  owner_id: string;
  owner_nickname: string;
  wins: number;
  losses: number;
  draws: number;
  is_active: boolean;
  created_at: string;
};

type Topic = {
  id: string;
  title: string;
  description: string | null;
  mode: string;
  status: string;
  max_turns: number;
  turn_token_limit: number;
  scheduled_start_at: string | null;
  scheduled_end_at: string | null;
  is_admin_topic: boolean;
  queue_count: number;
  match_count: number;
  created_at: string;
};

const MODE_LABELS: Record<string, string> = {
  debate: '찬반 토론',
  persuasion: '설득',
  cross_exam: '교차 심문',
};

const STATUS_COLORS: Record<string, string> = {
  scheduled: 'text-blue-400',
  open: 'text-green-500',
  in_progress: 'text-yellow-500',
  closed: 'text-text-muted',
};

const STATUS_LABELS: Record<string, string> = {
  scheduled: '예정',
  open: '모집 중',
  in_progress: '진행 중',
  closed: '종료',
};

/** 로컬 datetime-local 값을 ISO 문자열로 변환. 빈 값이면 null. */
function toISOOrNull(localStr: string): string | null {
  if (!localStr) return null;
  return new Date(localStr).toISOString();
}

/** ISO → datetime-local input 값 형식 (YYYY-MM-DDTHH:mm) */
function toLocalDatetime(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

type Season = {
  id: string;
  season_number: number;
  title: string;
  start_at: string;
  end_at: string;
  status: string;
};

type Tournament = {
  id: string;
  title: string;
  status: string;
  bracket_size: number;
  current_round: number;
  created_at: string;
};

const SEASON_STATUS_LABELS: Record<string, string> = {
  upcoming: '예정',
  active: '진행 중',
  completed: '종료',
};

const TOURNAMENT_STATUS_LABELS: Record<string, string> = {
  registration: '등록 중',
  in_progress: '진행 중',
  completed: '완료',
  cancelled: '취소',
};

export default function AdminDebatePage() {
  const router = useRouter();

  const [stats, setStats] = useState<DebateStats | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // 토픽 중지/삭제 상태
  const [closingId, setClosingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Topic | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // 에이전트 관리 상태
  const [agents, setAgents] = useState<AdminDebateAgent[]>([]);
  const [agentsTotal, setAgentsTotal] = useState(0);
  const [agentDeleteTarget, setAgentDeleteTarget] = useState<AdminDebateAgent | null>(null);
  const [agentDeleting, setAgentDeleting] = useState(false);
  const [agentActionError, setAgentActionError] = useState<string | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [agentSearch, setAgentSearch] = useState('');
  const [agentProvider, setAgentProvider] = useState('');

  // 매치 로그 & 디버그 상태
  const [matches, setMatches] = useState<AdminDebateMatch[]>([]);
  const [matchesTotal, setMatchesTotal] = useState(0);
  const [debugData, setDebugData] = useState<DebugData | null>(null);
  const [debugLoadingId, setDebugLoadingId] = useState<string | null>(null);
  const [matchSearch, setMatchSearch] = useState('');
  const [matchStatusFilter, setMatchStatusFilter] = useState('');

  // 강제 매치 모달 상태
  const [forceMatchTopic, setForceMatchTopic] = useState<Topic | null>(null);
  const [forceAgentA, setForceAgentA] = useState('');
  const [forceAgentB, setForceAgentB] = useState('');
  const [forceMatching, setForceMatching] = useState(false);
  const [forceMatchError, setForceMatchError] = useState<string | null>(null);

  // 시즌 관리 상태
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [showSeasonForm, setShowSeasonForm] = useState(false);
  const [seasonForm, setSeasonForm] = useState({
    season_number: 1,
    title: '',
    start_at: '',
    end_at: '',
  });
  const [seasonSubmitting, setSeasonSubmitting] = useState(false);
  const [seasonClosingId, setSeasonClosingId] = useState<string | null>(null);
  const [seasonDeletingId, setSeasonDeletingId] = useState<string | null>(null);
  const [seasonActivatingId, setSeasonActivatingId] = useState<string | null>(null);
  const [seasonError, setSeasonError] = useState<string | null>(null);

  // 토너먼트 관리 상태
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [showTournamentForm, setShowTournamentForm] = useState(false);
  const [tournamentForm, setTournamentForm] = useState({
    title: '',
    topic_id: '',
    bracket_size: 8,
  });
  const [tournamentSubmitting, setTournamentSubmitting] = useState(false);
  const [tournamentStartingId, setTournamentStartingId] = useState<string | null>(null);
  const [tournamentError, setTournamentError] = useState<string | null>(null);

  // 대기 정리 상태
  const [cleaning, setCleaning] = useState(false);
  const [cleanupResult, setCleanupResult] = useState<{
    deleted_queue_entries: number;
    fixed_stuck_matches: number;
  } | null>(null);

  const [form, setForm] = useState({
    title: '',
    description: '',
    mode: 'debate',
    max_turns: 6,
    turn_token_limit: 1500,
    tools_enabled: true,
    scheduled_start_at: '',
    scheduled_end_at: '',
  });

  const fetchData = () => {
    api
      .get<DebateStats>('/admin/debate/stats')
      .then(setStats)
      .catch(() => {});
    api
      .get<{ items: Topic[]; total: number }>('/topics?page_size=100')
      .then((r) => setTopics(r.items))
      .catch(() => {});

    const agentParams = new URLSearchParams({ limit: '100' });
    if (agentSearch) agentParams.set('search', agentSearch);
    if (agentProvider) agentParams.set('provider', agentProvider);
    api
      .get<{ items: AdminDebateAgent[]; total: number }>(`/admin/debate/agents?${agentParams}`)
      .then((r) => {
        setAgents(r.items);
        setAgentsTotal(r.total);
      })
      .catch(() => {});

    const matchParams = new URLSearchParams({ limit: '30' });
    if (matchSearch) matchParams.set('search', matchSearch);
    if (matchStatusFilter) matchParams.set('status', matchStatusFilter);
    api
      .get<{ items: AdminDebateMatch[]; total: number }>(`/admin/debate/matches?${matchParams}`)
      .then((r) => {
        setMatches(r.items);
        setMatchesTotal(r.total);
      })
      .catch(() => {});

    api
      .get<{ items: Season[] }>('/admin/debate/seasons')
      .then((r) => setSeasons(r.items))
      .catch(() => {});
    api
      .get<{ items: Tournament[] }>('/tournaments?limit=20')
      .then((r) => setTournaments(r.items))
      .catch(() => {});
  };

  const handleOpenDebug = async (matchId: string) => {
    setDebugLoadingId(matchId);
    try {
      const data = await api.get<DebugData>(`/admin/debate/matches/${matchId}/debug`);
      setDebugData(data);
    } catch (err) {
      console.error('debug fetch error', err);
    } finally {
      setDebugLoadingId(null);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchData();
    }, 300);
    return () => clearTimeout(timer);
  }, [agentSearch, agentProvider, matchSearch, matchStatusFilter]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const startAt = toISOOrNull(form.scheduled_start_at);
    const endAt = toISOOrNull(form.scheduled_end_at);

    if (startAt && endAt && new Date(endAt) <= new Date(startAt)) {
      setError('종료 시각은 시작 시각보다 뒤여야 합니다.');
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/topics', {
        title: form.title.trim(),
        description: form.description.trim() || null,
        mode: form.mode,
        max_turns: form.max_turns,
        turn_token_limit: form.turn_token_limit,
        tools_enabled: form.tools_enabled,
        scheduled_start_at: startAt,
        scheduled_end_at: endAt,
      });
      setSuccess(true);
      setForm({
        title: '',
        description: '',
        mode: 'debate',
        max_turns: 6,
        turn_token_limit: 1500,
        tools_enabled: true,
        scheduled_start_at: '',
        scheduled_end_at: '',
      });
      setShowForm(false);
      fetchData();
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '생성 실패';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = async (topic: Topic) => {
    setActionError(null);
    setClosingId(topic.id);
    try {
      await api.patch(`/admin/debate/topics/${topic.id}`, { status: 'closed' });
      fetchData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '중지 실패';
      setActionError(msg);
    } finally {
      setClosingId(null);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    setActionError(null);
    try {
      await api.delete(`/admin/debate/topics/${deleteTarget.id}`);
      setDeleteTarget(null);
      fetchData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '삭제 실패';
      setActionError(msg);
    } finally {
      setDeleting(false);
    }
  };

  const handleAgentDeleteConfirm = async () => {
    if (!agentDeleteTarget) return;
    setAgentDeleting(true);
    setAgentActionError(null);
    try {
      await api.delete(`/admin/debate/agents/${agentDeleteTarget.id}`);
      setAgentDeleteTarget(null);
      fetchData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '삭제 실패';
      setAgentActionError(msg);
    } finally {
      setAgentDeleting(false);
    }
  };

  const handleForceMatch = async () => {
    if (!forceMatchTopic || !forceAgentA || !forceAgentB) return;
    setForceMatchError(null);
    setForceMatching(true);
    try {
      const result = await api.post<{ match_id: string }>(
        `/admin/debate/topics/${forceMatchTopic.id}/force-match`,
        { agent_a_id: forceAgentA, agent_b_id: forceAgentB },
      );
      setForceMatchTopic(null);
      setForceAgentA('');
      setForceAgentB('');
      fetchData();
      router.push(`/debate/matches/${result.match_id}`);
    } catch (err: unknown) {
      setForceMatchError(err instanceof Error ? err.message : '매치 생성 실패');
    } finally {
      setForceMatching(false);
    }
  };

  const handleSeasonCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSeasonError(null);
    setSeasonSubmitting(true);
    try {
      await api.post('/admin/debate/seasons', {
        season_number: seasonForm.season_number,
        title: seasonForm.title,
        start_at: new Date(seasonForm.start_at).toISOString(),
        end_at: new Date(seasonForm.end_at).toISOString(),
      });
      setShowSeasonForm(false);
      setSeasonForm({ season_number: 1, title: '', start_at: '', end_at: '' });
      fetchData();
    } catch (err: unknown) {
      setSeasonError(err instanceof Error ? err.message : '생성 실패');
    } finally {
      setSeasonSubmitting(false);
    }
  };

  const handleSeasonClose = async (seasonId: string) => {
    if (!confirm('시즌을 종료하면 결산·보상·ELO 리셋이 즉시 실행됩니다. 계속하시겠습니까?')) return;
    setSeasonClosingId(seasonId);
    try {
      await api.post(`/admin/debate/seasons/${seasonId}/close`);
      fetchData();
    } catch (err: unknown) {
      setSeasonError(err instanceof Error ? err.message : '종료 실패');
    } finally {
      setSeasonClosingId(null);
    }
  };

  const handleSeasonActivate = async (seasonId: string) => {
    if (!confirm('이 시즌을 활성화하면 사용자 토론 페이지에 표시됩니다. 계속하시겠습니까?')) return;
    setSeasonActivatingId(seasonId);
    try {
      await api.post(`/admin/debate/seasons/${seasonId}/activate`);
      fetchData();
    } catch (err: unknown) {
      setSeasonError(err instanceof Error ? err.message : '활성화 실패');
    } finally {
      setSeasonActivatingId(null);
    }
  };

  const handleSeasonDelete = async (seasonId: string) => {
    if (!confirm('이 시즌을 삭제하시겠습니까? 삭제된 시즌은 복구할 수 없습니다.')) return;
    setSeasonDeletingId(seasonId);
    try {
      await api.delete(`/admin/debate/seasons/${seasonId}`);
      fetchData();
    } catch (err: unknown) {
      setSeasonError(err instanceof Error ? err.message : '삭제 실패');
    } finally {
      setSeasonDeletingId(null);
    }
  };

  const handleTournamentCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setTournamentError(null);
    setTournamentSubmitting(true);
    try {
      await api.post('/admin/debate/tournaments', {
        title: tournamentForm.title,
        topic_id: tournamentForm.topic_id,
        bracket_size: tournamentForm.bracket_size,
      });
      setShowTournamentForm(false);
      setTournamentForm({ title: '', topic_id: '', bracket_size: 8 });
      fetchData();
    } catch (err: unknown) {
      setTournamentError(err instanceof Error ? err.message : '생성 실패');
    } finally {
      setTournamentSubmitting(false);
    }
  };

  const handleCleanup = async () => {
    if (
      !confirm(
        '대기 중인 모든 큐 항목을 삭제하고, pending/waiting_agent 매치를 error로 처리합니다. 계속하시겠습니까?',
      )
    )
      return;
    setCleaning(true);
    setCleanupResult(null);
    try {
      const result = await api.post<{ deleted_queue_entries: number; fixed_stuck_matches: number }>(
        '/admin/debate/cleanup',
      );
      setCleanupResult(result);
      fetchData();
      setTimeout(() => setCleanupResult(null), 5000);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : '정리 실패');
    } finally {
      setCleaning(false);
    }
  };

  const handleTournamentStart = async (tournamentId: string) => {
    setTournamentStartingId(tournamentId);
    try {
      await api.post(`/admin/debate/tournaments/${tournamentId}/start`);
      fetchData();
    } catch (err: unknown) {
      setTournamentError(err instanceof Error ? err.message : '시작 실패');
    } finally {
      setTournamentStartingId(null);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-xl font-bold text-text flex items-center gap-2">
          <Swords size={22} className="text-primary" />
          AI 토론 관리
        </h1>
        <div className="flex items-center gap-2">
          {cleanupResult && (
            <span className="text-xs text-green-400">
              큐 {cleanupResult.deleted_queue_entries}건 삭제, 매치{' '}
              {cleanupResult.fixed_stuck_matches}건 정리 완료
            </span>
          )}
          <button
            onClick={handleCleanup}
            disabled={cleaning}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 text-xs font-semibold disabled:opacity-50 transition-colors"
          >
            {cleaning ? <Loader2 size={13} className="animate-spin" /> : <Eraser size={13} />}
            대기 정리
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
        <StatCard title="에이전트" value={stats?.agents_count ?? 0} icon={<Bot size={18} />} />
        <StatCard
          title="토론 주제"
          value={stats?.topics_count ?? 0}
          icon={<MessageSquare size={18} />}
        />
        <StatCard title="총 매치" value={stats?.matches_total ?? 0} icon={<Trophy size={18} />} />
        <StatCard
          title="완료 매치"
          value={stats?.matches_completed ?? 0}
          icon={<Trophy size={18} />}
        />
        <StatCard
          title="진행 중"
          value={stats?.matches_in_progress ?? 0}
          icon={<Activity size={18} />}
        />
      </div>

      {/* 토론 주제 섹션 */}
      <div className="bg-bg-surface border border-border rounded-xl p-5 mb-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-text">토론 주제</h2>
          <button
            onClick={() => {
              setShowForm(!showForm);
              setError(null);
            }}
            className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors"
          >
            {showForm ? <X size={15} /> : <Plus size={15} />}
            {showForm ? '닫기' : '새 주제 생성'}
          </button>
        </div>

        {success && (
          <div className="mb-4 text-sm text-green-500 bg-green-500/10 rounded-lg px-3 py-2">
            토론 주제가 생성되었습니다.
          </div>
        )}

        {actionError && (
          <div className="mb-4 text-sm text-danger bg-danger/10 rounded-lg px-3 py-2">
            {actionError}
          </div>
        )}

        {/* 생성 폼 */}
        {showForm && (
          <form
            onSubmit={handleSubmit}
            className="mb-5 bg-bg border border-border rounded-lg p-4 space-y-3"
          >
            <div>
              <label className="block text-xs text-text-muted mb-1">
                주제 제목 <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                required
                maxLength={200}
                placeholder="예: 인공지능은 인간의 일자리를 빼앗는가?"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text placeholder-text-muted focus:outline-none focus:border-primary"
              />
            </div>

            <div>
              <label className="block text-xs text-text-muted mb-1">설명 (선택)</label>
              <textarea
                rows={2}
                maxLength={1000}
                placeholder="주제에 대한 배경 설명"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text placeholder-text-muted focus:outline-none focus:border-primary resize-none"
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-text-muted mb-1">토론 방식</label>
                <select
                  value={form.mode}
                  onChange={(e) => setForm({ ...form, mode: e.target.value })}
                  className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                >
                  <option value="debate">찬반 토론</option>
                  <option value="persuasion">설득</option>
                  <option value="cross_exam">교차 심문</option>
                </select>
              </div>

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

              <div>
                <label className="block text-xs text-text-muted mb-1">
                  턴 토큰 한도 (100–2000)
                </label>
                <input
                  type="number"
                  min={100}
                  max={2000}
                  step={100}
                  value={form.turn_token_limit}
                  onChange={(e) => setForm({ ...form, turn_token_limit: Number(e.target.value) })}
                  className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                />
              </div>
            </div>

            {/* 툴 사용 허용 토글 */}
            <div className="flex items-center justify-between border border-border rounded-lg px-4 py-3">
              <div>
                <p className="text-sm font-medium text-text">툴 사용 허용</p>
                <p className="text-[11px] text-text-muted mt-0.5">
                  calculator, stance_tracker, opponent_summary, turn_info
                </p>
              </div>
              <button
                type="button"
                onClick={() => setForm({ ...form, tools_enabled: !form.tools_enabled })}
                className={`relative inline-flex items-center w-11 h-6 rounded-full transition-colors ${
                  form.tools_enabled ? 'bg-emerald-500' : 'bg-text-muted/30'
                }`}
              >
                <span
                  className={`inline-block w-4 h-4 rounded-full bg-white shadow transition-transform ${
                    form.tools_enabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            {/* 스케줄 설정 (관리자 전용) */}
            <div className="border border-primary/20 rounded-lg p-3 bg-primary/5">
              <p className="text-xs font-semibold text-primary mb-2 flex items-center gap-1.5">
                <CalendarClock size={13} />
                자동 스케줄 설정 (선택)
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-text-muted mb-1">시작 시각</label>
                  <input
                    type="datetime-local"
                    value={form.scheduled_start_at}
                    onChange={(e) => setForm({ ...form, scheduled_start_at: e.target.value })}
                    className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                  />
                  <p className="text-[10px] text-text-muted mt-0.5">비워두면 즉시 모집 시작</p>
                </div>
                <div>
                  <label className="block text-xs text-text-muted mb-1">종료 시각</label>
                  <input
                    type="datetime-local"
                    value={form.scheduled_end_at}
                    min={form.scheduled_start_at || undefined}
                    onChange={(e) => setForm({ ...form, scheduled_end_at: e.target.value })}
                    className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                  />
                  <p className="text-[10px] text-text-muted mt-0.5">도달 시 자동으로 토론 종료</p>
                </div>
              </div>
            </div>

            {error && <p className="text-xs text-red-400">{error}</p>}

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowForm(false);
                  setError(null);
                }}
                className="text-sm px-4 py-1.5 rounded-lg border border-border text-text-muted hover:text-text transition-colors"
              >
                취소
              </button>
              <button
                type="submit"
                disabled={submitting || !form.title.trim()}
                className="text-sm px-4 py-1.5 rounded-lg bg-primary text-white hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                {submitting ? '생성 중...' : '주제 생성'}
              </button>
            </div>
          </form>
        )}

        {/* 주제 목록 */}
        {topics.length === 0 ? (
          <p className="text-sm text-text-muted text-center py-6">생성된 토론 주제가 없습니다.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-text-muted text-left">
                  <th className="pb-2 pr-4 font-medium">제목</th>
                  <th className="pb-2 pr-4 font-medium">방식</th>
                  <th className="pb-2 pr-4 font-medium">상태</th>
                  <th className="pb-2 pr-4 font-medium">스케줄</th>
                  <th className="pb-2 pr-4 font-medium text-right">턴수</th>
                  <th className="pb-2 pr-4 font-medium text-right">매치</th>
                  <th className="pb-2 pr-4 font-medium text-right">대기</th>
                  <th className="pb-2 font-medium text-right">관리</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {topics.map((t) => (
                  <tr key={t.id} className="hover:bg-bg transition-colors">
                    <td className="py-2 pr-4">
                      <div className="flex items-center gap-1.5">
                        {t.is_admin_topic && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-semibold">
                            공식
                          </span>
                        )}
                        <span className="font-medium text-text">{t.title}</span>
                      </div>
                      {t.description && (
                        <p className="text-xs text-text-muted mt-0.5 line-clamp-1">
                          {t.description}
                        </p>
                      )}
                    </td>
                    <td className="py-2 pr-4 text-text-muted">{MODE_LABELS[t.mode] ?? t.mode}</td>
                    <td className={`py-2 pr-4 font-medium ${STATUS_COLORS[t.status] ?? ''}`}>
                      {STATUS_LABELS[t.status] ?? t.status}
                    </td>
                    <td className="py-2 pr-4 text-xs text-text-muted">
                      {t.scheduled_start_at || t.scheduled_end_at ? (
                        <div className="flex flex-col gap-0.5">
                          {t.scheduled_start_at && (
                            <span>
                              시작: {toLocalDatetime(t.scheduled_start_at).replace('T', ' ')}
                            </span>
                          )}
                          {t.scheduled_end_at && (
                            <span>
                              종료: {toLocalDatetime(t.scheduled_end_at).replace('T', ' ')}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-text-muted/50">-</span>
                      )}
                    </td>
                    <td className="py-2 pr-4 text-right text-text-muted">{t.max_turns}</td>
                    <td className="py-2 pr-4 text-right text-text-muted">{t.match_count}</td>
                    <td className="py-2 pr-4 text-right text-text-muted">{t.queue_count}</td>

                    {/* 관리 버튼 */}
                    <td className="py-2 text-right">
                      <div className="flex items-center justify-end gap-1">
                        {/* 테스트 매치 생성 */}
                        {(t.status === 'open' || t.status === 'in_progress') && (
                          <button
                            onClick={() => {
                              setForceMatchError(null);
                              setForceAgentA('');
                              setForceAgentB('');
                              setForceMatchTopic(t);
                            }}
                            title="테스트 매치 생성"
                            className="p-1.5 rounded hover:bg-primary/10 text-text-muted
                              hover:text-primary transition-colors"
                          >
                            <Zap size={15} />
                          </button>
                        )}
                        {/* 중지 — closed가 아닌 경우에만 표시 */}
                        {t.status !== 'closed' && (
                          <button
                            onClick={() => handleClose(t)}
                            disabled={closingId === t.id}
                            title="토론 중지"
                            className="p-1.5 rounded hover:bg-yellow-500/10 text-text-muted
                              hover:text-yellow-400 transition-colors disabled:opacity-50"
                          >
                            <StopCircle size={15} />
                          </button>
                        )}
                        {/* 삭제 — superadmin 전용 (서버에서 권한 검증) */}
                        <button
                          onClick={() => {
                            setActionError(null);
                            setDeleteTarget(t);
                          }}
                          title="토론 삭제"
                          className="p-1.5 rounded hover:bg-danger/10 text-text-muted
                            hover:text-danger transition-colors"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 에이전트 관리 섹션 */}
      <div className="bg-bg-surface border border-border rounded-xl p-5 mb-4">
        <h2 className="font-semibold text-text mb-4 flex items-center gap-2">
          <Bot size={16} className="text-primary" />
          토론 에이전트
          <span className="text-xs text-text-muted font-normal">({agentsTotal}개)</span>
        </h2>

        {agentActionError && (
          <div className="mb-3 text-sm text-danger bg-danger/10 rounded-lg px-3 py-2">
            {agentActionError}
          </div>
        )}

        <div className="flex gap-2 mb-3 flex-wrap">
          <div className="relative flex-1 min-w-[160px]">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
            />
            <input
              type="text"
              placeholder="에이전트명/소유자 검색..."
              value={agentSearch}
              onChange={(e) => setAgentSearch(e.target.value)}
              className="w-full bg-bg border border-border rounded-lg pl-8 pr-3 py-1.5 text-xs text-text placeholder-text-muted focus:outline-none focus:border-primary"
            />
          </div>
          <select
            value={agentProvider}
            onChange={(e) => setAgentProvider(e.target.value)}
            className="bg-bg border border-border rounded-lg px-2 py-1.5 text-xs text-text focus:outline-none focus:border-primary"
          >
            <option value="">전체 Provider</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="google">Google</option>
            <option value="runpod">RunPod</option>
            <option value="local">Local</option>
          </select>
        </div>

        {agents.length === 0 ? (
          <p className="text-sm text-text-muted text-center py-6">등록된 에이전트가 없습니다.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-text-muted text-left">
                  <th className="pb-2 pr-4 font-medium">에이전트</th>
                  <th className="pb-2 pr-4 font-medium">소유자</th>
                  <th className="pb-2 pr-4 font-medium">모델</th>
                  <th className="pb-2 pr-4 font-medium text-right">ELO</th>
                  <th className="pb-2 pr-4 font-medium text-right">승/패/무</th>
                  <th className="pb-2 font-medium text-right">관리</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {agents.map((agent) => (
                  <tr
                    key={agent.id}
                    className="hover:bg-bg transition-colors cursor-pointer"
                    onClick={() => setSelectedAgentId(agent.id)}
                  >
                    <td className="py-2 pr-4">
                      <div className="flex items-center gap-2">
                        {agent.image_url ? (
                          <img
                            src={agent.image_url}
                            alt={agent.name}
                            className="w-7 h-7 rounded-full object-cover flex-shrink-0"
                          />
                        ) : (
                          <div className="w-7 h-7 rounded-full bg-bg flex items-center justify-center flex-shrink-0">
                            <Bot size={14} className="text-text-muted" />
                          </div>
                        )}
                        <div>
                          <p className="font-medium text-text">{agent.name}</p>
                          {!agent.is_active && (
                            <span className="text-[10px] text-text-muted">비활성</span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="py-2 pr-4 text-text-muted">{agent.owner_nickname}</td>
                    <td className="py-2 pr-4">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-bg text-text-muted border border-border">
                        {agent.provider}
                      </span>
                      <span className="ml-1.5 text-xs text-text-muted">{agent.model_id}</span>
                    </td>
                    <td className="py-2 pr-4 text-right font-mono text-sm">{agent.elo_rating}</td>
                    <td className="py-2 pr-4 text-right text-xs text-text-muted">
                      <span className="text-green-500">{agent.wins}</span>
                      {' / '}
                      <span className="text-red-400">{agent.losses}</span>
                      {' / '}
                      <span>{agent.draws}</span>
                    </td>
                    <td className="py-2 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setAgentActionError(null);
                          setAgentDeleteTarget(agent);
                        }}
                        title="에이전트 삭제"
                        className="p-1.5 rounded hover:bg-danger/10 text-text-muted hover:text-danger transition-colors"
                      >
                        <Trash2 size={15} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 매치 로그 섹션 */}
      <div className="bg-bg-surface border border-border rounded-xl p-5 mb-4">
        <h2 className="font-semibold text-text mb-4 flex items-center gap-2">
          <FileSearch size={16} className="text-primary" />
          매치 로그
          <span className="text-xs text-text-muted font-normal">
            (최근 {matches.length}/{matchesTotal}건)
          </span>
        </h2>

        <div className="flex gap-2 mb-3 flex-wrap">
          <div className="relative flex-1 min-w-[160px]">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
            />
            <input
              type="text"
              placeholder="에이전트명 검색..."
              value={matchSearch}
              onChange={(e) => setMatchSearch(e.target.value)}
              className="w-full bg-bg border border-border rounded-lg pl-8 pr-3 py-1.5 text-xs text-text placeholder-text-muted focus:outline-none focus:border-primary"
            />
          </div>
          <select
            value={matchStatusFilter}
            onChange={(e) => setMatchStatusFilter(e.target.value)}
            className="bg-bg border border-border rounded-lg px-2 py-1.5 text-xs text-text focus:outline-none focus:border-primary"
          >
            <option value="">전체 상태</option>
            <option value="pending">대기</option>
            <option value="in_progress">진행 중</option>
            <option value="completed">완료</option>
            <option value="error">오류</option>
            <option value="forfeit">몰수패</option>
          </select>
        </div>

        {matches.length === 0 ? (
          <p className="text-sm text-text-muted text-center py-6">매치 기록이 없습니다.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-text-muted text-left">
                  <th className="pb-2 pr-4 font-medium">주제</th>
                  <th className="pb-2 pr-4 font-medium">에이전트 A</th>
                  <th className="pb-2 pr-4 font-medium">에이전트 B</th>
                  <th className="pb-2 pr-4 font-medium">상태</th>
                  <th className="pb-2 pr-4 font-medium text-right">점수</th>
                  <th className="pb-2 pr-4 font-medium text-center">차단</th>
                  <th className="pb-2 font-medium text-right">디버그</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {matches.map((m) => {
                  const aIsWinner = m.winner_id === m.agent_a.id;
                  const bIsWinner = m.winner_id === m.agent_b.id;
                  return (
                    <tr key={m.id} className="hover:bg-bg transition-colors">
                      <td className="py-2 pr-4">
                        <p className="font-medium text-text line-clamp-1 max-w-[180px]">
                          {m.topic_title}
                        </p>
                        <p className="text-[10px] text-text-muted">
                          {new Date(m.created_at).toLocaleDateString('ko-KR')}
                        </p>
                      </td>
                      <td className="py-2 pr-4">
                        <span
                          className={`text-xs font-medium ${aIsWinner ? 'text-blue-400' : 'text-text'}`}
                        >
                          {m.agent_a.name}
                        </span>
                        <p className="text-[10px] text-text-muted">{m.agent_a.model_id}</p>
                      </td>
                      <td className="py-2 pr-4">
                        <span
                          className={`text-xs font-medium ${bIsWinner ? 'text-violet-400' : 'text-text'}`}
                        >
                          {m.agent_b.name}
                        </span>
                        <p className="text-[10px] text-text-muted">{m.agent_b.model_id}</p>
                      </td>
                      <td
                        className={`py-2 pr-4 text-xs font-medium ${MATCH_STATUS_COLORS[m.status] ?? 'text-text-muted'}`}
                      >
                        {MATCH_STATUS_LABELS[m.status] ?? m.status}
                      </td>
                      <td className="py-2 pr-4 text-right font-mono text-xs">
                        <span className={aIsWinner ? 'text-blue-400 font-bold' : 'text-text'}>
                          {m.score_a}
                        </span>
                        <span className="text-text-muted mx-1">:</span>
                        <span className={bIsWinner ? 'text-violet-400 font-bold' : 'text-text'}>
                          {m.score_b}
                        </span>
                        {(m.penalty_a > 0 || m.penalty_b > 0) && (
                          <p className="text-[10px] text-orange-400">
                            -({m.penalty_a}/{m.penalty_b})
                          </p>
                        )}
                      </td>
                      <td className="py-2 pr-4 text-center">
                        {(m.blocked_turns_count ?? 0) > 0 ? (
                          <span className="inline-flex items-center gap-0.5 text-[10px] font-bold text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded">
                            <Ban size={9} />
                            {m.blocked_turns_count}
                          </span>
                        ) : m.penalty_a > 0 || m.penalty_b > 0 ? (
                          <span className="inline-flex items-center gap-0.5 text-[10px] text-orange-400 bg-orange-500/10 px-1.5 py-0.5 rounded">
                            <AlertTriangle size={9} />
                            벌점
                          </span>
                        ) : (
                          <span className="text-[10px] text-text-muted/40">—</span>
                        )}
                      </td>
                      <td className="py-2 text-right">
                        <button
                          onClick={() => handleOpenDebug(m.id)}
                          disabled={debugLoadingId === m.id}
                          title="디버그 로그 보기"
                          className="flex items-center gap-1 text-[11px] px-2 py-1 rounded hover:bg-primary/10 text-text-muted hover:text-primary transition-colors disabled:opacity-50 ml-auto"
                        >
                          {debugLoadingId === m.id ? (
                            <Loader2 size={13} className="animate-spin" />
                          ) : (
                            <FileSearch size={13} />
                          )}
                          디버그
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 테스트 매치 생성 모달 */}
      {forceMatchTopic && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
          <div className="bg-bg-surface border border-border rounded-2xl w-full max-w-sm shadow-xl p-5">
            <div className="flex items-center justify-between mb-1">
              <h2 className="font-bold text-text flex items-center gap-2">
                <Zap size={16} className="text-primary" />
                테스트 매치 생성
              </h2>
              <button
                onClick={() => {
                  setForceMatchTopic(null);
                  setForceMatchError(null);
                }}
                className="text-text-muted hover:text-text transition-colors"
              >
                <X size={20} />
              </button>
            </div>
            <p className="text-xs text-text-muted mb-4 line-clamp-1">
              주제: <span className="text-text font-medium">{forceMatchTopic.title}</span>
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs text-text-muted mb-1">에이전트 A (파란색)</label>
                <select
                  value={forceAgentA}
                  onChange={(e) => setForceAgentA(e.target.value)}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                >
                  <option value="">에이전트 선택...</option>
                  {agents
                    .filter((a) => a.id !== forceAgentB)
                    .map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name} ({a.provider} · ELO {a.elo_rating})
                      </option>
                    ))}
                </select>
              </div>

              <div>
                <label className="block text-xs text-text-muted mb-1">에이전트 B (주황색)</label>
                <select
                  value={forceAgentB}
                  onChange={(e) => setForceAgentB(e.target.value)}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                >
                  <option value="">에이전트 선택...</option>
                  {agents
                    .filter((a) => a.id !== forceAgentA)
                    .map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name} ({a.provider} · ELO {a.elo_rating})
                      </option>
                    ))}
                </select>
              </div>
            </div>

            {forceMatchError && <p className="text-xs text-red-400 mt-3">{forceMatchError}</p>}

            <div className="flex gap-2 mt-4">
              <button
                type="button"
                onClick={() => {
                  setForceMatchTopic(null);
                  setForceMatchError(null);
                }}
                className="flex-1 py-2.5 rounded-xl border border-border text-sm text-text-muted hover:text-text transition-colors"
              >
                취소
              </button>
              <button
                type="button"
                onClick={handleForceMatch}
                disabled={!forceAgentA || !forceAgentB || forceMatching}
                className="flex-1 py-2.5 rounded-xl bg-primary text-white text-sm font-semibold
                  hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center justify-center gap-1.5"
              >
                {forceMatching ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
                {forceMatching ? '매칭 중...' : '매치 시작'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 시즌 관리 */}
      <div className="bg-bg-surface border border-border rounded-xl p-5 mb-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-text flex items-center gap-2">
            <Calendar size={16} className="text-primary" />
            시즌 관리
          </h2>
          <button
            onClick={() => {
              setShowSeasonForm(!showSeasonForm);
              setSeasonError(null);
            }}
            className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors"
          >
            {showSeasonForm ? <X size={15} /> : <Plus size={15} />}
            {showSeasonForm ? '닫기' : '새 시즌 생성'}
          </button>
        </div>

        {seasonError && (
          <p className="text-xs text-danger bg-danger/10 rounded-lg px-3 py-2 mb-3">
            {seasonError}
          </p>
        )}

        {showSeasonForm && (
          <form
            onSubmit={handleSeasonCreate}
            className="mb-4 bg-bg border border-border rounded-lg p-4 space-y-3"
          >
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-text-muted mb-1">시즌 번호</label>
                <input
                  type="number"
                  min={1}
                  required
                  value={seasonForm.season_number}
                  onChange={(e) =>
                    setSeasonForm({ ...seasonForm, season_number: Number(e.target.value) })
                  }
                  className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="block text-xs text-text-muted mb-1">시즌 제목</label>
                <input
                  type="text"
                  required
                  maxLength={100}
                  placeholder="예: Season 1"
                  value={seasonForm.title}
                  onChange={(e) => setSeasonForm({ ...seasonForm, title: e.target.value })}
                  className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="block text-xs text-text-muted mb-1">시작일</label>
                <input
                  type="datetime-local"
                  required
                  value={seasonForm.start_at}
                  onChange={(e) => setSeasonForm({ ...seasonForm, start_at: e.target.value })}
                  className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="block text-xs text-text-muted mb-1">종료일</label>
                <input
                  type="datetime-local"
                  required
                  value={seasonForm.end_at}
                  onChange={(e) => setSeasonForm({ ...seasonForm, end_at: e.target.value })}
                  className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowSeasonForm(false)}
                className="text-sm px-4 py-1.5 rounded-lg border border-border text-text-muted hover:text-text transition-colors"
              >
                취소
              </button>
              <button
                type="submit"
                disabled={seasonSubmitting}
                className="text-sm px-4 py-1.5 rounded-lg bg-primary text-white hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                {seasonSubmitting ? '생성 중...' : '시즌 생성'}
              </button>
            </div>
          </form>
        )}

        {seasons.length === 0 ? (
          <p className="text-sm text-text-muted text-center py-4">활성 시즌이 없습니다.</p>
        ) : (
          <div className="space-y-2">
            {seasons.map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between p-3 bg-bg border border-border rounded-lg"
              >
                <div>
                  <span className="text-sm font-semibold text-text">
                    S{s.season_number} — {s.title}
                  </span>
                  <span
                    className={`ml-2 text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                      s.status === 'active'
                        ? 'bg-green-500/10 text-green-500'
                        : s.status === 'upcoming'
                          ? 'bg-blue-500/10 text-blue-400'
                          : 'bg-text-muted/10 text-text-muted'
                    }`}
                  >
                    {SEASON_STATUS_LABELS[s.status] ?? s.status}
                  </span>
                  <p className="text-[11px] text-text-muted mt-0.5">
                    {new Date(s.start_at).toLocaleDateString('ko-KR')} ~{' '}
                    {new Date(s.end_at).toLocaleDateString('ko-KR')}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {s.status === 'upcoming' && (
                    <button
                      onClick={() => handleSeasonActivate(s.id)}
                      disabled={seasonActivatingId === s.id}
                      className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-primary/40 text-primary hover:bg-primary/10 disabled:opacity-50 transition-colors"
                    >
                      {seasonActivatingId === s.id ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <Play size={12} />
                      )}
                      활성화
                    </button>
                  )}
                  {s.status === 'active' && (
                    <button
                      onClick={() => handleSeasonClose(s.id)}
                      disabled={seasonClosingId === s.id}
                      className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-danger/40 text-danger hover:bg-danger/10 disabled:opacity-50 transition-colors"
                    >
                      {seasonClosingId === s.id ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <StopCircle size={12} />
                      )}
                      시즌 종료
                    </button>
                  )}
                  {s.status === 'upcoming' && (
                    <button
                      onClick={() => handleSeasonDelete(s.id)}
                      disabled={seasonDeletingId === s.id}
                      className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-border text-text-muted hover:text-danger hover:border-danger/40 disabled:opacity-50 transition-colors"
                    >
                      {seasonDeletingId === s.id ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <Trash2 size={12} />
                      )}
                      삭제
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 토너먼트 관리 */}
      <div className="bg-bg-surface border border-border rounded-xl p-5 mb-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-text flex items-center gap-2">
            <Trophy size={16} className="text-primary" />
            토너먼트 관리
          </h2>
          <button
            onClick={() => {
              setShowTournamentForm(!showTournamentForm);
              setTournamentError(null);
            }}
            className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors"
          >
            {showTournamentForm ? <X size={15} /> : <Plus size={15} />}
            {showTournamentForm ? '닫기' : '새 토너먼트 생성'}
          </button>
        </div>

        {tournamentError && (
          <p className="text-xs text-danger bg-danger/10 rounded-lg px-3 py-2 mb-3">
            {tournamentError}
          </p>
        )}

        {showTournamentForm && (
          <form
            onSubmit={handleTournamentCreate}
            className="mb-4 bg-bg border border-border rounded-lg p-4 space-y-3"
          >
            <div>
              <label className="block text-xs text-text-muted mb-1">토너먼트 제목</label>
              <input
                type="text"
                required
                maxLength={200}
                placeholder="예: 2025 AI 토론 챔피언십"
                value={tournamentForm.title}
                onChange={(e) => setTournamentForm({ ...tournamentForm, title: e.target.value })}
                className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-text-muted mb-1">토론 주제</label>
                <select
                  required
                  value={tournamentForm.topic_id}
                  onChange={(e) =>
                    setTournamentForm({ ...tournamentForm, topic_id: e.target.value })
                  }
                  className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                >
                  <option value="">주제 선택...</option>
                  {topics.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.title}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-text-muted mb-1">대진 규모</label>
                <select
                  value={tournamentForm.bracket_size}
                  onChange={(e) =>
                    setTournamentForm({ ...tournamentForm, bracket_size: Number(e.target.value) })
                  }
                  className="w-full bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
                >
                  <option value={4}>4강</option>
                  <option value={8}>8강</option>
                  <option value={16}>16강</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowTournamentForm(false)}
                className="text-sm px-4 py-1.5 rounded-lg border border-border text-text-muted hover:text-text transition-colors"
              >
                취소
              </button>
              <button
                type="submit"
                disabled={tournamentSubmitting}
                className="text-sm px-4 py-1.5 rounded-lg bg-primary text-white hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                {tournamentSubmitting ? '생성 중...' : '토너먼트 생성'}
              </button>
            </div>
          </form>
        )}

        {tournaments.length === 0 ? (
          <p className="text-sm text-text-muted text-center py-4">생성된 토너먼트가 없습니다.</p>
        ) : (
          <div className="space-y-2">
            {tournaments.map((t) => (
              <div
                key={t.id}
                className="flex items-center justify-between p-3 bg-bg border border-border rounded-lg"
              >
                <div>
                  <span className="text-sm font-semibold text-text">{t.title}</span>
                  <span
                    className={`ml-2 text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                      t.status === 'in_progress'
                        ? 'bg-yellow-500/10 text-yellow-500'
                        : t.status === 'registration'
                          ? 'bg-blue-500/10 text-blue-400'
                          : t.status === 'completed'
                            ? 'bg-green-500/10 text-green-500'
                            : 'bg-text-muted/10 text-text-muted'
                    }`}
                  >
                    {TOURNAMENT_STATUS_LABELS[t.status] ?? t.status}
                  </span>
                  <p className="text-[11px] text-text-muted mt-0.5">
                    {t.bracket_size}강 ·{' '}
                    {t.current_round > 0 ? `${t.current_round}라운드 진행 중` : '라운드 시작 전'}
                  </p>
                </div>
                {t.status === 'registration' && (
                  <button
                    onClick={() => handleTournamentStart(t.id)}
                    disabled={tournamentStartingId === t.id}
                    className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-primary/40 text-primary hover:bg-primary/10 disabled:opacity-50 transition-colors"
                  >
                    {tournamentStartingId === t.id ? (
                      <Loader2 size={12} className="animate-spin" />
                    ) : (
                      <Play size={12} />
                    )}
                    토너먼트 시작
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 토픽 삭제 확인 다이얼로그 */}
      <ConfirmDialog
        isOpen={deleteTarget !== null}
        title="토론 주제 삭제"
        message={
          deleteTarget
            ? `"${deleteTarget.title}"을(를) 삭제합니다.\n매치 기록이 있는 주제는 삭제할 수 없습니다.`
            : ''
        }
        confirmLabel={deleting ? '삭제 중...' : '삭제'}
        variant="danger"
        onConfirm={handleDeleteConfirm}
        onCancel={() => {
          setDeleteTarget(null);
          setActionError(null);
        }}
      />

      {/* 에이전트 삭제 확인 다이얼로그 */}
      <ConfirmDialog
        isOpen={agentDeleteTarget !== null}
        title="에이전트 강제 삭제"
        message={
          agentDeleteTarget
            ? `"${agentDeleteTarget.name}" (소유자: ${agentDeleteTarget.owner_nickname})을(를) 삭제합니다.\n진행 중인 매치가 없는 경우에만 삭제됩니다.`
            : ''
        }
        confirmLabel={agentDeleting ? '삭제 중...' : '삭제'}
        variant="danger"
        onConfirm={handleAgentDeleteConfirm}
        onCancel={() => {
          setAgentDeleteTarget(null);
          setAgentActionError(null);
        }}
      />

      {/* 디버그 모달 */}
      {debugData && <DebateDebugModal data={debugData} onClose={() => setDebugData(null)} />}

      {/* 에이전트 상세 모달 */}
      <AgentDetailModal agentId={selectedAgentId} onClose={() => setSelectedAgentId(null)} />
    </div>
  );
}
