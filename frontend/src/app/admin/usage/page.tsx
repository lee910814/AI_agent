'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { api } from '@/lib/api';
import { StatCard } from '@/components/admin/StatCard';
import { DataTable } from '@/components/admin/DataTable';
import { SkeletonStat } from '@/components/ui/Skeleton';
import {
  Coins,
  Hash,
  CalendarDays,
  ShieldAlert,
  Pencil,
  Check,
  X,
  Loader2,
  Search,
  User,
} from 'lucide-react';

type UsagePeriod = {
  input_tokens: number;
  output_tokens: number;
  cost: number;
  unique_users: number;
};

type ModelUsage = {
  model_name: string;
  input_tokens: number;
  output_tokens: number;
  cost: number;
};

type UsageSummaryResponse = {
  total: UsagePeriod;
  daily: UsagePeriod;
  monthly: UsagePeriod;
  by_model: ModelUsage[];
};

type QuotaEntry = {
  user_id: string;
  nickname: string | null;
  daily_token_limit: number;
  monthly_token_limit: number;
};

type LLMModel = {
  id: string;
  provider: string;
  model_id: string;
  display_name: string;
  input_cost_per_1m: number;
  output_cost_per_1m: number;
  max_context_length: number;
  is_active: boolean;
  tier: string;
  credit_per_1k_tokens: number;
};

type UserSearchResult = {
  id: string;
  nickname: string;
  login_id: string;
};

function UserSearchInput({ onSelect }: { onSelect: (user: UserSearchResult) => void }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<UserSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<UserSearchResult | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const search = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      setOpen(false);
      return;
    }
    setSearching(true);
    try {
      const data = await api.get<UserSearchResult[]>(
        `/admin/usage/user-search?q=${encodeURIComponent(q)}`,
      );
      setResults(data);
      setOpen(true);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    setSelected(null);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 300);
  };

  const handleSelect = (u: UserSearchResult) => {
    setSelected(u);
    setQuery(`${u.nickname} (${u.login_id})`);
    setOpen(false);
    onSelect(u);
  };

  // 외부 클릭 시 드롭다운 닫기
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={wrapRef} className="relative">
      <label className="block text-xs text-text-muted mb-1">사용자 검색 (닉네임 / 로그인ID)</label>
      <div className="relative">
        <input
          type="text"
          placeholder="닉네임 또는 ID 입력..."
          value={query}
          onChange={handleChange}
          onFocus={() => results.length > 0 && setOpen(true)}
          className="bg-bg-surface border border-border rounded-lg pl-8 pr-3 py-2 text-sm text-text w-64 focus:outline-none focus:border-primary"
        />
        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted">
          {searching ? <Loader2 size={13} className="animate-spin" /> : <Search size={13} />}
        </span>
      </div>
      {open && results.length > 0 && (
        <ul className="absolute z-20 mt-1 w-64 bg-bg-surface border border-border rounded-lg shadow-lg overflow-hidden max-h-52 overflow-y-auto">
          {results.map((u) => (
            <li key={u.id}>
              <button
                type="button"
                onClick={() => handleSelect(u)}
                className="w-full text-left px-3 py-2 hover:bg-bg-hover transition-colors flex items-center gap-2"
              >
                <User size={12} className="text-text-muted shrink-0" />
                <div className="min-w-0">
                  <span className="block text-sm font-medium text-text truncate">{u.nickname}</span>
                  <span className="block text-[11px] text-text-muted truncate">{u.login_id}</span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
      {selected && (
        <p className="mt-1 text-[11px] text-text-muted font-mono truncate">UUID: {selected.id}</p>
      )}
    </div>
  );
}

export default function AdminUsagePage() {
  const [summary, setSummary] = useState<UsageSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [quotas, setQuotas] = useState<QuotaEntry[]>([]);
  const [models, setModels] = useState<LLMModel[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ daily_token_limit: 0, monthly_token_limit: 0 });
  const [savingId, setSavingId] = useState<string | null>(null);
  const [selectedUser, setSelectedUser] = useState<UserSearchResult | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);

  useEffect(() => {
    api
      .get<UsageSummaryResponse>('/admin/usage/summary')
      .then(setSummary)
      .catch(() => {})
      .finally(() => setLoading(false));
    api
      .get<QuotaEntry[]>('/admin/usage/quotas')
      .then(setQuotas)
      .catch(() => {});
    api
      .get<{ items: LLMModel[] }>('/admin/models')
      .then((r) => setModels(r.items))
      .catch(() => {});
  }, []);

  const startEdit = (q: QuotaEntry) => {
    setEditingId(q.user_id);
    setEditForm({
      daily_token_limit: q.daily_token_limit,
      monthly_token_limit: q.monthly_token_limit,
    });
  };

  const saveQuota = async (userId: string) => {
    setSavingId(userId);
    try {
      const updated = await api.put<QuotaEntry>(`/admin/usage/quotas/${userId}`, editForm);
      setQuotas((prev) => prev.map((q) => (q.user_id === userId ? updated : q)));
      setEditingId(null);
    } catch {
      // keep editing on error
    } finally {
      setSavingId(null);
    }
  };

  const addQuota = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser) return;
    setSavingId('new');
    try {
      const created = await api.put<QuotaEntry>(`/admin/usage/quotas/${selectedUser.id}`, editForm);
      setQuotas((prev) => [...prev, created]);
      setSelectedUser(null);
      setShowAddForm(false);
      setEditForm({ daily_token_limit: 100000, monthly_token_limit: 2000000 });
    } catch {
      // ignore
    } finally {
      setSavingId(null);
    }
  };

  const modelColumns = [
    { key: 'model_name' as const, label: '모델' },
    {
      key: 'input_tokens' as const,
      label: '입력 토큰',
      render: (val: unknown) => Number(val).toLocaleString(),
    },
    {
      key: 'output_tokens' as const,
      label: '출력 토큰',
      render: (val: unknown) => Number(val).toLocaleString(),
    },
    {
      key: 'cost' as const,
      label: '비용',
      render: (val: unknown) => `$${Number(val).toFixed(4)}`,
    },
  ];

  return (
    <div>
      <h1 className="page-title">사용량 & 과금</h1>

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 mb-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonStat key={i} />
          ))}
        </div>
      ) : summary ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 mb-6">
          <StatCard
            title="오늘 토큰"
            value={(summary.daily.input_tokens + summary.daily.output_tokens).toLocaleString()}
            icon={<Hash className="w-5 h-5" />}
          />
          <StatCard
            title="오늘 비용"
            value={`$${summary.daily.cost.toFixed(4)}`}
            icon={<Coins className="w-5 h-5" />}
          />
          <StatCard
            title="이번 달 토큰"
            value={(summary.monthly.input_tokens + summary.monthly.output_tokens).toLocaleString()}
            icon={<CalendarDays className="w-5 h-5" />}
          />
          <StatCard
            title="이번 달 비용"
            value={`$${summary.monthly.cost.toFixed(4)}`}
            icon={<Coins className="w-5 h-5" />}
          />
          <StatCard
            title="전체 토큰"
            value={(summary.total.input_tokens + summary.total.output_tokens).toLocaleString()}
            icon={<Hash className="w-5 h-5" />}
          />
          <StatCard
            title="전체 비용"
            value={`$${summary.total.cost.toFixed(4)}`}
            icon={<Coins className="w-5 h-5" />}
          />
        </div>
      ) : null}

      {summary && summary.by_model.length > 0 && (
        <section className="mb-6">
          <h2 className="section-title">모델별 사용량</h2>
          <div className="card">
            <DataTable columns={modelColumns} data={summary.by_model} />
          </div>
        </section>
      )}

      {/* 등록된 전체 모델 목록 */}
      {models.length > 0 && (
        <section className="mb-6">
          <h2 className="section-title">등록된 LLM 모델 ({models.length}개)</h2>
          <div className="card overflow-x-auto">
            <table className="w-full text-sm min-w-[700px]">
              <thead>
                <tr className="border-b border-border text-text-muted text-left">
                  <th className="pb-2 pr-4 font-medium">모델명</th>
                  <th className="pb-2 pr-4 font-medium">Provider</th>
                  <th className="pb-2 pr-4 font-medium">Model ID</th>
                  <th className="pb-2 pr-4 font-medium text-right">입력 단가</th>
                  <th className="pb-2 pr-4 font-medium text-right">출력 단가</th>
                  <th className="pb-2 pr-4 font-medium text-right">컨텍스트</th>
                  <th className="pb-2 font-medium text-center">상태</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {models.map((m) => (
                  <tr key={m.id} className="hover:bg-bg transition-colors">
                    <td className="py-2 pr-4 font-medium text-text">{m.display_name}</td>
                    <td className="py-2 pr-4 text-text-secondary">{m.provider}</td>
                    <td className="py-2 pr-4 font-mono text-xs text-text-muted">{m.model_id}</td>
                    <td className="py-2 pr-4 text-right font-mono text-xs">
                      ${m.input_cost_per_1m.toFixed(2)}/1M
                    </td>
                    <td className="py-2 pr-4 text-right font-mono text-xs">
                      ${m.output_cost_per_1m.toFixed(2)}/1M
                    </td>
                    <td className="py-2 pr-4 text-right text-xs text-text-muted">
                      {(m.max_context_length / 1000).toFixed(0)}K
                    </td>
                    <td className="py-2 text-center">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold ${
                          m.is_active ? 'bg-success/10 text-success' : 'bg-border text-text-muted'
                        }`}
                      >
                        {m.is_active ? '활성' : '비활성'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* 사용자별 쿼터 관리 */}
      <section className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="section-title flex items-center gap-2 m-0">
            <ShieldAlert size={16} className="text-primary" />
            사용자별 쿼터 설정
          </h2>
          <button
            onClick={() => {
              setShowAddForm(!showAddForm);
              setEditForm({ daily_token_limit: 100000, monthly_token_limit: 2000000 });
              setSelectedUser(null);
            }}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors"
          >
            {showAddForm ? <X size={13} /> : <Pencil size={13} />}
            {showAddForm ? '닫기' : '쿼터 추가'}
          </button>
        </div>

        {showAddForm && (
          <form onSubmit={addQuota} className="card p-4 mb-3 flex flex-wrap gap-3 items-end">
            <UserSearchInput onSelect={setSelectedUser} />
            <div>
              <label className="block text-xs text-text-muted mb-1">일일 토큰 한도</label>
              <input
                type="number"
                min={0}
                value={editForm.daily_token_limit}
                onChange={(e) =>
                  setEditForm({ ...editForm, daily_token_limit: Number(e.target.value) })
                }
                className="bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text w-36 focus:outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">월간 토큰 한도</label>
              <input
                type="number"
                min={0}
                value={editForm.monthly_token_limit}
                onChange={(e) =>
                  setEditForm({ ...editForm, monthly_token_limit: Number(e.target.value) })
                }
                className="bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text w-36 focus:outline-none focus:border-primary"
              />
            </div>
            <button
              type="submit"
              disabled={!selectedUser || savingId === 'new'}
              className="px-4 py-2 rounded-lg bg-primary text-white text-sm hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {savingId === 'new' ? '저장 중...' : '추가'}
            </button>
          </form>
        )}

        <div className="card overflow-x-auto">
          {quotas.length === 0 ? (
            <p className="text-sm text-text-muted text-center py-6">
              커스텀 쿼터 설정이 없습니다. (기본값 적용 중)
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-text-muted text-left">
                  <th className="pb-2 pr-4 font-medium">사용자</th>
                  <th className="pb-2 pr-4 font-medium text-right">일일 한도</th>
                  <th className="pb-2 pr-4 font-medium text-right">월간 한도</th>
                  <th className="pb-2 font-medium text-right">관리</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {quotas.map((q) => (
                  <tr key={q.user_id} className="hover:bg-bg transition-colors">
                    <td className="py-2 pr-4">
                      {q.nickname ? (
                        <div>
                          <span className="font-medium text-text">{q.nickname}</span>
                          <span className="block font-mono text-[11px] text-text-muted mt-0.5">
                            {q.user_id}
                          </span>
                        </div>
                      ) : (
                        <span className="font-mono text-xs text-text-muted">{q.user_id}</span>
                      )}
                    </td>
                    {editingId === q.user_id ? (
                      <>
                        <td className="py-2 pr-4 text-right">
                          <input
                            type="number"
                            min={0}
                            value={editForm.daily_token_limit}
                            onChange={(e) =>
                              setEditForm({
                                ...editForm,
                                daily_token_limit: Number(e.target.value),
                              })
                            }
                            className="w-28 bg-bg border border-primary/40 rounded px-2 py-1 text-sm text-text text-right focus:outline-none"
                          />
                        </td>
                        <td className="py-2 pr-4 text-right">
                          <input
                            type="number"
                            min={0}
                            value={editForm.monthly_token_limit}
                            onChange={(e) =>
                              setEditForm({
                                ...editForm,
                                monthly_token_limit: Number(e.target.value),
                              })
                            }
                            className="w-32 bg-bg border border-primary/40 rounded px-2 py-1 text-sm text-text text-right focus:outline-none"
                          />
                        </td>
                        <td className="py-2 text-right">
                          <div className="flex items-center gap-1 justify-end">
                            <button
                              onClick={() => saveQuota(q.user_id)}
                              disabled={savingId === q.user_id}
                              className="p-1.5 rounded text-green-500 hover:bg-green-500/10 disabled:opacity-50 transition-colors"
                            >
                              {savingId === q.user_id ? (
                                <Loader2 size={13} className="animate-spin" />
                              ) : (
                                <Check size={13} />
                              )}
                            </button>
                            <button
                              onClick={() => setEditingId(null)}
                              className="p-1.5 rounded text-text-muted hover:bg-bg-hover transition-colors"
                            >
                              <X size={13} />
                            </button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="py-2 pr-4 text-right font-mono text-xs">
                          {q.daily_token_limit.toLocaleString()}
                        </td>
                        <td className="py-2 pr-4 text-right font-mono text-xs">
                          {q.monthly_token_limit.toLocaleString()}
                        </td>
                        <td className="py-2 text-right">
                          <button
                            onClick={() => startEdit(q)}
                            className="p-1.5 rounded text-text-muted hover:text-text hover:bg-bg-hover transition-colors"
                          >
                            <Pencil size={13} />
                          </button>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}
