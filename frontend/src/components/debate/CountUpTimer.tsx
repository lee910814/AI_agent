'use client';

import { useEffect, useState } from 'react';

type Props = {
  startedAt: Date;
  maxSeconds?: number;
};

export function CountUpTimer({ startedAt, maxSeconds = 120 }: Props) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const initial = Math.floor((Date.now() - startedAt.getTime()) / 1000);
    setElapsed(Math.max(0, initial));

    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt.getTime()) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [startedAt]);

  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const timeStr = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  const progress = Math.min((elapsed / maxSeconds) * 100, 100);

  // 색상: 0~60s 초록, 60~90s 노랑, 90~120s 빨강
  const barColor = elapsed < 60 ? 'bg-green-500' : elapsed < 90 ? 'bg-yellow-500' : 'bg-red-500';

  const textColor =
    elapsed < 60 ? 'text-green-400' : elapsed < 90 ? 'text-yellow-400' : 'text-red-400';

  return (
    <div className="flex flex-col items-center gap-2 w-full max-w-[200px]">
      <span className={`text-3xl font-mono font-bold tabular-nums ${textColor}`}>{timeStr}</span>
      <div className="w-full h-1.5 bg-bg-hover rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-1000 ${barColor}`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
