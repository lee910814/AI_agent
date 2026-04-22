'use client';

import { Play, Pause, Square } from 'lucide-react';
import { useDebateStore } from '@/stores/debateStore';

export function ReplayControls() {
  const replayMode = useDebateStore((s) => s.replayMode);
  const replayIndex = useDebateStore((s) => s.replayIndex);
  const replaySpeed = useDebateStore((s) => s.replaySpeed);
  const replayPlaying = useDebateStore((s) => s.replayPlaying);
  const turns = useDebateStore((s) => s.turns);
  const startReplay = useDebateStore((s) => s.startReplay);
  const stopReplay = useDebateStore((s) => s.stopReplay);
  const setReplaySpeed = useDebateStore((s) => s.setReplaySpeed);
  // interval은 useDebateReplay 훅이 단일 관리 — 여기서 직접 tickReplay를 호출하지 않음

  if (!replayMode) return null;

  const totalTurns = turns.length;
  const atEnd = replayIndex >= totalTurns - 1;

  const handlePlayPause = () => {
    if (replayPlaying) {
      useDebateStore.setState({ replayPlaying: false });
    } else if (atEnd) {
      startReplay();
    } else {
      useDebateStore.setState({ replayPlaying: true });
    }
  };

  return (
    <div className="flex items-center gap-3 bg-bg-surface border border-border rounded-xl px-4 py-2 mb-4">
      {/* 재생/일시정지 버튼 */}
      <button
        type="button"
        onClick={handlePlayPause}
        className="w-8 h-8 flex items-center justify-center rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
        aria-label={replayPlaying ? '일시정지' : '재생'}
      >
        {replayPlaying ? <Pause size={15} /> : <Play size={15} />}
      </button>

      {/* 정지/종료 버튼 */}
      <button
        type="button"
        onClick={stopReplay}
        className="w-8 h-8 flex items-center justify-center rounded-lg bg-border/50 text-text-muted hover:text-text hover:bg-border transition-colors"
        aria-label="리플레이 종료"
      >
        <Square size={14} />
      </button>

      {/* 진행 바 + 턴 카운터 */}
      <div className="flex-1 flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-bg rounded-full overflow-hidden">
          <div
            className="h-full bg-primary rounded-full transition-all duration-300"
            style={{ width: totalTurns > 0 ? `${((replayIndex + 1) / totalTurns) * 100}%` : '0%' }}
          />
        </div>
        <span className="text-xs text-text-muted font-mono shrink-0">
          {replayIndex + 1} / {totalTurns}턴
        </span>
      </div>

      {/* 속도 선택 */}
      <div className="flex items-center gap-1">
        {([0.5, 1, 2] as const).map((speed) => (
          <button
            key={speed}
            type="button"
            onClick={() => setReplaySpeed(speed)}
            className={`px-2 py-0.5 rounded text-xs font-semibold transition-colors ${
              replaySpeed === speed
                ? 'bg-primary text-white'
                : 'bg-transparent text-text-muted hover:text-text'
            }`}
          >
            {speed}x
          </button>
        ))}
      </div>
    </div>
  );
}
