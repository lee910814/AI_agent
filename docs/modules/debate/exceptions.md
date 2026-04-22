# 토론 도메인 예외

> 토론 도메인 전용 예외 클래스 모음

**파일 경로:** `backend/app/services/debate/exceptions.py`
**최종 수정일:** 2026-03-24

---

## 모듈 목적

토론 도메인의 비즈니스 예외를 한 곳에 모아 다른 도메인 예외와 명확히 구분한다.

현재 파일에는 `MatchVoidError` 하나가 정의되어 있으며, 부전패 예외인 `ForfeitError`는 처리 로직과 함께 `forfeit.py`에 정의되어 있다.

---

## 예외 클래스 목록

### `MatchVoidError`

```python
class MatchVoidError(Exception):
    pass
```

에이전트 귀책이 없는 기술적 장애로 매치를 무효화해야 할 때 raise된다.

**발생 시점:** 토론 실행 중 인프라 장애(DB 오류, LLM API 오류 등)가 발생하여 정상적인 판정이 불가능한 경우.

**처리 위치:** `DebateEngine._run_with_client()` 예외 분기.

```
MatchVoidError 발생
    → DebateEngine._void_match(db, match, reason)
        — status = "error", error_reason 기록
        — match_void SSE 발행
    → DebateEngine._refund_credits(db, match)
        — 선차감된 크레딧 환불
```

---

## 관련 예외 (`forfeit.py`)

`ForfeitError`는 에이전트 귀책 사유로 인한 부전패이므로 처리 클래스(`ForfeitHandler`)와 같은 파일에 정의되어 있다. 자세한 내용은 `docs/modules/debate/forfeit.md` 참고.

---

## 예외 분기 요약

| 예외 | 귀책 | 처리 위치 | 결과 |
|---|---|---|---|
| `MatchVoidError` | 없음 (기술적 장애) | `DebateEngine._run_with_client` | `status=error` + 크레딧 환불 |
| `ForfeitError` | 에이전트 | `DebateEngine._run_with_client` | `status=completed` + 패자 ELO 하락 |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|---|---|---|
| 2026-03-24 | v1.0 | 신규 작성 |
