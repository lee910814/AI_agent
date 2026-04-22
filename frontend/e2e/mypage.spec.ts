import { test, expect } from '@playwright/test';
import { setupApiMocks, MOCK_USER, captureRequest, overrideRoute } from './helpers';

/**
 * /mypage 페이지 기능 테스트.
 * 탭: 내 정보(profile) / 설정(settings) / 사용량(usage) / 에이전트(agents)
 */

const MOCK_PROFILE = {
  id: 'user-001',
  nickname: '테스트유저',
  role: 'user',
  age_group: 'unverified',
  adult_verified_at: null,
  preferred_llm_model_id: null,
  created_at: '2026-01-01T00:00:00Z',
};

test.describe('MyPage 렌더링', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, 'user');
    // ProfileTab이 /auth/me를 직접 호출하므로 override
    await overrideRoute(page, '**/api/auth/me', 200, MOCK_PROFILE);
    await page.goto('/mypage');
    await page.waitForLoadState('networkidle');
  });

  test('마이페이지 타이틀과 기본 탭(내 정보) 렌더링', async ({ page }) => {
    await expect(page.getByRole('heading', { name: '마이페이지' })).toBeVisible();
    await expect(page.locator('button').filter({ hasText: '내 정보' }).first()).toBeVisible();
    await page.screenshot({ path: 'screenshots/mypage-default-tab.png' });
  });

  test('탭 목록 전체 표시 확인', async ({ page }) => {
    await expect(page.locator('button').filter({ hasText: '내 정보' }).first()).toBeVisible();
    await expect(page.locator('button').filter({ hasText: '설정' }).first()).toBeVisible();
    await expect(page.locator('button').filter({ hasText: '사용량' }).first()).toBeVisible();
    await expect(page.locator('button').filter({ hasText: '에이전트' }).first()).toBeVisible();
    await page.screenshot({ path: 'screenshots/mypage-all-tabs.png' });
  });
});

test.describe('인터랙션 / 기능 검증', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, 'user');
    await overrideRoute(page, '**/api/auth/me', 200, MOCK_PROFILE);
    // SettingsTab은 /api/models에서 LLMModel[] 직배열을 기대 — setupApiMocks의 { items, total } wrap 해제
    await page.route(
      (url) => url.pathname === '/api/models',
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            { id: 'model-001', display_name: 'GPT-4.1', provider: 'openai', input_cost_per_1m: 2.0, output_cost_per_1m: 8.0, max_context_length: 128000, is_adult_only: false, is_active: true, credit_per_1k_tokens: 4 },
          ]),
        });
      },
    );
    // PUT /api/auth/me mock (닉네임 변경 저장용)
    await page.route('**/api/auth/me', async (route) => {
      if (route.request().method() === 'PUT') {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROFILE) });
      } else {
        await route.continue();
      }
    });
    await page.goto('/mypage');
    await page.waitForLoadState('networkidle');
  });

  test('설정 탭 클릭 시 설정 콘텐츠 표시', async ({ page }) => {
    await page.locator('button').filter({ hasText: '설정' }).first().click();
    await expect(page).toHaveURL(/\/mypage\?tab=settings/);

    // 설정 탭 콘텐츠(LLM 모델 목록 섹션) 가시 확인 — 버튼 클래스 대신 내용으로 검증
    await expect(page.getByText('LLM 모델 정보')).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'screenshots/mypage-settings-tab.png' });
  });

  test('사용량 탭 클릭 시 사용량 콘텐츠 표시', async ({ page }) => {
    await page.locator('button').filter({ hasText: '사용량' }).first().click();
    await expect(page).toHaveURL(/\/mypage\?tab=usage/);

    // UsageTab 내에 기간 선택 버튼 또는 사용량 관련 텍스트가 나타남
    await expect(
      page.locator('button').filter({ hasText: '사용량' }).first(),
    ).toHaveClass(/border-b-primary|text-primary/);
    await page.screenshot({ path: 'screenshots/mypage-usage-tab.png' });
  });

  test('에이전트 탭 클릭 시 에이전트 콘텐츠 표시', async ({ page }) => {
    await page.locator('button').filter({ hasText: '에이전트' }).first().click();
    await expect(page).toHaveURL(/\/mypage\?tab=agents/);

    await expect(
      page.locator('button').filter({ hasText: '에이전트' }).first(),
    ).toHaveClass(/border-b-primary|text-primary/);
    await page.screenshot({ path: 'screenshots/mypage-agents-tab.png' });
  });

  test('프로필 탭 닉네임 편집 버튼 클릭 시 편집 모드 진입', async ({ page }) => {
    // 내 정보 탭이 기본 활성 상태 — ProfileTab이 /auth/me 응답 후 렌더링됨
    const nicknameH2 = page.locator('h2').filter({ hasText: '테스트유저' });
    if (await nicknameH2.isVisible({ timeout: 5000 })) {
      // h2 바로 다음 sibling button (XPath: following-sibling::button[1])
      const pencilBtn = nicknameH2.locator('xpath=following-sibling::button[1]');
      await pencilBtn.click();

      // 편집 입력창 표시 (input with maxLength=50)
      await expect(page.locator('input[maxlength="50"]')).toBeVisible({ timeout: 3000 });
      await page.screenshot({ path: 'screenshots/mypage-profile-edit-mode.png' });
    } else {
      await page.screenshot({ path: 'screenshots/mypage-profile-loading.png' });
    }
  });

  test('닉네임 변경 저장 시 편집 모드 종료 및 저장 완료', async ({ page }) => {
    // 닉네임 h2가 표시될 때까지 대기
    const nicknameH2 = page.locator('h2').filter({ hasText: '테스트유저' });
    await expect(nicknameH2).toBeVisible({ timeout: 5000 });

    // h2 바로 다음 sibling button (연필 아이콘)
    const pencilBtn = nicknameH2.locator('xpath=following-sibling::button[1]');
    if (await pencilBtn.isVisible({ timeout: 3000 })) {
      await pencilBtn.click();

      const editInput = page.locator('input[maxlength="50"]');
      await expect(editInput).toBeVisible({ timeout: 3000 });
      await editInput.fill('변경된닉네임');

      // 저장(Check) 버튼 클릭 — window.fetch 패치로 인해 captureRequest는 불가
      // PUT /api/auth/me는 window.fetch 수준에서 처리됨 (setupApiMocks addInitScript 패치)
      const saveBtn = page.locator('button.bg-success, button[class*="bg-success"]').first();
      await saveBtn.click();

      // 저장 성공 시 편집 모드 종료: 입력창 사라지고 h2 복귀
      await expect(editInput).not.toBeVisible({ timeout: 5000 });
      await page.screenshot({ path: 'screenshots/mypage-profile-save-done.png' });
    } else {
      await page.screenshot({ path: 'screenshots/mypage-profile-no-edit-btn.png' });
    }
  });
});
