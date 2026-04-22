'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { UserPlus, UserCheck, UserMinus } from 'lucide-react';
import { useUserStore } from '@/stores/userStore';
import { useFollowStore } from '@/stores/followStore';
import { useToastStore } from '@/stores/toastStore';

type Props = {
  targetType: 'user' | 'agent';
  targetId: string;
  initialIsFollowing: boolean;
  initialFollowerCount: number;
  className?: string;
};

export function FollowButton({
  targetType,
  targetId,
  initialIsFollowing,
  initialFollowerCount,
  className = '',
}: Props) {
  const router = useRouter();
  const { user } = useUserStore();
  const { follow, unfollow } = useFollowStore();
  const { addToast } = useToastStore();
  const [isFollowing, setIsFollowing] = useState(initialIsFollowing);
  const [followerCount, setFollowerCount] = useState(initialFollowerCount);
  const [hovered, setHovered] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    if (!user) {
      router.push('/');
      return;
    }
    if (loading) return;

    // 낙관적 업데이트
    const nextFollowing = !isFollowing;
    setIsFollowing(nextFollowing);
    setFollowerCount((c) => c + (nextFollowing ? 1 : -1));
    setLoading(true);

    try {
      if (nextFollowing) {
        await follow(targetType, targetId);
      } else {
        await unfollow(targetType, targetId);
      }
    } catch {
      // 실패 시 로컬 롤백 (followStore는 unfollow에서 자체 롤백)
      setIsFollowing(!nextFollowing);
      setFollowerCount((c) => c + (nextFollowing ? -1 : 1));
      addToast('error', nextFollowing ? '팔로우에 실패했습니다.' : '언팔로우에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  if (isFollowing) {
    return (
      <button
        type="button"
        onClick={handleClick}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        disabled={loading}
        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-colors disabled:opacity-50 ${
          hovered
            ? 'bg-red-500/10 border-red-500/30 text-red-500'
            : 'bg-bg border-border text-text-muted'
        } ${className}`}
      >
        {hovered ? (
          <>
            <UserMinus size={13} />
            언팔로우
          </>
        ) : (
          <>
            <UserCheck size={13} />
            팔로잉 {followerCount.toLocaleString()}명
          </>
        )}
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={loading}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-primary text-white hover:opacity-90 transition-opacity disabled:opacity-50 ${className}`}
    >
      <UserPlus size={13} />
      팔로우 {followerCount.toLocaleString()}명
    </button>
  );
}
