'use client';

import { memo, useCallback, useEffect, useState } from 'react';
import {
  X,
  User,
  ShieldCheck,
  MessageSquare,
  CalendarDays,
  Crown,
  Gem,
  ShieldAlert,
  Check,
  Pencil,
  Copy,
} from 'lucide-react';
import { api } from '@/lib/api';
import { toast } from '@/stores/toastStore';
import { useUserStore } from '@/stores/userStore';

type AdminUserDetail = {
  id: string;
  nickname: string;
  role: string;
  age_group: string;
  adult_verified_at: string | null;
  preferred_llm_model_id: string | null;
  preferred_themes: string[] | null;
  credit_balance: number;
  last_credit_grant_at: string | null;
  created_at: string;
  updated_at: string | null;
  session_count: number;
  message_count: number;
  subscription_status: string | null;
};

type QuotaInfo = {
  daily_token_limit: number;
  monthly_token_limit: number;
  is_active: boolean;
} | null;

type Props = {
  userId: string | null;
  onClose: () => void;
  onUserUpdated: () => void;
};

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '-';
  return new Date(iso).toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded-md text-xs font-semibold ${color}`}>
      {label}
    </span>
  );
}

function roleBadge(role: string) {
  switch (role) {
    case 'superadmin':
      return <Badge label="슈퍼관리자" color="bg-purple-500/15 text-purple-400" />;
    case 'admin':
      return <Badge label="관리자" color="bg-primary/15 text-primary" />;
    default:
      return <Badge label="사용자" color="bg-bg-hover text-text-muted" />;
  }
}

function ageBadge(ag: string) {
  switch (ag) {
    case 'adult_verified':
      return <Badge label="성인인증" color="bg-success/15 text-success" />;
    case 'minor_safe':
      return <Badge label="청소년" color="bg-warning/15 text-warning" />;
    default:
      return <Badge label="미인증" color="bg-bg-hover text-text-muted" />;
  }
}

function StatMini({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof User;
  label: string;
  value: string | number;
}) {
  return (
    <div className="flex flex-col gap-1 p-3 bg-bg rounded-lg">
      <div className="flex items-center gap-1.5 text-text-muted">
        <Icon size={14} />
        <span className="text-xs">{label}</span>
      </div>
      <span className="text-lg font-bold text-text">
        {typeof value === 'number' ? value.toLocaleString() : value}
      </span>
    </div>
  );
}

export const UserDetailDrawer = memo(function UserDetailDrawer({
  userId,
  onClose,
  onUserUpdated,
}: Props) {
  const isSuperAdmin = useUserStore((s) => s.isSuperAdmin);
  const [detail, setDetail] = useState<AdminUserDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [creditAmount, setCreditAmount] = useState('');
  const [granting, setGranting] = useState(false);
  const [roleChanging, setRoleChanging] = useState(false);

  // 쿼터
  const [quota, setQuota] = useState<QuotaInfo>(undefined as unknown as QuotaInfo);
  const [quotaLoaded, setQuotaLoaded] = useState(false);
  const [editingQuota, setEditingQuota] = useState(false);
  const [quotaForm, setQuotaForm] = useState({
    daily_token_limit: 100000,
    monthly_token_limit: 2000000,
  });
  const [savingQuota, setSavingQuota] = useState(false);

  const fetchDetail = useCallback(
    async (id: string) => {
      setLoading(true);
      try {
        const data = await api.get<AdminUserDetail>(`/admin/users/${id}`);
        setDetail(data);
      } catch {
        toast.error('사용자 정보를 불러올 수 없습니다');
        onClose();
      } finally {
        setLoading(false);
      }
    },
    [onClose],
  );

  const fetchQuota = useCallback(async (id: string) => {
    try {
      const data = await api.get<QuotaInfo>(`/admin/usage/quotas/${id}`);
      setQuota(data);
      if (data) {
        setQuotaForm({
          daily_token_limit: data.daily_token_limit,
          monthly_token_limit: data.monthly_token_limit,
        });
      }
    } catch {
      setQuota(null);
    } finally {
      setQuotaLoaded(true);
    }
  }, []);

  useEffect(() => {
    if (userId) {
      setDetail(null);
      setCreditAmount('');
      setQuota(undefined as unknown as QuotaInfo);
      setQuotaLoaded(false);
      setEditingQuota(false);
      fetchDetail(userId);
      fetchQuota(userId);
    }
  }, [userId, fetchDetail, fetchQuota]);

  useEffect(() => {
    if (!userId) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [userId, onClose]);

  if (!userId) return null;

  const handleRoleChange = async (newRole: string) => {
    if (!detail || detail.role === newRole) return;
    setRoleChanging(true);
    try {
      await api.put(`/admin/users/${detail.id}/role`, { role: newRole });
      const roleLabel =
        { superadmin: '슈퍼관리자', admin: '관리자', user: '사용자' }[newRole] ?? newRole;
      toast.success(`역할을 ${roleLabel}(으)로 변경했습니다`);
      await fetchDetail(detail.id);
      onUserUpdated();
    } catch {
      toast.error('역할 변경에 실패했습니다');
    } finally {
      setRoleChanging(false);
    }
  };

  const handleSaveQuota = async () => {
    if (!detail) return;
    setSavingQuota(true);
    try {
      const updated = await api.put<
        QuotaInfo & { daily_token_limit: number; monthly_token_limit: number; is_active: boolean }
      >(`/admin/usage/quotas/${detail.id}`, quotaForm);
      setQuota(updated);
      setEditingQuota(false);
      toast.success('쿼터를 저장했습니다');
    } catch {
      toast.error('쿼터 저장에 실패했습니다');
    } finally {
      setSavingQuota(false);
    }
  };

  const handleGrantCredits = async () => {
    if (!detail) return;
    const amount = parseInt(creditAmount, 10);
    if (!amount || amount <= 0) {
      toast.error('유효한 금액을 입력하세요');
      return;
    }
    setGranting(true);
    try {
      await api.put('/admin/credits/grant', { user_id: detail.id, amount });
      toast.success(`${amount.toLocaleString()} 대화석을 지급했습니다`);
      setCreditAmount('');
      await fetchDetail(detail.id);
      onUserUpdated();
    } catch {
      toast.error('크레딧 지급에 실패했습니다');
    } finally {
      setGranting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50" onClick={onClose}>
      <div
        className="w-[480px] h-full bg-bg-surface overflow-y-auto animate-slide-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 bg-bg-surface flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-lg font-semibold text-text m-0">사용자 상세</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-transparent border-none text-text-muted hover:text-text hover:bg-bg-hover cursor-pointer"
          >
            <X size={20} />
          </button>
        </div>

        {loading || !detail ? (
          <div className="p-6 space-y-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-16 bg-bg-hover rounded-lg animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="p-6 space-y-6">
            {/* 기본 정보 */}
            <section>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 rounded-full bg-primary/20 flex items-center justify-center text-primary flex-shrink-0">
                  <User size={24} />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-text m-0">{detail.nickname}</h3>
                  <div className="flex items-center gap-2 mt-1">
                    {roleBadge(detail.role)}
                    {ageBadge(detail.age_group)}
                  </div>
                </div>
              </div>

              <div className="space-y-2 text-sm">
                <div className="flex justify-between items-center">
                  <span className="text-text-muted">UUID</span>
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-[11px] text-text-secondary">{detail.id}</span>
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard.writeText(detail.id);
                        toast.success('UUID 복사됨');
                      }}
                      className="p-1 rounded text-text-muted hover:text-text hover:bg-bg-hover transition-colors border-none bg-transparent cursor-pointer"
                      title="복사"
                    >
                      <Copy size={12} />
                    </button>
                  </div>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-muted">역할</span>
                  {isSuperAdmin() ? (
                    <select
                      value={detail.role}
                      onChange={(e) => handleRoleChange(e.target.value)}
                      disabled={roleChanging}
                      className="bg-bg border border-border rounded px-2 py-1 text-sm text-text cursor-pointer"
                    >
                      <option value="user">사용자</option>
                      <option value="admin">관리자</option>
                      <option value="superadmin">슈퍼관리자</option>
                    </select>
                  ) : (
                    <span className="text-text text-sm">{roleBadge(detail.role)}</span>
                  )}
                </div>
                <div className="flex justify-between">
                  <span className="text-text-muted">성인인증</span>
                  <span className="text-text">
                    {detail.adult_verified_at ? formatDate(detail.adult_verified_at) : '미인증'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-muted">가입일</span>
                  <span className="text-text">{formatDate(detail.created_at)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-muted">수정일</span>
                  <span className="text-text">{formatDate(detail.updated_at)}</span>
                </div>
                {detail.preferred_themes && detail.preferred_themes.length > 0 && (
                  <div className="flex justify-between">
                    <span className="text-text-muted">관심 테마</span>
                    <span className="text-text">{detail.preferred_themes.join(', ')}</span>
                  </div>
                )}
              </div>
            </section>

            {/* 크레딧 */}
            <section>
              <h4 className="text-sm font-semibold text-text-muted uppercase tracking-wide mb-3 flex items-center gap-1.5">
                <Gem size={14} />
                크레딧
              </h4>
              <div className="space-y-2 text-sm mb-3">
                <div className="flex justify-between">
                  <span className="text-text-muted">잔액</span>
                  <span className="text-text font-semibold">
                    {detail.credit_balance.toLocaleString()} 대화석
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-muted">마지막 충전</span>
                  <span className="text-text">{formatDate(detail.last_credit_grant_at)}</span>
                </div>
              </div>
              {isSuperAdmin() && (
                <div className="flex gap-2">
                  <input
                    type="number"
                    value={creditAmount}
                    onChange={(e) => setCreditAmount(e.target.value)}
                    placeholder="지급할 대화석"
                    min="1"
                    className="flex-1 bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-muted"
                  />
                  <button
                    onClick={handleGrantCredits}
                    disabled={granting || !creditAmount}
                    className="px-4 py-2 rounded-lg text-sm text-white bg-primary hover:bg-primary/80 border-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {granting ? '...' : '지급'}
                  </button>
                </div>
              )}
            </section>

            {/* 활동 통계 */}
            <section>
              <h4 className="text-sm font-semibold text-text-muted uppercase tracking-wide mb-3 flex items-center gap-1.5">
                <ShieldCheck size={14} />
                활동 통계
              </h4>
              <div className="grid grid-cols-2 gap-2">
                <StatMini icon={CalendarDays} label="세션" value={detail.session_count} />
                <StatMini icon={MessageSquare} label="메시지" value={detail.message_count} />
                <StatMini icon={Crown} label="구독" value={detail.subscription_status ?? '없음'} />
              </div>
            </section>

            {/* 토큰 쿼터 */}
            {quotaLoaded && (
              <section>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-semibold text-text-muted uppercase tracking-wide flex items-center gap-1.5 m-0">
                    <ShieldAlert size={14} />
                    토큰 쿼터
                  </h4>
                  {isSuperAdmin() && !editingQuota && (
                    <button
                      onClick={() => {
                        if (quota) {
                          setQuotaForm({
                            daily_token_limit: quota.daily_token_limit,
                            monthly_token_limit: quota.monthly_token_limit,
                          });
                        }
                        setEditingQuota(true);
                      }}
                      className="p-1.5 rounded text-text-muted hover:text-text hover:bg-bg-hover transition-colors border-none bg-transparent cursor-pointer"
                    >
                      <Pencil size={13} />
                    </button>
                  )}
                </div>

                {editingQuota ? (
                  <div className="space-y-2">
                    <div>
                      <label className="block text-xs text-text-muted mb-1">일일 토큰 한도</label>
                      <input
                        type="number"
                        min={0}
                        value={quotaForm.daily_token_limit}
                        onChange={(e) =>
                          setQuotaForm({ ...quotaForm, daily_token_limit: Number(e.target.value) })
                        }
                        className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-text-muted mb-1">월간 토큰 한도</label>
                      <input
                        type="number"
                        min={0}
                        value={quotaForm.monthly_token_limit}
                        onChange={(e) =>
                          setQuotaForm({
                            ...quotaForm,
                            monthly_token_limit: Number(e.target.value),
                          })
                        }
                        className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text"
                      />
                    </div>
                    <div className="flex gap-2 pt-1">
                      <button
                        onClick={handleSaveQuota}
                        disabled={savingQuota}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-white text-xs hover:bg-primary/90 disabled:opacity-50 border-none cursor-pointer"
                      >
                        <Check size={12} />
                        {savingQuota ? '저장 중...' : '저장'}
                      </button>
                      <button
                        onClick={() => setEditingQuota(false)}
                        className="px-3 py-1.5 rounded-lg text-xs text-text-muted border border-border bg-transparent hover:bg-bg-hover cursor-pointer"
                      >
                        취소
                      </button>
                    </div>
                  </div>
                ) : quota ? (
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-text-muted">일일 한도</span>
                      <span className="font-mono text-text">
                        {quota.daily_token_limit.toLocaleString()} 토큰
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-text-muted">월간 한도</span>
                      <span className="font-mono text-text">
                        {quota.monthly_token_limit.toLocaleString()} 토큰
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-text-muted">상태</span>
                      <span
                        className={
                          quota.is_active
                            ? 'text-success text-xs font-semibold'
                            : 'text-text-muted text-xs'
                        }
                      >
                        {quota.is_active ? '활성' : '비활성'}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="text-sm text-text-muted">
                    <p className="mb-2">커스텀 쿼터 없음 (기본값 적용 중)</p>
                    {isSuperAdmin() && (
                      <button
                        onClick={() => setEditingQuota(true)}
                        className="text-xs px-3 py-1.5 rounded-lg border border-border text-text-muted hover:text-text hover:bg-bg-hover transition-colors bg-transparent cursor-pointer"
                      >
                        쿼터 설정
                      </button>
                    )}
                  </div>
                )}
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  );
});
