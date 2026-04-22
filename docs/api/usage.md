# Usage API

> 내 LLM 토큰 사용량 요약 및 일별 히스토리 조회

**파일 경로:** `backend/app/api/usage.py`
**라우터 prefix:** `/api/usage`
**최종 수정일:** 2026-03-24

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| `GET` | `/api/usage/me` | 내 토큰 사용량 요약 (일/월/총계) | Bearer JWT |
| `GET` | `/api/usage/me/history` | 일별 사용량 히스토리 (차트용) | Bearer JWT |

---

## 주요 엔드포인트 상세

### `GET /api/usage/me`

**설명:** 현재 로그인 사용자의 토큰 사용량을 일/월/총계 기준으로 집계해 반환. `UsageService.get_user_summary()`가 `token_usage_logs` 테이블을 기반으로 집계.

**인증:** Bearer JWT 필요

**쿼리 파라미터:** 없음

**응답 (200):** `UsageSummary`
```json
{
  "today_tokens": 12500,
  "today_cost": 0.025,
  "month_tokens": 340000,
  "month_cost": 0.68,
  "total_tokens": 1200000,
  "total_cost": 2.4
}
```

---

### `GET /api/usage/me/history`

**설명:** 최근 N일간 일별 토큰 사용량 및 비용 히스토리. 프론트엔드 차트 렌더링에 사용.

**인증:** Bearer JWT 필요

**쿼리 파라미터:**
| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `days` | int | `30` | 조회 기간 (1~365일) |

**응답 (200):** `UsageHistoryResponse`
```json
{
  "items": [
    {
      "date": "2026-03-24",
      "tokens": 8200,
      "cost": 0.016
    }
  ]
}
```

---

## 관련 모델

사용량 데이터는 `token_usage_logs` 테이블에 기록됨. 모든 LLM 호출은 `InferenceClient`를 통해 자동으로 해당 테이블에 INSERT됨.

관리자 전용 전체 사용량 API는 `/api/admin/usage/*` 참조.

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
