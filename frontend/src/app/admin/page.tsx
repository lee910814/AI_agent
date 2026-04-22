'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { StatCard } from '@/components/admin/StatCard';
import { SkeletonStat } from '@/components/ui/Skeleton';
import { Users, UserPlus, Sword, Trophy } from 'lucide-react';

type MonitoringStats = {
  totals?: { users?: number; agents?: number; matches?: number };
  weekly?: { new_users?: number };
};

type DashboardData = {
  users: number | null;
  newUsersWeekly: number | null;
  agents: number | null;
  matches: number | null;
};

type RecentUser = {
  id: string;
  login_id: string;
  nickname: string;
  role: string;
  created_at: string;
};

type RecentMatch = {
  id: string;
  topic_title: string;
  status: string;
  created_at: string;
};

const MATCH_STATUS_LABEL: Record<string, string> = {
  pending: '대기 중',
  in_progress: '진행 중',
  completed: '완료',
  cancelled: '취소',
};

function formatDate(isoString: string): string {
  const date = new Date(isoString);
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${month}월 ${day}일 ${hours}:${minutes}`;
}

export default function AdminDashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [recentUsers, setRecentUsers] = useState<RecentUser[]>([]);
  const [recentMatches, setRecentMatches] = useState<RecentMatch[]>([]);
  const [activityLoading, setActivityLoading] = useState(true);

  useEffect(() => {
    async function fetchAll() {
      const result: DashboardData = {
        users: null,
        newUsersWeekly: null,
        agents: null,
        matches: null,
      };

      await api
        .get<MonitoringStats>('/admin/monitoring/stats')
        .then((stats) => {
          result.users = stats?.totals?.users ?? null;
          result.newUsersWeekly = stats?.weekly?.new_users ?? null;
          result.agents = stats?.totals?.agents ?? null;
          result.matches = stats?.totals?.matches ?? null;
        })
        .catch(() => {});

      setData(result);
      setLoading(false);
    }

    async function fetchActivity() {
      await Promise.all([
        api
          .get<{ items: RecentUser[] }>('/admin/users?limit=5&sort_by=created_at')
          .then((res) => setRecentUsers(res?.items ?? []))
          .catch(() => {}),
        api
          .get<{ items: RecentMatch[] }>('/admin/debate/matches?limit=5')
          .then((res) => setRecentMatches(res?.items ?? []))
          .catch(() => {}),
      ]);
      setActivityLoading(false);
    }

    fetchAll();
    fetchActivity();
  }, []);

  const fmt = (val: number | null) => (val === null ? '-' : val);

  return (
    <div>
      <h1 className="page-title">대시보드</h1>

      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonStat key={i} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-4">
          <StatCard
            title="전체 사용자"
            value={fmt(data?.users ?? null)}
            description="등록 사용자 수"
            icon={<Users className="w-5 h-5" />}
          />
          <StatCard
            title="이번 주 신규 사용자"
            value={fmt(data?.newUsersWeekly ?? null)}
            description="최근 7일 가입"
            icon={<UserPlus className="w-5 h-5" />}
          />
          <StatCard
            title="에이전트 수"
            value={fmt(data?.agents ?? null)}
            description="등록된 AI 에이전트"
            icon={<Sword className="w-5 h-5" />}
          />
          <StatCard
            title="매치 수"
            value={fmt(data?.matches ?? null)}
            description="전체 토론 매치"
            icon={<Trophy className="w-5 h-5" />}
          />
        </div>
      )}

      <section className="mt-8">
        <h2 className="section-title">최근 활동</h2>
        {activityLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="card animate-pulse">
                <div className="h-4 bg-bg-surface rounded w-1/3 mb-4" />
                {Array.from({ length: 5 }).map((__, j) => (
                  <div key={j} className="h-10 bg-bg-surface rounded mb-2" />
                ))}
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 최근 가입 사용자 */}
            <div className="card">
              <h3 className="text-sm font-semibold text-text mb-3 flex items-center gap-2">
                <UserPlus className="w-4 h-4 text-primary" />
                최근 가입 사용자
              </h3>
              {recentUsers.length === 0 ? (
                <p className="text-sm text-text-muted py-4 text-center">데이터가 없습니다.</p>
              ) : (
                <ul className="divide-y divide-border">
                  {recentUsers.map((user) => (
                    <li key={user.id} className="py-2.5 flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-text truncate">{user.nickname}</p>
                        <p className="text-xs text-text-muted truncate">{user.login_id}</p>
                      </div>
                      <span className="text-xs text-text-muted whitespace-nowrap shrink-0">
                        {formatDate(user.created_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* 최근 매치 */}
            <div className="card">
              <h3 className="text-sm font-semibold text-text mb-3 flex items-center gap-2">
                <Sword className="w-4 h-4 text-primary" />
                최근 매치
              </h3>
              {recentMatches.length === 0 ? (
                <p className="text-sm text-text-muted py-4 text-center">데이터가 없습니다.</p>
              ) : (
                <ul className="divide-y divide-border">
                  {recentMatches.map((match) => (
                    <li key={match.id} className="py-2.5 flex items-center justify-between gap-3">
                      <p className="text-sm text-text truncate min-w-0">{match.topic_title}</p>
                      <div className="flex items-center gap-2 shrink-0">
                        <span
                          className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                            match.status === 'completed'
                              ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                              : match.status === 'in_progress'
                                ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                                : 'bg-bg-surface text-text-muted'
                          }`}
                        >
                          {MATCH_STATUS_LABEL[match.status] ?? match.status}
                        </span>
                        <span className="text-xs text-text-muted whitespace-nowrap">
                          {formatDate(match.created_at)}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
