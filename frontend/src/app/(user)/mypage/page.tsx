'use client';

import { Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { UserCircle, Settings, BarChart3, Bot } from 'lucide-react';
import { ProfileTab } from '@/components/mypage/ProfileTab';
import { SettingsTab } from '@/components/mypage/SettingsTab';
import { UsageTab } from '@/components/mypage/UsageTab';
import { AgentTab } from '@/components/mypage/AgentTab';

const TABS = [
  { key: 'profile', label: '내 정보', icon: UserCircle },
  { key: 'settings', label: '설정', icon: Settings },
  { key: 'usage', label: '사용량', icon: BarChart3 },
  { key: 'agents', label: '에이전트', icon: Bot },
] as const;

type TabKey = (typeof TABS)[number]['key'];

function MyPageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const currentTab = (searchParams.get('tab') as TabKey) || 'profile';

  const handleTabChange = (tab: TabKey) => {
    router.push(`/mypage?tab=${tab}`, { scroll: false });
  };

  return (
    <div className="max-w-[800px] mx-auto py-6 px-4">
      <h1 className="page-title">마이페이지</h1>

      <div className="relative mb-6 -mx-4">
        <div className="flex gap-1 border-b border-border overflow-x-auto scrollbar-hide px-4">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const active = currentTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => handleTabChange(tab.key)}
                className={`flex items-center gap-1.5 px-2.5 md:px-3 py-2.5 text-sm font-medium border-b-2 transition-colors duration-200 bg-transparent border-x-0 border-t-0 cursor-pointer whitespace-nowrap flex-shrink-0 ${
                  active
                    ? 'border-b-primary text-primary'
                    : 'border-b-transparent text-text-muted hover:text-text'
                }`}
              >
                <Icon size={16} />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab content */}
      {currentTab === 'profile' && <ProfileTab />}
      {currentTab === 'settings' && <SettingsTab />}
      {currentTab === 'usage' && <UsageTab />}
      {currentTab === 'agents' && <AgentTab />}
    </div>
  );
}

export default function MyPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-[800px] mx-auto py-6 px-4">
          <div className="h-8 w-32 bg-bg-hover rounded animate-pulse mb-6" />
          <div className="flex gap-1 mb-6 border-b border-border">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-10 w-20 bg-bg-hover rounded animate-pulse" />
            ))}
          </div>
          <div className="h-64 bg-bg-hover rounded animate-pulse" />
        </div>
      }
    >
      <MyPageContent />
    </Suspense>
  );
}
