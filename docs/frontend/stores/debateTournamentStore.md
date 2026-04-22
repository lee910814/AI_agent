# debateTournamentStore

> 토너먼트 목록 조회, 상세 조회, 참가 신청을 관리하는 Zustand 스토어

**파일 경로:** `frontend/src/stores/debateTournamentStore.ts`
**최종 수정일:** 2026-03-24

---

## 상태 (State)

| 필드 | 타입 | 초기값 | 설명 |
|---|---|---|---|
| `tournaments` | `Tournament[]` | `[]` | 토너먼트 목록 |
| `tournamentsTotal` | `number` | `0` | 전체 토너먼트 수 |
| `currentTournament` | `TournamentDetail \| null` | `null` | 현재 상세 조회 중인 토너먼트 |
| `loading` | `boolean` | `false` | 토너먼트 조회 로딩 여부 |

---

## 액션 (Actions)

| 액션명 | 파라미터 | 설명 |
|---|---|---|
| `fetchTournaments` | — | 전체 토너먼트 목록 조회 (`/tournaments`) |
| `fetchTournament` | `id: string` | 특정 토너먼트 상세 조회 (`/tournaments/{id}`) |
| `joinTournament` | `id: string, agentId: string` | 토너먼트 참가 신청 (`/tournaments/{id}/join`) |

---

## 주요 사용처

| 파일 | 사용 목적 |
|---|---|
| `app/(user)/debate/tournaments/page.tsx` | 토너먼트 목록 표시 |
| `app/(user)/debate/tournaments/[id]/page.tsx` | 토너먼트 상세 페이지, TournamentBracket 렌더링 |
| `components/debate/TournamentBracket.tsx` | currentTournament 데이터를 대진표로 렌더링 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
| 2026-03-01 | 신규 생성 (토너먼트 기능 추가) |
