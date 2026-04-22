'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { UserSidebar } from '@/components/layout/UserSidebar';
import { TopHeader } from '@/components/layout/TopHeader';
import { Footer } from '@/components/layout/Footer';
import { ErrorBoundary } from '@/components/layout/ErrorBoundary';
import { GuideProvider } from '@/components/guide/GuideProvider';
import { useUserStore } from '@/stores/userStore';
import { useUIStore } from '@/stores/uiStore';

export default function UserLayout({ children }: { children: React.ReactNode }) {
  const { initialized, user, initialize } = useUserStore();
  const { theme } = useUIStore();
  const router = useRouter();

  useEffect(() => {
    initialize();
  }, [initialize]);

  // 테마 변경 시 html 요소에 data-theme 속성 동기화
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // 비로그인 → 로그인 페이지로 이동 (useEffect로 처리해야 렌더 중 setState 에러 방지)
  useEffect(() => {
    if (initialized && !user) {
      router.replace('/login');
    }
  }, [initialized, user, router]);

  // 초기화 전 또는 비로그인 상태: 스피너 표시
  if (!initialized || !user) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-bg">
        <span className="inline-block w-6 h-6 border-2 border-text-muted border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <UserSidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopHeader />
        <div className="flex-1 overflow-y-auto flex flex-col">
          <main className="flex-1 p-4 md:p-6 pb-0">
            <ErrorBoundary>
              <GuideProvider>{children}</GuideProvider>
            </ErrorBoundary>
          </main>
          <Footer />
        </div>
      </div>
    </div>
  );
}
