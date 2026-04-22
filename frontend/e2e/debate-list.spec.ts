import { test, expect } from '@playwright/test';
import { setupApiMocks, MOCK_TOPICS, captureRequest } from './helpers';

test.describe('Debate List Page', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/debate');
    await page.waitForLoadState('networkidle');
  });

  test('should render page title and navigation buttons', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'AI 토론', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: /내 에이전트/ })).toBeVisible();
    await page.screenshot({ path: 'screenshots/debate-list-page.png' });
  });

  test('should show topic/popular/ranking tabs', async ({ page }) => {
    await expect(page.getByRole('button', { name: '주제', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '인기', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '랭킹', exact: true })).toBeVisible();
  });

  test('should show status filter buttons', async ({ page }) => {
    await expect(page.getByRole('button', { name: '전체', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '참가 가능' })).toBeVisible();
    await expect(page.getByRole('button', { name: '진행 중' })).toBeVisible();
    await expect(page.getByRole('button', { name: '종료' })).toBeVisible();
    await page.screenshot({ path: 'screenshots/debate-list-filters.png' });
  });

  test('should display topic cards from mock data', async ({ page }) => {
    await expect(page.getByText(MOCK_TOPICS[0].title)).toBeVisible();
    await expect(page.getByText(MOCK_TOPICS[1].title)).toBeVisible();
  });

  test('should highlight active filter button', async ({ page }) => {
    const activeBtn = page.getByRole('button', { name: '전체', exact: true });
    await expect(activeBtn).toHaveClass(/bg-primary/);

    await page.getByRole('button', { name: '진행 중', exact: true }).click();
    await expect(page.getByRole('button', { name: '진행 중', exact: true })).toHaveClass(/bg-primary/);
    await page.screenshot({ path: 'screenshots/debate-list-filter-active.png' });
  });

  test('should open topic creation modal', async ({ page }) => {
    await page.getByRole('button', { name: '주제 제안' }).click();
    await expect(page.getByText('토론 주제 제안')).toBeVisible();
    await expect(page.getByPlaceholder('예: 원자력 발전은 친환경 에너지인가?')).toBeVisible();
    await page.screenshot({ path: 'screenshots/debate-list-create-modal.png' });
  });

  test('should switch to popular tab', async ({ page }) => {
    await page.getByRole('button', { name: '인기', exact: true }).click();
    await expect(page.getByRole('button', { name: '인기', exact: true })).toHaveClass(/bg-primary/);
    await page.screenshot({ path: 'screenshots/debate-list-popular-tab.png' });
  });

  test('should switch to ranking tab and show ranking entries', async ({ page }) => {
    await page.getByRole('button', { name: '랭킹', exact: true }).click();
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('논리왕 Alpha')).toBeVisible();
    await page.screenshot({ path: 'screenshots/debate-list-ranking-tab.png' });
  });
});

test.describe('인터랙션 / 기능 검증', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/debate');
    await page.waitForLoadState('networkidle');
  });

  test('참가 가능 필터 버튼 클릭 시 버튼 활성 스타일로 변경', async ({ page }) => {
    await page.getByRole('button', { name: '참가 가능', exact: true }).click();
    await expect(
      page.getByRole('button', { name: '참가 가능', exact: true }),
    ).toHaveClass(/bg-primary/);
    await page.screenshot({ path: 'screenshots/debate-list-open-filter-active.png' });
  });

  test('진행 중 필터 클릭 시 이전 필터(전체) 비활성화', async ({ page }) => {
    await page.getByRole('button', { name: '진행 중', exact: true }).click();

    // 전체 버튼은 비활성
    await expect(
      page.getByRole('button', { name: '전체', exact: true }),
    ).not.toHaveClass(/bg-primary/);
    // 진행 중 버튼만 활성
    await expect(
      page.getByRole('button', { name: '진행 중', exact: true }),
    ).toHaveClass(/bg-primary/);
    await page.screenshot({ path: 'screenshots/debate-list-in-progress-filter.png' });
  });

  test('주제 제안 버튼 클릭 → 모달 열림 → 내용 입력 → 제출 시 POST 요청 발생', async ({
    page,
  }) => {
    await page.getByRole('button', { name: '주제 제안' }).click();
    await expect(page.getByText('토론 주제 제안')).toBeVisible();

    await page.getByPlaceholder('예: 원자력 발전은 친환경 에너지인가?').fill('테스트 토론 주제');

    const [request] = await Promise.all([
      captureRequest(page, '/api/topics', 'POST'),
      page.getByRole('button', { name: '제안하기' }).click(),
    ]);

    expect(request.url).toContain('/api/topics');
    const body = request.body as Record<string, unknown>;
    expect(body.title).toBe('테스트 토론 주제');
    await page.screenshot({ path: 'screenshots/debate-list-topic-submit.png' });
  });

  test('토픽 카드 클릭 시 /debate/topics/{id} 페이지로 이동', async ({ page }) => {
    // TopicCard는 Link 또는 클릭 가능한 영역으로 이동
    const firstTopic = page.getByText(MOCK_TOPICS[0].title).first();
    await firstTopic.click();
    await expect(page).toHaveURL(/\/debate\/topics\//);
    await page.screenshot({ path: 'screenshots/debate-list-topic-click.png' });
  });

  test('랭킹 탭 클릭 시 랭킹 데이터 표시', async ({ page }) => {
    await page.getByRole('button', { name: '랭킹', exact: true }).click();
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('논리왕 Alpha')).toBeVisible();
    await expect(page.getByRole('button', { name: '랭킹', exact: true })).toHaveClass(/bg-primary/);
    await page.screenshot({ path: 'screenshots/debate-list-ranking-data.png' });
  });
});
