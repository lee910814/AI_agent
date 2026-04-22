'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Sidebar } from '@/components/admin/Sidebar';
import { MobileHeader } from '@/components/layout/MobileHeader';
import { GuideProvider } from '@/components/guide/GuideProvider';
import { useUserStore } from '@/stores/userStore';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { initialized, user, initialize } = useUserStore();

  useEffect(() => {
    initialize();
  }, [initialize]);

  useEffect(() => {
    if (initialized && (!user || !['admin', 'superadmin'].includes(user.role))) {
      router.push('/');
    }
  }, [initialized, user, router]);

  if (!initialized || !user || !['admin', 'superadmin'].includes(user.role)) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-bg">
        <span className="inline-block w-6 h-6 border-2 border-text-muted border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <MobileHeader />
        <main className="flex-1 p-4 md:p-6 bg-bg overflow-y-auto">
          <GuideProvider>{children}</GuideProvider>
        </main>
      </div>
    </div>
  );
}
