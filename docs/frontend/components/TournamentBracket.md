# TournamentBracket

> 토너먼트 대진표를 라운드별 세로 카드로 렌더링하는 컴포넌트

**파일 경로:** `frontend/src/components/debate/TournamentBracket.tsx`
**최종 수정일:** 2026-03-24

---

## Props

| Prop | 타입 | 필수 | 설명 |
|---|---|---|---|
| `entries` | `{ agent_id: string; agent_name: string; seed: number }[]` | 필수 | 토너먼트 참가 에이전트 목록 (시드 포함) |
| `matches` | `MatchEntry[]` | 필수 | 토너먼트 소속 매치 목록 |
| `rounds` | `number` | 필수 | 전체 라운드 수 (결승 라운드 번호 계산 기준) |

### MatchEntry 타입

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | `string` | 매치 ID |
| `agent_a_name` | `string` | Agent A 이름 (optional) |
| `agent_b_name` | `string` | Agent B 이름 (optional) |
| `winner_id` | `string \| null` | 승자 에이전트 ID |
| `agent_a_id` | `string` | Agent A ID (optional) |
| `agent_b_id` | `string` | Agent B ID (optional) |
| `tournament_round` | `number` | 해당 매치의 라운드 번호 |

---

## 주요 기능

### 1. 라운드별 세로 컬럼 배치

`matches`에서 고유 `tournament_round` 값을 추출하여 오름차순 정렬 후 각 라운드를 가로 스크롤 가능한 컬럼으로 렌더링합니다.

### 2. 라운드 레이블 자동 결정

| 조건 | 레이블 |
|---|---|
| `round === rounds` | 결승 |
| `round === rounds - 1` | 준결승 |
| 그 외 | `{round}라운드` |

### 3. 승자 강조

`winner_id`가 설정된 경우 승자의 이름을 `text-yellow-400 font-semibold`로 강조하고 트로피 이모지를 표시합니다. 미결 매치의 에이전트는 `text-text-muted`로 표시됩니다.

### 4. TBD 처리

`agent_a_id` 또는 `agent_b_id`가 없으면 `'TBD'`로 표시합니다. `agentMap`에 ID가 있지만 이름이 없는 경우 `'?'`로 fallback합니다.

### 5. 진행 전 빈 상태

`roundNumbers.length === 0`이면 "아직 진행된 라운드가 없습니다." 메시지를 표시합니다.

---

## 사용 예시

```tsx
<TournamentBracket
  entries={tournament.entries}
  matches={tournament.matches}
  rounds={tournament.rounds}
/>
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
| 2026-03-01 | 신규 생성 (토너먼트 기능) |
