# debateMatchStore

> 매치 관전·SSE 스트리밍·리플레이·예측투표 상태를 담당하는 분리 Zustand 스토어

**파일 경로:** `frontend/src/stores/debateMatchStore.ts`
**최종 수정일:** 2026-03-24

---

## 개요

`debateMatchStore`는 기존 `debateStore.ts`에서 매치 관련 상태를 추출해 분리한 스토어입니다. `debateStore.ts`의 `useDebateStore`는 하위 호환성을 위해 이 스토어의 상태/액션을 통합 재공개합니다.

신규 코드 작성 시에는 `useDebateMatchStore`를 직접 사용하는 것을 권장합니다.

---

## 상태 (State)

| 필드 | 타입 | 초기값 | 설명 |
|---|---|---|---|
| `currentMatch` | `DebateMatch \| null` | `null` | 현재 관전 중인 매치 |
| `turns` | `TurnLog[]` | `[]` | 완료된 턴 목록 |
| `streamingTurn` | `StreamingTurn \| null` | `null` | 현재 SSE 스트리밍 중인 턴 |
| `pendingStreamingTurn` | `StreamingTurn \| null` | `null` | 최적화 모드에서 A 검토 중 도착한 B 청크 버퍼 |
| `pendingTurnLogs` | `TurnLog[]` | `[]` | 타이핑 애니메이션 대기 중인 완료 턴 버퍼 |
| `turnReviews` | `TurnReview[]` | `[]` | LLM 검토 결과 목록 |
| `matchLoading` | `boolean` | `false` | 매치 조회 로딩 여부 |
| `streaming` | `boolean` | `false` | SSE 스트리밍 활성 여부 |
| `nextSpeaker` | `string \| null` | `null` | 다음 발화 예정 화자 |
| `replayMode` | `boolean` | `false` | 리플레이 모드 활성 여부 |
| `replayIndex` | `number` | `0` | 현재 리플레이 턴 인덱스 |
| `replaySpeed` | `number` | `1` | 재생 속도 (0.5 / 1 / 2) |
| `replayPlaying` | `boolean` | `false` | 자동 재생 여부 |
| `replayTyping` | `boolean` | `false` | 타이핑 애니메이션 진행 여부 |
| `debateShowAll` | `boolean` | `false` | 완료 매치 전체 보기 여부 |
| `predictionStats` | `PredictionStats \| null` | `null` | 예측투표 통계 |
| `predictionLoading` | `boolean` | `false` | 예측투표 통계 로딩 여부 |
| `waitingAgent` | `boolean` | `false` | 로컬 에이전트 WebSocket 연결 대기 중 |
| `creditInsufficient` | `boolean` | `false` | 크레딧 부족으로 토론 중단 |
| `matchVoidReason` | `string \| null` | `null` | 매치 무효화 사유 |

---

## 액션 (Actions)

| 액션명 | 파라미터 | 설명 |
|---|---|---|
| `fetchMatch` | `matchId: string` | 매치 정보 조회. 동일 매치 중복 호출 방지, 새 매치 진입 시에만 상태 초기화 |
| `fetchTurns` | `matchId: string` | 완료 턴 목록 조회 및 정렬 |
| `addTurnFromSSE` | `turn: TurnLog` | SSE `turn` 이벤트 처리 — 스트리밍 중이면 pendingTurnLogs에 버퍼링 |
| `flushPendingTurn` | `turn_number: number, speaker: string` | 타이핑 완료 콜백 — pendingTurnLogs → turns 이동 및 pendingStreamingTurn 승격 |
| `appendChunk` | `turn_number, speaker, chunk` | SSE 청크 수신 — streamingTurn 또는 pendingStreamingTurn에 append |
| `clearStreamingTurn` | — | 스트리밍 종료 처리 + pendingTurnLogs 병합 |
| `setStreaming` | `v: boolean` | 스트리밍 플래그 설정 |
| `addTurnReview` | `review: TurnReview` | LLM 검토 결과 추가 |
| `startReplay` | — | 리플레이 시작 (replayIndex: -1) |
| `stopReplay` | — | 리플레이 종료 (debateShowAll: true) |
| `setReplaySpeed` | `speed: number` | 재생 속도 변경 |
| `tickReplay` | — | 한 턴 진행 (타이핑 중이면 건너뜀) |
| `setReplayTyping` | `v: boolean` | 타이핑 애니메이션 상태 설정 |
| `setDebateShowAll` | `v: boolean` | 전체 보기 토글 |
| `setWaitingAgent` | `v: boolean` | 에이전트 대기 상태 설정 |
| `setCreditInsufficient` | `v: boolean` | 크레딧 부족 상태 설정 |
| `setMatchVoidReason` | `reason: string \| null` | 매치 무효화 사유 설정 |
| `submitPrediction` | `matchId, prediction` | 예측투표 제출 후 통계 자동 갱신 |
| `fetchPredictionStats` | `matchId: string` | 예측투표 통계 조회 |

---

## addTurnFromSSE 처리 로직

`addTurnFromSSE`는 동시 스트리밍 상황에서 턴이 올바른 순서로 표시되도록 세 단계로 분기합니다.

1. `streamingTurn`과 동일한 `(turn_number, speaker)` → `pendingTurnLogs`에 버퍼링
2. `pendingStreamingTurn`과 동일한 `(turn_number, speaker)` → `pendingTurnLogs`에 버퍼링
3. 그 외 → `turns`에 즉시 추가, `pendingStreamingTurn`을 `streamingTurn`으로 승격

---

## 주요 사용처

| 파일 | 사용 목적 |
|---|---|
| `hooks/useDebateStream.ts` | SSE 이벤트 → 스토어 액션 매핑 |
| `components/debate/DebateViewer.tsx` | turns, streamingTurn, replayMode 구독 |
| `stores/debateStore.ts` | 하위 호환성 통합 스토어에서 동일 로직 재구현 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
