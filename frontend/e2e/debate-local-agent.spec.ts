import { test, expect } from '@playwright/test';
import { setupApiMocks } from './helpers';

const MOCK_DEVELOPER = {
  id: 'dev-001',
  login_id: 'devuser',
  nickname: 'devuser',
  role: 'user' as const,
  age_group: 'adult',
  adult_verified_at: '2026-01-15T00:00:00Z',
  preferred_llm_model_id: null,
  credit_balance: 100,
  subscription_plan_key: null,
};

const MOCK_LOCAL_AGENTS = [
  {
    id: 'agent-local-1',
    owner_id: 'dev-001',
    name: 'My Local Agent',
    description: 'Test local agent',
    provider: 'local',
    model_name: 'custom',
    elo_rating: 1500,
    wins: 0,
    losses: 0,
    draws: 0,
    is_active: true,
    is_connected: false,
    is_profile_public: true,
    use_platform_credits: false,
    tier: 'iron',
    owner_nickname: 'devuser',
    image_url: null,
    created_at: '2026-01-01T00:00:00Z',
  },
];

async function setupLocalAgentMocks(page: import('@playwright/test').Page) {
  await setupApiMocks(page, 'user');

  // Override auth/me with developer user
  await page.route('**/api/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_DEVELOPER),
    });
  });

  // Override agents with local agent data (broad catch-all)
  await page.route('**/api/agents/**', async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    if (url.match(/\/agents\/agent-local-1\/versions/)) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    } else if (url.match(/\/agents\/agent-local-1$/)) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_LOCAL_AGENTS[0]),
      });
    } else if (method === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ ...MOCK_LOCAL_AGENTS[0], id: 'agent-new-local' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: MOCK_LOCAL_AGENTS, total: MOCK_LOCAL_AGENTS.length }),
      });
    }
  });

  // /api/agents/me must return direct array (fetchMyAgents expects DebateAgent[])
  // Register AFTER the catch-all so it has higher priority (Playwright LIFO)
  await page.route('**/api/agents/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_LOCAL_AGENTS),
    });
  });
}

test.describe('Local Agent Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupLocalAgentMocks(page);
  });

  test('should display local agent in agent list', async ({ page }) => {
    await page.goto('/debate/agents');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('My Local Agent')).toBeVisible();
    await page.screenshot({ path: 'screenshots/local-agent-list.png' });
  });

  test('should show agent creation form with local provider option', async ({ page }) => {
    await page.goto('/debate/agents/create');
    await page.waitForLoadState('networkidle');

    // Step 1: advance past template selection
    await page.getByRole('button', { name: '직접 프롬프트 작성' }).click();

    const providerSelect = page.locator('select').first();
    await providerSelect.selectOption('local');

    await expect(page.getByText('로컬 에이전트 안내')).toBeVisible();
    await page.screenshot({ path: 'screenshots/local-agent-create-form.png' });
  });

  test('should not require API key for local provider', async ({ page }) => {
    await page.goto('/debate/agents/create');
    await page.waitForLoadState('networkidle');

    // Step 1: advance past template selection
    await page.getByRole('button', { name: '직접 프롬프트 작성' }).click();

    const providerSelect = page.locator('select').first();
    await providerSelect.selectOption('local');

    // API key field should be hidden for local provider
    const apiKeyInput = page.getByPlaceholder(/sk-|API 키/);
    const isVisible = await apiKeyInput.isVisible().catch(() => false);
    expect(isVisible).toBe(false);
    await page.screenshot({ path: 'screenshots/local-agent-no-api-key.png' });
  });

  test('should create local agent and redirect to agents list', async ({ page }) => {
    await page.goto('/debate/agents/create');
    await page.waitForLoadState('networkidle');

    // Step 1: advance past template selection
    await page.getByRole('button', { name: '직접 프롬프트 작성' }).click();

    await page.locator('select').first().selectOption('local');
    await page.getByPlaceholder('My Debate Agent').fill('New Local Agent');

    await page.getByRole('button', { name: '에이전트 생성' }).click();
    await page.waitForURL('**/debate/agents/**');
    await page.screenshot({ path: 'screenshots/local-agent-created.png' });
  });

  test('should show WebSocket connection guide on agent detail page', async ({ page }) => {
    await page.goto('/debate/agents/agent-local-1');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText(/WebSocket 연결/)).toBeVisible();
    await page.screenshot({ path: 'screenshots/local-agent-detail.png' });
  });

  test('should show WebSocket URL on agent detail page', async ({ page }) => {
    await page.goto('/debate/agents/agent-local-1');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText(/ws:\/\/.*\/ws\/agent\/agent-local-1/)).toBeVisible();
    await page.screenshot({ path: 'screenshots/local-agent-ws-url.png' });
  });
});
