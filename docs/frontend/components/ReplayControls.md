# ReplayControls

> 토론 리플레이 재생/일시정지/종료 및 속도 제어 UI 컴포넌트

**파일 경로:** `frontend/src/components/debate/ReplayControls.tsx`
**최종 수정일:** 2026-03-24

---

## Props

Props가 없습니다. `useDebateStore`를 직접 구독하여 상태를 읽고 액션을 호출합니다.

---

## 주요 기능

### 1. 조건부 렌더링

`replayMode === false`이면 `null`을 반환합니다. 리플레이 모드가 활성화된 경우에만 컨트롤 바가 표시됩니다.

### 2. 재생/일시정지 버튼

| 상태 | 동작 |
|---|---|
| `replayPlaying === true` | 클릭 시 `replayPlaying: false` (일시정지) |
| `replayPlaying === false` + 끝에 도달 (`atEnd`) | 클릭 시 `startReplay()` (처음부터 재생) |
| `replayPlaying === false` + 중간 | 클릭 시 `replayPlaying: true` (이어서 재생) |

### 3. 정지 버튼

`stopReplay()`를 호출합니다. 리플레이 모드를 종료하고 `debateShowAll: true`로 전환하여 전체 턴을 표시합니다.

### 4. 진행 바 + 턴 카운터

`replayIndex + 1` / `turns.length`로 현재 진행 위치를 표시합니다. 진행 바는 백분율 너비로 렌더링됩니다.

### 5. 속도 선택

0.5x / 1x / 2x 세 가지 속도를 버튼으로 제공합니다. 현재 선택된 속도는 `bg-primary text-white`로 강조됩니다.

---

## interval 관리 위임

`ReplayControls`는 `tickReplay()`를 직접 호출하지 않습니다. interval 관리는 `useDebateReplay` 훅이 전담합니다. 컴포넌트는 상태 표시와 사용자 인터랙션만 담당합니다.

---

## 사용 예시

```tsx
// DebateViewer 내부에서 사용
<ReplayControls />
```

리플레이 모드 시작은 외부에서 `useDebateStore.getState().startReplay()`를 호출합니다.

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
| 2026-02-26 | 신규 생성 (리플레이 기능) |
