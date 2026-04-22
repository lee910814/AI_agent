import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock debateStore
const mockFetchTurns = vi.fn();
const mockAddTurnFromSSE = vi.fn();
const mockSetStreaming = vi.fn();

// useDebateStore를 선택자 함수(selector) 방식으로 호출하므로 mock도 이를 지원
const mockStoreState = {
  turns: [] as unknown[],
  streamingTurn: null,
  turnReviews: [] as unknown[],
  streaming: false,
  replayMode: false,
  replayIndex: -1,
  replaySpeed: 1,
  replayPlaying: false,
  replayTyping: false,
  debateShowAll: false,
  nextSpeaker: null,
  predictionStats: null,
  predictionLoading: false,
  fetchTurns: mockFetchTurns,
  fetchMatch: vi.fn(),
  addTurnFromSSE: mockAddTurnFromSSE,
  appendChunk: vi.fn(),
  clearStreamingTurn: vi.fn(),
  setStreaming: mockSetStreaming,
  addTurnReview: vi.fn(),
  setReplayTyping: vi.fn(),
  setDebateShowAll: vi.fn(),
  startReplay: vi.fn(),
  stopReplay: vi.fn(),
  submitPrediction: vi.fn(),
  fetchPredictionStats: vi.fn(),
  flushPendingTurn: vi.fn(),
  tickReplay: vi.fn(),
};

vi.mock('@/stores/debateStore', () => ({
  useDebateStore: vi.fn((selector?: (s: typeof mockStoreState) => unknown) => {
    if (typeof selector === 'function') return selector(mockStoreState);
    return mockStoreState;
  }),
}));

vi.mock('./TurnBubble', () => ({
  TurnBubble: ({ turn }: { turn: { claim: string } }) => <div data-testid="turn">{turn.claim}</div>,
}));

vi.mock('./StreamingTurnBubble', () => ({
  StreamingTurnBubble: () => <div data-testid="streaming-turn" />,
}));

vi.mock('./ReplayControls', () => ({
  ReplayControls: () => <div data-testid="replay-controls" />,
}));

vi.mock('./LiveBadge', () => ({
  LiveBadge: () => <div data-testid="live-badge" />,
}));

vi.mock('@/components/ui/Skeleton', () => ({
  SkeletonCard: () => <div data-testid="skeleton" />,
}));

vi.mock('@/components/ui/ScrollToTop', () => ({
  ScrollToTop: () => null,
}));

vi.mock('@/lib/api', () => ({
  api: { get: vi.fn().mockResolvedValue({ count: 0 }) },
}));

vi.mock('@/hooks/useDebateStream', () => ({
  useDebateStream: vi.fn().mockReturnValue({ connected: false, error: null }),
}));

vi.mock('@/hooks/useDebateReplay', () => ({
  useDebateReplay: vi.fn(),
}));

// jsdom에 scrollIntoView가 없으므로 mock
Element.prototype.scrollIntoView = vi.fn();

import { DebateViewer } from './DebateViewer';

const baseMatch = {
  id: 'match-1',
  topic_id: 'topic-1',
  topic_title: 'Test Topic',
  agent_a: { id: 'a1', name: 'Agent A', provider: 'openai', model_id: 'gpt-4o', elo_rating: 1500 },
  agent_b: {
    id: 'a2',
    name: 'Agent B',
    provider: 'anthropic',
    model_id: 'claude',
    elo_rating: 1500,
  },
  status: 'completed' as const,
  winner_id: null,
  score_a: 50,
  score_b: 50,
  penalty_a: 0,
  penalty_b: 0,
  started_at: '2026-01-01',
  finished_at: '2026-01-01',
  created_at: '2026-01-01',
};

describe('DebateViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should show waiting_agent message', () => {
    const match = { ...baseMatch, status: 'waiting_agent' as const };
    render(<DebateViewer match={match} />);
    expect(screen.getByText(/로컬 에이전트 접속 대기 중/)).toBeInTheDocument();
  });

  it('should show forfeit message', () => {
    const match = { ...baseMatch, status: 'forfeit' as const };
    render(<DebateViewer match={match} />);
    expect(screen.getByText(/에이전트 미접속 — 몰수패/)).toBeInTheDocument();
  });

  it('should not show waiting message for completed match', () => {
    render(<DebateViewer match={baseMatch} />);
    expect(screen.queryByText(/로컬 에이전트 접속 대기 중/)).not.toBeInTheDocument();
    expect(screen.queryByText(/몰수패/)).not.toBeInTheDocument();
  });

  it('should call fetchTurns on mount', () => {
    render(<DebateViewer match={baseMatch} />);
    expect(mockFetchTurns).toHaveBeenCalledWith('match-1');
  });

  it('should show waiting_agent with pulse animation', () => {
    const match = { ...baseMatch, status: 'waiting_agent' as const };
    const { container } = render(<DebateViewer match={match} />);
    const pulseEl = container.querySelector('.animate-pulse');
    expect(pulseEl).not.toBeNull();
  });

  it('should show forfeit with red styling', () => {
    const match = { ...baseMatch, status: 'forfeit' as const };
    const { container } = render(<DebateViewer match={match} />);
    const redEl = container.querySelector('.text-red-600');
    expect(redEl).not.toBeNull();
  });
});
