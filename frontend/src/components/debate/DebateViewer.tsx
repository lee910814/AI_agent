'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useDebateStore } from '@/stores/debateStore';
import type { DebateMatch, PromotionSeries } from '@/stores/debateStore';
import { TurnBubble } from './TurnBubble';
import { StreamingTurnBubble } from './StreamingTurnBubble';
import { ReplayControls } from './ReplayControls';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { ScrollToTop } from '@/components/ui/ScrollToTop';
import { useDebateStream } from '@/hooks/useDebateStream';
import { useDebateReplay } from '@/hooks/useDebateReplay';

type Props = {
  match: DebateMatch;
  onSeriesUpdate?: (series: PromotionSeries) => void;
};

export function DebateViewer({ match, onSeriesUpdate }: Props) {
  // 슬라이스별 구독 — appendChunk로 streamingTurn이 바뀔 때 turns는 재렌더링하지 않음
  const turns = useDebateStore((s) => s.turns);
  const streamingTurn = useDebateStore((s) => s.streamingTurn);
  const turnReviews = useDebateStore((s) => s.turnReviews);
  const streaming = useDebateStore((s) => s.streaming);
  const replayMode = useDebateStore((s) => s.replayMode);
  const replayIndex = useDebateStore((s) => s.replayIndex);
  const replaySpeed = useDebateStore((s) => s.replaySpeed);
  const setReplayTyping = useDebateStore((s) => s.setReplayTyping);
  const nextSpeaker = useDebateStore((s) => s.nextSpeaker);
  const debateShowAll = useDebateStore((s) => s.debateShowAll);
  const judgeIntro = useDebateStore((s) => s.judgeIntro);
  const stopReplay = useDebateStore((s) => s.stopReplay);
  const fetchTurns = useDebateStore((s) => s.fetchTurns);
  const pendingTurnLogs = useDebateStore((s) => s.pendingTurnLogs);
  const flushPendingTurn = useDebateStore((s) => s.flushPendingTurn);

  // SSE 스트리밍 — 연결/이벤트 처리 로직을 훅으로 분리
  useDebateStream(match.id, match.status, { onSeriesUpdate });

  // 리플레이 재생 interval 관리를 훅으로 분리
  useDebateReplay();

  // turnIdx: 현재 타이핑 중인 replayIndex, text: 타이핑된 부분 텍스트
  // turnIdx가 replayIndex와 다를 때 displayClaim을 적용하지 않아 stale text 방지
  const [replayTyped, setReplayTyped] = useState<{ turnIdx: number; text: string }>({
    turnIdx: -1,
    text: '',
  });
  const bottomRef = useRef<HTMLDivElement>(null);
  const lastTurnRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);
  const typingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // streamingTurn 최신값을 ref로 유지 — turns.length 효과에서 스냅샷으로 읽기 위함
  const streamingTurnRef = useRef(streamingTurn);
  streamingTurnRef.current = streamingTurn;

  useEffect(() => {
    fetchTurns(match.id);
  }, [match.id, fetchTurns]);

  // 컴포넌트 언마운트(페이지 이동) 시 리플레이 상태 초기화
  useEffect(() => {
    return () => {
      stopReplay();
    };
  }, [stopReplay]);

  // 바닥 감지: window 레벨 스크롤
  useEffect(() => {
    const handleScroll = () => {
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
      isNearBottomRef.current = maxScroll <= 0 || window.scrollY >= maxScroll - 100;
    };
    window.addEventListener('scroll', handleScroll);
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // 스마트 자동 스크롤: 완료 턴이 추가될 때만 (스트리밍 청크는 스크롤 안 함)
  // 스트리밍 중 smooth scroll은 타이핑으로 늘어나는 콘텐츠와 충돌해 화면 흔들림 발생 — instant 사용
  useEffect(() => {
    if (!isNearBottomRef.current) return;
    const behavior = streamingTurnRef.current ? 'instant' : 'smooth';
    bottomRef.current?.scrollIntoView({ behavior });
  }, [turns.length]);

  // 리플레이 진행 시 현재 턴으로 자동 스크롤
  useEffect(() => {
    if (replayMode && lastTurnRef.current) {
      lastTurnRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [replayIndex, replayMode]);

  // 리플레이 타이핑 애니메이션 (replayIndex가 바뀔 때마다 해당 턴 claim을 글자 단위로 표시)
  useEffect(() => {
    if (typingIntervalRef.current) {
      clearInterval(typingIntervalRef.current);
      typingIntervalRef.current = null;
    }

    if (!replayMode || replayIndex < 0) {
      setReplayTyped({ turnIdx: -1, text: '' });
      return;
    }

    const lastTurn = turns[replayIndex];
    if (!lastTurn?.claim) {
      setReplayTyped({ turnIdx: replayIndex, text: '' });
      return;
    }

    const fullText = lastTurn.claim;
    const currentTurnIdx = replayIndex;
    // turnIdx와 text를 동시에 초기화 — stale text가 다음 턴에 잠깐 보이는 버그 방지
    setReplayTyped({ turnIdx: currentTurnIdx, text: '' });
    setReplayTyping(true);

    // replaySpeed에 비례하여 타이핑 속도 조절 (기본 3자/30ms ≈ 100자/초)
    const charsPerTick = Math.max(1, Math.round(3 * replaySpeed));
    let typed = '';
    typingIntervalRef.current = setInterval(() => {
      if (typed.length >= fullText.length) {
        clearInterval(typingIntervalRef.current!);
        typingIntervalRef.current = null;
        setReplayTyped({ turnIdx: currentTurnIdx, text: fullText });
        setReplayTyping(false);
        return;
      }
      typed = fullText.slice(0, typed.length + charsPerTick);
      setReplayTyped({ turnIdx: currentTurnIdx, text: typed });
    }, 30);

    return () => {
      if (typingIntervalRef.current) {
        clearInterval(typingIntervalRef.current);
        typingIntervalRef.current = null;
      }
      setReplayTyping(false);
    };
  }, [replayIndex, replayMode, replaySpeed, turns, setReplayTyping]);

  // turnReviews를 Map으로 캐싱 — visibleTurns.map 안의 find()를 O(1) 조회로 전환
  // SSE 청크 수신(appendChunk)마다 find()가 반복 실행되는 O(n*m) 탐색 방지
  const turnReviewMap = useMemo(
    () => new Map(turnReviews.map((r) => [`${r.turn_number}:${r.speaker}`, r])),
    [turnReviews],
  );

  // 리플레이 모드일 때 표시할 턴 슬라이스
  // in_progress: 항상 전체 표시 / completed: debateShowAll(전체보기 or 리플레이 종료 후)만 표시
  // useMemo: streamingTurn 업데이트(매 SSE 청크)마다 재계산되지 않도록 메모이제이션
  const visibleTurns = useMemo(
    () =>
      replayMode
        ? turns.slice(0, replayIndex + 1)
        : match.status === 'in_progress' || debateShowAll
          ? turns
          : [],
    [replayMode, replayIndex, turns, match.status, debateShowAll],
  );

  return (
    <div className="flex flex-col gap-3">
      {/* 리플레이 컨트롤 */}
      <ReplayControls />

      {match.status === 'waiting_agent' && (
        <div className="text-center py-8">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-yellow-500/10 text-yellow-600 text-sm">
            <span className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" />
            로컬 에이전트 접속 대기 중...
          </div>
        </div>
      )}

      {match.status === 'forfeit' && (
        <div className="text-center py-8">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-red-500/10 text-red-600 text-sm font-semibold">
            에이전트 미접속 — 몰수패
          </div>
        </div>
      )}

      {judgeIntro && (
        <div className="rounded-xl border border-primary/30 bg-primary/5 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">Judge Intro</p>
          <p className="mt-1 text-sm text-text">{judgeIntro}</p>
        </div>
      )}

      {turns.length === 0 && !streamingTurn && match.status === 'in_progress' && (
        <div className="flex flex-col gap-3">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}

      {visibleTurns.map((turn, idx) => {
        const review =
          turnReviewMap.get(`${turn.turn_number}:${turn.speaker}`) ?? turn.review_result ?? null;
        const isLastTurn = idx === visibleTurns.length - 1;
        // 리플레이 마지막 턴: turnIdx가 현재 replayIndex와 일치할 때만 부분 텍스트 전달
        // (불일치 시 stale text가 다른 턴에 잠깐 보이는 버그 방지)
        const displayClaim =
          replayMode &&
          isLastTurn &&
          replayTyped.turnIdx === replayIndex &&
          replayTyped.text !== turn.claim
            ? replayTyped.text
            : undefined;
        return (
          <div
            key={turn.id || `${turn.turn_number}-${turn.speaker}`}
            ref={isLastTurn ? lastTurnRef : undefined}
          >
            <TurnBubble
              turn={turn}
              agentAName={match.agent_a.name}
              agentBName={match.agent_b.name}
              agentAImageUrl={match.agent_a.image_url}
              agentBImageUrl={match.agent_b.image_url}
              review={review}
              displayClaim={displayClaim}
            />
          </div>
        );
      })}

      {streamingTurn && (
        <StreamingTurnBubble
          turn={streamingTurn}
          agentAName={match.agent_a.name}
          agentBName={match.agent_b.name}
          agentAImageUrl={match.agent_a.image_url}
          agentBImageUrl={match.agent_b.image_url}
          onTypingDone={() => flushPendingTurn(streamingTurn.turn_number, streamingTurn.speaker)}
          turnComplete={pendingTurnLogs.some(
            (t) =>
              t.turn_number === streamingTurn.turn_number && t.speaker === streamingTurn.speaker,
          )}
        />
      )}

      {streaming &&
        !streamingTurn &&
        !debateShowAll &&
        (nextSpeaker ? (
          <div
            className={`flex ${nextSpeaker === 'agent_b' ? 'justify-end' : 'justify-start'} px-2`}
          >
            <div className="flex items-center gap-2 px-4 py-2 rounded-2xl bg-bg-surface border border-border text-sm text-text-muted">
              <span className="font-medium text-text">
                {nextSpeaker === 'agent_a' ? match.agent_a.name : match.agent_b.name}
              </span>
              <span className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </span>
            </div>
          </div>
        ) : (
          <div className="text-center text-xs text-primary animate-pulse py-2">토론 진행 중...</div>
        ))}

      <div ref={bottomRef} />
      <ScrollToTop />
    </div>
  );
}
