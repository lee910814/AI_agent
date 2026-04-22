import { create } from 'zustand';
import { api } from '@/lib/api';
import type {
  DebateMatch,
  TurnLog,
  TurnReview,
  StreamingTurn,
  PredictionStats,
} from '@/types/debate';

type DebateMatchState = {
  currentMatch: DebateMatch | null;
  turns: TurnLog[];
  streamingTurn: StreamingTurn | null;
  // 최적화 모드에서 A 검토 중 B가 동시 스트리밍될 때 B 청크를 버퍼링
  pendingStreamingTurn: StreamingTurn | null;
  // turn SSE 이벤트가 도착했지만 StreamingTurnBubble 타이핑이 아직 진행 중인 턴을 보관
  pendingTurnLogs: TurnLog[];
  turnReviews: TurnReview[];
  matchLoading: boolean;
  streaming: boolean;
  nextSpeaker: string | null; // A turn 완료 후 B 청크 대기 구간에서 표시할 다음 화자
  // 리플레이 상태
  replayMode: boolean;
  replayIndex: number;
  replaySpeed: number; // 0.5 | 1 | 2
  replayPlaying: boolean;
  replayTyping: boolean; // 타이핑 애니메이션 진행 중 여부 (true이면 tick 대기)
  // 완료된 매치 전체 보기 여부 — false: 턴 숨김(기본), true: 전체 표시
  // Scorecard/SummaryReport 노출 제어에도 사용
  debateShowAll: boolean;
  predictionStats: PredictionStats | null;
  predictionLoading: boolean;
  // SSE 특수 이벤트 상태
  waitingAgent: boolean; // 에이전트 WebSocket 연결 대기 중
  creditInsufficient: boolean; // 크레딧 부족으로 토론 중단
  matchVoidReason: string | null; // 매치 무효화 사유
  fetchMatch: (matchId: string) => Promise<void>;
  fetchTurns: (matchId: string) => Promise<void>;
  addTurnFromSSE: (turn: TurnLog) => void;
  // StreamingTurnBubble 타이핑 완료 후 호출 — pendingTurnLogs에 있던 턴을 turns로 이동
  flushPendingTurn: (turn_number: number, speaker: string) => void;
  appendChunk: (turn_number: number, speaker: string, chunk: string) => void;
  clearStreamingTurn: () => void;
  setStreaming: (v: boolean) => void;
  addTurnReview: (review: TurnReview) => void;
  // 리플레이 액션
  startReplay: () => void;
  stopReplay: () => void;
  setReplaySpeed: (speed: number) => void;
  tickReplay: () => void;
  setReplayTyping: (v: boolean) => void;
  setDebateShowAll: (v: boolean) => void;
  setWaitingAgent: (v: boolean) => void;
  setCreditInsufficient: (v: boolean) => void;
  setMatchVoidReason: (reason: string | null) => void;
  submitPrediction: (matchId: string, prediction: 'a_win' | 'b_win' | 'draw') => Promise<void>;
  fetchPredictionStats: (matchId: string) => Promise<void>;
};

export const useDebateMatchStore = create<DebateMatchState>((set, get) => ({
  currentMatch: null,
  turns: [],
  streamingTurn: null,
  pendingStreamingTurn: null,
  pendingTurnLogs: [],
  turnReviews: [],
  matchLoading: false,
  streaming: false,
  nextSpeaker: null,
  replayMode: false,
  replayIndex: 0,
  replaySpeed: 1,
  replayPlaying: false,
  replayTyping: false,
  debateShowAll: false,
  predictionStats: null,
  predictionLoading: false,
  waitingAgent: false,
  creditInsufficient: false,
  matchVoidReason: null,
  fetchMatch: async (matchId) => {
    // 동일 매치 로딩 중 중복 호출 방지 (빠른 새로고침 시 DB 커넥션 풀 고갈 방지)
    if (get().matchLoading) return;
    // 새 매치 로드 시에만 상태 초기화 — 동일 매치 재조회(SSE finished, 폴링)는 기존 상태 유지
    // 동일 매치 리셋 시 debateShowAll이 false로 돌아가 completed 상태에서 결과창이 비워지는 버그 방지
    const isSameMatch = get().currentMatch?.id === matchId;
    set({
      matchLoading: true,
      ...(!isSameMatch && {
        turns: [],
        streamingTurn: null,
        pendingStreamingTurn: null,
        pendingTurnLogs: [],
        turnReviews: [],
        replayMode: false,
        replayPlaying: false,
        replayIndex: -1,
        replayTyping: false,
        debateShowAll: false,
        predictionStats: null,
        waitingAgent: false,
        creditInsufficient: false,
        matchVoidReason: null,
      }),
    });
    try {
      const data = await api.get<DebateMatch>(`/matches/${matchId}`);
      set({ currentMatch: data });
    } catch (err) {
      console.error('Failed to fetch match:', err);
    } finally {
      set({ matchLoading: false });
    }
  },
  fetchTurns: async (matchId) => {
    try {
      const data = await api.get<TurnLog[]>(`/matches/${matchId}/turns`);
      // turn_number 오름차순, 동점 시 agent_a 먼저 (백엔드 ORDER BY 보완)
      const sorted = data.sort(
        (a, b) =>
          a.turn_number - b.turn_number ||
          (a.speaker === 'agent_a' ? -1 : 1) - (b.speaker === 'agent_a' ? -1 : 1),
      );
      set({ turns: sorted });
    } catch (err) {
      console.error('Failed to fetch turns:', err);
    }
  },
  addTurnFromSSE: (turn) => {
    set((s) => {
      // StreamingTurnBubble이 같은 (turn_number, speaker)를 타이핑 중이면
      // 타이핑이 끝날 때까지 turns에 추가하지 않고 pendingTurnLogs에 버퍼링
      const isCurrentStreaming =
        s.streamingTurn?.turn_number === turn.turn_number &&
        s.streamingTurn?.speaker === turn.speaker;

      if (isCurrentStreaming) {
        // 이미 pending에 같은 턴이 있으면 최신 데이터로 교체, 없으면 추가
        const alreadyPending = s.pendingTurnLogs.some(
          (t) => t.turn_number === turn.turn_number && t.speaker === turn.speaker,
        );
        return {
          pendingTurnLogs: alreadyPending
            ? s.pendingTurnLogs.map((t) =>
                t.turn_number === turn.turn_number && t.speaker === turn.speaker ? turn : t,
              )
            : [...s.pendingTurnLogs, turn],
          // streamingTurn은 유지 — 타이핑이 계속 진행되도록
        };
      }

      // pendingStreamingTurn과 동일한 (turn_number, speaker) — B 청크가 버퍼링 중인데
      // B의 turn 이벤트가 도착한 경우. streamingTurn(A)이 아직 타이핑 중이므로
      // 교체하지 않고 pendingTurnLogs에 버퍼링. flushPendingTurn(A)이 끝날 때 승격.
      const isPendingStreaming =
        s.pendingStreamingTurn?.turn_number === turn.turn_number &&
        s.pendingStreamingTurn?.speaker === turn.speaker;

      if (isPendingStreaming) {
        const alreadyPending = s.pendingTurnLogs.some(
          (t) => t.turn_number === turn.turn_number && t.speaker === turn.speaker,
        );
        return {
          pendingTurnLogs: alreadyPending
            ? s.pendingTurnLogs.map((t) =>
                t.turn_number === turn.turn_number && t.speaker === turn.speaker ? turn : t,
              )
            : [...s.pendingTurnLogs, turn],
        };
      }

      // 스트리밍 없는 상태 — turns에 즉시 추가 (pendingStreamingTurn이 있으면 승격)
      const nextStreaming = s.pendingStreamingTurn;
      const exists = s.turns.some(
        (t) => t.turn_number === turn.turn_number && t.speaker === turn.speaker,
      );

      if (exists) {
        return {
          turns: s.turns.map((t) =>
            t.turn_number === turn.turn_number && t.speaker === turn.speaker ? turn : t,
          ),
          streamingTurn: nextStreaming,
          pendingStreamingTurn: null,
          nextSpeaker: turn.speaker === 'agent_a' ? 'agent_b' : 'agent_a',
        };
      }
      return {
        turns: [...s.turns, turn],
        streamingTurn: nextStreaming,
        pendingStreamingTurn: null,
        nextSpeaker: turn.speaker === 'agent_a' ? 'agent_b' : 'agent_a',
      };
    });
  },
  flushPendingTurn: (turn_number, speaker) => {
    set((s) => {
      const pending = s.pendingTurnLogs.find(
        (t) => t.turn_number === turn_number && t.speaker === speaker,
      );
      if (!pending) {
        // pending이 없어도 streamingTurn/pendingStreamingTurn 승격은 수행
        const isCurrentStreaming =
          s.streamingTurn?.turn_number === turn_number && s.streamingTurn?.speaker === speaker;
        if (!isCurrentStreaming) return {};
        return {
          streamingTurn: s.pendingStreamingTurn,
          pendingStreamingTurn: null,
          nextSpeaker: speaker === 'agent_a' ? 'agent_b' : 'agent_a',
        };
      }

      const remainingPendingLogs = s.pendingTurnLogs.filter(
        (t) => !(t.turn_number === turn_number && t.speaker === speaker),
      );
      const exists = s.turns.some((t) => t.turn_number === turn_number && t.speaker === speaker);
      const updatedTurns = exists
        ? s.turns.map((t) => (t.turn_number === turn_number && t.speaker === speaker ? pending : t))
        : [...s.turns, pending];

      return {
        turns: updatedTurns,
        pendingTurnLogs: remainingPendingLogs,
        streamingTurn: s.pendingStreamingTurn,
        pendingStreamingTurn: null,
        nextSpeaker: speaker === 'agent_a' ? 'agent_b' : 'agent_a',
      };
    });
  },
  addTurnReview: (review) => {
    set((s) => {
      const exists = s.turnReviews.some(
        (r) => r.turn_number === review.turn_number && r.speaker === review.speaker,
      );
      if (exists) {
        return {
          turnReviews: s.turnReviews.map((r) =>
            r.turn_number === review.turn_number && r.speaker === review.speaker ? review : r,
          ),
        };
      }
      return { turnReviews: [...s.turnReviews, review] };
    });
  },
  appendChunk: (turn_number, speaker, chunk) => {
    set((s) => {
      // 현재 스트리밍 중인 화자와 같은 턴이면 이어 붙이기
      if (s.streamingTurn?.turn_number === turn_number && s.streamingTurn?.speaker === speaker) {
        return { streamingTurn: { ...s.streamingTurn, raw: s.streamingTurn.raw + chunk } };
      }
      // 다른 화자의 chunk가 왔고 현재 streamingTurn이 활성 상태 — pending 버퍼에 쌓기
      if (s.streamingTurn) {
        if (
          s.pendingStreamingTurn?.turn_number === turn_number &&
          s.pendingStreamingTurn?.speaker === speaker
        ) {
          return {
            pendingStreamingTurn: {
              ...s.pendingStreamingTurn,
              raw: s.pendingStreamingTurn.raw + chunk,
            },
          };
        }
        return { pendingStreamingTurn: { turn_number, speaker, raw: chunk } };
      }
      // streamingTurn 없음 — 바로 활성화
      return { streamingTurn: { turn_number, speaker, raw: chunk }, nextSpeaker: null };
    });
  },
  clearStreamingTurn: () =>
    set((s) => {
      // 대기 중인 pendingTurnLogs를 turns에 병합 — finished/error 이벤트 시 손실 방지
      const logsToFlush = s.pendingTurnLogs;
      if (logsToFlush.length === 0) {
        return {
          streamingTurn: null,
          pendingStreamingTurn: null,
          pendingTurnLogs: [],
          nextSpeaker: null,
        };
      }
      let updatedTurns = [...s.turns];
      for (const pending of logsToFlush) {
        const exists = updatedTurns.some(
          (t) => t.turn_number === pending.turn_number && t.speaker === pending.speaker,
        );
        if (exists) {
          updatedTurns = updatedTurns.map((t) =>
            t.turn_number === pending.turn_number && t.speaker === pending.speaker ? pending : t,
          );
        } else {
          updatedTurns.push(pending);
        }
      }
      return {
        turns: updatedTurns,
        streamingTurn: null,
        pendingStreamingTurn: null,
        pendingTurnLogs: [],
        nextSpeaker: null,
      };
    }),
  setStreaming: (v) => set({ streaming: v }),
  // replayIndex -1: 재생 시작 시 0턴도 아직 안 보임. 첫 tick에서 0으로 올라가 첫 턴 등장
  startReplay: () =>
    set({
      replayMode: true,
      replayIndex: -1,
      replayPlaying: true,
      replayTyping: false,
      debateShowAll: false,
    }),
  stopReplay: () =>
    set({
      replayMode: false,
      replayPlaying: false,
      replayIndex: -1,
      replayTyping: false,
      debateShowAll: true,
    }),
  setReplaySpeed: (speed) => set({ replaySpeed: speed }),
  tickReplay: () => {
    const { replayIndex, turns, replayTyping } = get();
    // 타이핑 애니메이션 진행 중이면 tick 건너뜀
    if (replayTyping) return;
    const maxIndex = turns.length - 1;
    if (replayIndex >= maxIndex) {
      set({ replayPlaying: false });
    } else {
      set({ replayIndex: replayIndex + 1 });
    }
  },
  setReplayTyping: (v) => set({ replayTyping: v }),
  setDebateShowAll: (v) => set({ debateShowAll: v }),
  setWaitingAgent: (v) => set({ waitingAgent: v }),
  setCreditInsufficient: (v) => set({ creditInsufficient: v }),
  setMatchVoidReason: (reason) => set({ matchVoidReason: reason }),
  submitPrediction: async (matchId, prediction) => {
    await api.post(`/matches/${matchId}/predictions`, { prediction });
    // 제출 후 통계 갱신
    const stats = await api.get<PredictionStats>(`/matches/${matchId}/predictions`);
    set({ predictionStats: stats });
  },
  fetchPredictionStats: async (matchId) => {
    set({ predictionLoading: true });
    try {
      const stats = await api.get<PredictionStats>(`/matches/${matchId}/predictions`);
      set({ predictionStats: stats });
    } catch {
      // 로그인 안 된 경우 등 무시
    } finally {
      set({ predictionLoading: false });
    }
  },
}));

export type { DebateMatchState };
