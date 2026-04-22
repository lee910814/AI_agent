'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { Calendar, Clock } from 'lucide-react';

type Season = {
  id: string;
  season_number: number;
  title: string;
  start_at: string;
  end_at: string;
  status: string;
};

export function SeasonBanner() {
  const [season, setSeason] = useState<Season | null>(null);

  useEffect(() => {
    api
      .get<{ season: Season | null }>('/agents/season/current')
      .then((data) => setSeason(data.season))
      .catch(() => {});
  }, []);

  if (!season) return null;

  const isUpcoming = season.status === 'upcoming';
  const startDate = new Date(season.start_at);
  const endDate = new Date(season.end_at);
  const daysLeft = Math.max(0, Math.ceil((endDate.getTime() - Date.now()) / 86400000));
  const daysUntilStart = Math.max(0, Math.ceil((startDate.getTime() - Date.now()) / 86400000));

  return (
    <Link
      href={`/debate/seasons/${season.id}`}
      className={`flex items-center gap-3 border rounded-xl px-4 py-3 mb-4 transition-colors ${
        isUpcoming
          ? 'bg-blue-500/10 border-blue-500/30 hover:bg-blue-500/15'
          : 'bg-primary/10 border-primary/30 hover:bg-primary/15'
      }`}
    >
      {isUpcoming ? (
        <Clock size={16} className="text-blue-400 shrink-0" />
      ) : (
        <Calendar size={16} className="text-primary shrink-0" />
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-text">
          시즌 {season.season_number}: {season.title}
        </div>
        <div className="text-xs text-text-muted">
          {isUpcoming
            ? `${daysUntilStart}일 후 시작 · ${startDate.toLocaleDateString('ko-KR')}`
            : `종료까지 ${daysLeft}일 남음 · ${endDate.toLocaleDateString('ko-KR')}`}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {isUpcoming && (
          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400">
            예정
          </span>
        )}
        <span className={`text-xs ${isUpcoming ? 'text-blue-400' : 'text-primary'}`}>
          순위 보기 →
        </span>
      </div>
    </Link>
  );
}
