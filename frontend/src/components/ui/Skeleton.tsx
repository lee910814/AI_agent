/** 로딩 스켈레톤 UI 모음. SkeletonCard, SkeletonTable 등. */
export function SkeletonCard() {
  return (
    <div className="card animate-pulse">
      <div className="h-[140px] rounded-lg bg-bg-hover mb-3" />
      <div className="h-4 w-2/3 rounded bg-bg-hover mb-2" />
      <div className="h-3 w-full rounded bg-bg-hover mb-1" />
      <div className="h-3 w-4/5 rounded bg-bg-hover" />
    </div>
  );
}

export function SkeletonTable({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="animate-pulse">
      <div className="flex gap-4 mb-3 pb-3 border-b border-border">
        {Array.from({ length: cols }).map((_, i) => (
          <div key={i} className="h-3 rounded bg-bg-hover flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-4 py-3 border-b border-border/50">
          {Array.from({ length: cols }).map((_, c) => (
            <div key={c} className="h-3 rounded bg-bg-hover flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function SkeletonStat() {
  return (
    <div className="card animate-pulse">
      <div className="h-3 w-1/2 rounded bg-bg-hover mb-3" />
      <div className="h-7 w-1/3 rounded bg-bg-hover" />
    </div>
  );
}
