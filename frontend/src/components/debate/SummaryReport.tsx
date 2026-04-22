'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import {
  Loader2,
  FileText,
  Trophy,
  AlertTriangle,
  Zap,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

type SummaryData = {
  status: 'ready' | 'generating' | 'unavailable';
  agent_a_arguments?: string[];
  agent_b_arguments?: string[];
  turning_points?: string[];
  rule_violations?: string[];
  overall_summary?: string;
  generated_at?: string;
  model_used?: string;
  input_tokens?: number;
  output_tokens?: number;
};

type Props = {
  matchId: string;
  agentAName?: string;
  agentBName?: string;
};

function Section({
  title,
  icon,
  children,
  defaultOpen = true,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-border rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-bg-surface hover:bg-bg-hover transition-colors cursor-pointer border-none text-left"
      >
        <span className="flex items-center gap-2 text-xs font-bold text-text-muted uppercase tracking-wider">
          {icon}
          {title}
        </span>
        {open ? (
          <ChevronUp size={14} className="text-text-muted" />
        ) : (
          <ChevronDown size={14} className="text-text-muted" />
        )}
      </button>
      {open && <div className="px-4 py-3 bg-bg">{children}</div>}
    </div>
  );
}

function ArgList({ items, color }: { items: string[]; color: 'blue' | 'orange' }) {
  const dot = color === 'blue' ? 'bg-blue-400' : 'bg-orange-400';
  const empty = color === 'blue' ? 'text-blue-400' : 'text-orange-400';
  return (
    <ul className="space-y-2">
      {items.map((arg, i) => (
        <li key={i} className="flex gap-2.5 text-sm text-text leading-relaxed">
          <span className={`mt-1.5 w-1.5 h-1.5 rounded-full ${dot} shrink-0`} />
          <span>{arg}</span>
        </li>
      ))}
      {items.length === 0 && (
        <li className={`text-xs ${empty} opacity-60`}>기록된 논거가 없습니다.</li>
      )}
    </ul>
  );
}

export function SummaryReport({ matchId, agentAName = 'Agent A', agentBName = 'Agent B' }: Props) {
  const [data, setData] = useState<SummaryData | null>(null);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    const fetchSummary = async () => {
      try {
        const result = await api.get<SummaryData>(`/matches/${matchId}/summary`);
        setData(result);
        if (result.status === 'ready' || result.status === 'unavailable') {
          if (interval) clearInterval(interval);
        }
      } catch {
        /* ignore */
      }
    };
    fetchSummary();
    interval = setInterval(fetchSummary, 5000);
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [matchId]);

  if (!data) return null;
  if (data.status === 'unavailable') return null;

  if (data.status === 'generating') {
    return (
      <div className="mt-6 bg-bg-surface border border-border rounded-2xl p-6">
        <div className="flex items-center gap-3 text-text-muted">
          <Loader2 size={18} className="animate-spin text-primary" />
          <div>
            <p className="text-sm font-semibold text-text">AI 토론 분석 중...</p>
            <p className="text-xs text-text-muted mt-0.5">요약 리포트를 생성하고 있습니다.</p>
          </div>
        </div>
      </div>
    );
  }

  const argA = data.agent_a_arguments ?? [];
  const argB = data.agent_b_arguments ?? [];
  const turningPoints = data.turning_points ?? [];
  const violations = data.rule_violations ?? [];
  const totalTokens = (data.input_tokens ?? 0) + (data.output_tokens ?? 0);

  return (
    <div className="mt-6 space-y-3">
      {/* 헤더 */}
      <div className="flex items-center gap-2 px-1">
        <FileText size={16} className="text-primary" />
        <h3 className="text-sm font-bold text-text">AI 토론 요약 리포트</h3>
        {data.model_used && (
          <span className="ml-auto text-[10px] text-text-muted bg-bg-surface border border-border px-2 py-0.5 rounded-full">
            {data.model_used}
          </span>
        )}
      </div>

      {/* 전체 총평 */}
      {data.overall_summary && (
        <div className="bg-primary/5 border border-primary/20 rounded-xl px-4 py-3">
          <p className="text-sm text-text leading-relaxed">{data.overall_summary}</p>
        </div>
      )}

      {/* 에이전트별 핵심 논거 비교 */}
      <Section
        title="에이전트별 핵심 논거"
        icon={<span className="text-base leading-none">🧠</span>}
      >
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-[11px] font-black text-blue-400 mb-2 truncate">{agentAName}</p>
            <ArgList items={argA} color="blue" />
          </div>
          <div>
            <p className="text-[11px] font-black text-orange-400 mb-2 truncate">{agentBName}</p>
            <ArgList items={argB} color="orange" />
          </div>
        </div>
      </Section>

      {/* 승부 전환점 */}
      {turningPoints.length > 0 && (
        <Section title="승부 전환점" icon={<Trophy size={12} className="text-yellow-400" />}>
          <ul className="space-y-2">
            {turningPoints.map((point, i) => (
              <li key={i} className="flex gap-2.5 text-sm text-text leading-relaxed">
                <span className="mt-0.5 text-yellow-400 font-black shrink-0 tabular-nums">
                  {i + 1}.
                </span>
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* 규칙 위반 */}
      {violations.length > 0 && (
        <Section
          title={`규칙 위반 (${violations.length}건)`}
          icon={<AlertTriangle size={12} className="text-red-400" />}
          defaultOpen={false}
        >
          <ul className="space-y-1.5">
            {violations.map((v, i) => (
              <li key={i} className="text-xs text-red-400/80 leading-relaxed flex gap-2">
                <span className="shrink-0 font-bold">!</span>
                <span>{v}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* 푸터 */}
      {totalTokens > 0 && (
        <div className="flex items-center gap-1.5 px-1 text-[10px] text-text-muted">
          <Zap size={10} />
          <span>
            분석 토큰 {totalTokens.toLocaleString()}
            {data.input_tokens !== undefined &&
              ` (입력 ${data.input_tokens.toLocaleString()} / 출력 ${(data.output_tokens ?? 0).toLocaleString()})`}
          </span>
        </div>
      )}
    </div>
  );
}
