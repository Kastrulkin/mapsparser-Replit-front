import { expect, test } from '@playwright/test';
test.use({ launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] } });

test('Mini App reviews voice before sending and keeps a text response', async ({ page }, testInfo) => {
  let chatCalls = 0;
  await page.route('https://telegram.org/js/telegram-web-app.js*', route => route.fulfill({ contentType: 'application/javascript', body: '' }));
  await page.addInitScript(() => { localStorage.setItem('localos-mini-onboarding-v3:voice-user', 'completed'); Object.defineProperty(window, 'Telegram', { configurable: true, value: { WebApp: { initData: 'signed-test', ready: () => {}, expand: () => {} } } }); });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/operator/telegram/bootstrap') return route.fulfill({ json: {
      success: true, user: { id: 'voice-user' }, web_session_token: 'voice-test', today_v2_enabled: false,
      selected_scope: { kind: 'business', id: 'voice-business', name: 'Тестовый бизнес', business_ids: ['voice-business'] },
      summary: { attention_items: [] }, catalog: { businesses: [], networks: [], total_choices: 1 },
      navigation: [{ key: 'today', label: 'Сегодня', group: 'primary', status: 'available' }, { key: 'operator', label: 'Оператор', group: 'primary', status: 'available' }],
    } });
    if (path === '/api/operator/audio/config') return route.fulfill({ json: { input_enabled: true, output_enabled: false } });
    if (path === '/api/operator/audio/transcriptions') return route.fulfill({ status: 202, json: { asset_id: 'asset-1', job_id: 'job-1', conversation_id: 'conversation-1' } });
    if (path === '/api/operator/mobile/jobs/job-1') return route.fulfill({ json: { job: { status: 'completed', result: { transcript: 'Подготовь пост про мастера' } } } });
    if (path === '/api/operator/chat') {
      chatCalls++;
      expect(route.request().postDataJSON()).toMatchObject({ message: 'Подготовь пост про нового мастера', transcription_id: 'asset-1', conversation_id: 'conversation-1', channel: 'telegram_mini_app' });
      return route.fulfill({ json: { conversation_id: 'conversation-1', operator_result: { message_id: 'reply-1', input_type: 'voice', status: 'completed', chat_response: 'Черновик поста подготовлен.' } } });
    }
    return route.fulfill({ json: { items: [], summary: { attention_items: [] } } });
  });
  await page.goto('/telegram/control');
  await page.getByRole('button', { name: 'Ещё', exact: true }).click();
  await page.getByRole('button', { name: 'Оператор', exact: true }).click();
  await page.getByLabel('Загрузить аудио', { exact: true }).setInputFiles({ name: 'voice.ogg', mimeType: 'audio/ogg', buffer: Buffer.from('mocked voice') });
  await page.getByRole('button', { name: 'Распознать запись' }).click();
  await expect(page.getByLabel('Проверьте команду')).toHaveValue('Подготовь пост про мастера');
  expect(chatCalls).toBe(0);
  await page.screenshot({ path: testInfo.outputPath('voice-review.png'), fullPage: true });
  await page.getByLabel('Проверьте команду').fill('Подготовь пост про нового мастера');
  await page.getByRole('button', { name: 'Отправить Оператору' }).click();
  await expect(page.getByText('Черновик поста подготовлен.', { exact: true })).toBeVisible();
  expect(chatCalls).toBe(1);
  await page.context().grantPermissions(['microphone']);
  await page.getByRole('button', { name: 'Записать голосом' }).click();
  await page.getByRole('button', { name: /Остановить/ }).click();
  await expect(page.getByRole('button', { name: 'Распознать запись' })).toBeVisible();
  await page.getByRole('button', { name: 'Отменить запись' }).click();
  expect(chatCalls).toBe(1);
});

test('web Operator sends reviewed voice through the same chat contract', async ({ page }, testInfo) => {
  let calls = 0;
  await page.addInitScript(() => {
    localStorage.setItem('auth_token', 'voice-test'); localStorage.setItem('selectedBusinessId', 'voice-business'); localStorage.setItem('language', 'ru');
  });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 'voice-user', email: 'voice@example.test', businesses: [{ id: 'voice-business', name: 'Тестовый бизнес', subscription_tier: 'concierge', subscription_status: 'active' }] } });
    if (path === '/api/business/voice-business') return route.fulfill({ json: { id: 'voice-business', name: 'Тестовый бизнес', subscription_tier: 'concierge', subscription_status: 'active' } });
    if (path === '/api/operator/audio/config') return route.fulfill({ json: { input_enabled: true, output_enabled: false } });
    if (path === '/api/operator/audio/transcriptions') return route.fulfill({ status: 202, json: { asset_id: 'web-a', job_id: 'web-j', conversation_id: 'web-c' } });
    if (path === '/api/operator/mobile/jobs/web-j') return route.fulfill({ json: { job: { status: 'completed', result: { transcript: 'Покажи отзывы' } } } });
    if (path === '/api/operator/chat') {
      calls++;
      expect(route.request().postDataJSON()).toMatchObject({ message: 'Покажи отзывы', transcription_id: 'web-a', conversation_id: 'web-c', channel: 'web' });
      return route.fulfill({ json: { conversation_id: 'web-c', operator_result: { message_id: 'web-reply', input_type: 'voice', status: 'completed', chat_response: 'Найдено четыре отзыва.' } } });
    }
    return route.fulfill({ json: { success: true, items: [], messages: [], businesses: [{ id: 'voice-business', name: 'Тестовый бизнес', subscription_tier: 'concierge', subscription_status: 'active' }] } });
  });
  await page.goto('/dashboard/operator');
  await page.getByLabel('Загрузить аудио', { exact: true }).setInputFiles({ name: 'voice.ogg', mimeType: 'audio/ogg', buffer: Buffer.from('mocked voice') });
  await page.getByRole('button', { name: 'Распознать запись' }).click();
  await expect(page.getByLabel('Проверьте команду')).toHaveValue('Покажи отзывы');
  expect(calls).toBe(0);
  await page.screenshot({ path: testInfo.outputPath('voice-review.png'), fullPage: true });
  await page.getByRole('button', { name: 'Отправить Оператору' }).click();
  await expect(page.getByText('Найдено четыре отзыва.', { exact: true })).toBeVisible();
  expect(calls).toBe(1);
});
