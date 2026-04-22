'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';
import { StatCard } from '@/components/admin/StatCard';
import { DataTable } from '@/components/admin/DataTable';
import { SkeletonStat } from '@/components/ui/Skeleton';
import { Users, Sword, Trophy, UserPlus, X } from 'lucide-react';

type MonitoringStats = {
  totals?: { users?: number; agents?: number; matches?: number };
  weekly?: { new_users?: number };
};

type LogEntry = {
  id: string;
  user_id: string;
  user_nickname: string;
  session_id: string | null;
  llm_model_id: string | null;
  model_name: string | null;
  model_provider: string | null;
  match_id: string | null;
  topic_title: string | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost: number;
  created_at: string;
};

type LogDetail = {
  id: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost: number;
  created_at: string;
  session_id: string | null;
  match_id: string | null;
  topic_title: string | null;
};

export default function AdminMonitoringPage() {
  const [stats, setStats] = useState<MonitoringStats | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [statsLoading, setStatsLoading] = useState(true);
  const [logsLoading, setLogsLoading] = useState(true);
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null);
  const [logDetail, setLogDetail] = useState<LogDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchData = useCallback(() => {
    api
      .get<MonitoringStats>('/admin/monitoring/stats')
      .then(setStats)
      .catch(() => {})
      .finally(() => setStatsLoading(false));
    api
      .get<{ logs: LogEntry[]; period_days: number; total_returned: number }>(
        '/admin/monitoring/logs?limit=50',
      )
      .then((res) => setLogs(res.logs ?? []))
      .catch(() => {})
      .finally(() => setLogsLoading(false));
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRowClick = useCallback(async (row: LogEntry) => {
    setSelectedLog(row);
    setLogDetail(null);
    setDetailLoading(true);
    try {
      const detail = await api.get<LogDetail>(`/admin/monitoring/logs/${row.id}`);
      setLogDetail(detail);
    } catch {
      // 상세 로드 실패 시 기본 정보만 표시
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const closeModal = () => {
    setSelectedLog(null);
    setLogDetail(null);
  };

  const columns = [
    {
      key: 'created_at' as const,
      label: '시간',
      render: (val: unknown) => new Date(String(val)).toLocaleString('ko-KR'),
    },
    { key: 'user_nickname' as const, label: '사용자' },
    {
      key: 'topic_title' as const,
      label: '토론 주제',
      render: (val: unknown) =>
        val ? (
          <span className="text-xs font-medium truncate max-w-[140px] inline-block" title={String(val)}>
            {String(val)}
          </span>
        ) : (
          <span className="text-text-muted text-xs">—</span>
        ),
    },
    {
      key: 'model_name' as const,
      label: '모델',
      render: (val: unknown, row: LogEntry) =>
        val ? (
          <span className="text-xs">
            <span className="font-medium">{String(val)}</span>
            <span className="text-text-muted ml-1">({row.model_provider})</span>
          </span>
        ) : (
          <span className="text-text-muted">-</span>
        ),
    },
    {
      key: 'total_tokens' as const,
      label: '총 토큰',
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
      <h1 className="page-title">모니터링</h1>

      {statsLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonStat key={i} />
          ))}
        </div>
      ) : stats ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatCard
            title="전체 사용자"
            value={stats.totals?.users ?? '-'}
            icon={<Users className="w-5 h-5" />}
          />
          <StatCard
            title="이번 주 신규"
            value={stats.weekly?.new_users ?? '-'}
            icon={<UserPlus className="w-5 h-5" />}
          />
          <StatCard
            title="에이전트 수"
            value={stats.totals?.agents ?? '-'}
            icon={<Sword className="w-5 h-5" />}
          />
          <StatCard
            title="매치 수"
            value={stats.totals?.matches ?? '-'}
            icon={<Trophy className="w-5 h-5" />}
          />
        </div>
      ) : null}

      <section className="mb-6">
        <h2 className="section-title">최근 LLM 호출 로그</h2>
        <div className="card">
          <DataTable
            columns={columns}
            data={logs}
            loading={logsLoading}
            onRowClick={(row) => handleRowClick(row as LogEntry)}
          />
        </div>
      </section>

      {selectedLog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={closeModal}
        >
          <div
            className="bg-bg-surface rounded-2xl shadow-lg w-full max-w-xl mx-4 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b border-border">
              <h3 className="text-base font-bold text-text">호출 상세</h3>
              <button
                onClick={closeModal}
                className="p-1 rounded-lg bg-transparent border-none text-text-muted hover:text-text hover:bg-bg-hover cursor-pointer transition-colors"
              >
                <X size={18} />
              </button>
            </div>
            <div className="p-5 flex flex-col gap-3">
              <DetailRow
                label="시간"
                value={new Date(selectedLog.created_at).toLocaleString('ko-KR')}
              />
              <DetailRow label="사용자" value={selectedLog.user_nickname} />
              <DetailRow
                label="모델"
                value={
                  selectedLog.model_name
                    ? `${selectedLog.model_name} (${selectedLog.model_provider})`
                    : '-'
                }
              />
              {(selectedLog.topic_title || logDetail?.topic_title) && (
                <DetailRow
                  label="토론 주제"
                  value={logDetail?.topic_title ?? selectedLog.topic_title ?? '-'}
                />
              )}

              <div className="border-t border-border my-1" />

              {detailLoading ? (
                <div className="grid grid-cols-3 gap-3">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="h-16 rounded-xl bg-bg-hover animate-pulse" />
                  ))}
                </div>
              ) : (
                <div className="grid grid-cols-3 gap-3">
                  <TokenBox
                    label="입력 토큰"
                    value={logDetail?.input_tokens ?? selectedLog.input_tokens}
                    color="text-blue-400"
                  />
                  <TokenBox
                    label="출력 토큰"
                    value={logDetail?.output_tokens ?? selectedLog.output_tokens}
                    color="text-green-400"
                  />
                  <TokenBox
                    label="총 토큰"
                    value={logDetail?.total_tokens ?? selectedLog.total_tokens}
                    color="text-primary"
                  />
                </div>
              )}

              <div className="border-t border-border my-1" />

              <DetailRow label="비용" value={`$${selectedLog.cost.toFixed(6)}`} highlight />

              {selectedLog.session_id && (
                <DetailRow label="세션 ID" value={selectedLog.session_id} mono />
              )}
              <DetailRow label="로그 ID" value={String(selectedLog.id)} mono />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DetailRow({
  label,
  value,
  highlight,
  mono,
}: {
  label: string;
  value: string;
  highlight?: boolean;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-text-muted font-medium">{label}</span>
      <span
        className={`text-sm ${highlight ? 'font-bold text-primary' : 'text-text'} ${mono ? 'font-mono text-xs' : ''}`}
      >
        {value}
      </span>
    </div>
  );
}

function TokenBox({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-bg-hover rounded-xl p-3 text-center">
      <div className="text-[11px] text-text-muted mb-1">{label}</div>
      <div className={`text-lg font-bold ${color}`}>{value.toLocaleString()}</div>
    </div>
  );
}
