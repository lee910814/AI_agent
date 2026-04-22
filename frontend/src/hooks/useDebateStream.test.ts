import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// fetch mock — SSE 연결 시도를 가로챔
const mockFetch = vi.fn();
global.fetch = mockFetch;

// debateStore mock
const mockStoreActions = {
  fetchTurns: vi.fn(),
  fetchPredictionStats: vi.fn(),
  fetchMatch: vi.fn(),
  addTurnFromSSE: vi.fn(),
  appendChunk: vi.fn(),
  clearStreamingTurn: vi.fn(),
  setStreaming: vi.fn(),
  addTurnReview: vi.fn(),
  setDebateShowAll: vi.fn(),
  setJudgeIntro: vi.fn(),
};

vi.mock('@/stores/debateStore', () => ({
  // getState()는 정적 메서드로 추가 — getState() 패턴으로 변경된 useDebateStream에서 사용
  useDebateStore: Object.assign(
    vi.fn((selector?: (s: typeof mockStoreActions) => unknown) => {
      if (typeof selector === 'function') return selector(mockStoreActions);
      return mockStoreActions;
    }),
    { getState: () => mockStoreActions },
  ),
}));

import { useDebateStream } from './useDebateStream';

describe('useDebateStream', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // localStorage.getItem mock
    vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
  });

  it('훅이 export되어 있다', async () => {
    const mod = await import('./useDebateStream');
    expect(typeof mod.useDebateStream).toBe('function');
  });

  it('matchId가 null이면 SSE 연결을 시도하지 않는다', () => {
    const { result } = renderHook(() => useDebateStream(null, undefined));
    expect(result.current.connected).toBe(false);
    expect(result.current.error).toBeNull();
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('status가 in_progress가 아니면 SSE 연결을 시도하지 않는다', () => {
    const { result } = renderHook(() => useDebateStream('match-1', 'completed'));
    expect(result.current.connected).toBe(false);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('status가 undefined이면 SSE 연결을 시도하지 않는다', () => {
    const { result } = renderHook(() => useDebateStream('match-1', undefined));
    expect(result.current.connected).toBe(false);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('status=in_progress이면 fetch를 호출한다', async () => {
    // fetch가 절대 resolve되지 않는 pending Promise 반환 → 연결 중 상태 유지
    mockFetch.mockReturnValue(new Promise(() => {}));

    renderHook(() => useDebateStream('match-1', 'in_progress'));

    // fetch 호출은 비동기이므로 짧게 기다림
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/matches/match-1/stream',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it('언마운트 시 AbortController를 통해 연결을 취소한다', async () => {
    mockFetch.mockReturnValue(new Promise(() => {}));

    const { unmount } = renderHook(() => useDebateStream('match-1', 'in_progress'));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });

    // 언마운트 시 abort 신호를 통한 연결 취소 — fetch의 signal이 aborted 상태가 됨
    let signal: AbortSignal | undefined;
    if (mockFetch.mock.calls.length > 0) {
      signal = mockFetch.mock.calls[0][1]?.signal as AbortSignal;
    }

    unmount();

    if (signal) {
      expect(signal.aborted).toBe(true);
    }
  });

  it('connected와 error를 반환한다', () => {
    const { result } = renderHook(() => useDebateStream(null, undefined));
    expect('connected' in result.current).toBe(true);
    expect('error' in result.current).toBe(true);
  });
});
