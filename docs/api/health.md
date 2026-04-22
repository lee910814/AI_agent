# Health API

> 서버 상태 확인 — PostgreSQL 및 Redis 연결 상태를 점검해 반환

**파일 경로:** `backend/app/api/health.py`
**라우터 prefix:** (없음, 루트에 직접 등록)
**최종 수정일:** 2026-03-24

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| `GET` | `/health` | 서버·DB·Redis 상태 확인 | 없음 (인증 불필요) |

---

## 주요 엔드포인트 상세

### `GET /health`

**설명:** 서버 전체 상태를 확인. PostgreSQL에 `SELECT 1`, Redis에 `PING`을 실행해 각 컴포넌트가 정상인지 점검. 하나라도 실패하면 `status: "degraded"` 및 HTTP 503 반환.

**인증:** 불필요

**쿼리 파라미터:** 없음

**응답 (200) — 정상:**
```json
{
  "status": "ok",
  "db": "ok",
  "redis": "ok"
}
```

**응답 (503) — 일부 장애:**
```json
{
  "status": "degraded",
  "db": "error",
  "redis": "ok"
}
```

**응답 필드:**
| 필드 | 값 | 설명 |
|---|---|---|
| `status` | `"ok"` / `"degraded"` | 전체 상태. DB 또는 Redis 중 하나라도 오류이면 `"degraded"` |
| `db` | `"ok"` / `"error"` | PostgreSQL 연결 상태 |
| `redis` | `"ok"` / `"error"` | Redis 연결 상태 |

**HTTP 상태 코드:**
- `200`: 모든 컴포넌트 정상
- `503`: 하나 이상의 컴포넌트 오류 (`status: "degraded"`)

---

## 운영 활용

로드 밸런서 헬스체크, 배포 후 연결 검증, 모니터링 시스템(Prometheus/Grafana)의 업타임 지표 수집에 사용된다.

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
