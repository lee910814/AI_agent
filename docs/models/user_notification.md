# UserNotification

> 매치 이벤트·예측 결과·신규 팔로워 등 플랫폼 알림을 저장한다

**파일 경로:** `backend/app/models/user_notification.py`
**테이블명:** `user_notifications`
**최종 수정일:** 2026-03-24

---

## 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `user_id` | UUID | NOT NULL | — | 알림 수신 사용자 FK → `users.id` ON DELETE CASCADE |
| `type` | VARCHAR(30) | NOT NULL | — | 알림 유형 (예: match_completed, prediction_result, new_follower) |
| `title` | VARCHAR(200) | NOT NULL | — | 알림 제목 |
| `body` | VARCHAR(500) | NULL | — | 알림 본문 텍스트 |
| `link` | VARCHAR(300) | NULL | — | 관련 페이지 URL |
| `is_read` | BOOLEAN | NOT NULL | false | 읽음 여부 |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 알림 생성 시각 |

---

## 관계 (Relationships)

| 관계명 | 대상 모델 | 유형 | 설명 |
|---|---|---|---|
| `user` | User | ManyToOne | 알림 수신 사용자 |

---

## 인덱스 / 제약 조건

```sql
-- 미읽기 알림 목록 조회: user_id + is_read 필터 후 최신순 정렬
Index("idx_user_notifications_user_unread", "user_id", "is_read", "created_at")
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
