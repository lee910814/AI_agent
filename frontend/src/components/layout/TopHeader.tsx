'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Sun, Moon, UserCircle, LogOut } from 'lucide-react';
import { useUserStore } from '@/stores/userStore';
import { useUIStore } from '@/stores/uiStore';
import { NotificationBell } from '@/components/layout/NotificationBell';

export function TopHeader() {
  const { user, logout } = useUserStore();
  const { toggleSidebar, theme, toggleTheme } = useUIStore();
  const router = useRouter();

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const initial = user?.nickname?.[0]?.toUpperCase() ?? 'U';

  // 외부 클릭 시 드롭다운 닫기
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    setDropdownOpen(false);
    setShowLogoutConfirm(true);
  };

  const confirmLogout = () => {
    logout();
    router.push('/login');
  };

  return (
    <>
      <header className="h-14 border-b border-border bg-bg-surface flex items-center px-4 md:px-6 sticky top-0 z-30 relative">
        {/* 모바일 햄버거 */}
        <button
          className="md:hidden p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-bg-hover border-none bg-transparent cursor-pointer shrink-0"
          onClick={toggleSidebar}
          aria-label="메뉴 열기"
        >
          <span className="block w-5 h-0.5 bg-current mb-1" />
          <span className="block w-5 h-0.5 bg-current mb-1" />
          <span className="block w-5 h-0.5 bg-current" />
        </button>

        {/* 우측 액션 */}
        <div className="flex items-center gap-2 ml-auto shrink-0">
          <button
            onClick={toggleTheme}
            className="w-8 h-8 rounded-full bg-bg border border-border flex items-center justify-center text-text-muted hover:text-text transition-colors cursor-pointer"
            aria-label="테마 변경"
          >
            {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
          </button>

          {/* 알림 */}
          <NotificationBell />

          {/* 프로필 드롭다운 */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setDropdownOpen((v) => !v)}
              className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-white text-sm font-bold select-none cursor-pointer hover:opacity-90 transition-opacity border-none"
            >
              {initial}
            </button>

            {dropdownOpen && (
              <div className="absolute right-0 top-10 w-44 bg-bg-surface border border-border rounded-xl shadow-lg overflow-hidden z-50 animate-fade-in">
                {/* 유저 정보 */}
                <div className="px-4 py-3 border-b border-border">
                  <p className="text-xs font-black text-text truncate">{user?.nickname}</p>
                  <p className="text-[11px] text-text-muted truncate">{user?.login_id}</p>
                </div>

                {/* 메뉴 */}
                <div className="py-1">
                  <button
                    onClick={() => {
                      setDropdownOpen(false);
                      router.push('/mypage');
                    }}
                    className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm font-bold text-text hover:bg-bg-hover transition-colors cursor-pointer border-none bg-transparent text-left"
                  >
                    <UserCircle size={16} className="text-primary shrink-0" />
                    마이페이지
                  </button>
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm font-bold text-red-500 hover:bg-red-50 transition-colors cursor-pointer border-none bg-transparent text-left"
                  >
                    <LogOut size={16} className="shrink-0" />
                    로그아웃
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* 로그아웃 확인 모달 */}
      {showLogoutConfirm && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={() => setShowLogoutConfirm(false)}
        >
          <div
            className="bg-bg-surface border border-border w-full max-w-sm p-8 rounded-2xl shadow-xl animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center text-red-500 border-2 border-red-200">
                <LogOut size={32} />
              </div>
            </div>
            <h3 className="text-xl font-black text-center text-text mb-2">
              로그아웃 하시겠습니까?
            </h3>
            <p className="text-sm font-bold text-center text-text-muted mb-8">
              안전하게 세션이 종료됩니다.
            </p>
            <div className="flex flex-col gap-3">
              <button
                onClick={confirmLogout}
                className="w-full py-4 bg-red-500 text-white font-black rounded-xl hover:bg-red-600 transition-colors cursor-pointer border-none"
              >
                로그아웃
              </button>
              <button
                onClick={() => setShowLogoutConfirm(false)}
                className="w-full py-4 bg-bg-hover text-text font-black rounded-xl hover:opacity-80 transition-opacity cursor-pointer border-none"
              >
                취소
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
