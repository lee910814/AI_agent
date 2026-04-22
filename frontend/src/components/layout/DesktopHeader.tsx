'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Sun, Moon, Bell, LogOut, UserCircle } from 'lucide-react';
import { useThemeStore } from '@/stores/themeStore';
import { useUserStore } from '@/stores/userStore';

export function DesktopHeader() {
  const { theme, toggleTheme } = useThemeStore();
  const { user, logout } = useUserStore();
  const router = useRouter();
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    logout();
    setShowDropdown(false);
    router.push('/');
  };

  return (
    <header className="hidden md:flex items-center px-6 h-[68px] bg-bg-surface border-b border-border sticky top-0 z-50">
      {/* Left empty spacer for perfect centering */}
      <div className="flex-1" />

      {/* Right actions */}
      <div className="flex-1 flex justify-end items-center gap-3">
        <button
          onClick={toggleTheme}
          className="w-10 h-10 rounded-full bg-nemo flex items-center justify-center text-white cursor-pointer border-none hover:bg-nemo-dark transition-colors"
          title={theme === 'light' ? '다크 모드' : '라이트 모드'}
        >
          {theme === 'light' ? <Sun size={18} /> : <Moon size={18} />}
        </button>
        <button className="w-10 h-10 rounded-full bg-bg border border-border flex items-center justify-center text-text-muted cursor-pointer hover:text-text hover:border-primary/40 transition-colors">
          <Bell size={18} />
        </button>
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setShowDropdown(!showDropdown)}
            className="w-10 h-10 rounded-full bg-nemo flex items-center justify-center text-white font-bold text-sm cursor-pointer border-none hover:bg-nemo-dark transition-colors"
          >
            {user?.nickname?.charAt(0)?.toUpperCase() ?? 'U'}
          </button>

          {/* Dropdown Menu */}
          {showDropdown && (
            <div className="absolute right-0 top-[calc(100%+8px)] w-48 bg-bg-surface border border-border rounded-xl shadow-lg py-2 z-[100] animate-in fade-in slide-in-from-top-2 duration-200">
              <div className="px-4 py-2 border-b border-border mb-1">
                <p className="text-sm font-semibold text-text truncate">
                  {user?.nickname ?? '사용자'}님
                </p>
              </div>
              <Link
                href="/mypage"
                onClick={() => setShowDropdown(false)}
                className="flex items-center gap-2 px-4 py-2.5 text-sm text-text hover:bg-bg-hover transition-colors no-underline block w-full"
              >
                <UserCircle size={16} className="text-text-muted" />
                <span>마이페이지</span>
              </Link>
              <button
                onClick={handleLogout}
                className="flex items-center gap-2 px-4 py-2.5 text-sm text-red-500 hover:bg-red-500/10 cursor-pointer border-none bg-transparent transition-colors w-full text-left"
              >
                <LogOut size={16} />
                <span>로그아웃</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
