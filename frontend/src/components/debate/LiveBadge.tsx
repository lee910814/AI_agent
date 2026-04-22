'use client';

type Props = { count: number; className?: string };

export function LiveBadge({ count, className = '' }: Props) {
  return (
    <div
      className={`flex items-center gap-1.5 bg-red-500/20 text-red-400 rounded-full px-2.5 py-0.5 text-xs font-semibold ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
      LIVE {count.toLocaleString()}명 관전
    </div>
  );
}
