/** 토큰 사용량 차트. Recharts BarChart로 일별 사용량 추이를 시각화. */
'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

type Props = {
  data: Array<{ date: string; cost: number; tokens: number }>;
};

export function UsageChart({ data }: Props) {
  if (data.length === 0) {
    return <div className="empty-state">사용량 데이터가 없습니다</div>;
  }

  return (
    <div className="card">
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333333" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12, fill: '#9e9e9e' }}
            tickFormatter={(v: string) => v.slice(5)}
          />
          <YAxis
            yAxisId="tokens"
            orientation="left"
            tick={{ fontSize: 12, fill: '#9e9e9e' }}
            tickFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v))}
          />
          <YAxis
            yAxisId="cost"
            orientation="right"
            tick={{ fontSize: 12, fill: '#9e9e9e' }}
            tickFormatter={(v: number) => `$${v.toFixed(3)}`}
          />
          <Tooltip
            contentStyle={{ backgroundColor: '#262626', border: '1px solid #333', borderRadius: 8 }}
            labelStyle={{ color: '#e0e0e0' }}
            itemStyle={{ color: '#e0e0e0' }}
          />
          <Legend wrapperStyle={{ color: '#9e9e9e' }} />
          <Bar yAxisId="tokens" dataKey="tokens" fill="#e91e63" radius={[4, 4, 0, 0]} name="토큰" />
          <Bar yAxisId="cost" dataKey="cost" fill="#ff9800" radius={[4, 4, 0, 0]} name="비용($)" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
