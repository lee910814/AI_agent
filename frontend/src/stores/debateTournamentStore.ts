import { create } from 'zustand';
import { api } from '@/lib/api';
import type { Tournament, TournamentEntry, TournamentDetail } from '@/types/debate';

type State = {
  tournaments: Tournament[];
  tournamentsTotal: number;
  currentTournament: TournamentDetail | null;
  loading: boolean;
  fetchTournaments: () => Promise<void>;
  fetchTournament: (id: string) => Promise<void>;
  joinTournament: (id: string, agentId: string) => Promise<void>;
};

export const useTournamentStore = create<State>((set) => ({
  tournaments: [],
  tournamentsTotal: 0,
  currentTournament: null,
  loading: false,
  fetchTournaments: async () => {
    set({ loading: true });
    try {
      const data = await api.get<{ items: Tournament[]; total: number }>('/tournaments');
      set({ tournaments: data.items, tournamentsTotal: data.total });
    } catch {
      /* ignore */
    } finally {
      set({ loading: false });
    }
  },
  fetchTournament: async (id) => {
    set({ loading: true });
    try {
      const data = await api.get<TournamentDetail>(`/tournaments/${id}`);
      set({ currentTournament: data });
    } catch {
      /* ignore */
    } finally {
      set({ loading: false });
    }
  },
  joinTournament: async (id, agentId) => {
    await api.post(`/tournaments/${id}/join`, { agent_id: agentId });
  },
}));

export type { Tournament, TournamentEntry, TournamentDetail };
