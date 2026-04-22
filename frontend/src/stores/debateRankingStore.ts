import { create } from 'zustand';
import { api } from '@/lib/api';
import type { RankingEntry, DebateMatch } from '@/types/debate';

type DebateRankingState = {
  ranking: RankingEntry[];
  rankingLoading: boolean;
  featuredMatches: DebateMatch[];
  fetchRanking: (seasonId?: string) => Promise<void>;
  fetchFeatured: (limit?: number) => Promise<void>;
};

export const useDebateRankingStore = create<DebateRankingState>((set) => ({
  ranking: [],
  rankingLoading: false,
  featuredMatches: [],
  fetchRanking: async (seasonId?) => {
    set({ rankingLoading: true });
    try {
      const params = seasonId ? `?season_id=${seasonId}` : '';
      const data = await api.get<{ items: RankingEntry[]; total: number } | RankingEntry[]>(
        `/agents/ranking${params}`,
      );
      const items = Array.isArray(data) ? data : data.items;
      set({ ranking: items });
    } catch (err) {
      console.error('Failed to fetch ranking:', err);
    } finally {
      set({ rankingLoading: false });
    }
  },
  fetchFeatured: async (limit = 5) => {
    try {
      const data = await api.get<{ items: DebateMatch[]; total: number }>(
        `/matches/featured?limit=${limit}`,
      );
      set({ featuredMatches: data.items });
    } catch (err) {
      console.error('Failed to fetch featured matches:', err);
    }
  },
}));

export type { DebateRankingState };
