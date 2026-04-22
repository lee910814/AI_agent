/** 사용자 사이드바. 모바일에서는 드로어, 데스크톱에서는 고정 사이드바. */
'use client';

import { memo, useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { api } from '@/lib/api';
import {
  Swords,
  MessageSquare,
  Trophy,
  List,
  Users,
  ShieldCheck,
  X,
  Menu,
  LayoutGrid,
  Home,
} from 'lucide-react';
import { useUserStore } from '@/stores/userStore';
import { useUIStore } from '@/stores/uiStore';

type MenuItem = { href: string; label: string; icon: typeof Swords };

const PLATFORM_ITEMS: MenuItem[] = [
  { href: '/', label: 'Home', icon: Home },
  { href: '/debate', label: 'Debate', icon: MessageSquare },
  { href: '/debate/ranking', label: 'Ranking', icon: Trophy },
  { href: '/debate/gallery', label: 'Gallery', icon: LayoutGrid },
  { href: '/community', label: 'Community', icon: Users },
];

type TopicCountResponse = { items: unknown[]; total: number };

export const UserSidebar = memo(function UserSidebar() {
  const pathname = usePathname();
  const { isAdmin } = useUserStore();
  const { sidebarOpen, closeSidebar, sidebarCollapsed, toggleSidebarCollapsed } = useUIStore();

  const [liveCount, setLiveCount] = useState<number | null>(null);
  const [scheduledCount, setScheduledCount] = useState<number | null>(null);

  useEffect(() => {
    closeSidebar();
  }, [pathname, closeSidebar]);

  useEffect(() => {
    async function fetchStats() {
      try {
        const [liveData, scheduledData] = await Promise.all([
          api.get<TopicCountResponse>('/topics?status=in_progress&page=1&page_size=1'),
          api.get<TopicCountResponse>('/topics?status=scheduled&page=1&page_size=1'),
        ]);
        setLiveCount(liveData.total);
        setScheduledCount(scheduledData.total);
      } catch {
        // 통계 로드 실패는 조용히 무시
      }
    }

    fetchStats();
    const interval = setInterval(fetchStats, 30_000);
    return () => clearInterval(interval);
  }, []);

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    if (href === '/debate') {
      return (
        pathname === '/debate' ||
        (pathname.startsWith('/debate/') &&
          !pathname.startsWith('/debate/ranking') &&
          !pathname.startsWith('/debate/agents') &&
          !pathname.startsWith('/debate/gallery') &&
          !pathname.startsWith('/debate/tournaments'))
      );
    }
    return pathname === href || pathname.startsWith(href + '/');
  };

  const sidebarWidth = sidebarCollapsed ? 'w-[70px]' : 'w-[200px]';

  return (
    <>
      {/* 모바일 백드롭 */}
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/50 z-[79] md:hidden" onClick={closeSidebar} />
      )}

      <aside
        className={`${sidebarWidth} bg-bg-surface border-r-2 border-border flex flex-col
          fixed top-0 left-0 h-full z-[80] transition-all duration-300 ease-in-out
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          md:sticky md:translate-x-0 md:min-h-screen`}
      >
        {/* 로고 헤더 */}
        <div
          className={`px-4 py-6 flex items-center ${sidebarCollapsed ? 'justify-center' : 'justify-between'}`}
        >
          {!sidebarCollapsed ? (
            <Link href="/" className="flex-1 no-underline group select-none">
              <p className="text-xl font-bold text-text m-0 leading-tight tracking-tight group-hover:text-primary transition-colors">
                NEMo
              </p>
              <p className="text-[10px] font-black m-0 text-primary tracking-widest">AI DEBATE</p>
            </Link>
          ) : (
            <button
              onClick={toggleSidebarCollapsed}
              className="w-8 h-8 bg-black text-white rounded-lg flex items-center justify-center font-black text-xl hover:bg-primary transition-colors select-none border-none cursor-pointer"
              aria-label="사이드바 펼치기"
            >
              N
            </button>
          )}
          {!sidebarCollapsed && (
            <button
              onClick={toggleSidebarCollapsed}
              className="p-2 rounded-lg bg-transparent border-none text-text hover:bg-bg-hover cursor-pointer hidden md:flex items-center justify-center transition-colors"
              aria-label="사이드바 토글"
            >
              <Menu size={20} strokeWidth={2.5} />
            </button>
          )}

          <button
            onClick={closeSidebar}
            className="p-1 rounded-lg bg-transparent border-none text-text-muted hover:text-text cursor-pointer md:hidden"
          >
            <X size={18} />
          </button>
        </div>

        {/* 네비게이션 */}
        <nav className="flex-1 flex flex-col py-2 px-3 gap-6 overflow-y-auto scrollbar-hide">
          {/* 플랫폼 */}
          <div>
            {!sidebarCollapsed && (
              <p className="text-[10px] font-black text-text-muted uppercase tracking-widest px-3 mb-3">
                플랫폼
              </p>
            )}
            <div className={`flex flex-col gap-1.5 ${sidebarCollapsed ? 'items-center' : ''}`}>
              {PLATFORM_ITEMS.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-3 no-underline text-sm font-bold transition-all duration-150 select-none
                      ${sidebarCollapsed ? 'justify-center p-2.5 rounded-xl' : 'px-4 py-2.5 rounded-xl'}
                      ${
                        active
                          ? 'bg-primary text-white brutal-border brutal-shadow-sm'
                          : 'text-text-secondary hover:text-text hover:bg-bg-hover'
                      }`}
                    title={sidebarCollapsed ? item.label : undefined}
                  >
                    <Icon size={18} strokeWidth={active ? 2.5 : 2} />
                    {!sidebarCollapsed && <span>{item.label}</span>}
                  </Link>
                );
              })}
            </div>
          </div>
        </nav>

        {/* 관리자 링크 */}
        {isAdmin() && (
          <div className={`px-3 py-2 ${sidebarCollapsed ? 'flex justify-center' : ''}`}>
            <Link
              href="/admin"
              className={`flex items-center gap-2 rounded-xl text-sm text-amber-500 hover:bg-amber-50 transition-colors no-underline font-bold
                ${sidebarCollapsed ? 'p-2.5 justify-center' : 'px-4 py-2.5'}`}
              title={sidebarCollapsed ? '관리자' : undefined}
            >
              <ShieldCheck size={18} />
              {!sidebarCollapsed && <span>관리자</span>}
            </Link>
          </div>
        )}

        {/* 통계 */}
        {!sidebarCollapsed && (
          <div
            className="px-3 py-3 bg-bg rounded-xl mx-3 border-2 border-[#1db865]"
            style={{ marginBottom: '25px' }}
          >
            <p className="text-[10px] font-black text-text-muted uppercase tracking-widest px-1 mb-2">
              통계
            </p>
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between px-1">
                <span className="text-[11px] font-bold text-text-secondary flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                  실시간 토론
                </span>
                <span className="text-sm font-black text-text">
                  {liveCount === null ? '...' : liveCount.toLocaleString()}
                </span>
              </div>
              <div className="flex items-center justify-between px-1">
                <span className="text-[11px] font-bold text-text-secondary flex items-center gap-1.5">
                  <List size={10} className="text-text-muted" />
                  진행 예정
                </span>
                <span className="text-sm font-black text-text">
                  {scheduledCount === null ? '...' : scheduledCount.toLocaleString()}
                </span>
              </div>
            </div>
          </div>
        )}
      </aside>
    </>
  );
});
