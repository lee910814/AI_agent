import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useDebateAgentStore } from './debateAgentStore';

vi.mock('@/lib/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import { api } from '@/lib/api';

/** 테스트용 에이전트 목 팩토리 */
function makeAgent(overrides: Record<string, unknown> = {}) {
  return {
    id: 'a1',
    owner_id: 'u1',
    name: 'Agent 1',
    description: null,
    provider: 'openai',
    model_id: 'gpt-4o',
    image_url: null,
    elo_rating: 1500,
    wins: 0,
    losses: 0,
    draws: 0,
    is_active: true,
    is_connected: false,
    is_system_prompt_public: false,
    use_platform_credits: false,
    tier: 'Iron',
    tier_protection_count: 0,
    active_series_id: null,
    is_profile_public: true,
    name_changed_at: null,
    template_id: null,
    customizations: null,
    follower_count: 0,
    is_following: false,
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
    ...overrides,
  };
}

describe('debateAgentStore', () => {
  beforeEach(() => {
    useDebateAgentStore.setState({ agents: [], loading: false });
    vi.clearAllMocks();
  });

  it('fetchMyAgents should update agents state', async () => {
    const mockAgents = [makeAgent({ name: 'Agent 1' })];

    vi.mocked(api.get).mockResolvedValueOnce(mockAgents);

    await useDebateAgentStore.getState().fetchMyAgents();

    const state = useDebateAgentStore.getState();
    expect(state.agents).toHaveLength(1);
    expect(state.agents[0].name).toBe('Agent 1');
    expect(state.loading).toBe(false);
  });

  it('createAgent should add agent to state', async () => {
    const newAgent = makeAgent({
      id: 'a2',
      name: 'New Agent',
      provider: 'anthropic',
      model_id: 'claude-sonnet-4-5-20250929',
    });

    vi.mocked(api.post).mockResolvedValueOnce(newAgent);

    const result = await useDebateAgentStore.getState().createAgent({
      name: 'New Agent',
      provider: 'anthropic',
      model_id: 'claude-sonnet-4-5-20250929',
      api_key: 'sk-test',
      system_prompt: 'Test prompt',
    });

    expect(result.name).toBe('New Agent');
    expect(useDebateAgentStore.getState().agents).toHaveLength(1);
  });

  it('updateAgent should update agent in state', async () => {
    useDebateAgentStore.setState({ agents: [makeAgent({ id: 'a1', name: 'Old Name' })] });

    const updated = { ...useDebateAgentStore.getState().agents[0], name: 'Updated Name' };

    vi.mocked(api.put).mockResolvedValueOnce(updated);

    await useDebateAgentStore.getState().updateAgent('a1', { name: 'Updated Name' });

    expect(useDebateAgentStore.getState().agents[0].name).toBe('Updated Name');
  });

  it('createAgent should work for local provider without api_key', async () => {
    const localAgent = makeAgent({
      id: 'a3',
      name: 'Local Agent',
      provider: 'local',
      model_id: 'custom',
    });

    vi.mocked(api.post).mockResolvedValueOnce(localAgent);

    const result = await useDebateAgentStore.getState().createAgent({
      name: 'Local Agent',
      provider: 'local',
      system_prompt: 'Local test prompt',
    });

    expect(result.provider).toBe('local');
    expect(result.is_connected).toBe(false);
    expect(useDebateAgentStore.getState().agents).toHaveLength(1);
    expect(api.post).toHaveBeenCalledWith('/agents', {
      name: 'Local Agent',
      provider: 'local',
      system_prompt: 'Local test prompt',
    });
  });

  it('deleteAgent should remove agent from state', async () => {
    useDebateAgentStore.setState({
      agents: [
        makeAgent({ id: 'a1', name: 'Agent To Delete' }),
        makeAgent({ id: 'a2', name: 'Agent To Keep' }),
      ],
    });

    vi.mocked(api.delete).mockResolvedValueOnce(undefined);

    await useDebateAgentStore.getState().deleteAgent('a1');

    const state = useDebateAgentStore.getState();
    expect(state.agents).toHaveLength(1);
    expect(state.agents[0].id).toBe('a2');
    expect(api.delete).toHaveBeenCalledWith('/agents/a1');
  });

  it('deleteAgent should throw on API error', async () => {
    useDebateAgentStore.setState({ agents: [makeAgent({ id: 'a1', name: 'Agent' })] });

    vi.mocked(api.delete).mockRejectedValueOnce(new Error('Permission denied'));

    await expect(useDebateAgentStore.getState().deleteAgent('a1')).rejects.toThrow();
    // 실패 시 로컬 상태는 변경되지 않아야 함
    expect(useDebateAgentStore.getState().agents).toHaveLength(1);
  });

  it('fetchVersions should return versions array', async () => {
    const mockVersions = [
      {
        id: 'v1',
        version_number: 1,
        version_tag: 'v1',
        system_prompt: 'Test',
        parameters: null,
        wins: 0,
        losses: 0,
        draws: 0,
        created_at: '2026-01-01',
      },
    ];

    vi.mocked(api.get).mockResolvedValueOnce(mockVersions);

    const versions = await useDebateAgentStore.getState().fetchVersions('a1');

    expect(versions).toHaveLength(1);
    expect(api.get).toHaveBeenCalledWith('/agents/a1/versions');
  });
});
