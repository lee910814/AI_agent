'use client';

import Link from 'next/link';
import { Menu, Sun, Moon, Bell } from 'lucide-react';
import { useUIStore } from '@/stores/uiStore';
import { useThemeStore } from '@/stores/themeStore';
import { useUserStore } from '@/stores/userStore';

export function MobileHeader() {
  const { toggleSidebar } = useUIStore();
  const { theme, toggleTheme } = useThemeStore();
  const { user } = useUserStore();

  return (
    <div className="md:hidden flex items-center gap-3 px-4 py-3 bg-white border-b-2 border-black sticky top-0 z-[10]">
      <button
        onClick={toggleSidebar}
        className="p-1.5 rounded-lg bg-transparent border-none text-black cursor-pointer hover:bg-gray-100 transition-colors"
        aria-label="메뉴 열기"
      >
        <Menu size={22} strokeWidth={2.5} />
      </button>
      <Link href="/" className="no-underline transition-opacity hover:opacity-80">
        <span className="text-xl font-black text-black tracking-tight italic">NEMO</span>
      </Link>

      <div className="flex-1" />

      <button
        onClick={toggleTheme}
        className="w-8 h-8 rounded-full bg-nemo flex items-center justify-center text-white cursor-pointer border-none"
        title={theme === 'light' ? '다크 모드' : '라이트 모드'}
      >
        {theme === 'light' ? <Sun size={14} /> : <Moon size={14} />}
      </button>

      <button className="w-8 h-8 rounded-full bg-bg border border-border flex items-center justify-center text-text-muted cursor-pointer">
        <Bell size={14} />
      </button>

      <div className="w-8 h-8 rounded-full bg-nemo flex items-center justify-center text-white font-bold text-xs">
        {user?.nickname?.charAt(0)?.toUpperCase() ?? 'U'}
      </div>
    </div>
  );
}
