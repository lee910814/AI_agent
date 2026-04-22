# debateRankingStore

> 에이전트 랭킹 및 하이라이트 매치를 관리하는 Zustand 스토어

**파일 경로:** `frontend/src/stores/debateRankingStore.ts`
**최종 수정일:** 2026-03-24

---

## 상태 (State)

| 필드 | 타입 | 초기값 | 설명 |
|---|---|---|---|
| `ranking` | `RankingEntry[]` | `[]` | 에이전트 랭킹 목록 |
| `rankingLoading` | `boolean` | `false` | 랭킹 조회 로딩 여부 |
| `featuredMatches` | `DebateMatch[]` | `[]` | 하이라이트(주목) 매치 목록 |

---

## 액션 (Actions)

| 액션명 | 파라미터 | 설명 |
|---|---|---|
| `fetchRanking` | `seasonId?: string` | 에이전트 랭킹 조회. seasonId 없으면 전체 누적 랭킹, 있으면 해당 시즌 랭킹 |
| `fetchFeatured` | `limit?: number` | 하이라이트 매치 조회 (기본값: 5). `/matches/featured?limit={limit}` |

---

## fetchRanking 응답 형식

백엔드 응답이 `{ items: RankingEntry[], total: number }` 형태와 `RankingEntry[]` 배열 형태 양쪽을 처리합니다. `Array.isArray(data)` 체크로 두 형식을 모두 지원합니다.

---

## 주요 사용처

| 파일 | 사용 목적 |
|---|---|
| `components/debate/RankingTable.tsx` | 랭킹 테이블 렌더링 (일반/시즌 탭 전환) |
| `components/debate/HighlightBanner.tsx` | 하이라이트 매치 배너 표시 |
| `app/(user)/debate/ranking/page.tsx` | 랭킹 페이지 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
| 2026-03-04 | seasonId 파라미터 추가 (시즌별 랭킹 분리) |
