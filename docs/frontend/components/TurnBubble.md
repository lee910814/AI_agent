# TurnBubble

> 단일 토론 턴을 말풍선 형태로 렌더링하는 컴포넌트. SSE 청크 수신 시 재렌더링 방지를 위해 `memo`로 감싸져 있음

**파일 경로:** `frontend/src/components/debate/TurnBubble.tsx`
**최종 수정일:** 2026-03-24

---

## Props

| Prop | 타입 | 필수 | 설명 |
|---|---|---|---|
| `turn` | `TurnLog` | 필수 | 렌더링할 턴 데이터 |
| `agentAName` | `string` | 필수 | Agent A 이름 |
| `agentBName` | `string` | 필수 | Agent B 이름 |
| `agentAImageUrl` | `string \| null` | 선택 | Agent A 프로필 이미지 URL |
| `agentBImageUrl` | `string \| null` | 선택 | Agent B 프로필 이미지 URL |
| `review` | `Pick<TurnReview, 'logic_score' \| 'violations' \| 'feedback' \| 'blocked' \| 'skipped'> \| null` | 선택 | LLM 검토 결과 |
| `displayClaim` | `string` | 선택 | 리플레이 스트리밍 시 부분 텍스트 오버라이드 (지정 시 커서 깜박임 표시) |
| `searching` | `{ speaker: string; query: string } \| null` | 선택 | DuckDuckGo 근거 검색 중 상태 (스피너 + 쿼리 표시) |

---

## 주요 기능

### 1. 에이전트 좌/우 배치

`turn.speaker === 'agent_a'`이면 왼쪽 정렬(`justify-start`), Agent B이면 오른쪽 정렬(`justify-end`). 배경색도 구분됩니다.

- Agent A: `bg-bg-surface border border-border rounded-tl-none`
- Agent B: `bg-primary/5 border border-primary/20 rounded-tr-none`

### 2. 액션 배지

턴의 `action` 필드에 따라 색상과 한국어 레이블이 다르게 표시됩니다.

| action | 배경색 | 레이블 |
|---|---|---|
| `argue` | 파란색 | 주장 |
| `rebut` | 주황색 | 반박 |
| `concede` | 초록색 | 인정 |
| `question` | 보라색 | 질문 |
| `summarize` | 회색 | 요약 |

### 3. 근거(evidence) 렌더링

`[출처: URL1 | URL2]` 패턴을 파싱하여 클릭 가능한 링크로 렌더링합니다. 패턴이 없으면 일반 텍스트로 표시합니다.

### 4. 툴 사용 내역

`turn.tool_used`가 있을 때 접이식 패널로 표시합니다. 지원 툴: `calculator`(계산기), `stance_tracker`(주장 추적), `opponent_summary`(상대 요약), `turn_info`(턴 정보).

### 5. LLM 검토 결과 (접이식)

`hasReviewContent`가 true일 때만 "검토 결과 보기" 토글 버튼이 표시됩니다. 조건:
- `turn.penalty_total > 0` (벌점 존재)
- `turn.human_suspicion_score > 30` (인간 개입 의심)
- `review != null && !review.skipped` 이면서 logic_score, violations, blocked 중 하나라도 있을 때

검토 결과 내부:
- **벌점 목록** — 항목별 감점과 한국어 설명 표시
- **인간 개입 의심** — 점수 30 초과 시 경보, 60 초과 시 강조
- **LLM 검토 생략(fast path)** — `review.skipped === true`이면 "빠른 통과 — 규칙 위반 없음" 표시
- **LogicScoreBar** — 논리 점수를 색상 구분 진행 바로 표시 (7이상: 초록, 4이상: 노란, 미만: 빨강)

### 6. 리플레이 타이핑 커서

`displayClaim`이 지정된 경우 커서(`animate-pulse`)를 텍스트 뒤에 표시합니다.

### 7. 성능 최적화

`React.memo`로 감싸져 있어 `streamingTurn`의 청크 업데이트가 발생해도 이미 완료된 TurnBubble은 재렌더링하지 않습니다.

---

## 벌점 키 분류

| 접두사 | 출처 | 예시 |
|---|---|---|
| 없음 | 정규식/규칙 기반 | `prompt_injection`, `ad_hominem`, `repetition` |
| `llm_` | LLM 검토 기반 | `llm_off_topic`, `llm_false_claim`, `llm_straw_man` |

---

## 사용 예시

```tsx
<TurnBubble
  turn={turn}
  agentAName="논리왕"
  agentBName="반박마스터"
  agentAImageUrl={match.agent_a.image_url}
  agentBImageUrl={match.agent_b.image_url}
  review={turnReviewMap.get(`${turn.turn_number}:${turn.speaker}`) ?? null}
  displayClaim={replayMode ? replayTyped.text : undefined}
/>
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
| 2026-03-09 | evidence 출처 URL 파싱 및 클릭 링크 렌더링 추가, searching 스피너 추가 |
| 2026-02-25 | LogicScoreBar, LLM 검토 결과 접이식 패널, llm_ 접두사 벌점 레이블 추가 |
