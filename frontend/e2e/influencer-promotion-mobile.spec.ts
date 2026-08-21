import { expect, test } from '@playwright/test';

const business = {
  id: 'business-1',
  name: 'Органика',
  city: 'Санкт-Петербург',
  subscription_tier: 'business',
  subscription_status: 'active',
  creator_promotion_available: true,
};

const results = Array.from({ length: 31 }, (_, index) => ({
  id: `result-${index}`,
  creator_profile_id: `creator-${index}`,
  display_name: `Автор ${index + 1}`,
  result_group: index < 5 ? 'best_fit' : 'needs_review',
  shortlist_status: index === 30 ? 'shortlisted' : 'suggested',
  score: 90 - index,
  reasons: ['Есть подтверждённая связь с Санкт-Петербургом'],
  canonical_url: `https://t.me/creator_${index}`,
}));

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem('auth_token', 'mobile-qa-token');
    window.localStorage.setItem('selectedBusinessId', 'business-1');
  });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/me') {
      await route.fulfill({ json: { id: 'user-1', email: 'qa@localos.pro', is_superadmin: true, businesses: [business] } });
      return;
    }
    if (path === '/api/promotion/influencers/overview') {
      await route.fulfill({ json: {
        overview: {
          feature_state: { discovery: true, outreach: true, metrics: true },
          latest_search: { id: 'search-1' },
          campaigns: [{
            id: 'campaign-1',
            title: 'Локальное продвижение · Органика',
            goal: 'Получить локальный охват и обращения',
            status: 'draft',
            candidates: [{ id: 'candidate-1', display_name: 'Автор 31', platform: 'telegram' }],
          }],
          collaborations: [{
            id: 'collaboration-1',
            display_name: 'Автор 31',
            status: 'measuring',
            deliverables: [{
              id: 'deliverable-1',
              platform: 'telegram',
              deliverable_type: 'post',
              publication_url: 'https://t.me/creator_31/10',
              verification_status: 'verified',
              tracking: {
                tracked_url: 'https://organika.example/book?utm_source=telegram',
                promo_code: 'ORGANIKA15',
                cta: 'Записаться на консультацию',
              },
              measurement_checkpoints: [
                { checkpoint: '24h', status: 'pending', due_at: '2026-08-22T10:00:00Z' },
                { checkpoint: '7d', status: 'pending', due_at: '2026-08-28T10:00:00Z' },
                { checkpoint: '14d', status: 'pending', due_at: '2026-09-04T10:00:00Z' },
              ],
            }],
          }],
          metrics: {},
          next_action: 'Проверить найденных авторов',
        },
      } });
      return;
    }
    if (path === '/api/promotion/influencers/searches/search-1') {
      await route.fulfill({ json: { search: { id: 'search-1', status: 'ready', results } } });
      return;
    }
    if (path === '/api/promotion/influencers/campaigns/campaign-1/candidates/candidate-1/outreach-preview') {
      await route.fulfill({ json: {
        preview: {
          display_name: 'Автор 31',
          message: 'Здравствуйте!\n\nВидим, что вы рассказываете о локальном wellness.',
          personalization: { summary: 'Публичный профиль посвящён локальному wellness' },
          contact: { status: 'public_unverified', value: '@creator_31' },
          terms_review: { missing: ['бюджет или бартер', 'сроки', 'права на материал'] },
          requires_campaign_approval: true,
        },
      } });
      return;
    }
    await route.fulfill({ json: {} });
  });
});

test('keeps the first review batch usable on a phone and preserves the approval gate', async ({ page }) => {
  await page.goto('/dashboard/promotion/influencers');

  await expect(page.getByRole('heading', { name: 'Локальные авторы' })).toBeVisible();
  await expect(page.getByText(/30 из 31/)).toBeVisible();
  await expect(page.locator('article')).toHaveCount(30);
  await expect(page.getByRole('button', { name: 'Показать ещё 1' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

  const searchTab = page.getByRole('tab', { name: 'Поиск' });
  await searchTab.focus();
  await searchTab.press('ArrowRight');

  const campaignTab = page.getByRole('tab', { name: 'Кампании' });
  await expect(campaignTab).toBeFocused();
  await expect(campaignTab).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('button', { name: 'Подготовить контакт: Автор 31' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Подтвердить условия' })).toBeVisible();
  await page.getByRole('button', { name: 'Черновик приглашения: Автор 31' }).click();
  await expect(page.getByText(/локальном wellness/)).toBeVisible();
  await expect(page.getByText(/принадлежность не подтверждена/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

  await page.getByRole('tab', { name: 'Коллаборации' }).click();
  await expect(page.getByText('ORGANIKA15')).toBeVisible();
  await expect(page.getByRole('button', { name: '24 часа' })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Ссылка бизнеса для UTM' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});
