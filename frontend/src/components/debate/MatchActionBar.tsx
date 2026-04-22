'use client';

import { useEffect, useState } from 'react';
import { Eye, Play } from 'lucide-react';
import { useDebateStore } from '@/stores/debateStore';
import { api } from '@/lib/api';
import { LiveBadge } from './LiveBadge';
import { PredictionPanel } from './PredictionPanel';
import { ShareButton } from './ShareButton';

type Props = {
  matchId: string;
  matchStatus: string;
  agentAName: string;
  agentBName: string;
  topicTitle?: string | null;
};

export function MatchActionBar({
  matchId,
  matchStatus,
  agentAName,
  agentBName,
  topicTitle,
}: Props) {
  const turns = useDebateStore((s) => s.turns);
  const startReplay = useDebateStore((s) => s.startReplay);
  const debateShowAll = useDebateStore((s) => s.debateShowAll);
  const setDebateShowAll = useDebateStore((s) => s.setDebateShowAll);
  const replayMode = useDebateStore((s) => s.replayMode);
  const [viewerCount, setViewerCount] = useState(0);

  // 관전자 수 폴링 (in_progress 매치, 30초 간격) — DebateViewer에서 이동
  useEffect(() => {
    if (matchStatus !== 'in_progress') return;
    const fetchViewers = async () => {
      try {
        const data = await api.get<{ count: number }>(`/matches/${matchId}/viewers`);
        setViewerCount(data.count);
      } catch {
        /* ignore */
      }
    };
    fetchViewers();
    const interval = setInterval(fetchViewers, 30000);
    return () => clearInterval(interval);
  }, [matchId, matchStatus]);

  if (matchStatus !== 'in_progress' && matchStatus !== 'completed') return null;
  // 리플레이 진행 중에는 액션바 숨김 (빈 박스 방지)
  if (matchStatus === 'completed' && replayMode) return null;

  return (
    <div className="sticky bottom-0 z-20 bg-bg/95 backdrop-blur-sm border-t border-border">
      <div className="max-w-[700px] mx-auto px-4 py-3">
        {/* 진행 중: 관전자 수 + 예측투표 */}
        {matchStatus === 'in_progress' && (
          <div className="flex flex-col gap-2">
            {viewerCount > 0 && (
              <div className="flex justify-end">
                <LiveBadge count={viewerCount} />
              </div>
            )}
            <PredictionPanel
              matchId={matchId}
              agentAName={agentAName}
              agentBName={agentBName}
              turnCount={turns.length}
            />
          </div>
        )}
        {/* 완료: 리플레이 + 전체보기 + 공유 */}
        {matchStatus === 'completed' && !replayMode && (
          <div className="flex items-center gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => {
                setDebateShowAll(false);
                window.scrollTo({ top: 0, behavior: 'smooth' });
                startReplay();
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 text-sm font-semibold transition-colors"
            >
              <Play size={14} />
              리플레이 시작
            </button>
            {!debateShowAll && (
              <button
                type="button"
                onClick={() => setDebateShowAll(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-surface border border-border text-text-muted hover:text-text hover:bg-border/20 text-sm font-semibold transition-colors"
              >
                <Eye size={14} />
                전체 보기
              </button>
            )}
            <ShareButton
              url={`${typeof window !== 'undefined' ? window.location.origin : ''}/debate/matches/${matchId}`}
              title={`AI 토론 결과: ${topicTitle ?? 'AI 토론'}`}
            />
          </div>
        )}
      </div>
    </div>
  );
}
