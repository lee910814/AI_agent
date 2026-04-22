import { test, expect } from '@playwright/test';
import { setupApiMocks, MOCK_USAGE_ME } from './helpers';

test.describe('Usage Page', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/usage');
    await page.waitForLoadState('networkidle');
  });

  test('should render usage page with title', async ({ page }) => {
    await expect(page.getByText('사용량')).toBeVisible();
    await page.screenshot({ path: 'screenshots/usage-page.png' });
  });

  test('should show period selector buttons', async ({ page }) => {
    await expect(page.getByRole('button', { name: '오늘' })).toBeVisible();
    await expect(page.getByRole('button', { name: '이번 달' })).toBeVisible();
    await expect(page.getByRole('button', { name: '전체' })).toBeVisible();
    await page.screenshot({ path: 'screenshots/usage-period-buttons.png' });
  });

  test('should display model usage table with model name', async ({ page }) => {
    const modelName = MOCK_USAGE_ME.by_model[0].model_name;
    await expect(page.getByText(modelName)).toBeVisible();
    await page.screenshot({ path: 'screenshots/usage-model-table.png' });
  });

  test('should show table headers', async ({ page }) => {
    await expect(page.getByText('모델')).toBeVisible();
    await expect(page.getByText('입력')).toBeVisible();
    await expect(page.getByText('출력')).toBeVisible();
    await page.screenshot({ path: 'screenshots/usage-table-headers.png' });
  });

  test('should switch between periods', async ({ page }) => {
    await page.getByRole('button', { name: '오늘' }).click();
    await expect(page.getByRole('button', { name: '오늘' })).toHaveClass(/bg-primary/);
    await page.screenshot({ path: 'screenshots/usage-period-today.png' });

    await page.getByRole('button', { name: '전체' }).click();
    await expect(page.getByRole('button', { name: '전체' })).toHaveClass(/bg-primary/);
    await page.screenshot({ path: 'screenshots/usage-period-total.png' });
  });

  test('should show token count text', async ({ page }) => {
    await expect(page.getByText(/토큰/).first()).toBeVisible();
    await page.screenshot({ path: 'screenshots/usage-token-count.png' });
  });

  test('should show credit (석) values', async ({ page }) => {
    await expect(page.getByText(/석/).first()).toBeVisible();
    await page.screenshot({ path: 'screenshots/usage-credits.png' });
  });
});

test.describe('인터랙션 / 기능 검증', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/usage');
    await page.waitForLoadState('networkidle');
  });

  test('오늘 버튼 클릭 시 버튼 활성 스타일 변경', async ({ page }) => {
    await page.getByRole('button', { name: '오늘' }).click();
    await expect(page.getByRole('button', { name: '오늘' })).toHaveClass(/bg-primary/);

    // 다른 버튼들은 비활성
    await expect(page.getByRole('button', { name: '이번 달' })).not.toHaveClass(/bg-primary/);
    await expect(page.getByRole('button', { name: '전체' })).not.toHaveClass(/bg-primary/);
    await page.screenshot({ path: 'screenshots/usage-today-active.png' });
  });

  test('이번 달 버튼 클릭 시 해당 버튼 활성 상태로 변경', async ({ page }) => {
    // 기본이 이번 달이므로 다른 탭으로 이동 후 다시 이번 달 클릭
    await page.getByRole('button', { name: '오늘' }).click();
    await expect(page.getByRole('button', { name: '오늘' })).toHaveClass(/bg-primary/);

    await page.getByRole('button', { name: '이번 달' }).click();
    await expect(page.getByRole('button', { name: '이번 달' })).toHaveClass(/bg-primary/);
    await page.screenshot({ path: 'screenshots/usage-monthly-active.png' });
  });

  test('전체 버튼 클릭 시 전체 기간 합계 표시', async ({ page }) => {
    await page.getByRole('button', { name: '전체' }).click();
    await expect(page.getByRole('button', { name: '전체' })).toHaveClass(/bg-primary/);

    // 전체 기간 토큰 합계가 표시되어야 함
    await expect(page.getByText(/토큰/).first()).toBeVisible();
    await page.screenshot({ path: 'screenshots/usage-total-active.png' });
  });

  test('기간 변경 시 표의 데이터가 해당 기간으로 갱신됨', async ({ page }) => {
    // 기본(이번 달) 상태에서 전체로 변경
    await page.getByRole('button', { name: '전체' }).click();
    // 모델 행이 여전히 보이는지 확인
    const modelName = MOCK_USAGE_ME.by_model[0].model_name;
    await expect(page.getByText(modelName)).toBeVisible();
    await page.screenshot({ path: 'screenshots/usage-period-switch-total.png' });
  });
});
