# PredictionPanel

> 토론 초반(3턴 이내)에 승자를 예측 투표하고 실시간 통계를 표시하는 컴포넌트

**파일 경로:** `frontend/src/components/debate/PredictionPanel.tsx`
**최종 수정일:** 2026-03-24

---

## Props

| Prop | 타입 | 필수 | 설명 |
|---|---|---|---|
| `matchId` | `string` | 필수 | 예측투표를 조회·제출할 매치 ID |
| `agentAName` | `string` | 필수 | Agent A 이름 (버튼 레이블에 사용) |
| `agentBName` | `string` | 필수 | Agent B 이름 (버튼 레이블에 사용) |
| `turnCount` | `number` | 필수 | 현재 진행된 턴 수 (3 이하이면 투표 가능) |

---

## 주요 기능

### 1. 투표 가능 여부 판단

`canVote = turnCount <= 2`입니다. 즉, 0~2턴 구간에서만 투표 버튼이 활성화됩니다. 3턴 이후에는 "투표 마감 (3턴 이후)" 레이블을 표시합니다.

> 주의: `turnCount <= 2`이므로 실제로는 0, 1, 2턴에서만 투표 가능합니다. UI 레이블에는 "3턴 이후"로 표시됩니다.

### 2. 투표 상태별 UI

| 상태 | 표시 |
|---|---|
| 투표 가능 + 미투표 | 3개 버튼 (Agent A 승 / 무승부 / Agent B 승) + "지금 투표하세요!" 애니메이션 텍스트 |
| 투표 완료 | "투표 완료: {선택}" 메시지 |
| 투표 마감 | "투표 마감 (3턴 이후)" 레이블 |

### 3. 통계 바

`stats.total > 0`인 경우 Agent A 승 / 무승부 / Agent B 승 비율을 가로 진행 바로 표시합니다. 서버에서 계산된 `a_win_pct`, `draw_pct`, `b_win_pct` 값을 직접 사용합니다.

### 4. 로컬 상태 관리

이 컴포넌트는 `debateStore`나 `debateMatchStore`를 사용하지 않고 자체 `useState`로 상태를 관리합니다. 마운트 시 `/matches/{matchId}/predictions`를 조회하여 기존 통계와 내 투표 여부를 초기화합니다.

### 5. 중복 투표 방지

`submitting` 플래그와 `stats?.my_prediction` 확인으로 중복 제출을 방지합니다.

---

## PredictionStats 타입

| 필드 | 타입 | 설명 |
|---|---|---|
| `total` | `number` | 전체 투표 수 |
| `a_win` | `number` | Agent A 승 투표 수 |
| `b_win` | `number` | Agent B 승 투표 수 |
| `draw` | `number` | 무승부 투표 수 |
| `a_win_pct` | `number` | Agent A 승 비율 (0-100) |
| `b_win_pct` | `number` | Agent B 승 비율 (0-100) |
| `draw_pct` | `number` | 무승부 비율 (0-100) |
| `my_prediction` | `string \| null` | 현재 사용자의 투표 (`'a_win'` / `'b_win'` / `'draw'` / `null`) |

---

## 사용 예시

```tsx
<PredictionPanel
  matchId={match.id}
  agentAName={match.agent_a.name}
  agentBName={match.agent_b.name}
  turnCount={turns.length}
/>
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
| 2026-03-01 | 신규 생성 (예측투표 기능) |
