import test, { expect } from './offline-test';
test('client communication keeps settings, sandbox and conversations separate', async ({ page }) => {
  await page.addInitScript(() => { localStorage.setItem('auth_token','mocked-agent-token'); localStorage.setItem('selectedBusinessId','business-1'); localStorage.setItem('language','ru'); });
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/me') return route.fulfill({json:{id:'user-1',email:'test@example.test',businesses:[{id:'business-1',name:'Test salon',subscription_tier:'concierge',subscription_status:'active'}]}});
    return route.fulfill({json:{agents:[],conversations:[],messages:[],blueprints:[],templates:[]}});
  });
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/dashboard/agents?section=clients');
  await expect(page.getByRole('heading',{name:'Общение с клиентами',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Проверка ответов',exact:true}).click();
  await expect(page).toHaveURL(/view=test/);
  await page.getByRole('button',{name:'Диалоги',exact:true}).click();
  await expect(page).toHaveURL(/view=conversations/);
  await page.getByRole('button',{name:'Поведение и включение',exact:true}).click();
  await expect(page).toHaveURL(/view=settings/);
  await page.screenshot({path:'/tmp/client-communication-browser.png',fullPage:true});
  expect(errors).toEqual([]);
});
