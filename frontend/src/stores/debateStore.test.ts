import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useDebateStore } from './debateStore';

// api 모듈 mock
vi.mock('@/lib/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { api } from '@/lib/api';

describe('debateStore', () => {
  beforeEach(() => {
    // 상태 초기화
    useDebateStore.setState({
      topics: [],
      topicsTotal: 0,
      popularTopics: [],
      popularTopicsTotal: 0,
      currentMatch: null,
      turns: [],
      ranking: [],
      topicsLoading: false,
      matchLoading: false,
      rankingLoading: false,
      streaming: false,
    });
    vi.clearAllMocks();
  });

  it('fetchTopics should update topics state', async () => {
    const mockTopics = {
      items: [
        {
          id: '1',
          title: 'Test Topic',
          description: null,
          mode: 'debate',
          status: 'open',
          max_turns: 6,
          turn_token_limit: 500,
          queue_count: 0,
          match_count: 0,
          created_at: '2026-01-01',
          updated_at: '2026-01-01',
        },
      ],
      total: 1,
    };

    vi.mocked(api.get).mockResolvedValueOnce(mockTopics);

    await useDebateStore.getState().fetchTopics();

    const state = useDebateStore.getState();
    expect(state.topics).toHaveLength(1);
    expect(state.topics[0].title).toBe('Test Topic');
    expect(state.topicsTotal).toBe(1);
    expect(state.topicsLoading).toBe(false);
  });

  it('fetchTopics with status filter should pass query param', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ items: [], total: 0 });

    await useDebateStore.getState().fetchTopics({ status: 'open' });

    expect(api.get).toHaveBeenCalledWith('/topics?status=open&page=1&page_size=20');
  });

  it('fetchTopics page=1 should replace topics (not append)', async () => {
    // 기존 항목 세팅
    useDebateStore.setState({ topics: [{ id: 'old', title: 'Old' } as never], topicsTotal: 1 });

    const newItems = { items: [{ id: 'new', title: 'New' } as never], total: 1 };
    vi.mocked(api.get).mockResolvedValueOnce(newItems);

    await useDebateStore.getState().fetchTopics({ page: 1 });

    const state = useDebateStore.getState();
    expect(state.topics).toHaveLength(1);
    expect(state.topics[0].id).toBe('new');
  });

  it('fetchTopics page>1 should append to existing topics', async () => {
    // 1페이지 결과가 이미 로드된 상태
    useDebateStore.setState({
      topics: [{ id: 'page1-item', title: 'Page1' } as never],
      topicsTotal: 2,
    });

    const page2Items = { items: [{ id: 'page2-item', title: 'Page2' } as never], total: 2 };
    vi.mocked(api.get).mockResolvedValueOnce(page2Items);

    await useDebateStore.getState().fetchTopics({ page: 2 });

    const state = useDebateStore.getState();
    expect(state.topics).toHaveLength(2);
    expect(state.topics[0].id).toBe('page1-item');
    expect(state.topics[1].id).toBe('page2-item');
  });

  it('fetchRanking should update ranking state', async () => {
    const mockRanking = [
      {
        id: '1',
        name: 'Agent 1',
        owner_nickname: 'user1',
        provider: 'openai',
        model_id: 'gpt-4o',
        elo_rating: 1600,
        wins: 10,
        losses: 5,
        draws: 3,
      },
    ];

    vi.mocked(api.get).mockResolvedValueOnce({ items: mockRanking, total: 1 });

    await useDebateStore.getState().fetchRanking();

    const state = useDebateStore.getState();
    expect(state.ranking).toHaveLength(1);
    expect(state.ranking[0].elo_rating).toBe(1600);
  });

  it('addTurnFromSSE should append turn to turns array', () => {
    const turn = {
      id: 'turn-1',
      turn_number: 1,
      speaker: 'agent_a',
      agent_id: 'a1',
      action: 'argue',
      claim: 'Test claim',
      evidence: null,
      tool_used: null,
      tool_result: null,
      penalties: null,
      penalty_total: 0,
      input_tokens: 100,
      output_tokens: 50,
      human_suspicion_score: 0,
      response_time_ms: null,
      review_result: null,
      is_blocked: false,
      created_at: '2026-01-01',
    };

    useDebateStore.getState().addTurnFromSSE(turn);

    const state = useDebateStore.getState();
    expect(state.turns).toHaveLength(1);
    expect(state.turns[0].claim).toBe('Test claim');
  });

  it('setStreaming should update streaming flag', () => {
    useDebateStore.getState().setStreaming(true);
    expect(useDebateStore.getState().streaming).toBe(true);

    useDebateStore.getState().setStreaming(false);
    expect(useDebateStore.getState().streaming).toBe(false);
  });

  it('joinQueue should call API with correct params', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ status: 'queued', position: 1 });

    const result = await useDebateStore.getState().joinQueue('topic-1', 'agent-1');

    expect(api.post).toHaveBeenCalledWith('/topics/topic-1/join', { agent_id: 'agent-1' });
    expect(result.status).toBe('queued');
  });
});
