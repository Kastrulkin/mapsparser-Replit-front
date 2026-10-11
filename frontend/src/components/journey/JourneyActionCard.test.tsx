import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageContext } from '@/i18n/LanguageContext.logic';
import { en } from '@/i18n/locales/en';
import { runJourneyCommand, type JourneyAction } from '@/lib/leadJourney';
import { JourneyActionCard } from './JourneyActionCard';

vi.mock('@/lib/leadJourney', () => ({
  createJourneyCommandIdempotencyKey: vi.fn(() => 'stable-command-key'),
  runJourneyCommand: vi.fn(),
}));

Object.defineProperties(HTMLElement.prototype, {
  hasPointerCapture: { configurable: true, value: () => false },
  setPointerCapture: { configurable: true, value: () => undefined },
  releasePointerCapture: { configurable: true, value: () => undefined },
  scrollIntoView: { configurable: true, value: () => undefined },
});

const action: JourneyAction = {
  id: 'action-1',
  business_id: 'business-1',
  flow_type: 'partnership',
  entity_type: 'lead_workstream',
  entity_id: 'workstream-1',
  action_type: 'check_reply',
  status: 'ready',
  priority: 120,
  title: 'Проверить ответ',
  description: 'Зафиксируйте реальный ответ.',
  cta_label: 'Указать результат',
  payload: {},
  allowed_commands: ['record_reply', 'prepare_followup'],
  version: 7,
};

const renderRussian = (
  nextAction: JourneyAction,
  onUpdated: (nextAction?: JourneyAction) => void,
  surface: 'web' | 'telegram_mini_app' = 'web',
) => render(
  <LanguageContext.Provider value={{ language: 'ru', setLanguage: vi.fn(), t: en }}>
    <JourneyActionCard action={nextAction} businessId="business-1" surface={surface} onUpdated={onUpdated} />
  </LanguageContext.Provider>,
);

describe('JourneyActionCard', () => {
  beforeEach(() => vi.clearAllMocks());

  it('sends the same version, surface and selected reply outcome to the controller', async () => {
    vi.mocked(runJourneyCommand).mockResolvedValue({ action, next_action: null });
    const updated = vi.fn();
    const user = userEvent.setup();
    renderRussian(action, updated, 'telegram_mini_app');

    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: 'Готов на бартер' }));
    await user.click(screen.getByRole('button', { name: /Сохранить ответ/ }));

    expect(runJourneyCommand).toHaveBeenCalledWith({
      action,
      businessId: 'business-1',
      command: 'record_reply',
      payload: { outcome: 'barter' },
      surface: 'telegram_mini_app',
      idempotencyKey: 'stable-command-key',
    });
    expect(updated).toHaveBeenCalledTimes(1);
  });

  it('offers the no-reply follow-up as a separate explicit command', async () => {
    vi.mocked(runJourneyCommand).mockResolvedValue({ action, next_action: null });
    const user = userEvent.setup();
    renderRussian(action, vi.fn());

    await user.click(screen.getByRole('button', { name: 'Ответа нет — follow-up' }));

    expect(runJourneyCommand).toHaveBeenCalledWith(expect.objectContaining({ command: 'prepare_followup' }));
  });

  it('saves an edited content draft through the shared web and Mini App controller', async () => {
    const contentAction: JourneyAction = {
      ...action,
      id: 'content-action', flow_type: 'content', entity_type: 'contentplanitem', entity_id: 'item-1',
      action_type: 'review_content', title: 'Проверить черновик', description: 'Отредактируйте текст.',
      payload: { content_excerpt: 'Первый вариант' }, allowed_commands: ['save_draft'], version: 2,
    };
    vi.mocked(runJourneyCommand).mockResolvedValue({ action: contentAction, next_action: null });
    const user = userEvent.setup();
    renderRussian(contentAction, vi.fn(), 'telegram_mini_app');

    const editor = screen.getByPlaceholderText('Проверьте и отредактируйте черновик');
    await user.clear(editor);
    await user.type(editor, 'Проверенный текст');
    await user.click(screen.getByRole('button', { name: /Сохранить черновик/ }));

    expect(runJourneyCommand).toHaveBeenCalledWith(expect.objectContaining({
      command: 'save_draft', surface: 'telegram_mini_app',
      payload: { draft_text: 'Проверенный текст', content_plan_item_id: 'item-1' },
    }));
  });

  it('collects a concrete automation task before preflight on Mini App', async () => {
    const automationAction: JourneyAction = {
      ...action,
      id: 'automation-action', flow_type: 'automation', entity_type: 'automation_use_case', entity_id: 'routine_control',
      action_type: 'configure_automation', title: 'Настроить первую задачу', description: 'Выберите повторяющуюся работу.',
      payload: {}, allowed_commands: ['save_configuration'], version: 1,
    };
    vi.mocked(runJourneyCommand).mockResolvedValue({ action: automationAction, next_action: null });
    const user = userEvent.setup();
    renderRussian(automationAction, vi.fn(), 'telegram_mini_app');

    const result = screen.getByDisplayValue('Подготовленные материалы для проверки');
    await user.clear(result);
    await user.type(result, 'Три черновика ответов без публикации');
    await user.click(screen.getByRole('button', { name: /Сохранить настройку/ }));

    expect(runJourneyCommand).toHaveBeenCalledWith(expect.objectContaining({
      command: 'save_configuration', surface: 'telegram_mini_app',
      payload: { use_case: 'reviews_without_reply', expected_result: 'Три черновика ответов без публикации' },
    }));
  });

  it('reuses the command key after a lost response and exposes the replayed next action', async () => {
    const nextAction: JourneyAction = {
      ...action,
      id: 'next-action',
      action_type: 'define_terms',
      title: 'Согласовать условия',
      allowed_commands: ['save_terms'],
      version: 1,
    };
    vi.mocked(runJourneyCommand)
      .mockRejectedValueOnce(new Error('Ошибка соединения'))
      .mockResolvedValueOnce({ action, next_action: nextAction, idempotent_replay: true });
    const updated = vi.fn();
    const user = userEvent.setup();
    renderRussian(action, updated);

    await user.click(screen.getByRole('button', { name: /Сохранить ответ/ }));
    expect(await screen.findByText('Ошибка соединения')).toBeVisible();
    await user.click(screen.getByRole('button', { name: /Сохранить ответ/ }));

    expect(runJourneyCommand).toHaveBeenCalledTimes(2);
    expect(vi.mocked(runJourneyCommand).mock.calls[0][0].idempotencyKey).toBe('stable-command-key');
    expect(vi.mocked(runJourneyCommand).mock.calls[1][0].idempotencyKey).toBe('stable-command-key');
    expect(updated).toHaveBeenCalledWith(nextAction);
  });
});
