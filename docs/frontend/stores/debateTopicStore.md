# debateTopicStore

> 토픽 목록 조회·생성·수정·삭제 및 매칭 큐 등록을 관리하는 Zustand 스토어

**파일 경로:** `frontend/src/stores/debateTopicStore.ts`
**최종 수정일:** 2026-03-24

---

## 상태 (State)

| 필드 | 타입 | 초기값 | 설명 |
|---|---|---|---|
| `topics` | `DebateTopic[]` | `[]` | 전체 토픽 목록 |
| `topicsTotal` | `number` | `0` | 전체 토픽 수 |
| `popularTopics` | `DebateTopic[]` | `[]` | 인기 토픽 목록 (최근 1주 기준, 최대 10개) |
| `popularTopicsTotal` | `number` | `0` | 인기 토픽 수 |
| `topicsLoading` | `boolean` | `false` | 토픽 조회 로딩 여부 |

---

## 액션 (Actions)

| 액션명 | 파라미터 | 설명 |
|---|---|---|
| `fetchTopics` | `params?: { status?, sort?, page?, pageSize? }` | 토픽 목록 조회. page=1이면 목록 교체, page>1이면 기존 목록에 append 없이 교체 |
| `fetchPopularTopics` | — | 인기 토픽 10개 조회 (`sort=popular_week&page_size=10`) |
| `createTopic` | `payload: TopicCreatePayload` | 토픽 생성 후 topics 맨 앞에 prepend, topicsTotal 증가 |
| `updateTopic` | `topicId: string, payload: Partial<TopicCreatePayload>` | 토픽 수정 (topics, popularTopics 양쪽 모두 반영) |
| `deleteTopic` | `topicId: string` | 토픽 삭제 (topics, popularTopics 양쪽에서 제거, 카운터 감소) |
| `joinQueue` | `topicId, agentId, password?` | 매칭 큐 등록. 응답으로 `{ status, match_id?, opponent_agent_id? }` 반환 |
| `leaveQueue` | `topicId, agentId` | 매칭 큐 이탈 |
| `randomMatch` | `agentId: string` | 랜덤 토픽으로 즉시 매칭 신청 |

---

## fetchTopics vs debateStore.fetchTopics 차이

`debateTopicStore.fetchTopics`는 page 파라미터 무관하게 항상 서버 응답으로 목록을 교체합니다.
`debateStore.fetchTopics`(통합 스토어)는 `page > 1`이면 기존 목록에 append하는 무한 스크롤 방식을 지원합니다.

---

## 주요 사용처

| 파일 | 사용 목적 |
|---|---|
| `app/(user)/debate/page.tsx` | 토픽 목록 표시, 큐 등록/이탈 처리 |
| `components/debate/TopicCard.tsx` | 토픽 카드 렌더링 |
| `stores/debateStore.ts` | 하위 호환성 통합 스토어에서 토픽 액션 위임 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
