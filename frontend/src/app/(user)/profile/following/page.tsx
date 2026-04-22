'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Bot, User, UserMinus } from 'lucide-react';
import { useFollowStore } from '@/stores/followStore';
import { useUserStore } from '@/stores/userStore';
import { useToastStore } from '@/stores/toastStore';
import { SkeletonCard } from '@/components/ui/Skeleton';

type TabKey = 'all' | 'agent' | 'user';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'all', label: '전체' },
  { key: 'agent', label: '에이전트' },
  { key: 'user', label: '사용자' },
];

export default function FollowingPage() {
  const router = useRouter();
  const { user } = useUserStore();
  const { followingList, loading, fetchFollowing, unfollow } = useFollowStore();
  const { addToast } = useToastStore();
  const [tab, setTab] = useState<TabKey>('all');
  const [unfollowingIds, setUnfollowingIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!user) {
      router.push('/');
      return;
    }
    fetchFollowing(tab === 'all' ? undefined : { target_type: tab });
  }, [user, tab, fetchFollowing, router]);

  const handleUnfollow = async (targetType: 'user' | 'agent', targetId: string) => {
    setUnfollowingIds((s) => new Set(s).add(targetId));
    try {
      await unfollow(targetType, targetId);
      addToast('success', '언팔로우했습니다.');
    } catch {
      addToast('error', '언팔로우에 실패했습니다.');
    } finally {
      setUnfollowingIds((s) => {
        const next = new Set(s);
        next.delete(targetId);
        return next;
      });
    }
  };

  const filtered =
    tab === 'all' ? followingList : followingList.filter((f) => f.target_type === tab);

  return (
    <div className="max-w-[600px] mx-auto py-6 px-4">
      <h1 className="text-xl font-bold text-text mb-5">팔로잉</h1>

      {/* 탭 */}
      <div className="flex gap-1 mb-5 bg-bg-surface border border-border rounded-xl p-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`flex-1 py-1.5 rounded-lg text-sm font-semibold transition-colors ${
              tab === t.key ? 'bg-primary text-white' : 'text-text-muted hover:text-text'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 목록 */}
      {loading ? (
        <div className="flex flex-col gap-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : filtered.length === 0 ? (
        <div className="py-16 text-center">
          <p className="text-sm text-text-muted">아직 팔로우한 항목이 없습니다.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {filtered.map((item) => (
            <div
              key={item.id}
              className="flex items-center gap-3 bg-bg-surface border border-border rounded-xl px-4 py-3"
            >
              {/* 아바타 */}
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0 overflow-hidden border border-border">
                {item.target_image_url ? (
                  <img
                    src={item.target_image_url}
                    alt={item.target_name}
                    className="w-full h-full object-cover"
                  />
                ) : item.target_type === 'agent' ? (
                  <Bot size={18} className="text-primary" />
                ) : (
                  <User size={18} className="text-primary" />
                )}
              </div>

              {/* 이름 + 타입 */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-text truncate">{item.target_name}</p>
                <p className="text-[11px] text-text-muted">
                  {item.target_type === 'agent' ? '에이전트' : '사용자'}
                </p>
              </div>

              {/* 언팔로우 버튼 */}
              <button
                type="button"
                onClick={() => handleUnfollow(item.target_type, item.target_id)}
                disabled={unfollowingIds.has(item.target_id)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs font-semibold text-text-muted hover:text-red-500 hover:border-red-500/30 hover:bg-red-500/10 transition-colors disabled:opacity-50"
              >
                <UserMinus size={13} />
                언팔로우
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
