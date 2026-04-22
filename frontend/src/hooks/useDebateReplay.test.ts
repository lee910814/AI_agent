import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// debateStore mock — replayPlaying=false가 기본값
const mockState = {
  replayPlaying: false,
  replaySpeed: 1,
  replayTyping: false,
  tickReplay: vi.fn(),
};

vi.mock('@/stores/debateStore', () => ({
  useDebateStore: vi.fn((selector?: (s: typeof mockState) => unknown) => {
    if (typeof selector === 'function') return selector(mockState);
    return mockState;
  }),
}));

import { useDebateReplay } from './useDebateReplay';

describe('useDebateReplay', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('훅이 export되어 있다', async () => {
    const mod = await import('./useDebateReplay');
    expect(typeof mod.useDebateReplay).toBe('function');
  });

  it('에러 없이 마운트된다', () => {
    expect(() => renderHook(() => useDebateReplay())).not.toThrow();
  });

  it('replayPlaying=false이면 interval을 등록하지 않는다', () => {
    mockState.replayPlaying = false;
    const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');

    renderHook(() => useDebateReplay());

    expect(setIntervalSpy).not.toHaveBeenCalled();
  });

  it('replayPlaying=true이면 interval을 등록한다', () => {
    mockState.replayPlaying = true;
    const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');

    renderHook(() => useDebateReplay());

    expect(setIntervalSpy).toHaveBeenCalled();
  });

  it('replayPlaying=true이면 interval이 지날 때 tickReplay를 호출한다', () => {
    mockState.replayPlaying = true;
    mockState.replaySpeed = 1;
    mockState.replayTyping = false;

    renderHook(() => useDebateReplay());

    // 1x 속도: 1500ms interval
    act(() => {
      vi.advanceTimersByTime(1600);
    });

    expect(mockState.tickReplay).toHaveBeenCalled();
  });

  it('언마운트 시 interval이 해제된다', () => {
    mockState.replayPlaying = true;
    const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');

    const { unmount } = renderHook(() => useDebateReplay());
    unmount();

    expect(clearIntervalSpy).toHaveBeenCalled();
  });
});
