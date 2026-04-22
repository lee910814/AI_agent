# debateStore

> 하위 호환성 유지를 위한 re-export 파사드 겸 통합 Zustand 스토어 — 토픽·매치·랭킹 상태를 단일 인터페이스로 제공

**파일 경로:** `frontend/src/stores/debateStore.ts`
**최종 수정일:** 2026-03-24

---

## 개요

`debateStore.ts`는 두 가지 역할을 동시에 수행합니다.

1. **Re-export 파사드** — 실제 구현이 분산된 세 개의 분리 스토어(`debateTopicStore`, `debateMatchStore`, `debateRankingStore`)를 단일 진입점으로 노출합니다.
2. **통합 Zustand 스토어** — `useDebateStore`라는 단일 스토어를 유지하여 기존 코드와의 하위 호환성을 보장합니다.

> 신규 코드 작성 시에는 분리된 세 스토어를 직접 import하는 것을 권장합니다.

---

## 상태 (State)

### 토픽 관련

| 필드 | 타입 | 초기값 | 설명 |
|---|---|---|---|
| `topics` | `DebateTopic[]` | `[]` | 전체 토픽 목록 |
| `topicsTotal` | `number` | `0` | 전체 토픽 수 (페이지네이션 용) |
| `popularTopics` | `DebateTopic[]` | `[]` | 인기 토픽 목록 (최근 1주 기준) |
| `popularTopicsTotal` | `number` | `0` | 인기 토픽 수 |
| `topicsLoading` | `boolean` | `false` | 토픽 조회 로딩 여부 |

### 매치 관련

| 필드 | 타입 | 초기값 | 설명 |
|---|---|---|---|
| `currentMatch` | `DebateMatch \| null` | `null` | 현재 관전 중인 매치 |
| `turns` | `TurnLog[]` | `[]` | 완료된 턴 목록 (turn_number 오름차순) |
| `streamingTurn` | `StreamingTurn \| null` | `null` | 현재 SSE 스트리밍 중인 턴 |
| `pendingStreamingTurn` | `StreamingTurn \| null` | `null` | A 검토 중 B가 동시 스트리밍될 때 버퍼링되는 B 청크 |
| `pendingTurnLogs` | `TurnLog[]` | `[]` | SSE `turn` 이벤트가 도착했지만 타이핑 애니메이션이 진행 중인 턴 버퍼 |
| `turnReviews` | `TurnReview[]` | `[]` | LLM 검토 결과 목록 |
| `matchLoading` | `boolean` | `false` | 매치 조회 로딩 여부 |
| `streaming` | `boolean` | `false` | SSE 스트리밍 활성 여부 |
| `nextSpeaker` | `string \| null` | `null` | A 턴 완료 후 B 청크 대기 구간에서 표시할 다음 화자 |
| `replayMode` | `boolean` | `false` | 리플레이 모드 활성 여부 |
| `replayIndex` | `number` | `0` | 현재 리플레이 중인 턴 인덱스 (-1: 시작 전) |
| `replaySpeed` | `number` | `1` | 리플레이 재생 속도 (0.5 / 1 / 2) |
| `replayPlaying` | `boolean` | `false` | 리플레이 자동 재생 여부 |
| `replayTyping` | `boolean` | `false` | 타이핑 애니메이션 진행 중 여부 (true이면 tick 대기) |
| `debateShowAll` | `boolean` | `false` | 완료 매치 전체 보기 여부 — false: 턴 숨김, true: 전체 표시 |
| `predictionStats` | `PredictionStats \| null` | `null` | 예측투표 통계 |
| `predictionLoading` | `boolean` | `false` | 예측투표 통계 조회 로딩 여부 |
| `waitingAgent` | `boolean` | `false` | 로컬 에이전트 WebSocket 연결 대기 중 |
| `creditInsufficient` | `boolean` | `false` | 크레딧 부족으로 토론 중단 상태 |
| `matchVoidReason` | `string \| null` | `null` | 매치 무효화 사유 |
| `judgeIntro` | `string \| null` | `null` | Judge 소개 문구 (SSE 이벤트 수신) |
| `turnSearching` | `Record<number, { speaker: string; query: string }>` | `{}` | DuckDuckGo 근거 검색 중인 턴 번호 → 화자/쿼리 |

### 랭킹 관련

| 필드 | 타입 | 초기값 | 설명 |
|---|---|---|---|
| `ranking` | `RankingEntry[]` | `[]` | 에이전트 랭킹 목록 |
| `rankingLoading` | `boolean` | `false` | 랭킹 조회 로딩 여부 |
| `featuredMatches` | `DebateMatch[]` | `[]` | 하이라이트(주목) 매치 목록 |

---

## 액션 (Actions)

### 토픽 액션

| 액션명 | 파라미터 | 설명 |
|---|---|---|
| `fetchTopics` | `params?: { status?, sort?, page?, pageSize? }` | 토픽 목록 조회 (페이지네이션 지원, page > 1이면 기존 목록에 append) |
| `fetchPopularTopics` | — | 인기 토픽 10개 조회 (`sort=popular_week`) |
| `createTopic` | `payload: TopicCreatePayload` | 토픽 생성 후 목록 prepend |
| `updateTopic` | `topicId: string, payload: Partial<TopicCreatePayload>` | 토픽 수정 (topics, popularTopics 동시 반영) |
| `deleteTopic` | `topicId: string` | 토픽 삭제 후 목록 및 카운터 갱신 |
| `joinQueue` | `topicId, agentId, password?` | 특정 토픽 큐에 에이전트 등록 |
| `leaveQueue` | `topicId, agentId` | 특정 토픽 큐에서 에이전트 이탈 |
| `randomMatch` | `agentId: string` | 랜덤 매치 신청 |

### 매치 액션

| 액션명 | 파라미터 | 설명 |
|---|---|---|
| `fetchMatch` | `matchId: string` | 매치 정보 조회 (동일 매치 로딩 중 중복 호출 방지, 새 매치 로드 시에만 상태 초기화) |
| `fetchTurns` | `matchId: string` | 완료 턴 목록 조회 (turn_number 오름차순 정렬) |
| `addTurnFromSSE` | `turn: TurnLog` | SSE `turn` 이벤트 수신 시 turns 또는 pendingTurnLogs에 추가 |
| `flushPendingTurn` | `turn_number: number, speaker: string` | `StreamingTurnBubble` 타이핑 완료 시 pendingTurnLogs → turns 이동 |
| `appendChunk` | `turn_number, speaker, chunk` | SSE 스트리밍 청크 수신 시 streamingTurn 또는 pendingStreamingTurn에 append |
| `clearStreamingTurn` | — | 스트리밍 종료 시 streamingTurn 초기화 + pendingTurnLogs를 turns에 병합 |
| `setStreaming` | `v: boolean` | 스트리밍 활성 여부 설정 |
| `addTurnReview` | `review: TurnReview` | LLM 검토 결과 추가 (중복 시 최신값으로 교체) |
| `patchTurnEvidence` | `turn_number, speaker, evidence` | 특정 턴의 근거(evidence) 패치 |
| `startReplay` | — | 리플레이 모드 시작 (replayIndex: -1, replayPlaying: true) |
| `stopReplay` | — | 리플레이 모드 종료 (debateShowAll: true로 전환) |
| `setReplaySpeed` | `speed: number` | 리플레이 속도 설정 (0.5 / 1 / 2) |
| `tickReplay` | — | 리플레이 한 턴 진행 (replayTyping이 true이면 건너뜀) |
| `setReplayTyping` | `v: boolean` | 타이핑 애니메이션 진행 중 여부 설정 |
| `setDebateShowAll` | `v: boolean` | 완료 매치 전체 보기 토글 |
| `setWaitingAgent` | `v: boolean` | 로컬 에이전트 대기 상태 설정 |
| `setCreditInsufficient` | `v: boolean` | 크레딧 부족 상태 설정 |
| `setMatchVoidReason` | `reason: string \| null` | 매치 무효화 사유 설정 |
| `setJudgeIntro` | `intro: string \| null` | Judge 소개 문구 설정 |
| `setTurnSearching` | `turnNumber, speaker, query` | 특정 턴 근거 검색 중 상태 기록 |
| `clearTurnSearching` | `turnNumber: number` | 특정 턴 근거 검색 완료 처리 |
| `submitPrediction` | `matchId, prediction: 'a_win' \| 'b_win' \| 'draw'` | 예측투표 제출 후 통계 갱신 |
| `fetchPredictionStats` | `matchId: string` | 예측투표 통계 조회 |

### 랭킹 액션

| 액션명 | 파라미터 | 설명 |
|---|---|---|
| `fetchRanking` | `seasonId?: string` | 에이전트 랭킹 조회 (seasonId 없으면 전체 누적, 있으면 시즌 랭킹) |
| `fetchFeatured` | `limit?: number` | 하이라이트 매치 조회 (기본값: 5) |

---

## 내부 설계 — 이중 스트리밍 버퍼

OptimizedDebateOrchestrator에서 A 검토와 B 실행을 병렬 수행할 때 두 에이전트의 SSE 청크가 동시에 도달합니다. 이를 처리하는 버퍼 계층이 세 단계로 구성됩니다.

```
SSE 청크 도착
    ↓
streamingTurn (현재 타이핑 활성) → 이어 붙이기
    ↓ (다른 화자 청크)
pendingStreamingTurn (대기 버퍼)
    ↓ (turn SSE 이벤트 도착)
pendingTurnLogs → flushPendingTurn() → turns
```

---

## 주요 사용처

| 파일 | 사용 목적 |
|---|---|
| `components/debate/DebateViewer.tsx` | 턴 목록, 스트리밍, 리플레이 상태 구독 |
| `components/debate/ReplayControls.tsx` | 리플레이 재생/일시정지/속도 제어 |
| `hooks/useDebateStream.ts` | SSE 이벤트 수신 후 스토어 액션 호출 |
| `hooks/useDebateReplay.ts` | 리플레이 interval 관리 및 tickReplay 호출 |
| `app/(user)/debate/[id]/page.tsx` | 매치 페이지 진입 시 fetchMatch 호출 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
| 2026-03-09 | patchTurnEvidence, setTurnSearching/clearTurnSearching 액션 추가 (출처 검증 시스템) |
| 2026-02-26 | 리플레이 모드(startReplay/stopReplay/tickReplay), 예측투표(submitPrediction/fetchPredictionStats) 추가 |
| 2026-02-25 | turnReviews, addTurnReview, LLM 검토 관련 SSE 이벤트 상태 추가 |
