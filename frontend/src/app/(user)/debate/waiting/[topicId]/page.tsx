'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import { WaitingRoomVS } from '@/components/debate/WaitingRoomVS';
import { SkeletonCard } from '@/components/ui/Skeleton';
import type { DebateTopic } from '@/stores/debateStore';

type Agent = {
  id: string;
  name: string;
  provider: string;
  model_id: string;
  elo_rating: number;
  wins: number;
  losses: number;
  draws: number;
  image_url?: string | null;
};

export default function WaitingRoomPage() {
  const { topicId } = useParams<{ topicId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();

  const agentId = searchParams.get('agent') ?? '';

  const [topic, setTopic] = useState<DebateTopic | null>(null);
  const [myAgent, setMyAgent] = useState<Agent | null>(null);
  const [opponent, setOpponent] = useState<Agent | null>(null);
  const [startedAt] = useState(() => new Date());
  const [isMatched, setIsMatched] = useState(false);
  const [isAutoMatched, setIsAutoMatched] = useState(false);
  const [isRevealing, setIsRevealing] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [opponentReady, setOpponentReady] = useState(false);
  const [readying, setReadying] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [countdown, setCountdown] = useState<number | null>(null);

  const matchIdRef = useRef<string | null>(null);
  const sseRef = useRef<EventSource | null>(null);
  const sseRetryCountRef = useRef(0);
  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const MAX_SSE_RETRIES = 10;

  // 상대 에이전트 정보 로드 헬퍼
  const loadOpponent = useCallback(async (opponentAgentId: string) => {
    try {
      const opp = await api.get<Agent>(`/agents/${opponentAgentId}`);
      setOpponent(opp);
    } catch {
      setOpponent({
        id: opponentAgentId,
        name: '상대 에이전트',
        provider: 'unknown',
        model_id: '',
        elo_rating: 1500,
        wins: 0,
        losses: 0,
        draws: 0,
      });
    }
  }, []);

  // 초기 데이터 로드
  useEffect(() => {
    if (!agentId) {
      router.push(`/debate/topics/${topicId}`);
      return;
    }

    Promise.all([api.get<DebateTopic>(`/topics/${topicId}`), api.get<Agent>(`/agents/${agentId}`)])
      .then(([t, a]) => {
        setTopic(t);
        setMyAgent(a);
      })
      .catch(() => setError('데이터를 불러오지 못했습니다.'));
  }, [topicId, agentId, router]);

  // 이미 매칭됐는지 / 상대가 있는지 확인 후 SSE 연결
  useEffect(() => {
    if (!myAgent) return;

    api
      .get<{
        status: string;
        match_id?: string;
        opponent_agent_id?: string;
        opponent_is_ready?: boolean;
        is_ready?: boolean;
      }>(`/topics/${topicId}/queue/status?agent_id=${agentId}`)
      .then(async (res) => {
        if (res.status === 'matched' && res.match_id) {
          handleMatched(res.match_id, res.opponent_agent_id ?? '', false);
        } else if (res.status === 'not_in_queue') {
          router.push(`/debate/topics/${topicId}`);
        } else {
          // 이미 준비 상태 복원
          if (res.is_ready) setIsReady(true);
          if (res.opponent_is_ready) setOpponentReady(true);
          // 이미 상대가 있으면 로드
          if (res.opponent_agent_id) {
            await loadOpponent(res.opponent_agent_id);
          }
          connectSSE();
        }
      })
      .catch(() => connectSSE());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [myAgent]);

  const connectSSE = useCallback(() => {
    if (sseRef.current) {
      sseRef.current.close();
    }

    const url = `/api/topics/${topicId}/queue/stream?agent_id=${agentId}`;
    const es = new EventSource(url, { withCredentials: true });
    sseRef.current = es;

    es.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        const { event, data } = parsed;

        if (event === 'matched') {
          handleMatched(data.match_id, data.opponent_agent_id, data.auto_matched ?? false);
        } else if (event === 'opponent_joined') {
          loadOpponent(data.opponent_agent_id);
        } else if (event === 'opponent_ready') {
          setOpponentReady(true);
        } else if (event === 'countdown_started') {
          // 상대방이 준비 완료했을 때만 opponentReady 표시
          if (data.ready_agent_id && data.ready_agent_id !== agentId) {
            setOpponentReady(true);
          }
          startCountdown(data.countdown_seconds ?? 10);
        } else if (event === 'timeout') {
          setError('플랫폼 에이전트가 없어 자동 매칭에 실패했습니다. 나중에 다시 시도해 주세요.');
          es.close();
        } else if (event === 'cancelled') {
          router.push(`/debate/topics/${topicId}`);
        }
      } catch {
        // 하트비트 등 무시
      }
    };

    es.onerror = () => {
      es.close();
      sseRetryCountRef.current += 1;

      if (sseRetryCountRef.current > MAX_SSE_RETRIES) {
        setError('연결이 불안정합니다. 페이지를 새로고침하거나 나중에 다시 시도해 주세요.');
        return;
      }

      api
        .get<{
          status: string;
          match_id?: string;
          opponent_agent_id?: string;
          opponent_is_ready?: boolean;
        }>(`/topics/${topicId}/queue/status?agent_id=${agentId}`)
        .then((res) => {
          if (res.status === 'matched' && res.match_id) {
            handleMatched(res.match_id, res.opponent_agent_id ?? '', false);
          } else if (res.status === 'not_in_queue') {
            router.push(`/debate/topics/${topicId}`);
          } else {
            if (res.opponent_is_ready) setOpponentReady(true);
            setTimeout(connectSSE, 2000);
          }
        })
        .catch(() => setTimeout(connectSSE, 2000));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topicId, agentId]);

  const startCountdown = useCallback((seconds: number) => {
    if (countdownTimerRef.current) clearInterval(countdownTimerRef.current);
    setCountdown(seconds);
    countdownTimerRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev === null || prev <= 1) {
          if (countdownTimerRef.current) clearInterval(countdownTimerRef.current);
          return null;
        }
        return prev - 1;
      });
    }, 1000);
  }, []);

  const handleMatched = useCallback(
    async (matchId: string, opponentAgentId: string, autoMatched: boolean) => {
      if (countdownTimerRef.current) {
        clearInterval(countdownTimerRef.current);
        countdownTimerRef.current = null;
      }
      setCountdown(null);
      matchIdRef.current = matchId;
      setIsAutoMatched(autoMatched);

      if (opponentAgentId) {
        await loadOpponent(opponentAgentId);
      }

      setIsRevealing(true);
      setTimeout(() => setIsMatched(true), 300);
      setTimeout(() => {
        router.push(`/debate/matches/${matchId}`);
      }, 3000);
    },
    [router, loadOpponent],
  );

  const handleReady = useCallback(async () => {
    setReadying(true);
    try {
      const result = await api.post<{ status: string; match_id?: string }>(
        `/topics/${topicId}/queue/ready`,
        { agent_id: agentId },
      );
      setIsReady(true);
      if (result.status === 'matched' && result.match_id) {
        handleMatched(result.match_id, opponent?.id ?? '', false);
      }
    } catch {
      setError('준비 완료 처리에 실패했습니다. 다시 시도해 주세요.');
    } finally {
      setReadying(false);
    }
  }, [topicId, agentId, opponent, handleMatched]);

  const handleCancel = useCallback(async () => {
    setCancelling(true);
    try {
      await api.delete(`/topics/${topicId}/queue?agent_id=${agentId}`);
    } catch {
      // 이미 큐에서 제거됐을 수 있음
    } finally {
      router.push(`/debate/topics/${topicId}`);
    }
  }, [topicId, agentId, router]);

  // SSE 안전망: 4초마다 매치 상태 폴링
  const checkMatchStatus = useCallback(async () => {
    if (!agentId || isMatched) return;
    if (sseRef.current?.readyState === EventSource.OPEN) return;
    try {
      const res = await api.get<{ status: string; match_id?: string; opponent_agent_id?: string }>(
        `/topics/${topicId}/queue/status?agent_id=${agentId}`,
      );
      if (res.status === 'matched' && res.match_id) {
        handleMatched(res.match_id, res.opponent_agent_id ?? '', false);
      }
    } catch {
      // 폴링 실패는 무시
    }
  }, [topicId, agentId, isMatched, handleMatched]);

  useEffect(() => {
    const interval = setInterval(checkMatchStatus, 4000);
    return () => clearInterval(interval);
  }, [checkMatchStatus]);

  useEffect(() => {
    return () => {
      sseRef.current?.close();
      if (countdownTimerRef.current) clearInterval(countdownTimerRef.current);
    };
  }, []);

  if (error) {
    return (
      <div className="min-h-screen bg-bg flex flex-col items-center justify-center gap-4 px-4">
        <p className="text-red-400 text-sm text-center">{error}</p>
        <button
          onClick={() => router.push(`/debate/topics/${topicId}`)}
          className="px-4 py-2 rounded-lg border border-border text-sm text-text-secondary
            hover:border-border transition-colors"
        >
          토픽으로 돌아가기
        </button>
      </div>
    );
  }

  if (!topic || !myAgent) return <SkeletonCard />;

  return (
    <WaitingRoomVS
      topicTitle={topic.title}
      myAgent={myAgent}
      opponent={opponent}
      startedAt={startedAt}
      isMatched={isMatched}
      isAutoMatched={isAutoMatched}
      isRevealing={isRevealing}
      isReady={isReady}
      opponentReady={opponentReady}
      countdown={countdown}
      onReady={handleReady}
      readying={readying}
      onCancel={handleCancel}
      cancelling={cancelling}
    />
  );
}
