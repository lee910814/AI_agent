# notificationStore

> 알림 목록 조회, 미읽기 카운트 관리, 읽음 처리(낙관적 업데이트)를 담당하는 Zustand 스토어

**파일 경로:** `frontend/src/stores/notificationStore.ts`
**최종 수정일:** 2026-03-24

---

## 상태 (State)

| 필드 | 타입 | 초기값 | 설명 |
|---|---|---|---|
| `notifications` | `NotificationResponse[]` | `[]` | 알림 목록 |
| `unreadCount` | `number` | `0` | 미읽기 알림 수 |
| `loading` | `boolean` | `false` | 알림 로딩 여부 |

---

## 액션 (Actions)

| 액션명 | 파라미터 | 설명 |
|---|---|---|
| `fetchNotifications` | `offset?: number` | 알림 목록 조회 (20개씩). offset=0이면 목록 교체, offset>0이면 기존에 append |
| `fetchUnreadCount` | — | 미읽기 알림 수 조회 |
| `markRead` | `id: string` | 특정 알림 읽음 처리 (낙관적 업데이트, 실패 시 fetchUnreadCount로 복원) |
| `markAllRead` | — | 전체 읽음 처리 (낙관적 업데이트, 실패 시 이전 스냅샷으로 롤백) |

---

## 낙관적 업데이트 패턴

`markRead`와 `markAllRead` 모두 API 호출 전에 먼저 로컬 상태를 변경합니다.

- `markRead`: 실패 시 `fetchUnreadCount()`로 카운트만 재조회
- `markAllRead`: 실패 시 이전 `notifications` 배열과 `unreadCount` 스냅샷으로 완전 롤백

---

## 주요 사용처

| 파일 | 사용 목적 |
|---|---|
| `components/ui/NotificationBell.tsx` | unreadCount 배지 표시 |
| `components/ui/NotificationPanel.tsx` | 알림 목록 표시 및 읽음 처리 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
