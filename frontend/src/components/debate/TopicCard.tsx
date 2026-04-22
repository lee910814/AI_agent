'use client';

import Link from 'next/link';
import { Users, Shield, Lock } from 'lucide-react';
import type { DebateTopic } from '@/stores/debateStore';

type Props = {
  topic: DebateTopic;
  currentUserId?: string | null;
  onEdit?: (topic: DebateTopic) => void;
  onDelete?: (topicId: string) => void;
};

const STATUS_STYLES: Record<string, string> = {
  scheduled: 'bg-blue-500/10 text-blue-400',
  open: 'bg-green-500/10 text-green-500',
  in_progress: 'bg-yellow-500/10 text-yellow-500',
  closed: 'bg-text-muted/10 text-text-muted',
};

const STATUS_LABELS: Record<string, string> = {
  scheduled: '예정',
  open: '참가 가능',
  in_progress: '진행 중',
  closed: '종료',
};

const MODE_LABELS: Record<string, string> = {
  debate: '토론',
  persuasion: '설득',
  cross_exam: '교차 심문',
};

function formatScheduleTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString('ko-KR', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getEndCountdown(iso: string): string | null {
  const diff = new Date(iso).getTime() - Date.now();
  if (diff <= 0) return null;
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  if (h > 0) return `${h}시간 ${m}분 후 종료`;
  if (m > 0) return `${m}분 후 종료`;
  return '곧 종료';
}

export function TopicCard({ topic, currentUserId, onEdit, onDelete }: Props) {
  const isLive = topic.status === 'in_progress';
  const countdown = topic.scheduled_end_at ? getEndCountdown(topic.scheduled_end_at) : null;

  return (
    <Link
      href={`/debate/topics/${topic.id}`}
      className="group block p-4 bg-bg-surface border border-border rounded-xl hover:border-primary/40 hover:shadow-sm transition-all no-underline"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            {isLive ? (
              <span className="flex items-center gap-1 text-[10px] font-bold text-red-500 bg-red-500/10 px-2 py-0.5 rounded-full">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse inline-block" />
                LIVE
              </span>
            ) : (
              <span
                className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                  STATUS_STYLES[topic.status] || STATUS_STYLES.closed
                }`}
              >
                {STATUS_LABELS[topic.status] || topic.status}
              </span>
            )}
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-primary/10 text-primary">
              {MODE_LABELS[topic.mode] || topic.mode}
            </span>
            {topic.is_admin_topic && <Shield size={12} className="text-primary" />}
            {topic.is_password_protected && <Lock size={10} className="text-yellow-500" />}
          </div>

          <h3 className="text-base font-black text-black m-0 group-hover:text-primary transition-colors leading-snug line-clamp-2">
            {topic.title}
          </h3>
        </div>

        <div className="flex items-center justify-between sm:justify-end gap-4 shrink-0">
          <div className="flex items-center gap-3 text-[11px] font-bold text-gray-400">
            <span className="flex items-center gap-1">
              <Users size={12} />
              {topic.queue_count}
            </span>
            <span className="hidden xs:inline">{topic.creator_nickname}</span>
            {countdown && (topic.status === 'open' || topic.status === 'in_progress') && (
              <span className="text-orange-500 font-black">{countdown}</span>
            )}
          </div>

          <div className="flex items-center gap-1.5 border-l border-border pl-4">
            {currentUserId && topic.created_by === currentUserId && (
              <div className="flex gap-1 mr-1">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    onEdit?.(topic);
                  }}
                  className="text-[10px] text-text-muted hover:text-primary px-1.5 py-1 rounded transition-colors bg-transparent border-none cursor-pointer"
                >
                  수정
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    onDelete?.(topic.id);
                  }}
                  className="text-[10px] text-text-muted hover:text-red-400 px-1.5 py-1 rounded transition-colors bg-transparent border-none cursor-pointer"
                >
                  삭제
                </button>
              </div>
            )}
            <div className="px-4 py-1.5 bg-primary text-white text-[11px] font-black rounded-lg brutal-border brutal-shadow-sm group-hover:translate-y-[-1px] transition-all">
              참가
            </div>
          </div>
        </div>
      </div>

      {topic.is_admin_topic && (
        <div className="mt-2 pt-2 border-t border-border flex items-center gap-1 text-[10px] text-primary/70">
          <Shield size={10} />
          <span>플랫폼 공식 주제</span>
          {topic.scheduled_end_at && topic.status !== 'closed' && (
            <span className="ml-auto">{formatScheduleTime(topic.scheduled_end_at)} 까지</span>
          )}
        </div>
      )}
    </Link>
  );
}
