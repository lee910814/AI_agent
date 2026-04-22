import { create } from 'zustand';
import {
  getNotifications,
  getUnreadCount,
  markNotificationRead,
  markAllNotificationsRead,
  type NotificationResponse,
} from '@/lib/api';

type NotificationState = {
  notifications: NotificationResponse[];
  unreadCount: number;
  loading: boolean;
  fetchNotifications: (offset?: number) => Promise<void>;
  fetchUnreadCount: () => Promise<void>;
  markRead: (id: string) => Promise<void>;
  markAllRead: () => Promise<void>;
};

export const useNotificationStore = create<NotificationState>((set, get) => ({
  notifications: [],
  unreadCount: 0,
  loading: false,

  fetchNotifications: async (offset = 0) => {
    set({ loading: true });
    try {
      const res = await getNotifications({ offset, limit: 20 });
      set({
        notifications: offset === 0 ? res.items : [...get().notifications, ...res.items],
        unreadCount: res.unread_count,
      });
    } catch {
      /* 알림 로드 실패는 무시 */
    } finally {
      set({ loading: false });
    }
  },

  fetchUnreadCount: async () => {
    try {
      const res = await getUnreadCount();
      set({ unreadCount: res.count });
    } catch {
      /* 미읽기 카운트 실패는 무시 */
    }
  },

  markRead: async (id) => {
    // 낙관적 업데이트
    set((s) => ({
      notifications: s.notifications.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
      unreadCount: Math.max(
        0,
        s.unreadCount - (s.notifications.find((n) => n.id === id && !n.is_read) ? 1 : 0),
      ),
    }));
    try {
      await markNotificationRead(id);
    } catch {
      // 실패 시 서버 상태 재조회
      get().fetchUnreadCount();
    }
  },

  markAllRead: async () => {
    // 낙관적 업데이트
    const prev = get().notifications;
    const prevCount = get().unreadCount;
    set((s) => ({
      notifications: s.notifications.map((n) => ({ ...n, is_read: true })),
      unreadCount: 0,
    }));
    try {
      await markAllNotificationsRead();
    } catch {
      // 실패 시 스냅샷으로 복원 (markRead와 동일한 실패 처리 방식)
      set({ notifications: prev, unreadCount: prevCount });
    }
  },
}));
