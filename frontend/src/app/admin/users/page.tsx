'use client';

import { useCallback, useEffect, useState } from 'react';
import { Users, ShieldCheck, Shield, Crown, UserX, Search, Trash2 } from 'lucide-react';
import { api } from '@/lib/api';
import { toast } from '@/stores/toastStore';
import { useUserStore } from '@/stores/userStore';
import { DataTable } from '@/components/admin/DataTable';
import { StatCard } from '@/components/admin/StatCard';
import { UserDetailDrawer } from '@/components/admin/UserDetailDrawer';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';

type AdminUser = {
  id: string;
  nickname: string;
  role: string;
  age_group: string;
  adult_verified_at: string | null;
  created_at: string;
};

type UserStats = {
  total_users: number;
  superadmin_count: number;
  admin_count: number;
  adult_verified_count: number;
  unverified_count: number;
  minor_safe_count: number;
};

type UserListResponse = {
  items: AdminUser[];
  total: number;
  stats: UserStats | null;
};

function formatDate(iso: string | null) {
  if (!iso) return '-';
  return new Date(iso).toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

function AgeBadge({ ageGroup }: { ageGroup: string }) {
  switch (ageGroup) {
    case 'adult_verified':
      return (
        <span className="inline-block px-2 py-0.5 rounded-md text-xs font-semibold bg-success/15 text-success">
          성인인증
        </span>
      );
    case 'minor_safe':
      return (
        <span className="inline-block px-2 py-0.5 rounded-md text-xs font-semibold bg-warning/15 text-warning">
          청소년
        </span>
      );
    default:
      return (
        <span className="inline-block px-2 py-0.5 rounded-md text-xs font-semibold bg-bg-hover text-text-muted">
          미인증
        </span>
      );
  }
}

function RoleBadge({ role }: { role: string }) {
  switch (role) {
    case 'superadmin':
      return (
        <span className="inline-block px-2 py-0.5 rounded-md text-xs font-semibold bg-purple-500/15 text-purple-400">
          슈퍼관리자
        </span>
      );
    case 'admin':
      return (
        <span className="inline-block px-2 py-0.5 rounded-md text-xs font-semibold bg-primary/15 text-primary">
          관리자
        </span>
      );
    default:
      return (
        <span className="inline-block px-2 py-0.5 rounded-md text-xs font-semibold bg-bg-hover text-text-muted">
          사용자
        </span>
      );
  }
}

const PAGE_SIZE = 20;

export default function AdminUsersPage() {
  const isSuperAdmin = useUserStore((s) => s.isSuperAdmin);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [page, setPage] = useState(0);

  // Selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Detail drawer
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);

  // Delete confirm
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Filters
  const [roleFilter, setRoleFilter] = useState('');
  const [ageGroupFilter, setAgeGroupFilter] = useState('');
  const [sortBy, setSortBy] = useState('');

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setPage(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('skip', String(page * PAGE_SIZE));
      params.set('limit', String(PAGE_SIZE));
      if (debouncedSearch) params.set('search', debouncedSearch);
      if (roleFilter) params.set('role', roleFilter);
      if (ageGroupFilter) params.set('age_group', ageGroupFilter);
      if (sortBy) params.set('sort_by', sortBy);

      const res = await api.get<UserListResponse>(`/admin/users?${params}`);
      setUsers(res.items ?? []);
      setTotal(res.total);
      setStats(res.stats ?? null);
    } catch {
      toast.error('사용자 목록을 불러올 수 없습니다');
    } finally {
      setLoading(false);
    }
  }, [page, debouncedSearch, roleFilter, ageGroupFilter, sortBy]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // Selection handlers
  const handleSelectChange = (id: string, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      checked ? next.add(id) : next.delete(id);
      return next;
    });
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(users.map((u) => u.id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  // Bulk delete
  const handleBulkDelete = async () => {
    setDeleting(true);
    try {
      const res = await api.post<{ deleted_count: number; skipped_admin_ids: string[] }>(
        '/admin/users/bulk-delete',
        { user_ids: Array.from(selectedIds) },
      );
      toast.success(`${res.deleted_count}명의 사용자를 삭제했습니다`);
      if (res.skipped_admin_ids.length > 0) {
        toast.info(`관리자 ${res.skipped_admin_ids.length}명은 삭제할 수 없습니다`);
      }
      setSelectedIds(new Set());
      fetchUsers();
    } catch {
      toast.error('삭제에 실패했습니다');
    } finally {
      setDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  const columns = [
    {
      key: 'nickname' as const,
      label: '닉네임',
      render: (_: unknown, row: AdminUser) => (
        <span className="font-medium text-text">{row.nickname}</span>
      ),
    },
    {
      key: 'role' as const,
      label: '역할',
      render: (_: unknown, row: AdminUser) => <RoleBadge role={row.role} />,
    },
    {
      key: 'age_group' as const,
      label: '연령 상태',
      render: (_: unknown, row: AdminUser) => <AgeBadge ageGroup={row.age_group} />,
    },
    {
      key: 'adult_verified_at' as const,
      label: '성인인증일',
      render: (v: unknown) => (
        <span className="text-text-secondary text-xs">{formatDate(v as string | null)}</span>
      ),
    },
    {
      key: 'created_at' as const,
      label: '가입일',
      render: (v: unknown) => (
        <span className="text-text-secondary text-xs">{formatDate(v as string)}</span>
      ),
    },
  ];

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const rangeStart = total > 0 ? page * PAGE_SIZE + 1 : 0;
  const rangeEnd = Math.min((page + 1) * PAGE_SIZE, total);

  return (
    <div className="max-w-[1200px] mx-auto">
      <h1 className="text-xl font-bold text-text mb-6">사용자 관리</h1>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <StatCard
          title="전체 사용자"
          value={stats?.total_users ?? '-'}
          icon={<Users size={20} />}
        />
        <StatCard
          title="슈퍼관리자"
          value={stats?.superadmin_count ?? '-'}
          icon={<Crown size={20} />}
        />
        <StatCard title="관리자" value={stats?.admin_count ?? '-'} icon={<Shield size={20} />} />
        <StatCard
          title="성인인증"
          value={stats?.adult_verified_count ?? '-'}
          icon={<ShieldCheck size={20} />}
        />
        <StatCard
          title="미인증"
          value={stats?.unverified_count ?? '-'}
          icon={<UserX size={20} />}
        />
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
        <input
          type="text"
          placeholder="닉네임으로 검색..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full bg-bg-surface border border-border rounded-lg pl-9 pr-4 py-2.5 text-sm text-text placeholder:text-text-muted focus:outline-none focus:border-primary"
        />
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <select
          value={roleFilter}
          onChange={(e) => {
            setRoleFilter(e.target.value);
            setPage(0);
          }}
          className="bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
        >
          <option value="">전체 역할</option>
          <option value="user">사용자</option>
          <option value="admin">관리자</option>
          <option value="superadmin">슈퍼관리자</option>
        </select>
        <select
          value={ageGroupFilter}
          onChange={(e) => {
            setAgeGroupFilter(e.target.value);
            setPage(0);
          }}
          className="bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
        >
          <option value="">전체 연령</option>
          <option value="unverified">미인증</option>
          <option value="minor_safe">청소년</option>
          <option value="adult_verified">성인인증</option>
        </select>
        <select
          value={sortBy}
          onChange={(e) => {
            setSortBy(e.target.value);
            setPage(0);
          }}
          className="bg-bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
        >
          <option value="">가입일순</option>
          <option value="nickname">닉네임순</option>
          <option value="credit_balance">크레딧순</option>
        </select>
      </div>

      {/* Selection toolbar (superadmin only) */}
      {isSuperAdmin() && selectedIds.size > 0 && (
        <div className="flex items-center gap-3 mb-3 p-3 bg-bg-surface rounded-lg border border-border">
          <span className="text-sm text-text-secondary">
            <strong className="text-text">{selectedIds.size}</strong>명 선택됨
          </span>
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="flex items-center gap-1.5 py-1.5 px-4 rounded-md border-none bg-danger text-white text-sm cursor-pointer hover:bg-danger/80"
          >
            <Trash2 size={14} />
            선택 삭제
          </button>
          <button
            onClick={() => setSelectedIds(new Set())}
            className="py-1.5 px-4 rounded-md text-sm cursor-pointer bg-transparent border border-border text-text-secondary hover:bg-bg-hover"
          >
            선택 해제
          </button>
        </div>
      )}

      {/* Table */}
      <div className="bg-bg-surface rounded-lg border border-border overflow-hidden">
        <DataTable
          columns={columns}
          data={users as (AdminUser & Record<string, unknown>)[]}
          loading={loading}
          selectable={isSuperAdmin()}
          selectedIds={selectedIds}
          onSelectChange={handleSelectChange}
          onSelectAll={handleSelectAll}
          onRowClick={(row) => setSelectedUserId(row.id as string)}
        />
      </div>

      {/* Pagination */}
      {total > 0 && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-sm text-text-muted">
            총 {total.toLocaleString()}명 중 {rangeStart}-{rangeEnd}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="py-1.5 px-4 rounded-md text-sm bg-bg-surface border border-border text-text-secondary hover:bg-bg-hover cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              이전
            </button>
            <span className="py-1.5 px-3 text-sm text-text-muted">
              {page + 1} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={(page + 1) * PAGE_SIZE >= total}
              className="py-1.5 px-4 rounded-md text-sm bg-bg-surface border border-border text-text-secondary hover:bg-bg-hover cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              다음
            </button>
          </div>
        </div>
      )}

      {/* Detail Drawer */}
      <UserDetailDrawer
        userId={selectedUserId}
        onClose={() => setSelectedUserId(null)}
        onUserUpdated={fetchUsers}
      />

      {/* Delete Confirm */}
      <ConfirmDialog
        isOpen={showDeleteConfirm}
        title="사용자 삭제"
        message={`선택한 ${selectedIds.size}명의 사용자를 삭제하시겠습니까? 관련된 채팅, 페르소나 등 모든 데이터가 함께 삭제되며 되돌릴 수 없습니다.`}
        confirmLabel="삭제"
        variant="danger"
        loading={deleting}
        onConfirm={handleBulkDelete}
        onCancel={() => setShowDeleteConfirm(false)}
      />
    </div>
  );
}
