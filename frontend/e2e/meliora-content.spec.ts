import { expect, test } from '@playwright/test';

const itemId = '46d70108-0df5-42e1-a4a3-b0560caa7f3c';
const businessId = 'meliora-test';
for (const platform of ['telegram', 'max']) {
  test(`${platform}: company facts, references, post edit, voice discussion and return`, async ({ page }) => {
    const errors: string[] = [];
    const chats: Record<string, unknown>[] = [];
    page.on('pageerror', error => errors.push(error.message));
    let draft = 'Пошив одежды для команды.';
    let saved = false;
    let founder = 'Начинали с небольшой мастерской.';
    await page.route('https://telegram.org/js/telegram-web-app.js*', route => route.fulfill({ body: '' }));
    await page.route('https://st.max.ru/js/max-web-app.js*', route => route.fulfill({ body: '' }));
    await page.addInitScript(({ platform }) => {
      localStorage.setItem('localos-mini-onboarding-v3:meliora-owner', 'completed');
      const open = (url: string) => document.documentElement.setAttribute('data-opened-bot', url);
      const bridge = { initData: 'fixture', ready() {}, expand() {}, openTelegramLink: open, openLink: open, openMaxLink: open };
      if (platform === 'telegram') Object.defineProperty(window, 'Telegram', { value: { WebApp: bridge }, configurable: true });
      else Object.defineProperty(window, 'WebApp', { value: bridge, configurable: true });
    }, { platform });
    await page.route('**/api/**', async route => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (path === `/api/operator/${platform}/bootstrap`) return route.fulfill({ json: {
        success: true, user: { id: 'meliora-owner' }, web_session_token: 'fixture-session', today_v2_enabled: false,
        selected_scope: { kind: 'business', id: businessId, name: 'Мелиора', business_ids: [businessId] },
        resolved_deep_link: { screen: 'content', item_type: 'content_item', item_id: itemId },
        summary: { attention_items: [] }, catalog: { businesses: [], networks: [], total_choices: 1 },
        navigation: ['today', 'operator', 'content'].map(key => ({ key, label: key, status: 'available', group: 'primary' })),
      } });
      if (path === '/api/operator/mobile/modules/content') return route.fulfill({ json: { items: [
        { id: 'other', business_id: businessId, plan_id: 'other-plan', plan_title: 'Другой план', title: 'Другой пост', draft_text: 'Другой текст', scheduled_for: '2060-02-01', version: 'v1' },
        { id: itemId, business_id: businessId, plan_id: 'selected-plan', plan_title: 'План Мелиоры', title: 'Одежда для команды', draft_text: draft, scheduled_for: '2060-01-01', updated_at: '2060-01-01T00:00:00Z', version: saved ? 'v2' : 'v1' },
      ] } });
      if (path === '/api/content-voice') {
        if (request.method() === 'PATCH') { expect(request.postDataJSON().expected_version).toBe(3); founder = request.postDataJSON().founder_story; }
        return route.fulfill({ json: { profile: { version: 3, summary: 'Спокойно', preferences: { business_description: 'Пошив одежды', editorial_notes: [{ id: 'founder', kind: 'founder_story', text: founder }] }, examples: [] } } });
      }
      if (path === '/api/content-voice/references') return route.fulfill({ json: { industry_label: 'Пошив одежды', items: [{ id: 'ref', source_name: 'Как показать качество пошива', source_url: 'https://example.test/ref', techniques: ['Показать детали'], scope: 'industry', enabled: true, moderation: 'approved', version: 1 }], settings_version: 1, can_manage: true, can_moderate: false, pending: [] } });
      if (path === `/api/operator/mobile/content/items/${itemId}` && request.method() === 'PUT') { expect(request.postDataJSON().expected_version).toBe('v1'); draft = request.postDataJSON().draft_text; saved = true; return route.fulfill({ json: { success: true } }); }
      if (path === '/api/operator/audio/config') return route.fulfill({ json: { input_enabled: true, output_enabled: false } });
      if (path === '/api/operator/audio/transcriptions') return route.fulfill({ status: 202, json: { asset_id: 'audio', job_id: 'audio-job', conversation_id: 'discussion' } });
      if (path === '/api/operator/mobile/jobs/audio-job') return route.fulfill({ json: { job: { status: 'completed', result: { transcript: 'Сделай этот пост короче' } } } });
      if (path === '/api/operator/chat') { chats.push(request.postDataJSON()); return route.fulfill({ json: { conversation_id: 'discussion', operator_result: { message_id: 'reply', status: 'completed', chat_response: 'Правка выбранного поста готова.' } } }); }
      if (path === '/api/operator/work-handoff') { expect(request.postDataJSON()).toMatchObject({ business_id: businessId, item_id: itemId, platform }); return route.fulfill({ json: { url: `https://${platform === 'max' ? 'max.ru' : 't.me'}/fixture_bot?start=work_fixture` } }); }
      return route.fulfill({ json: { success: true, items: [], summary: { attention_items: [] } } });
    });
    await page.goto(`/${platform}/control?screen=content&item_type=content_item&item_id=${itemId}`);
    await expect(page.getByRole('combobox', { name: 'Выбрать контент-план' })).toHaveValue('selected-plan');
    await page.getByRole('button', { name: 'О компании, основателе и стиле' }).click();
    await page.getByLabel('История основателя').fill('Я основала компанию после десяти лет практики.');
    await page.getByRole('button', { name: 'Как писать', exact: true }).click();
    await page.getByRole('button', { name: 'Сохранить', exact: true }).click();
    await expect(page.getByText(/Сохранено для будущих текстов/)).toBeVisible();
    await page.getByRole('button', { name: 'Ориентиры для постов' }).click();
    await expect(page.getByText('Как показать качество пошива')).toBeVisible();
    await page.getByRole('button', { name: 'Закрыть ориентиры', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Закрыть ориентиры', exact: true })).toHaveCount(0);
    await expect(page.getByRole('dialog', { name: 'Настроить контент' })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog', { name: 'Настроить контент' })).toHaveCount(0);
    await page.getByRole('button', { name: 'Редактировать текст' }).click();
    await page.getByRole('textbox', { name: 'Текст публикации' }).fill('Сохранённая правка Мелиоры.');
    await page.getByRole('button', { name: 'Сохранить', exact: true }).click();
    await expect.poll(() => saved).toBe(true);
    await expect(page.getByRole('textbox', { name: 'Текст публикации' })).toHaveCount(0);
    await page.getByRole('button', { name: 'Обсудить этот пост' }).click();
    await expect(page.getByText('Обсуждаем пост: Одежда для команды')).toBeVisible();
    await page.getByLabel('Загрузить аудио', { exact: true }).setInputFiles({ name: 'voice.ogg', mimeType: 'audio/ogg', buffer: Buffer.from('fixture transport') });
    await page.getByRole('button', { name: 'Распознать запись', exact: true }).click();
    await expect(page.getByText('Правка выбранного поста готова.', { exact: true })).toBeVisible();
    expect(chats).toHaveLength(1);
    expect(chats[0]).toMatchObject({ business_id: businessId, channel: `${platform}_mini_app`, transcription_id: 'audio', selected_object: { type: 'content_item', id: itemId } });
    await page.getByRole('button', { name: 'Вернуться к посту', exact: true }).click();
    await expect(page.getByRole('combobox', { name: 'Выбрать контент-план' })).toHaveValue('selected-plan');
    await page.getByRole('button', { name: `Продолжить в боте ${platform === 'max' ? 'MAX' : 'Telegram'}` }).click();
    await expect(page.locator('html')).toHaveAttribute('data-opened-bot', /fixture_bot/);
    expect(errors).toEqual([]);
  });
}
