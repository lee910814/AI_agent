# uiStore

> 사이드바 열림/닫힘 상태 및 라이트/다크 테마를 관리하는 UI 전용 Zustand 스토어

**파일 경로:** `frontend/src/stores/uiStore.ts`
**최종 수정일:** 2026-03-24

---

## 상태 (State)

| 필드 | 타입 | 초기값 | 설명 |
|---|---|---|---|
| `sidebarOpen` | `boolean` | `false` | 사이드바 열림 여부 (모바일 오버레이) |
| `sidebarCollapsed` | `boolean` | `false` | 사이드바 접힘 여부 (데스크톱 좁히기) |
| `theme` | `'dark' \| 'light'` | `'light'` | 현재 테마 |

---

## 액션 (Actions)

| 액션명 | 파라미터 | 설명 |
|---|---|---|
| `openSidebar` | — | 사이드바 열기 |
| `closeSidebar` | — | 사이드바 닫기 |
| `toggleSidebar` | — | 사이드바 토글 |
| `toggleSidebarCollapsed` | — | 사이드바 접힘 토글 |
| `toggleTheme` | — | 테마 전환 + `document.documentElement.setAttribute('data-theme', next)` 적용 |

---

## 참고 — themeStore와의 차이

`uiStore`의 테마 기능은 localStorage 영속화를 지원하지 않습니다. 페이지 새로고침 시 테마 복원이 필요하다면 `themeStore`를 사용하세요.

---

## 주요 사용처

| 파일 | 사용 목적 |
|---|---|
| `components/ui/Sidebar.tsx` | sidebarOpen, sidebarCollapsed 상태 구독 |
| `components/ui/Header.tsx` | 사이드바 토글 버튼 |
| `app/layout.tsx` | 테마 초기 적용 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
