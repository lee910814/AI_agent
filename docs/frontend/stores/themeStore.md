# themeStore

> localStorage 영속화를 지원하는 라이트/다크 테마 Zustand 스토어

**파일 경로:** `frontend/src/stores/themeStore.ts`
**최종 수정일:** 2026-03-24

---

## 상태 (State)

| 필드 | 타입 | 초기값 | 설명 |
|---|---|---|---|
| `theme` | `'light' \| 'dark'` | `'light'` | 현재 테마. 모듈 로드 시 localStorage의 `nemo-theme` 값으로 자동 초기화 |

---

## 액션 (Actions)

| 액션명 | 파라미터 | 설명 |
|---|---|---|
| `toggleTheme` | — | 테마 전환 후 `data-theme` 속성과 localStorage `nemo-theme` 동기화 |
| `setTheme` | `t: 'light' \| 'dark'` | 특정 테마 설정 |

---

## 초기화 메커니즘

모듈 최초 import 시 `getInitialTheme()`이 실행되어 localStorage의 `nemo-theme` 값을 읽고, `document.documentElement`의 `data-theme` 속성과 스토어 상태를 동기화합니다. SSR 환경(`typeof window === 'undefined'`)에서는 기본값 `'light'`를 사용합니다.

---

## uiStore와의 차이

| 항목 | themeStore | uiStore |
|---|---|---|
| localStorage 영속화 | 지원 (`nemo-theme` 키) | 미지원 |
| `setTheme` 직접 설정 | 지원 | 미지원 (toggleTheme만) |
| 사이드바 상태 | 없음 | 포함 |

---

## 주요 사용처

| 파일 | 사용 목적 |
|---|---|
| `components/ui/ThemeToggle.tsx` | 테마 토글 버튼 |
| `app/layout.tsx` | 초기 테마 적용 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
