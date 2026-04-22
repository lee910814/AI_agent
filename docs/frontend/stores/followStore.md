# followStore

> 팔로우/언팔로우 및 팔로잉 목록을 관리하는 Zustand 스토어

**파일 경로:** `frontend/src/stores/followStore.ts`
**최종 수정일:** 2026-03-24

---

## 상태 (State)

| 필드 | 타입 | 초기값 | 설명 |
|---|---|---|---|
| `followingList` | `FollowResponse[]` | `[]` | 현재 사용자의 팔로잉 목록 |
| `total` | `number` | `0` | 전체 팔로잉 수 |
| `loading` | `boolean` | `false` | 목록 조회 로딩 여부 |

---

## 액션 (Actions)

| 액션명 | 파라미터 | 설명 |
|---|---|---|
| `fetchFollowing` | `params?: { target_type?: string }` | 팔로잉 목록 조회. target_type으로 'user' 또는 'agent' 필터 가능 |
| `follow` | `targetType: 'user' \| 'agent', targetId: string` | 팔로우 처리 후 목록에 prepend, 반환값: `FollowResponse` |
| `unfollow` | `targetType: 'user' \| 'agent', targetId: string` | 언팔로우 처리 (낙관적 삭제, 실패 시 이전 스냅샷으로 롤백 후 에러 re-throw) |

---

## unfollow 낙관적 삭제 패턴

```
1. 이전 followingList, total 스냅샷 저장
2. 로컬 상태에서 즉시 제거 (total - 1)
3. API 호출
4. 실패 → 스냅샷으로 복원 + 에러 re-throw (호출자에서 토스트 등 처리 가능)
```

---

## 주요 사용처

| 파일 | 사용 목적 |
|---|---|
| `components/debate/FollowButton.tsx` | 팔로우/언팔로우 버튼 상태 및 액션 |
| `app/(user)/profile/page.tsx` | 팔로잉 목록 표시 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
