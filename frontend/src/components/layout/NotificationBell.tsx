'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Bell, CheckCheck } from 'lucide-react';
import { useUserStore } from '@/stores/userStore';
import { useNotificationStore } from '@/stores/notificationStore';
import { getTimeAgo } from '@/lib/format';

const POLL_INTERVAL_MS = 30_000;
const DROPDOWN_LIMIT = 10;
const MAX_BADGE = 99;

export function NotificationBell() {
  const router = useRouter();
  const { user } = useUserStore();
  const {
    notifications,
    unreadCount,
    loading,
    fetchNotifications,
    fetchUnreadCount,
    markRead,
    markAllRead,
  } = useNotificationStore();
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // 30초 폴링: 미읽기 카운트만 주기적으로 갱신
  useEffect(() => {
    if (!user) return;
    fetchUnreadCount();
    const timer = setInterval(fetchUnreadCount, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [user, fetchUnreadCount]);

  // 드롭다운 열릴 때 알림 목록 로드
  useEffect(() => {
    if (open) {
      fetchNotifications(0);
    }
  }, [open, fetchNotifications]);

  // 패널 외부 클릭 시 닫기
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  if (!user) return null;

  const handleNotificationClick = async (id: string, link: string | null) => {
    setOpen(false);
    await markRead(id);
    if (link) router.push(link);
  };

  const handleMarkAllRead = async () => {
    await markAllRead();
  };

  const badgeCount = Math.min(unreadCount, MAX_BADGE);
  const displayItems = notifications.slice(0, DROPDOWN_LIMIT);

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="relative p-2 rounded-full bg-bg border border-border text-text-muted hover:text-text transition-colors cursor-pointer"
        aria-label={`알림 ${unreadCount > 0 ? `(${unreadCount}개 미읽음)` : ''}`}
      >
        <Bell size={16} />
        {badgeCount > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center leading-none">
            {badgeCount === MAX_BADGE && unreadCount > MAX_BADGE ? `${MAX_BADGE}+` : badgeCount}
          </span>
        )}
      </button>

      {open && (
        <div
          ref={panelRef}
          className="absolute right-0 top-full mt-2 w-80 bg-bg-surface border border-border rounded-xl shadow-lg z-50 overflow-hidden"
        >
          {/* 헤더 */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <span className="text-sm font-bold text-text">알림</span>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={handleMarkAllRead}
                className="flex items-center gap-1 text-xs text-text-muted hover:text-primary transition-colors bg-transparent border-none cursor-pointer"
              >
                <CheckCheck size={13} />
                모두 읽음
              </button>
            )}
          </div>

          {/* 알림 목록 */}
          <div className="max-h-[360px] overflow-y-auto">
            {loading && displayItems.length === 0 ? (
              <div className="py-8 text-center">
                <span className="inline-block w-5 h-5 border-2 border-border border-t-primary rounded-full animate-spin" />
              </div>
            ) : displayItems.length === 0 ? (
              <p className="py-8 text-center text-sm text-text-muted">새 알림이 없습니다.</p>
            ) : (
              displayItems.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleNotificationClick(n.id, n.link)}
                  className={`w-full text-left px-4 py-3 border-b border-border last:border-b-0 hover:bg-bg-hover transition-colors cursor-pointer bg-transparent ${
                    n.is_read ? '' : 'bg-primary/5'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    {!n.is_read && (
                      <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                    )}
                    <div className={`flex-1 min-w-0 ${n.is_read ? 'pl-3.5' : ''}`}>
                      <p className="text-xs font-semibold text-text truncate">{n.title}</p>
                      {n.body && (
                        <p className="text-[11px] text-text-muted mt-0.5 line-clamp-2">{n.body}</p>
                      )}
                      <p className="text-[10px] text-text-muted mt-1">{getTimeAgo(n.created_at)}</p>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
