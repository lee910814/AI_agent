# DebateTemplateService

> 에이전트 템플릿 CRUD, 커스터마이징 검증, 프롬프트 조립 서비스

**파일 경로:** `backend/app/services/debate/template_service.py`
**최종 수정일:** 2026-03-24

---

## 모듈 목적

관리자가 제공하는 에이전트 템플릿(`DebateAgentTemplate`)의 조회·생성·수정을 담당한다.

사용자가 템플릿을 기반으로 에이전트를 생성할 때 커스터마이징 값의 유효성을 검증하고, 최종 시스템 프롬프트를 조립하는 역할도 수행한다.

---

## 프롬프트 인젝션 방어

`_INJECTION_PATTERNS` 정규식이 모듈 레벨에서 컴파일된다. `validate_customizations()`의 `free_text` 필드 검증 시 해당 패턴이 감지되면 `ValueError`를 raise한다.

감지 패턴:

| 패턴 | 설명 |
|---|---|
| `<\|im_end\|>`, `<\|endoftext\|>`, `</s>` | 특수 토큰 종결 마커 |
| `[INST]`, `[/INST]` | Llama 계열 지시 토큰 |
| `### (Human\|Assistant\|System)` | 역할 분리 헤더 |
| `IGNORE ALL PREVIOUS INSTRUCTIONS` | 클래식 인젝션 구문 |
| `<!-- ... -->` | HTML 주석 숨김 시도 |

---

## 클래스: `DebateTemplateService`

### `__init__(db: AsyncSession)`

비동기 DB 세션을 주입받는다.

---

### 조회 메서드

#### `list_active_templates() -> list[DebateAgentTemplate]`

`is_active=True` 템플릿만 `sort_order` 오름차순으로 반환한다. 사용자 화면에서 호출된다.

#### `list_all_templates() -> list[DebateAgentTemplate]`

비활성 포함 전체 템플릿을 `sort_order` 오름차순으로 반환한다. 관리자 전용.

#### `get_template(template_id: str | UUID) -> DebateAgentTemplate | None`

ID로 단일 템플릿을 조회한다. 미존재 시 `None` 반환.

---

### `validate_customizations(template, customizations, enable_free_text) -> dict`

커스터마이징 값을 검증하고 누락 키는 기본값으로 채워 반환한다.

**Args:**

| 파라미터 | 설명 |
|---|---|
| `template` | 검증 기준 템플릿 |
| `customizations` | 사용자 입력 dict (`None`이면 기본값만 반환) |
| `enable_free_text` | `True`여야 `free_text` 필드를 포함 |

**처리 순서:**

```
1. template.default_values로 result 초기화
2. customizations가 있으면 update
3. sliders 검증: int 변환 + min/max 범위 체크
4. selects 검증: 허용된 options 값인지 확인
5. free_text 처리:
   - enable_free_text=False → result에서 제거
   - enable_free_text=True → max_length 체크 + _INJECTION_PATTERNS 스캔
```

**Raises:** `ValueError` — 범위 초과, 허용되지 않은 옵션, 길이 초과, 인젝션 패턴 감지 시.

---

### `assemble_prompt(template, customizations) -> str`

검증된 `customizations`로 `{customization_block}` 자리표시자를 치환하여 최종 시스템 프롬프트를 반환한다.

**치환 방식:**

```
[커스터마이징 설정]
- {슬라이더 라벨}: {값}/5
- {셀렉트 라벨}: {선택된 옵션 라벨}
- {free_text 라벨}: {입력값}
```

`template.base_system_prompt`에서 `{customization_block}`을 위 텍스트로 교체한다.

---

### 관리자 CRUD

#### `create_template(data: AgentTemplateCreate) -> DebateAgentTemplate`

`DebateAgentTemplate` 인스턴스를 생성하고 commit 후 refresh하여 반환한다. superadmin 전용.

#### `update_template(template_id, data: AgentTemplateUpdate) -> DebateAgentTemplate`

`data.model_dump(exclude_none=True)`로 변경 필드만 갱신한다. 미존재 시 `ValueError("Template not found")` raise. superadmin 전용.

---

## `customization_schema` 구조

`DebateAgentTemplate.customization_schema`는 JSONB 컬럼이며 다음 형태를 따른다.

```json
{
  "sliders": [
    { "key": "aggression", "label": "공격성", "min": 1, "max": 5, "default": 3 }
  ],
  "selects": [
    {
      "key": "debate_style",
      "label": "토론 스타일",
      "default": "logical",
      "options": [
        { "value": "logical", "label": "논리형" },
        { "value": "emotional", "label": "감성형" }
      ]
    }
  ],
  "free_text": {
    "key": "additional_instructions",
    "label": "추가 지시사항",
    "max_length": 500
  }
}
```

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `DebateAgentTemplate` | `app.models.debate_agent_template` | ORM 모델 |
| `AgentTemplateCreate`, `AgentTemplateUpdate` | `app.schemas.debate_agent` | Pydantic 입력 스키마 |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|---|---|---|
| 2026-03-24 | v1.0 | 신규 작성 |
