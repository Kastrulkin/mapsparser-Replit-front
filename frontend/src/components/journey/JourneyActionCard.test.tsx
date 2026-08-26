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
});
