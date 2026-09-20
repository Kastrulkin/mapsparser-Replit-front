import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageContext, type Language } from '@/i18n/LanguageContext.logic';
import { journeyActionCopy } from '@/i18n/journeyActionCopy';
import { en } from '@/i18n/locales/en';
import { runJourneyCommand, type JourneyAction } from '@/lib/leadJourney';

import { JourneyActionCard } from './JourneyActionCard';

vi.mock('@/lib/leadJourney', () => ({
  createJourneyCommandIdempotencyKey: vi.fn(() => 'locale-command-key'),
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
  title: 'Проверить ответ владельца',
  description: 'Зафиксируйте только фактический ответ.',
  cta_label: 'Указать результат',
  payload: {},
  allowed_commands: ['record_reply', 'prepare_followup'],
  version: 7,
};

const renderLocalized = (language: Language, nextAction: JourneyAction = action) => render(
  <LanguageContext.Provider value={{ language, setLanguage: vi.fn(), t: en }}>
    <JourneyActionCard action={nextAction} businessId="business-1" surface="telegram_mini_app" onUpdated={vi.fn()} />
  </LanguageContext.Provider>,
);

const localizedCard = (language: Language, nextAction: JourneyAction) => (
  <LanguageContext.Provider value={{ language, setLanguage: vi.fn(), t: en }}>
    <JourneyActionCard action={nextAction} businessId="business-1" surface="telegram_mini_app" onUpdated={vi.fn()} />
  </LanguageContext.Provider>
);

const languages: Language[] = ['ru', 'en', 'fr', 'es', 'el', 'de', 'th', 'ar', 'ha', 'tr'];
let originalClipboardDescriptor: PropertyDescriptor | undefined;

describe('JourneyActionCard localization', () => {
  beforeEach(() => {
    vi.mocked(runJourneyCommand).mockReset();
    originalClipboardDescriptor = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
  });

  afterEach(() => {
    vi.restoreAllMocks();
    if (originalClipboardDescriptor) {
      Object.defineProperty(navigator, 'clipboard', originalClipboardDescriptor);
      return;
    }
    Reflect.deleteProperty(navigator, 'clipboard');
  });

  it('renders Spanish chrome, command and reply choice while preserving the server action text', async () => {
    vi.mocked(runJourneyCommand).mockResolvedValue({ action, next_action: null });
    const user = userEvent.setup();
    renderLocalized('es');

    expect(screen.getByText('Qué hacer ahora')).toBeVisible();
    expect(screen.getByText('Проверить ответ владельца')).toBeVisible();
    expect(screen.getByText('Зафиксируйте только фактический ответ.')).toBeVisible();
    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: 'Abierto al trueque' }));
    await user.click(screen.getByRole('button', { name: 'Guardar respuesta' }));
  });

  it('renders English chrome and command labels', () => {
    renderLocalized('en');

    expect(screen.getByText('What to do now')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Save reply' })).toBeVisible();
  });

  it('formats a due date in the selected Spanish locale', () => {
    const dueAt = '2026-03-22T15:30:00.000Z';
    renderLocalized('es', { ...action, due_at: dueAt });

    expect(screen.getByText(
      (content) => content.endsWith(new Date(dueAt).toLocaleString('es')),
      { selector: 'p' },
    )).toBeVisible();
  });

  it('keeps owner draft, unknown CTA and API error verbatim', async () => {
    const unknownAction: JourneyAction = {
      ...action,
      id: 'unknown-action',
      action_type: 'review_content',
      title: 'Черновик владельца',
      description: 'Не переводить содержание сообщения.',
      cta_label: 'Сохранить вручную',
      payload: { draft_text: 'Точный текст от владельца' },
      allowed_commands: ['custom_owner_command'],
    };
    vi.mocked(runJourneyCommand).mockRejectedValue(new Error('API: черновик устарел'));
    const user = userEvent.setup();
    renderLocalized('es', unknownAction);

    expect(screen.getByText('Черновик владельца')).toBeVisible();
    expect(screen.getByText('Не переводить содержание сообщения.')).toBeVisible();
    expect(screen.getByDisplayValue('Точный текст от владельца')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Сохранить вручную' }));
    expect(await screen.findByText('API: черновик устарел')).toBeVisible();
  });

  it('keeps the reply command payload, surface and retry identity under Spanish copy', async () => {
    vi.mocked(runJourneyCommand)
      .mockRejectedValueOnce(new Error('API: повторите'))
      .mockResolvedValueOnce({ action, next_action: null });
    const user = userEvent.setup();
    renderLocalized('es');

    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: 'Abierto al trueque' }));
    await user.click(screen.getByRole('button', { name: 'Guardar respuesta' }));
    expect(await screen.findByText('API: повторите')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Guardar respuesta' }));

    expect(runJourneyCommand).toHaveBeenCalledTimes(2);
    expect(vi.mocked(runJourneyCommand).mock.calls[0][0]).toMatchObject({
      action,
      businessId: 'business-1',
      command: 'record_reply',
      payload: { outcome: 'barter' },
      surface: 'telegram_mini_app',
      idempotencyKey: 'locale-command-key',
    });
    expect(vi.mocked(runJourneyCommand).mock.calls[1][0].idempotencyKey).toBe('locale-command-key');
  });

  it.each(languages)('uses the complete %s heading, reply command and barter option', async (language) => {
    vi.mocked(runJourneyCommand).mockResolvedValue({ action, next_action: null });
    const user = userEvent.setup();
    const copy = journeyActionCopy(language);
    renderLocalized(language);

    expect(screen.getByText(copy.now)).toBeVisible();
    expect(screen.getByRole('button', { name: copy.commands.record_reply })).toBeVisible();
    await user.click(screen.getByRole('combobox'));
    expect(await screen.findByRole('option', { name: copy.outcomes.barter })).toBeVisible();
  });

  it('changes only an absent automation default when the language context changes', () => {
    const automationAction: JourneyAction = {
      ...action,
      id: 'automation-default',
      action_type: 'configure_automation',
      payload: {},
      allowed_commands: ['save_configuration'],
    };
    const view = renderLocalized('ru', automationAction);
    expect(screen.getByDisplayValue(journeyActionCopy('ru').defaultExpectedResult)).toBeVisible();

    view.rerender(localizedCard('es', automationAction));
    expect(screen.getByDisplayValue(journeyActionCopy('es').defaultExpectedResult)).toBeVisible();
    view.rerender(localizedCard('en', automationAction));
    expect(screen.getByDisplayValue(journeyActionCopy('en').defaultExpectedResult)).toBeVisible();
  });

  it('preserves a supplied expected result and an operator edit across language changes', async () => {
    const automationAction: JourneyAction = {
      ...action,
      id: 'automation-supplied',
      action_type: 'configure_automation',
      payload: { expected_result: 'Согласованный результат владельца' },
      allowed_commands: ['save_configuration'],
    };
    const user = userEvent.setup();
    const view = renderLocalized('ru', automationAction);
    const expectedResult = screen.getByDisplayValue('Согласованный результат владельца');

    view.rerender(localizedCard('es', automationAction));
    expect(screen.getByDisplayValue('Согласованный результат владельца')).toBeVisible();
    await user.clear(expectedResult);
    await user.type(expectedResult, 'Edited by operator');
    view.rerender(localizedCard('en', automationAction));
    expect(screen.getByDisplayValue('Edited by operator')).toBeVisible();
  });

  it('preserves an explicitly supplied empty expected result across language changes', () => {
    const automationAction: JourneyAction = {
      ...action,
      id: 'automation-empty',
      action_type: 'configure_automation',
      payload: { expected_result: '' },
      allowed_commands: ['save_configuration'],
    };
    const view = renderLocalized('ru', automationAction);
    expect(screen.getByDisplayValue('')).toBeVisible();

    view.rerender(localizedCard('es', automationAction));
    expect(screen.getByDisplayValue('')).toBeVisible();
  });

  it('preserves an operator-cleared default expected result across language changes', async () => {
    const automationAction: JourneyAction = {
      ...action,
      id: 'automation-cleared',
      action_type: 'configure_automation',
      payload: {},
      allowed_commands: ['save_configuration'],
    };
    const user = userEvent.setup();
    const view = renderLocalized('ru', automationAction);
    const expectedResult = screen.getByDisplayValue(journeyActionCopy('ru').defaultExpectedResult);
    await user.clear(expectedResult);

    view.rerender(localizedCard('es', automationAction));
    expect(screen.getByDisplayValue('')).toBeVisible();
  });

  it('localizes editable form labels, copy and the generic save fallback', async () => {
    const copyAction: JourneyAction = {
      ...action,
      id: 'copy-action',
      action_type: 'define_terms',
      allowed_commands: ['copy', 'save_terms'],
    };
    const user = userEvent.setup();
    const copy = journeyActionCopy('es');
    vi.mocked(runJourneyCommand).mockRejectedValue('network unavailable');
    const view = renderLocalized('es', copyAction);

    expect(screen.getByPlaceholderText(copy.termsOrComment)).toBeVisible();
    expect(screen.getByRole('button', { name: copy.copy })).toBeVisible();
    await user.click(screen.getByRole('button', { name: copy.commands.save_terms }));
    expect(await screen.findByText(copy.saveError)).toBeVisible();

    view.unmount();
    renderLocalized('es', { ...copyAction, id: 'approval-action', action_type: 'approve_plan', allowed_commands: ['approve'] });
    expect(screen.getByRole('button', { name: copy.commands.approve })).toBeVisible();
  });

  it('copies the exact server bytes and records the separate copy command', async () => {
    const copyAction: JourneyAction = {
      ...action,
      id: 'copy-bytes',
      payload: { message: 'Строка владельца\nбез локализации' },
      allowed_commands: ['copy', 'prepare_followup'],
    };
    vi.mocked(runJourneyCommand).mockResolvedValue({ action: copyAction, next_action: null });
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue(undefined);
    renderLocalized('es', copyAction);

    await user.click(screen.getByRole('button', { name: journeyActionCopy('es').copy }));
    expect(writeText).toHaveBeenCalledWith('Строка владельца\nбез локализации');
    expect(runJourneyCommand).toHaveBeenCalledWith(expect.objectContaining({
      command: 'copy',
      payload: {},
      surface: 'telegram_mini_app',
    }));
  });

  it('sends the unchanged approval payload under localized command copy', async () => {
    const approvalAction: JourneyAction = {
      ...action,
      id: 'approval-payload',
      action_type: 'approve_plan',
      allowed_commands: ['approve'],
    };
    vi.mocked(runJourneyCommand).mockResolvedValue({ action: approvalAction, next_action: null });
    const user = userEvent.setup();
    renderLocalized('es', approvalAction);

    await user.click(screen.getByRole('button', { name: journeyActionCopy('es').commands.approve }));
    expect(runJourneyCommand).toHaveBeenCalledWith(expect.objectContaining({
      action: approvalAction,
      command: 'approve',
      payload: { confirmed: true },
      surface: 'telegram_mini_app',
    }));
  });

  it('saves an operator-edited expected result after a language switch without translating it', async () => {
    const automationAction: JourneyAction = {
      ...action,
      id: 'automation-save-edited',
      action_type: 'configure_automation',
      payload: { expected_result: 'Результат владельца' },
      allowed_commands: ['save_configuration'],
    };
    vi.mocked(runJourneyCommand).mockResolvedValue({ action: automationAction, next_action: null });
    const user = userEvent.setup();
    const view = renderLocalized('ru', automationAction);
    const expectedResult = screen.getByDisplayValue('Результат владельца');
    await user.clear(expectedResult);
    await user.type(expectedResult, 'Edited operator result');
    view.rerender(localizedCard('es', automationAction));
    await user.click(screen.getByRole('button', { name: journeyActionCopy('es').commands.save_configuration }));

    expect(runJourneyCommand).toHaveBeenCalledWith(expect.objectContaining({
      command: 'save_configuration',
      payload: { use_case: 'reviews_without_reply', expected_result: 'Edited operator result' },
    }));
  });

  it('saves an explicitly cleared expected result after a language switch', async () => {
    const automationAction: JourneyAction = {
      ...action,
      id: 'automation-save-cleared',
      action_type: 'configure_automation',
      payload: {},
      allowed_commands: ['save_configuration'],
    };
    vi.mocked(runJourneyCommand).mockResolvedValue({ action: automationAction, next_action: null });
    const user = userEvent.setup();
    const view = renderLocalized('ru', automationAction);
    const expectedResult = screen.getByDisplayValue(journeyActionCopy('ru').defaultExpectedResult);
    await user.clear(expectedResult);
    view.rerender(localizedCard('es', automationAction));
    await user.click(screen.getByRole('button', { name: journeyActionCopy('es').commands.save_configuration }));

    expect(runJourneyCommand).toHaveBeenCalledWith(expect.objectContaining({
      command: 'save_configuration',
      payload: { use_case: 'reviews_without_reply', expected_result: '' },
    }));
  });

  it.each(languages)('keeps every %s command, outcome and use-case key aligned with Russian', (language) => {
    const reference = journeyActionCopy('ru');
    const copy = journeyActionCopy(language);

    expect(Object.keys(copy.commands).sort()).toEqual(Object.keys(reference.commands).sort());
    expect(Object.keys(copy.outcomes).sort()).toEqual(Object.keys(reference.outcomes).sort());
    expect(Object.keys(copy.useCases).sort()).toEqual(Object.keys(reference.useCases).sort());
  });
});
