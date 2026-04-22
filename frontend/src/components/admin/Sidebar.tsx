/** 관리자 사이드바 네비게이션. 모바일에서는 드로어, 데스크톱에서는 고정 사이드바. */
'use client';

import { memo, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Users,
  Bot,
  DollarSign,
  Activity,
  User,
  LogOut,
  Swords,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useUserStore } from '@/stores/userStore';
import { useUIStore } from '@/stores/uiStore';

const MENU_ITEMS = [
  { href: '/admin', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/admin/users', label: '사용자 관리', icon: Users },
  { href: '/admin/models', label: 'LLM 모델', icon: Bot },
  { href: '/admin/usage', label: '사용량/과금', icon: DollarSign },
  { href: '/admin/monitoring', label: '모니터링', icon: Activity },
  { href: '/admin/debate', label: 'AI 토론 관리', icon: Swords },
];

export const Sidebar = memo(function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useUserStore();
  const { sidebarOpen, closeSidebar } = useUIStore();

  // 경로 변경 시 모바일 사이드바 자동 닫기
  useEffect(() => {
    closeSidebar();
  }, [pathname, closeSidebar]);

  const handleLogout = () => {
    logout();
    router.push('/');
  };

  return (
    <>
      {/* 모바일 백드롭 */}
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/50 z-[79] md:hidden" onClick={closeSidebar} />
      )}

      <aside
        className={`w-[240px] bg-bg-surface border-r border-border py-5 flex flex-col
          fixed top-0 left-0 h-full z-[80] transition-transform duration-250 ease-out
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          md:relative md:translate-x-0 md:z-auto md:min-h-screen`}
      >
        <div className="px-5 pb-5 border-b border-border mb-3">
          <Link href="/" className="text-text no-underline text-base font-bold block">
            AI 토론 플랫폼
          </Link>
          <span className="text-[11px] text-primary font-semibold uppercase tracking-wide">
            Admin
          </span>
        </div>
        <nav className="flex-1 flex flex-col gap-0.5 overflow-y-auto">
          {MENU_ITEMS.map((item) => {
            const active = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={closeSidebar}
                className={`flex items-center gap-2.5 px-5 py-2.5 no-underline text-sm transition-colors duration-200 ${
                  active
                    ? 'text-primary bg-primary/15 border-r-[3px] border-primary font-semibold'
                    : 'text-text-secondary hover:text-text hover:bg-bg-hover'
                }`}
              >
                <Icon size={20} />
                <span className="flex-1">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="px-5 py-4 border-t border-border">
          {user && (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary flex-shrink-0">
                  <User size={16} />
                </div>
                <span className="text-sm text-text truncate">{user.nickname}</span>
              </div>
              <button
                onClick={handleLogout}
                className="text-xs text-text-muted hover:text-danger bg-transparent border-none cursor-pointer"
                title="로그아웃"
              >
                <LogOut size={16} />
              </button>
            </div>
          )}
        </div>
      </aside>
    </>
  );
});
