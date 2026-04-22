'use client';

import { useEffect, useState } from 'react';
import { Gem } from 'lucide-react';
import { api } from '@/lib/api';

type ModelUsage = {
  model_name: string;
  provider: string;
  tier: string;
  credit_per_1k_tokens: number;
  input_cost_per_1m: number;
  output_cost_per_1m: number;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  request_count: number;
  daily_input_tokens: number;
  daily_output_tokens: number;
  daily_cost: number;
  daily_request_count: number;
  monthly_input_tokens: number;
  monthly_output_tokens: number;
  monthly_cost: number;
  monthly_request_count: number;
};

type UsageSummary = {
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost: number;
  daily_input_tokens: number;
  daily_output_tokens: number;
  daily_cost: number;
  monthly_input_tokens: number;
  monthly_output_tokens: number;
  monthly_cost: number;
  by_model: ModelUsage[];
};

type Period = 'daily' | 'monthly' | 'total';

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function getModelInput(m: ModelUsage, p: Period) {
  if (p === 'daily') return m.daily_input_tokens ?? 0;
  if (p === 'monthly') return m.monthly_input_tokens ?? 0;
  return m.input_tokens ?? 0;
}

function getModelOutput(m: ModelUsage, p: Period) {
  if (p === 'daily') return m.daily_output_tokens ?? 0;
  if (p === 'monthly') return m.monthly_output_tokens ?? 0;
  return m.output_tokens ?? 0;
}

function getModelRequests(m: ModelUsage, p: Period) {
  if (p === 'daily') return m.daily_request_count ?? 0;
  if (p === 'monthly') return m.monthly_request_count ?? 0;
  return m.request_count ?? 0;
}

/** 토큰 수 → 석 변환: ceil(totalTokens * rate / 1000) */
function tokensToCredits(tokens: number, creditPer1k: number): number {
  return Math.ceil((tokens * creditPer1k) / 1000);
}

function getModelCredits(m: ModelUsage, period: Period): number {
  const tokens = getModelInput(m, period) + getModelOutput(m, period);
  return tokensToCredits(tokens, m.credit_per_1k_tokens ?? 0);
}

const PERIODS: { key: Period; label: string }[] = [
  { key: 'daily', label: '오늘' },
  { key: 'monthly', label: '이번 달' },
  { key: 'total', label: '전체' },
];

export default function UsagePage() {
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState<Period>('monthly');

  useEffect(() => {
    api
      .get<UsageSummary>('/usage/me')
      .then((s) => setSummary(s))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="max-w-[900px] mx-auto py-6 px-4">
        <h1 className="m-0 text-2xl text-text mb-6">사용량</h1>
        <div className="flex flex-col gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="card h-24 animate-pulse bg-bg-hover" />
          ))}
        </div>
      </div>
    );
  }

  const periodTotalTokens =
    period === 'daily'
      ? (summary?.daily_input_tokens ?? 0) + (summary?.daily_output_tokens ?? 0)
      : period === 'monthly'
        ? (summary?.monthly_input_tokens ?? 0) + (summary?.monthly_output_tokens ?? 0)
        : (summary?.total_input_tokens ?? 0) + (summary?.total_output_tokens ?? 0);

  const totalCredits = (summary?.by_model ?? []).reduce(
    (sum, m) => sum + getModelCredits(m, period),
    0,
  );

  return (
    <div className="max-w-[900px] mx-auto py-6 px-4">
      <h1 className="m-0 text-2xl text-text mb-6">사용량</h1>

      {/* 기간 선택 + 전체 요약 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-1 bg-bg-hover/50 rounded-lg p-1">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPeriod(p.key)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md border-none cursor-pointer transition-colors ${
                period === p.key
                  ? 'bg-primary text-white'
                  : 'bg-transparent text-text-muted hover:text-text'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        <div className="text-right">
          <div className="text-sm font-bold text-text tabular-nums">
            {formatTokens(periodTotalTokens)} 토큰
          </div>
          <div className="text-xs text-text-muted tabular-nums flex items-center justify-end gap-1">
            <Gem size={12} />
            {totalCredits.toLocaleString()}석
          </div>
        </div>
      </div>

      {/* 모델별 사용량 표 */}
      {summary && summary.by_model.length > 0 ? (
        <div className="card overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-text-muted text-xs">
                <th className="text-left py-3 px-4 font-medium">모델</th>
                <th className="text-right py-3 px-3 font-medium">호출</th>
                <th className="text-right py-3 px-3 font-medium">입력</th>
                <th className="text-right py-3 px-3 font-medium">출력</th>
                <th className="text-right py-3 px-4 font-medium">석</th>
              </tr>
            </thead>
            <tbody>
              {summary.by_model.map((m) => {
                const requests = getModelRequests(m, period);
                const credits = getModelCredits(m, period);

                return (
                  <tr key={m.model_name} className="border-b border-border/50 last:border-0">
                    <td className="py-3 px-4">
                      <div className="font-medium text-text">{m.model_name}</div>
                      <div className="text-[11px] text-text-muted">
                        {m.provider} &middot; {m.credit_per_1k_tokens ?? 0}석/1K토큰
                      </div>
                    </td>
                    <td className="text-right py-3 px-3 tabular-nums text-text">
                      {requests.toLocaleString()}
                    </td>
                    <td className="text-right py-3 px-3 tabular-nums text-text">
                      {formatTokens(getModelInput(m, period))}
                    </td>
                    <td className="text-right py-3 px-3 tabular-nums text-text">
                      {formatTokens(getModelOutput(m, period))}
                    </td>
                    <td className="text-right py-3 px-4 tabular-nums font-semibold text-text">
                      {credits.toLocaleString()}석
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="border-t border-border bg-bg-hover/30">
                <td className="py-3 px-4 font-semibold text-text">합계</td>
                <td className="text-right py-3 px-3 tabular-nums font-semibold text-text">
                  {summary.by_model
                    .reduce((sum, m) => sum + getModelRequests(m, period), 0)
                    .toLocaleString()}
                </td>
                <td className="text-right py-3 px-3 tabular-nums font-semibold text-text">
                  {formatTokens(
                    summary.by_model.reduce((sum, m) => sum + getModelInput(m, period), 0),
                  )}
                </td>
                <td className="text-right py-3 px-3 tabular-nums font-semibold text-text">
                  {formatTokens(
                    summary.by_model.reduce((sum, m) => sum + getModelOutput(m, period), 0),
                  )}
                </td>
                <td className="text-right py-3 px-4 tabular-nums font-bold text-text">
                  {totalCredits.toLocaleString()}석
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      ) : (
        <div className="card text-center py-12">
          <Gem size={40} className="mx-auto text-text-muted mb-3" />
          <p className="m-0 text-text-muted text-sm">아직 사용 기록이 없습니다</p>
          <p className="m-0 text-text-muted text-xs mt-1">
            챗봇과 대화하면 모델별 사용량이 여기에 표시됩니다
          </p>
        </div>
      )}
    </div>
  );
}
