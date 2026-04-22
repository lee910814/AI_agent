'use client';

import { useEffect, useRef } from 'react';
import { useDebateStore } from '@/stores/debateStore';

/**
 * 리플레이 재생 interval을 관리한다.
 * replayPlaying=true일 때 replaySpeed에 비례한 간격으로 tickReplay를 호출한다.
 * 언마운트 시 interval을 해제한다.
 */
export function useDebateReplay(): void {
  const replayPlaying = useDebateStore((s) => s.replayPlaying);
  const replaySpeed = useDebateStore((s) => s.replaySpeed);
  const tickReplay = useDebateStore((s) => s.tickReplay);

  const tickReplayRef = useRef(tickReplay);
  tickReplayRef.current = tickReplay;

  useEffect(() => {
    if (!replayPlaying) return;

    // replaySpeed에 반비례: 1x → 1500ms, 2x → 750ms, 0.5x → 3000ms
    const intervalMs = Math.round(1500 / replaySpeed);
    const id = setInterval(() => {
      tickReplayRef.current();
    }, intervalMs);

    return () => {
      clearInterval(id);
    };
  }, [replayPlaying, replaySpeed]);
}
