import { create } from 'zustand';
import { api } from '@/lib/api';
import type { DebateTopic, TopicCreatePayload } from '@/types/debate';

type DebateTopicState = {
  topics: DebateTopic[];
  topicsTotal: number;
  popularTopics: DebateTopic[];
  popularTopicsTotal: number;
  topicsLoading: boolean;
  fetchTopics: (params?: {
    status?: string;
    sort?: string;
    page?: number;
    pageSize?: number;
  }) => Promise<void>;
  fetchPopularTopics: () => Promise<void>;
  createTopic: (payload: TopicCreatePayload) => Promise<DebateTopic>;
  updateTopic: (topicId: string, payload: Partial<TopicCreatePayload>) => Promise<DebateTopic>;
  deleteTopic: (topicId: string) => Promise<void>;
  joinQueue: (
    topicId: string,
    agentId: string,
    password?: string,
  ) => Promise<{ status: string; match_id?: string; opponent_agent_id?: string }>;
  leaveQueue: (topicId: string, agentId: string) => Promise<void>;
  randomMatch: (
    agentId: string,
  ) => Promise<{ topic_id: string; status: string; opponent_agent_id?: string }>;
};

export const useDebateTopicStore = create<DebateTopicState>((set) => ({
  topics: [],
  topicsTotal: 0,
  popularTopics: [],
  popularTopicsTotal: 0,
  topicsLoading: false,
  fetchTopics: async (params?) => {
    set({ topicsLoading: true });
    try {
      const { status, sort, page = 1, pageSize = 20 } = params ?? {};
      const queryParams = new URLSearchParams();
      if (status) queryParams.set('status', status);
      if (sort) queryParams.set('sort', sort);
      queryParams.set('page', String(page));
      queryParams.set('page_size', String(pageSize));
      const data = await api.get<{ items: DebateTopic[]; total: number }>(`/topics?${queryParams}`);
      set({ topics: data.items, topicsTotal: data.total });
    } catch (err) {
      console.error('Failed to fetch topics:', err);
    } finally {
      set({ topicsLoading: false });
    }
  },
  fetchPopularTopics: async () => {
    set({ topicsLoading: true });
    try {
      const data = await api.get<{ items: DebateTopic[]; total: number }>(
        '/topics?sort=popular_week&page_size=10',
      );
      set({ popularTopics: data.items, popularTopicsTotal: data.total });
    } catch (err) {
      console.error('Failed to fetch popular topics:', err);
    } finally {
      set({ topicsLoading: false });
    }
  },
  createTopic: async (payload) => {
    const data = await api.post<DebateTopic>('/topics', payload);
    set((s) => ({ topics: [data, ...s.topics], topicsTotal: s.topicsTotal + 1 }));
    return data;
  },
  updateTopic: async (topicId, payload) => {
    const data = await api.patch<DebateTopic>(`/topics/${topicId}`, payload);
    set((s) => ({
      topics: s.topics.map((t) => (t.id === topicId ? data : t)),
      popularTopics: s.popularTopics.map((t) => (t.id === topicId ? data : t)),
    }));
    return data;
  },
  deleteTopic: async (topicId) => {
    await api.delete(`/topics/${topicId}`);
    set((s) => ({
      topics: s.topics.filter((t) => t.id !== topicId),
      topicsTotal: s.topicsTotal - 1,
      popularTopics: s.popularTopics.filter((t) => t.id !== topicId),
      popularTopicsTotal: Math.max(0, s.popularTopicsTotal - 1),
    }));
  },
  joinQueue: async (topicId, agentId, password?) => {
    return api.post<{ status: string; match_id?: string; opponent_agent_id?: string }>(
      `/topics/${topicId}/join`,
      { agent_id: agentId, ...(password ? { password } : {}) },
    );
  },
  leaveQueue: async (topicId, agentId) => {
    await api.delete(`/topics/${topicId}/queue?agent_id=${agentId}`);
  },
  randomMatch: async (agentId) => {
    return api.post<{ topic_id: string; status: string; opponent_agent_id?: string }>(
      '/topics/random-match',
      { agent_id: agentId },
    );
  },
}));

export type { DebateTopicState };
