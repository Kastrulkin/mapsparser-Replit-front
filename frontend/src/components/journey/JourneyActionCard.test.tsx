import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { runJourneyCommand, type JourneyAction } from '@/lib/leadJourney';
import { JourneyActionCard } from './JourneyActionCard';

vi.mock('@/lib/leadJourney', () => ({ runJourneyCommand: vi.fn() }));

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

describe('JourneyActionCard', () => {
  beforeEach(() => vi.clearAllMocks());

  it('sends the same version, surface and selected reply outcome to the controller', async () => {
    vi.mocked(runJourneyCommand).mockResolvedValue({ action, next_action: null });
    const updated = vi.fn();
    const user = userEvent.setup();
    render(<JourneyActionCard action={action} businessId="business-1" surface="telegram_mini_app" onUpdated={updated} />);

    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: 'Готов на бартер' }));
    await user.click(screen.getByRole('button', { name: /Сохранить ответ/ }));

    expect(runJourneyCommand).toHaveBeenCalledWith({
      action,
      businessId: 'business-1',
      command: 'record_reply',
      payload: { outcome: 'barter' },
      surface: 'telegram_mini_app',
    });
    expect(updated).toHaveBeenCalledTimes(1);
  });

  it('offers the no-reply follow-up as a separate explicit command', async () => {
    vi.mocked(runJourneyCommand).mockResolvedValue({ action, next_action: null });
    const user = userEvent.setup();
    render(<JourneyActionCard action={action} businessId="business-1" onUpdated={vi.fn()} />);

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
    render(<JourneyActionCard action={contentAction} businessId="business-1" surface="telegram_mini_app" onUpdated={vi.fn()} />);

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
    render(<JourneyActionCard action={automationAction} businessId="business-1" surface="telegram_mini_app" onUpdated={vi.fn()} />);

    const result = screen.getByDisplayValue('Подготовленные материалы для проверки');
    await user.clear(result);
    await user.type(result, 'Три черновика ответов без публикации');
    await user.click(screen.getByRole('button', { name: /Сохранить настройку/ }));

    expect(runJourneyCommand).toHaveBeenCalledWith(expect.objectContaining({
      command: 'save_configuration', surface: 'telegram_mini_app',
      payload: { use_case: 'reviews_without_reply', expected_result: 'Три черновика ответов без публикации' },
    }));
  });
});
