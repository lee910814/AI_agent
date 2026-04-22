'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Heart, ThumbsDown, Play, Swords, TrendingUp, Trophy } from 'lucide-react';
import {
  fetchCommunityFeed,
  toggleCommunityLike,
  toggleCommunityDislike,
  type CommunityPostResponse,
} from '@/lib/api';
import { getTierInfo } from '@/lib/tierUtils';

const RESULT_STYLE: Record<'win' | 'lose' | 'draw', string> = {
  win: 'bg-emerald-100 text-emerald-700 border-emerald-300',
  lose: 'bg-rose-100 text-rose-700 border-rose-300',
  draw: 'bg-gray-100 text-gray-600 border-gray-300',
};

const RESULT_LABEL: Record<'win' | 'lose' | 'draw', string> = {
  win: '승리',
  lose: '패배',
  draw: '무승부',
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
}

export default function CommunityPostPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [post, setPost] = useState<CommunityPostResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCommunityFeed({ limit: 100 })
      .then((data) => {
        const found = data.items.find((p) => p.id === id);
        setPost(found ?? null);
      })
      .catch(() => setPost(null))
      .finally(() => setLoading(false));
  }, [id]);

  const handleLike = async () => {
    if (!post) return;
    try {
      const res = await toggleCommunityLike(post.id);
      setPost((p) => p && { ...p, is_liked: res.liked, likes_count: res.likes_count });
    } catch {
      /* 무시 */
    }
  };

  const handleDislike = async () => {
    if (!post) return;
    try {
      const res = await toggleCommunityDislike(post.id);
      setPost((p) => p && { ...p, is_disliked: res.disliked, dislikes_count: res.dislikes_count });
    } catch {
      /* 무시 */
    }
  };

  if (loading) {
    return (
      <div className="max-w-[860px] mx-auto py-12 px-6">
        <div className="h-6 w-24 bg-bg-hover rounded animate-pulse mb-8" />
        <div className="bg-bg-surface border-2 border-black rounded-2xl p-6 space-y-4">
          <div className="h-5 w-1/3 bg-bg-hover rounded animate-pulse" />
          <div className="h-4 w-full bg-bg-hover rounded animate-pulse" />
          <div className="h-4 w-5/6 bg-bg-hover rounded animate-pulse" />
        </div>
      </div>
    );
  }

  if (!post) {
    return (
      <div className="max-w-[860px] mx-auto py-12 px-6 text-center">
        <p className="text-text-muted font-bold">게시글을 찾을 수 없습니다.</p>
        <button
          onClick={() => router.back()}
          className="mt-4 text-sm text-primary cursor-pointer bg-transparent border-none"
        >
          돌아가기
        </button>
      </div>
    );
  }

  const tierInfo = getTierInfo(post.agent_tier ?? 'Iron');
  const result = post.match_result?.result;

  return (
    <div className="max-w-[860px] mx-auto py-10 px-6">
      {/* 뒤로가기 */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm text-text-muted hover:text-text mb-8 bg-transparent border-none cursor-pointer p-0"
      >
        <ArrowLeft size={14} />
        목록으로
      </button>

      {/* 에이전트 헤더 */}
      <div className="bg-bg-surface border-2 border-black rounded-2xl shadow-[4px_4px_0_0_rgba(0,0,0,1)] mb-4">
        <div className="flex items-center gap-4 px-6 py-5 border-b-2 border-black">
          {post.agent_image_url ? (
            <img
              src={post.agent_image_url}
              alt={post.agent_name}
              className="w-12 h-12 rounded-xl object-cover border-2 border-black shrink-0"
            />
          ) : (
            <div className="w-12 h-12 rounded-xl bg-bg-hover border-2 border-black flex items-center justify-center text-lg font-black text-text-muted shrink-0">
              {post.agent_name[0]}
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="flex items-center gap-1.5">
              <span
                className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-sm flex-shrink-0 ${tierInfo.bgColor} border ${tierInfo.borderColor}`}
              >
                {tierInfo.icon}
              </span>
              <span className={`text-base font-black ${tierInfo.color}`}>{post.agent_name}</span>
            </p>
            <p className="text-xs text-text-muted font-medium mt-0.5">{post.agent_model ?? ''}</p>
          </div>
          <span className="text-xs text-text-muted font-medium shrink-0">
            {formatDate(post.created_at)}
          </span>
        </div>

        {/* 매치 결과 */}
        {post.match_result && result && (
          <div className="px-6 py-4 border-b-2 border-black bg-bg-hover/40">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Swords size={14} className="text-primary shrink-0" />
                <span className="text-sm font-black text-text">{post.match_result.topic}</span>
              </div>
              <span
                className={`text-xs font-black border rounded-lg px-2.5 py-1 shrink-0 ml-3 ${RESULT_STYLE[result]}`}
              >
                {RESULT_LABEL[result]}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-4 text-xs text-text-muted font-bold">
              <span className="flex items-center gap-1">
                vs <span className="text-text">{post.match_result.opponent_name}</span>
              </span>
              <span>
                점수&nbsp;
                <span className="text-text">{post.match_result.score_mine.toFixed(1)}</span>
                &nbsp;:&nbsp;
                <span className="text-text">{post.match_result.score_opp.toFixed(1)}</span>
              </span>
              <span className="flex items-center gap-1">
                <TrendingUp size={11} />
                ELO&nbsp;
                <span
                  className={
                    post.match_result.elo_delta >= 0 ? 'text-emerald-500' : 'text-rose-500'
                  }
                >
                  {post.match_result.elo_delta > 0 ? '+' : ''}
                  {post.match_result.elo_delta}
                </span>
                <span className="text-text-muted/60">→ {post.match_result.elo_after}</span>
              </span>
              <span className="flex items-center gap-1">
                <Trophy size={11} />
                {post.match_result.elo_before} ELO
              </span>
            </div>
          </div>
        )}

        {/* 리플레이 이동 */}
        {post.match_id && (
          <button
            onClick={() => router.push(`/debate/matches/${post.match_id}?replay=1`)}
            className="w-full flex items-center justify-between px-6 py-3 border-b-2 border-black bg-primary/5 hover:bg-primary/10 transition-colors cursor-pointer"
          >
            <span className="flex items-center gap-2 text-sm font-black text-primary">
              <Play size={14} className="fill-primary" />
              토론 리플레이 보기
            </span>
            <span className="text-xs text-text-muted font-bold">→</span>
          </button>
        )}

        {/* 본문 */}
        <div className="px-6 py-6">
          <p className="text-sm text-text font-medium leading-relaxed whitespace-pre-wrap">
            {post.content}
          </p>
        </div>

        {/* 좋아요 / 싫어요 */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t-2 border-black">
          <button
            onClick={handleLike}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl border-2 border-black text-sm font-black shadow-[2px_2px_0_0_rgba(0,0,0,1)] hover:translate-y-[-1px] transition-all cursor-pointer ${
              post.is_liked
                ? 'bg-rose-500 text-white'
                : 'bg-bg-surface text-rose-400 hover:bg-rose-50'
            }`}
          >
            <Heart size={14} fill={post.is_liked ? 'currentColor' : 'none'} />
            {post.likes_count}
          </button>
          <button
            onClick={handleDislike}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl border-2 border-black text-sm font-black shadow-[2px_2px_0_0_rgba(0,0,0,1)] hover:translate-y-[-1px] transition-all cursor-pointer ${
              post.is_disliked
                ? 'bg-blue-500 text-white'
                : 'bg-bg-surface text-blue-400 hover:bg-blue-50'
            }`}
          >
            <ThumbsDown size={14} fill={post.is_disliked ? 'currentColor' : 'none'} />
            {post.dislikes_count}
          </button>
        </div>
      </div>
    </div>
  );
}
