import { test, expect } from '@playwright/test';
import { setupApiMocks, MOCK_AGENTS, captureRequest, overrideRoute } from './helpers';

test.describe('Agents Page', () => {
  test.describe('My Agents List', () => {
    test('should show agent list page with header', async ({ page }) => {
      await setupApiMocks(page, 'user');
      await page.goto('/debate/agents');
      await page.waitForLoadState('networkidle');

      await expect(page.getByText('내 에이전트')).toBeVisible();
      await expect(page.getByRole('link', { name: /새 에이전트/ })).toBeVisible();
      await page.screenshot({ path: 'screenshots/agents-list.png' });
    });

    test('should render agent cards from mock data', async ({ page }) => {
      await setupApiMocks(page, 'user');
      await page.goto('/debate/agents');
      await page.waitForLoadState('networkidle');

      await expect(page.getByText(MOCK_AGENTS[0].name)).toBeVisible();
      await expect(page.getByText(MOCK_AGENTS[1].name)).toBeVisible();
    });
  });

  test.describe('Agent Creation', () => {
    test('should show creation form', async ({ page }) => {
      await setupApiMocks(page, 'user');
      await page.goto('/debate/agents/create');
      await page.waitForLoadState('networkidle');

      // Step 1: click to proceed without template
      await page.getByRole('button', { name: '직접 프롬프트 작성' }).click();

      await expect(page.getByRole('heading', { name: '에이전트 생성' })).toBeVisible();
      await expect(page.getByPlaceholder('My Debate Agent')).toBeVisible();
      await page.screenshot({ path: 'screenshots/agents-create-form.png' });
    });

    test('should show local agent guide when local provider selected', async ({ page }) => {
      await setupApiMocks(page, 'user');
      await page.goto('/debate/agents/create');
      await page.waitForLoadState('networkidle');

      // Step 1: click to proceed without template
      await page.getByRole('button', { name: '직접 프롬프트 작성' }).click();

      const providerSelect = page.locator('select').first();
      await providerSelect.selectOption('local');

      await expect(page.getByText('로컬 에이전트 안내')).toBeVisible();
      await page.screenshot({ path: 'screenshots/agents-create-local.png' });
    });

    test('should show API key field for openai provider', async ({ page }) => {
      await setupApiMocks(page, 'user');
      await page.goto('/debate/agents/create');
      await page.waitForLoadState('networkidle');

      // Step 1: click to proceed without template
      await page.getByRole('button', { name: '직접 프롬프트 작성' }).click();

      const providerSelect = page.locator('select').first();
      await providerSelect.selectOption('openai');

      // API key input should appear
      const apiKeyInput = page.locator('input[placeholder*="sk-"]');
      await expect(apiKeyInput).toBeVisible();
      await page.screenshot({ path: 'screenshots/agents-create-openai.png' });
    });
  });

  test.describe('Gallery', () => {
    test('should render gallery page', async ({ page }) => {
      await setupApiMocks(page, 'user');
      await page.goto('/debate/gallery');
      await page.waitForLoadState('networkidle');

      await page.screenshot({ path: 'screenshots/agents-gallery.png' });
    });
  });
});

test.describe('인터랙션 / 기능 검증', () => {
  test.describe('에이전트 생성 폼', () => {
    test('이름 / 설명 / provider / 모델명 입력 가능', async ({ page }) => {
      await setupApiMocks(page, 'user');
      await page.goto('/debate/agents/create');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: '직접 프롬프트 작성' }).click();

      await page.getByPlaceholder('My Debate Agent').fill('신규에이전트');
      await expect(page.getByPlaceholder('My Debate Agent')).toHaveValue('신규에이전트');

      await page.screenshot({ path: 'screenshots/agents-create-name-input.png' });
    });

    test('provider=local 선택 시 API 키 필드 숨김', async ({ page }) => {
      await setupApiMocks(page, 'user');
      await page.goto('/debate/agents/create');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: '직접 프롬프트 작성' }).click();

      const providerSelect = page.locator('select').first();
      await providerSelect.selectOption('local');

      // local provider는 API 키 불필요 — 필드가 없거나 숨겨짐
      const apiKeyInput = page.locator('input[placeholder*="sk-"]');
      await expect(apiKeyInput).not.toBeVisible();
      await page.screenshot({ path: 'screenshots/agents-create-local-no-apikey.png' });
    });

    test('provider=openai 선택 시 API 키 필드 표시', async ({ page }) => {
      await setupApiMocks(page, 'user');
      await page.goto('/debate/agents/create');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: '직접 프롬프트 작성' }).click();

      const providerSelect = page.locator('select').first();
      await providerSelect.selectOption('openai');

      await expect(page.locator('input[placeholder*="sk-"]')).toBeVisible();
      await page.screenshot({ path: 'screenshots/agents-create-openai-apikey.png' });
    });

    test('폼 제출 시 POST /api/agents 요청 발생', async ({ page }) => {
      await setupApiMocks(page, 'user');
      await page.goto('/debate/agents/create');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: '직접 프롬프트 작성' }).click();

      await page.getByPlaceholder('My Debate Agent').fill('테스트에이전트');

      // provider=local로 선택 (API 키 불필요)
      const providerSelect = page.locator('select').first();
      await providerSelect.selectOption('local');

      const [request] = await Promise.all([
        captureRequest(page, '/api/agents', 'POST'),
        page.getByRole('button', { name: '에이전트 생성' }).click(),
      ]);

      expect(request.url).toContain('/api/agents');
      await page.screenshot({ path: 'screenshots/agents-create-post-request.png' });
    });
  });

  test.describe('에이전트 삭제', () => {
    test('삭제 버튼 클릭 시 confirm 다이얼로그 후 DELETE 요청 발생', async ({ page }) => {
      await setupApiMocks(page, 'user');

      // DELETE /api/agents/{id} mock
      await overrideRoute(page, /\/api\/agents\/agent-\w+$/, 200, {});

      await page.goto('/debate/agents');
      await page.waitForLoadState('networkidle');

      // 브라우저 confirm 다이얼로그를 자동 수락
      page.on('dialog', (dialog) => dialog.accept());

      // 삭제 버튼은 hover 시 나타남 — 에이전트 카드에 hover
      const agentCard = page.locator('.relative.group').first();
      await agentCard.hover();

      const deleteBtn = agentCard.getByRole('button', { name: '삭제' });
      await expect(deleteBtn).toBeVisible({ timeout: 3000 });

      const [request] = await Promise.all([
        captureRequest(page, /\/api\/agents\//, 'DELETE'),
        deleteBtn.click(),
      ]);

      expect(request.url).toContain('/api/agents/');
      await page.screenshot({ path: 'screenshots/agents-delete-request.png' });
    });
  });
});
