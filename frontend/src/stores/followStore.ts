import { create } from 'zustand';
import { getFollowing, followTarget, unfollowTarget, type FollowResponse } from '@/lib/api';

type FollowState = {
  followingList: FollowResponse[];
  total: number;
  loading: boolean;
  fetchFollowing: (params?: { target_type?: string }) => Promise<void>;
  follow: (targetType: 'user' | 'agent', targetId: string) => Promise<FollowResponse>;
  unfollow: (targetType: 'user' | 'agent', targetId: string) => Promise<void>;
};

export const useFollowStore = create<FollowState>((set, get) => ({
  followingList: [],
  total: 0,
  loading: false,

  fetchFollowing: async (params) => {
    set({ loading: true });
    try {
      const res = await getFollowing(params);
      set({ followingList: res.items, total: res.total });
    } catch {
      /* 팔로우 목록 로드 실패는 무시 */
    } finally {
      set({ loading: false });
    }
  },

  follow: async (targetType, targetId) => {
    const item = await followTarget(targetType, targetId);
    set((s) => ({
      followingList: [item, ...s.followingList],
      total: s.total + 1,
    }));
    return item;
  },

  unfollow: async (targetType, targetId) => {
    // 낙관적 삭제 후 실패 시 롤백
    const prev = get().followingList;
    const prevTotal = get().total;
    set((s) => ({
      followingList: s.followingList.filter(
        (f) => !(f.target_type === targetType && f.target_id === targetId),
      ),
      total: Math.max(0, s.total - 1),
    }));
    try {
      await unfollowTarget(targetType, targetId);
    } catch (err) {
      set({ followingList: prev, total: prevTotal });
      throw err;
    }
  },
}));
