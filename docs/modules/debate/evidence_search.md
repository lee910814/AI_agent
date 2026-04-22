# EvidenceSearchService

> claim → LLM 키워드 추출 → DuckDuckGo 검색 → 출처 포함 근거 반환

**파일 경로:** `backend/app/services/debate/evidence_search.py`
**최종 수정일:** 2026-03-24

---

## 모듈 목적

에이전트 발언 생성 시 주장(claim)에 대한 실제 웹 근거를 자동으로 검색하고, 출처 URL과 함께 요약된 근거 텍스트를 반환한다.

검색 파이프라인은 두 단계로 나뉜다.

1. `gpt-4o-mini`(또는 `debate_evidence_keyword_model` 설정값)로 claim에서 검색 키워드를 추출한다.
2. 추출된 키워드별로 DuckDuckGo 텍스트 검색을 병렬 실행하고 결과를 집계한다.

`search_by_query()`는 LLM 키워드 추출 단계를 생략하여 tool_call이 이미 쿼리를 제공한 경우에 사용한다.

전체 흐름은 `debate_evidence_search_timeout` 내에 완료되지 않으면 `None`을 반환하며, 예외가 발생해도 매치 실행을 중단하지 않는다.

---

## 데이터 클래스: `EvidenceResult`

```python
@dataclass
class EvidenceResult:
    text: str              # snippet 목록 (최대 5건)
    sources: list[str]     # 출처 URL 목록
```

### `format() -> str`

에이전트 프롬프트의 `evidence` 필드에 삽입할 최종 텍스트를 반환한다.

```
{text}

[출처: {url1} | {url2} | ...]
```

출처가 없으면 `[출처: 출처 없음]`이 붙는다.

---

## 클래스: `EvidenceSearchService`

### `search(claim, exclude_urls) -> EvidenceResult | None`

claim 텍스트로부터 웹 근거를 검색한다.

```
1. settings.debate_evidence_search_enabled 체크 (비활성이면 즉시 None)
2. asyncio.timeout(debate_evidence_search_timeout)
3. _extract_keywords(claim) — LLM으로 키워드 추출
4. _search_all(keywords)   — DuckDuckGo 병렬 검색
5. _aggregate(results, exclude_urls) — 중복 제거 + 출처 조합
```

**Args:**

| 파라미터 | 설명 |
|---|---|
| `claim` | 검색 대상 주장 텍스트 |
| `exclude_urls` | 이전 턴에서 사용된 URL 집합 — 동일 출처 반복 방지 |

타임아웃 또는 예외 발생 시 `None` 반환 (매치 실행에 영향 없음).

---

### `search_by_query(query, exclude_urls) -> EvidenceResult | None`

이미 준비된 쿼리 문자열로 DuckDuckGo 검색을 직접 실행한다. LLM 호출 없이 비용·지연을 절감한다.

tool_call에서 `query` 파라미터가 넘어오는 경우에 사용된다.

---

### `_extract_keywords(claim) -> list[str]`

OpenAI API(`debate_evidence_keyword_model`)를 호출하여 claim에서 검색 키워드 JSON 배열을 추출한다.

- 영어 키워드 2~3개 + 한국어 키워드 1~2개를 함께 추출한다.
- `openai_api_key`가 설정되지 않았거나 claim이 2000자를 초과하면 빈 리스트를 반환한다.
- 8초 타임아웃. 실패해도 예외를 전파하지 않고 빈 리스트를 반환한다.

> TODO(next-PR): `generate_byok()`로 교체 — InferenceClient 컨벤션 준수 + 연결 풀 재사용

---

### `_search_all(keywords) -> list[dict]`

키워드별 DuckDuckGo 검색을 `asyncio.gather`로 병렬 실행한다.

- 키워드는 최대 10개로 상한한다.
- 키워드당 5초 타임아웃 적용.
- 동기 `_ddg_search()`를 `loop.run_in_executor`로 실행한다.
- 반환 전 URL 기준 중복을 제거한다.

---

### `_ddg_search(query) -> list[dict]`

DuckDuckGo 동기 텍스트 검색 (run_in_executor 전용).

- `DDGS().text(query, max_results=debate_evidence_search_max_results)` 호출.
- 빈 쿼리이면 즉시 빈 리스트 반환.

---

### `_aggregate(results, exclude_urls) -> EvidenceResult`

검색 결과에서 중복 URL을 제거하고 최대 5건의 snippet과 출처를 조합한다.

- `exclude_urls`를 `seen` 초기값으로 사용하여 크로스-턴 중복을 방지한다.
- snippet 포맷: `- {title}: {body[:400]}`

---

## 관련 설정값 (`config.py`)

| 설정 키 | 설명 |
|---|---|
| `debate_evidence_search_enabled` | 웹 검색 기능 전체 활성화 여부 |
| `debate_evidence_search_timeout` | 전체 검색 파이프라인 타임아웃 (초) |
| `debate_evidence_keyword_model` | 키워드 추출 LLM 모델 ID |
| `debate_evidence_search_max_results` | DuckDuckGo 키워드당 최대 결과 수 |

---

## 에러 처리

| 상황 | 처리 방식 |
|---|---|
| `debate_evidence_search_enabled = False` | 즉시 `None` 반환 |
| 전체 타임아웃 (`TimeoutError`, `CancelledError`) | WARNING 로그 + `None` 반환 |
| 그 외 예외 | WARNING 로그 + `None` 반환 |
| 키워드당 DuckDuckGo 타임아웃 | WARNING 로그 + 해당 키워드 결과 빈 리스트로 처리 |
| `CancelledError` (DDG 단계) | 취소 신호 재전파 (상위 asyncio.timeout 처리로 위임) |

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `settings` | `app.core.config` | 기능 활성화 여부, 타임아웃, 모델명 조회 |
| `httpx.AsyncClient` | 외부 | OpenAI API 호출 (키워드 추출) |
| `DDGS` | `ddgs` | DuckDuckGo 텍스트 검색 (동기) |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|---|---|---|
| 2026-03-24 | v1.0 | 신규 작성 |
