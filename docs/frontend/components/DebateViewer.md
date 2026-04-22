# DebateViewer

> SSE 스트리밍·리플레이·리플레이 타이핑 애니메이션을 통합 관리하는 토론 관전 핵심 컴포넌트

**파일 경로:** `frontend/src/components/debate/DebateViewer.tsx`
**최종 수정일:** 2026-03-24

---

## Props

| Prop | 타입 | 필수 | 설명 |
|---|---|---|---|
| `match` | `DebateMatch` | 필수 | 현재 매치 정보 (에이전트 이름·이미지·상태 포함) |
| `onSeriesUpdate` | `(series: PromotionSeries) => void` | 선택 | 승급전/강등전 시리즈 업데이트 SSE 이벤트 수신 시 호출되는 콜백 |

---

## 주요 기능

### 1. SSE 스트리밍 연결

`useDebateStream(match.id, match.status, { onSeriesUpdate })` 훅을 통해 SSE 연결을 관리합니다. 컴포넌트는 스토어 구독만 담당하고, 실제 이벤트 처리 로직은 훅에 위임됩니다.

처리하는 SSE 이벤트 종류:
- `turn` — 완료된 턴 데이터 수신
- `chunk` — 스트리밍 청크 수신
- `turn_review` — LLM 검토 결과 수신
- `evidence` — DuckDuckGo 근거 수신
- `searching` — 근거 검색 시작
- `judge_intro` — Judge 소개 문구 수신
- `series_update` — 승급전/강등전 시리즈 업데이트
- `finished` / `error` — 스트리밍 종료

### 2. 리플레이 모드

`useDebateReplay()` 훅이 setInterval로 `tickReplay()`를 호출합니다. 타이핑 애니메이션이 진행 중일 때는 tick이 건너뜁니다(`replayTyping: true`).

`DebateViewer` 내부에서는 `replayIndex`가 변경될 때마다 `setInterval`로 글자 단위 타이핑 애니메이션을 구현합니다. 속도는 `replaySpeed`에 비례하며 기본 3자/30ms입니다.

### 3. 스마트 자동 스크롤

- 완료 턴(`turns.length` 변경) — 사용자가 하단 근처에 있을 때만 자동 스크롤
- 스트리밍 중에는 `instant` 방식으로 스크롤하여 콘텐츠 흔들림 방지
- 리플레이 진행 시 현재 턴으로 `smooth` 스크롤

### 4. 성능 최적화

- **슬라이스 구독** — `appendChunk`로 `streamingTurn`이 바뀔 때 `turns` 구독자는 재렌더링하지 않음
- **turnReviewMap** — `turnReviews` 배열을 `Map<'turn_number:speaker', TurnReview>`로 메모이제이션하여 O(n²) find 탐색을 O(1)로 전환
- **visibleTurns** — `useMemo`로 메모이제이션. 리플레이 모드 시 `turns.slice(0, replayIndex + 1)`, 완료 매치 기본 상태는 빈 배열 (전체보기 토글 후 전체 표시)
- **TurnBubble은 `memo`** — 스트리밍 청크가 올 때마다 완료 턴이 불필요하게 재렌더링되지 않음

### 5. 특수 상태 UI

- `waiting_agent` — "로컬 에이전트 접속 대기 중..." 스피너 표시
- `forfeit` — "에이전트 미접속 — 몰수패" 배지 표시
- `judgeIntro` — Judge 소개 문구 카드 표시
- 초기 로딩 상태 — `SkeletonCard` 2개 표시

---

## 렌더링 구조

```
DebateViewer
  ├── ReplayControls              (리플레이 컨트롤 바)
  ├── 특수 상태 UI                (waiting_agent / forfeit / judgeIntro)
  ├── visibleTurns.map()
  │     └── TurnBubble           (완료 턴, memo로 불필요 재렌더링 방지)
  ├── StreamingTurnBubble         (스트리밍 중인 현재 턴)
  └── 다음 화자 대기 인디케이터
```

---

## 사용 예시

```tsx
<DebateViewer
  match={currentMatch}
  onSeriesUpdate={(series) => setActiveSeries(series)}
/>
```

---

## 의존 훅

| 훅 | 역할 |
|---|---|
| `useDebateStream` | SSE 연결, 이벤트 → 스토어 액션 매핑 |
| `useDebateReplay` | 리플레이 interval 관리 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
| 2026-03-09 | 출처 검증(evidence/searching) SSE 이벤트 처리 추가, turnReviewMap 최적화 |
| 2026-02-26 | 리플레이 타이핑 애니메이션, pendingStreamingTurn 버퍼링 지원 |
| 2026-02-25 | turn_review SSE 이벤트 처리, LLM 검토 결과 표시 추가 |
