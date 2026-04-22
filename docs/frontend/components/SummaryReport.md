# SummaryReport

> 토론 완료 후 AI가 생성한 요약 리포트를 접이식 섹션으로 표시하는 컴포넌트

**파일 경로:** `frontend/src/components/debate/SummaryReport.tsx`
**최종 수정일:** 2026-03-24

---

## Props

| Prop | 타입 | 필수 | 설명 |
|---|---|---|---|
| `matchId` | `string` | 필수 | 요약 리포트를 조회할 매치 ID |
| `agentAName` | `string` | 선택 | Agent A 이름 (기본값: `'Agent A'`) |
| `agentBName` | `string` | 선택 | Agent B 이름 (기본값: `'Agent B'`) |

---

## 주요 기능

### 1. 폴링 기반 데이터 조회

컴포넌트 마운트 시 `/matches/{matchId}/summary`를 즉시 호출하고, 5초 간격으로 폴링합니다. 응답 `status`가 `ready` 또는 `unavailable`이 되면 폴링을 자동 중단합니다.

```
status === 'generating'  →  폴링 계속 + 로딩 UI 표시
status === 'ready'       →  폴링 중단 + 리포트 표시
status === 'unavailable' →  폴링 중단 + 컴포넌트 숨김 (null 반환)
```

### 2. 렌더링 섹션

| 섹션 | 기본 열림 | 설명 |
|---|---|---|
| 전체 총평 | 항상 표시 | `overall_summary` 텍스트, 카드 형태 |
| 에이전트별 핵심 논거 | 열림 | Agent A(파란색)/B(주황색) 핵심 논거 2열 비교 |
| 승부 전환점 | 열림 | `turning_points` 번호 목록 (없으면 섹션 숨김) |
| 규칙 위반 | 닫힘 | `rule_violations` 목록 (없으면 섹션 숨김) |

### 3. 섹션 접이식 UI

내부 `Section` 컴포넌트가 열림/닫힘을 독립적으로 관리합니다. 타이틀 클릭으로 토글 가능합니다.

### 4. 토큰 사용량 표시

`input_tokens + output_tokens > 0`이면 푸터에 분석 토큰 수를 표시합니다.

---

## SummaryData 타입

| 필드 | 타입 | 설명 |
|---|---|---|
| `status` | `'ready' \| 'generating' \| 'unavailable'` | 요약 생성 상태 |
| `agent_a_arguments` | `string[]` | Agent A 핵심 논거 목록 |
| `agent_b_arguments` | `string[]` | Agent B 핵심 논거 목록 |
| `turning_points` | `string[]` | 승부 전환점 목록 |
| `rule_violations` | `string[]` | 규칙 위반 목록 |
| `overall_summary` | `string` | 전체 총평 |
| `generated_at` | `string` | 생성 일시 |
| `model_used` | `string` | 사용된 LLM 모델명 |
| `input_tokens` | `number` | 입력 토큰 수 |
| `output_tokens` | `number` | 출력 토큰 수 |

---

## 사용 예시

```tsx
{match.status === 'completed' && debateShowAll && (
  <SummaryReport
    matchId={match.id}
    agentAName={match.agent_a.name}
    agentBName={match.agent_b.name}
  />
)}
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
| 2026-03-01 | 신규 생성 (요약 리포트 기능) |
