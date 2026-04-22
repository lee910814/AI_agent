import { test, expect } from '@playwright/test';
import { setupApiMocks, MOCK_AGENTS } from './helpers';

test.describe('Ranking Page', () => {
  test('should render dedicated ranking page', async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/debate/ranking');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: 'ELO 랭킹' })).toBeVisible();
    await page.screenshot({ path: 'screenshots/ranking-page.png' });
  });

  test('should show overall/season tab buttons', async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/debate/ranking');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('button', { name: '누적 랭킹' })).toBeVisible();
    await expect(page.getByRole('button', { name: /시즌/ })).toBeVisible();
    await page.screenshot({ path: 'screenshots/ranking-tabs.png' });
  });

  test('should show agent names in ranking table', async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/debate/ranking');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText(MOCK_AGENTS[0].name)).toBeVisible();
    await page.screenshot({ path: 'screenshots/ranking-agents.png' });
  });

  test('should show ELO ratings', async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/debate/ranking');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText(String(MOCK_AGENTS[0].elo_rating))).toBeVisible();
    await page.screenshot({ path: 'screenshots/ranking-elo.png' });
  });

  test('should show ranking via debate page ranking tab', async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/debate');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: '랭킹' }).click();
    await page.waitForLoadState('networkidle');

    await expect(page.getByText(MOCK_AGENTS[0].name)).toBeVisible();
    await page.screenshot({ path: 'screenshots/debate-ranking-tab.png' });
  });
});

test.describe('인터랙션 / 기능 검증', () => {
  test('시즌 랭킹 탭 클릭 시 다른 데이터/상태 표시', async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/debate/ranking');
    await page.waitForLoadState('networkidle');

    const seasonTabBtn = page.getByRole('button', { name: /시즌/ });
    await seasonTabBtn.click();
    await page.waitForLoadState('networkidle');

    // 시즌 탭이 활성화되어야 함
    await expect(seasonTabBtn).toHaveClass(/bg-primary/);
    await page.screenshot({ path: 'screenshots/ranking-season-tab-active.png' });
  });

  test('누적 랭킹 탭 다시 클릭 시 원래 활성 상태로 복귀', async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/debate/ranking');
    await page.waitForLoadState('networkidle');

    // 시즌 탭으로 이동
    await page.getByRole('button', { name: /시즌/ }).click();
    await page.waitForLoadState('networkidle');

    // 누적 랭킹 탭 클릭
    const overallBtn = page.getByRole('button', { name: '누적 랭킹', exact: true });
    await overallBtn.click();
    await page.waitForLoadState('networkidle');

    await expect(overallBtn).toHaveClass(/bg-primary/);
    // 에이전트 이름이 다시 표시되어야 함
    await expect(page.getByText(MOCK_AGENTS[0].name)).toBeVisible();
    await page.screenshot({ path: 'screenshots/ranking-overall-tab-back.png' });
  });
});
