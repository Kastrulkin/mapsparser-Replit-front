import { StrictMode } from 'react';
import '@testing-library/jest-dom/vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageContext } from '@/i18n/LanguageContext.logic';
import { en } from '@/i18n/locales/en';
import { runJourneyCommand, type JourneyAction } from '@/lib/leadJourney';

import { JourneyActionCard } from './JourneyActionCard';

vi.mock('@/lib/leadJourney', () => ({
  createJourneyCommandIdempotencyKey: vi.fn(() => 'scope-command-key'),
  runJourneyCommand: vi.fn(),
}));

Object.defineProperties(HTMLElement.prototype, {
  hasPointerCapture: { configurable: true, value: () => false },
  setPointerCapture: { configurable: true, value: () => undefined },
  releasePointerCapture: { configurable: true, value: () => undefined },
  scrollIntoView: { configurable: true, value: () => undefined },
});

const contentAction = (id: string, draftText: string, version = 1): JourneyAction => ({
  id,
  business_id: 'business-1',
  flow_type: 'content',
  entity_type: 'contentplanitem',
  entity_id: 'content-item-1',
  action_type: 'review_content',
  status: 'ready',
  priority: 100,
  title: `Проверить черновик ${id}`,
  description: 'Проверьте текст до сохранения.',
  cta_label: 'Сохранить черновик',
  payload: { draft_text: draftText },
  allowed_commands: ['save_draft'],
  version,
});

const contentStep = (id: string, actionType: string): JourneyAction => ({
  ...contentAction(id, ''),
  action_type: actionType,
  title: `Контентный шаг ${actionType}`,
  allowed_commands: ['complete'],
});

const replyAction = (id: string, businessId = 'business-1'): JourneyAction => ({
  id,
  business_id: businessId,
  flow_type: 'partnership',
  entity_type: 'lead_workstream',
  entity_id: 'workstream-1',
  action_type: 'check_reply',
  status: 'ready',
  priority: 100,
  title: `Проверить ответ ${id}`,
  description: 'Зафиксируйте ответ.',
  cta_label: 'Сохранить ответ',
  payload: {},
  allowed_commands: ['record_reply'],
  version: 1,
});

const copyAction = (id: string): JourneyAction => ({
  ...replyAction(id),
  action_type: 'prepare_followup',
  payload: { message: 'Точный текст для копирования' },
  allowed_commands: ['copy', 'prepare_followup'],
});

const card = (
  action: JourneyAction,
  businessId: string,
  onUpdated: (nextAction?: JourneyAction) => void,
  surface: 'web' | 'telegram_mini_app' = 'telegram_mini_app',
) => (
  <LanguageContext.Provider value={{ language: 'ru', setLanguage: vi.fn(), t: en }}>
    <JourneyActionCard action={action} businessId={businessId} surface={surface} onUpdated={onUpdated} />
  </LanguageContext.Provider>
);

const deferredCommand = () => {
  let resolve: (value: { action: JourneyAction; next_action: JourneyAction | null }) => void = () => undefined;
  let reject: (reason?: unknown) => void = () => undefined;
  const promise = new Promise<{ action: JourneyAction; next_action: JourneyAction | null }>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
};

describe('JourneyActionCard action scope', () => {
  beforeEach(() => {
    vi.mocked(runJourneyCommand).mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('replaces an edited content review A with a fresh supported review B after the backend cleared its draft', async () => {
    const actionA = contentAction('review-A', 'Черновик A');
    const actionB = contentAction('review-B', '');
    vi.mocked(runJourneyCommand).mockResolvedValue({ action: actionB, next_action: null });
    const user = userEvent.setup();
    const view = render(card(actionA, 'business-1', vi.fn()));
    const editor = screen.getByDisplayValue('Черновик A');
    await user.clear(editor);
    await user.type(editor, 'Правка из A');

    for (const step of [
      contentStep('schedule-A', 'save_to_calendar'),
      contentStep('publication-A', 'waiting_for_publication'),
      contentStep('result-A', 'add_content_result'),
      contentStep('next-cycle-A', 'start_next_content_cycle'),
      contentStep('prepare-B', 'prepare_content'),
    ]) {
      view.rerender(card(step, 'business-1', vi.fn()));
      expect(screen.getByRole('heading', { name: step.title })).toBeVisible();
    }
    view.rerender(card(actionB, 'business-1', vi.fn()));
    expect(await screen.findByDisplayValue('')).toBeVisible();
    await user.type(screen.getByDisplayValue(''), 'Свежая правка B');
    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));

    expect(runJourneyCommand).toHaveBeenCalledWith(expect.objectContaining({
      action: actionB,
      command: 'save_draft',
      payload: { draft_text: 'Свежая правка B', content_plan_item_id: 'content-item-1' },
    }));
  });

  it('retains an in-progress draft for the same business and action id across payload, version and surface refreshes', async () => {
    const actionA = contentAction('review-A', 'Черновик A');
    const user = userEvent.setup();
    const view = render(card(actionA, 'business-1', vi.fn()));
    const editor = screen.getByDisplayValue('Черновик A');
    await user.clear(editor);
    await user.type(editor, 'Правка, которую нельзя потерять');

    view.rerender(card(
      { ...actionA, version: 2, payload: { draft_text: 'Обновлённый серверный текст' } },
      'business-1',
      vi.fn(),
      'web',
    ));
    expect(screen.getByDisplayValue('Правка, которую нельзя потерять')).toBeVisible();
  });

  it('does not deliver a late old result after an action switch and keeps B usable', async () => {
    const actionA = contentAction('review-A', 'Черновик A');
    const actionB = replyAction('reply-B');
    const oldNextAction = replyAction('old-next');
    const pending = deferredCommand();
    const oldUpdated = vi.fn();
    const newUpdated = vi.fn();
    vi.mocked(runJourneyCommand)
      .mockImplementationOnce(() => pending.promise)
      .mockResolvedValueOnce({ action: actionB, next_action: null });
    const user = userEvent.setup();
    const view = render(card(actionA, 'business-1', oldUpdated));

    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    view.rerender(card(actionB, 'business-1', newUpdated));

    await act(async () => {
      pending.resolve({ action: actionA, next_action: oldNextAction });
    });
    expect(oldUpdated).not.toHaveBeenCalled();
    expect(screen.queryByText('Проверить ответ old-next')).not.toBeInTheDocument();
    const saveReply = await screen.findByRole('button', { name: 'Сохранить ответ' });
    expect(saveReply).toBeEnabled();
    await user.click(saveReply);
    expect(newUpdated).toHaveBeenCalledTimes(1);
  });

  it('does not render a late old error after an action switch', async () => {
    const actionA = contentAction('review-A', 'Черновик A');
    const actionB = replyAction('reply-B');
    const pending = deferredCommand();
    vi.mocked(runJourneyCommand).mockImplementationOnce(() => pending.promise);
    const user = userEvent.setup();
    const view = render(card(actionA, 'business-1', vi.fn()));

    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    view.rerender(card(actionB, 'business-1', vi.fn()));
    await act(async () => {
      pending.reject(new Error('Ошибка из старого действия'));
    });

    expect(screen.queryByText('Ошибка из старого действия')).not.toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Сохранить ответ' })).toBeEnabled();
  });

  it('isolates reused action ids when the business scope changes', async () => {
    const actionA = contentAction('reused-action', 'Черновик бизнеса A');
    const actionB: JourneyAction = {
      ...contentAction('reused-action', 'Черновик бизнеса B'),
      business_id: 'business-2',
    };
    vi.mocked(runJourneyCommand).mockResolvedValue({ action: actionB, next_action: null });
    const user = userEvent.setup();
    const view = render(card(actionA, 'business-1', vi.fn()));
    const editor = screen.getByDisplayValue('Черновик бизнеса A');
    await user.clear(editor);
    await user.type(editor, 'Локальная правка A');

    view.rerender(card(actionB, 'business-2', vi.fn()));
    expect(await screen.findByDisplayValue('Черновик бизнеса B')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    expect(runJourneyCommand).toHaveBeenCalledWith(expect.objectContaining({
      action: actionB,
      businessId: 'business-2',
      payload: { draft_text: 'Черновик бизнеса B', content_plan_item_id: 'content-item-1' },
    }));
  });

  it('keeps B busy when A finishes after B started its own request', async () => {
    const actionA = contentAction('review-A', 'Черновик A');
    const actionB = replyAction('reply-B');
    const pendingA = deferredCommand();
    const pendingB = deferredCommand();
    vi.mocked(runJourneyCommand)
      .mockImplementationOnce(() => pendingA.promise)
      .mockImplementationOnce(() => pendingB.promise);
    const user = userEvent.setup();
    const view = render(card(actionA, 'business-1', vi.fn()));

    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    view.rerender(card(actionB, 'business-1', vi.fn()));
    const saveReply = await screen.findByRole('button', { name: 'Сохранить ответ' });
    expect(saveReply).toBeEnabled();
    await user.click(saveReply);
    expect(saveReply).toBeDisabled();

    await act(async () => {
      pendingA.resolve({ action: actionA, next_action: null });
    });
    expect(screen.getByRole('button', { name: 'Сохранить ответ' })).toBeDisabled();

    await act(async () => {
      pendingB.resolve({ action: actionB, next_action: null });
    });
    expect(screen.getByRole('button', { name: 'Сохранить ответ' })).toBeEnabled();
  });

  it('does not execute a deferred clipboard copy after switching from A to B', async () => {
    const actionA = copyAction('copy-A');
    const actionB = replyAction('reply-B');
    const pendingClipboard = deferredCommand();
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, 'writeText').mockImplementation(() => pendingClipboard.promise.then(() => undefined));
    const view = render(card(actionA, 'business-1', vi.fn()));

    await user.click(screen.getByRole('button', { name: 'Скопировать' }));
    expect(writeText).toHaveBeenCalledWith('Точный текст для копирования');
    view.rerender(card(actionB, 'business-1', vi.fn()));
    await act(async () => {
      pendingClipboard.resolve({ action: actionA, next_action: null });
    });

    expect(runJourneyCommand).not.toHaveBeenCalledWith(expect.objectContaining({ action: actionA, command: 'copy' }));
  });

  it('does not execute a rejected deferred clipboard copy after unmount', async () => {
    const actionA = copyAction('copy-A');
    const pendingClipboard = deferredCommand();
    const user = userEvent.setup();
    vi.spyOn(navigator.clipboard, 'writeText').mockImplementation(() => pendingClipboard.promise.then(() => undefined));
    const view = render(card(actionA, 'business-1', vi.fn()));

    await user.click(screen.getByRole('button', { name: 'Скопировать' }));
    view.unmount();
    await act(async () => {
      pendingClipboard.reject(new Error('clipboard rejected'));
    });

    expect(runJourneyCommand).not.toHaveBeenCalledWith(expect.objectContaining({ action: actionA, command: 'copy' }));
  });

  it('copies exact bytes and executes copy while its current action remains mounted', async () => {
    const actionA = copyAction('copy-A');
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue(undefined);
    vi.mocked(runJourneyCommand).mockResolvedValue({ action: actionA, next_action: null });
    render(card(actionA, 'business-1', vi.fn()));

    await user.click(screen.getByRole('button', { name: 'Скопировать' }));
    expect(writeText).toHaveBeenCalledWith('Точный текст для копирования');
    expect(runJourneyCommand).toHaveBeenCalledWith(expect.objectContaining({ action: actionA, command: 'copy' }));
  });

  it('does not call back after a late command resolution from an unmounted card', async () => {
    const actionA = contentAction('review-A', 'Черновик A');
    const pending = deferredCommand();
    const updated = vi.fn();
    vi.mocked(runJourneyCommand).mockImplementationOnce(() => pending.promise);
    const user = userEvent.setup();
    const view = render(card(actionA, 'business-1', updated));

    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    view.unmount();
    await act(async () => {
      pending.resolve({ action: actionA, next_action: replyAction('late-next') });
    });

    expect(updated).not.toHaveBeenCalled();
  });

  it('does not surface a late command rejection from an unmounted card', async () => {
    const actionA = contentAction('review-A', 'Черновик A');
    const pending = deferredCommand();
    const updated = vi.fn();
    vi.mocked(runJourneyCommand).mockImplementationOnce(() => pending.promise);
    const user = userEvent.setup();
    const view = render(card(actionA, 'business-1', updated));

    await user.click(screen.getByRole('button', { name: 'Сохранить черновик' }));
    view.unmount();
    await act(async () => {
      pending.reject(new Error('Поздняя ошибка'));
    });

    expect(updated).not.toHaveBeenCalled();
    expect(screen.queryByText('Поздняя ошибка')).not.toBeInTheDocument();
  });

  it('lets the current StrictMode lifetime submit exactly once', async () => {
    const actionA = replyAction('reply-A');
    const updated = vi.fn();
    vi.mocked(runJourneyCommand).mockResolvedValue({ action: actionA, next_action: null });
    const user = userEvent.setup();
    render(<StrictMode>{card(actionA, 'business-1', updated)}</StrictMode>);

    await user.click(screen.getByRole('button', { name: 'Сохранить ответ' }));
    expect(runJourneyCommand).toHaveBeenCalledTimes(1);
    expect(updated).toHaveBeenCalledTimes(1);
  });

  it('does not navigate after a stale upgrade action resolves, but navigates for its current scope', async () => {
    const upgradeA: JourneyAction = {
      ...replyAction('upgrade-A'),
      action_type: 'upgrade',
      allowed_commands: ['open_upgrade'],
      access: {
        allowed: false,
        capability: 'upgrade',
        status: 'payment_required',
        cta_target: { url: '/billing?from=journey' },
      },
    };
    const actionB = replyAction('reply-B');
    const pending = deferredCommand();
    const assign = vi.fn();
    const runtimeWindow = window;
    const scopedLocation = { assign, pathname: '/dashboard/today', search: '?focus=journey' };
    vi.stubGlobal('window', new Proxy(runtimeWindow, {
      get(target, property) {
        if (property === 'location') return scopedLocation;
        return Reflect.get(target, property, target);
      },
    }));
    vi.mocked(runJourneyCommand).mockImplementationOnce(() => pending.promise);
    const user = userEvent.setup();
    const view = render(card(upgradeA, 'business-1', vi.fn()));

    await user.click(screen.getByRole('button', { name: 'Выбрать тариф' }));
    view.rerender(card(actionB, 'business-1', vi.fn()));
    await act(async () => {
      pending.resolve({ action: upgradeA, next_action: null });
    });
    expect(assign).not.toHaveBeenCalled();

    vi.mocked(runJourneyCommand).mockResolvedValue({ action: upgradeA, next_action: null });
    view.rerender(card(upgradeA, 'business-1', vi.fn()));
    await user.click(screen.getByRole('button', { name: 'Выбрать тариф' }));
    expect(assign).toHaveBeenCalledWith('/billing?from=journey&return_to=%2Fdashboard%2Ftoday%3Ffocus%3Djourney');
  });

  it('resets action-local fields for a new action scope', async () => {
    const user = userEvent.setup();
    const detailsA: JourneyAction = { ...contentStep('details-A', 'define_terms'), allowed_commands: ['save_terms'] };
    const detailsB: JourneyAction = { ...contentStep('details-B', 'define_terms'), allowed_commands: ['save_terms'] };
    const view = render(card(detailsA, 'business-1', vi.fn()));
    const details = screen.getByPlaceholderText('Условия или комментарий');
    await user.type(details, 'Старые условия');
    view.rerender(card(detailsB, 'business-1', vi.fn()));
    expect(screen.getByPlaceholderText('Условия или комментарий')).toHaveValue('');

    const scheduleA: JourneyAction = { ...contentStep('schedule-A', 'save_to_calendar'), payload: { scheduled_for: '2026-09-21' } };
    const scheduleB: JourneyAction = { ...contentStep('schedule-B', 'save_to_calendar'), payload: { scheduled_for: '2026-10-01' } };
    view.rerender(card(scheduleA, 'business-1', vi.fn()));
    fireEvent.change(screen.getByLabelText('Дата публикации'), { target: { value: '2026-09-25' } });
    view.rerender(card(scheduleB, 'business-1', vi.fn()));
    expect(screen.getByLabelText('Дата публикации')).toHaveValue('2026-10-01');

    const replyA = replyAction('reply-A');
    const replyB = replyAction('reply-B');
    view.rerender(card(replyA, 'business-1', vi.fn()));
    await user.click(screen.getByRole('combobox', { name: 'Результат ответа' }));
    await user.click(await screen.findByRole('option', { name: 'Готов на бартер' }));
    view.rerender(card(replyB, 'business-1', vi.fn()));
    expect(screen.getByRole('combobox', { name: 'Результат ответа' })).toHaveTextContent('Интересно');

    const automationA: JourneyAction = { ...contentStep('automation-A', 'configure_automation'), allowed_commands: ['save_configuration'] };
    const automationB: JourneyAction = { ...contentStep('automation-B', 'configure_automation'), allowed_commands: ['save_configuration'] };
    view.rerender(card(automationA, 'business-1', vi.fn()));
    await user.click(screen.getByRole('combobox', { name: 'Что поручить' }));
    await user.click(await screen.findByRole('option', { name: 'Готовить черновики контента' }));
    const expectedResult = screen.getByDisplayValue('Подготовленные материалы для проверки');
    await user.clear(expectedResult);
    await user.type(expectedResult, 'Старое ожидаемое значение');
    view.rerender(card(automationB, 'business-1', vi.fn()));
    expect(screen.getByDisplayValue('Подготовленные материалы для проверки')).toBeVisible();
    expect(screen.getByRole('combobox', { name: 'Что поручить' })).toHaveTextContent('Собирать отзывы без ответа');

    const metricsA: JourneyAction = { ...contentStep('metrics-A', 'add_content_result'), allowed_commands: ['add_result'] };
    const metricsB: JourneyAction = { ...contentStep('metrics-B', 'add_content_result'), allowed_commands: ['add_result'] };
    view.rerender(card(metricsA, 'business-1', vi.fn()));
    await user.type(screen.getByPlaceholderText('Просмотры'), '42');
    await user.type(screen.getByPlaceholderText('Обращения'), '3');
    view.rerender(card(metricsB, 'business-1', vi.fn()));
    expect(screen.getByPlaceholderText('Просмотры')).toHaveValue('');
    expect(screen.getByPlaceholderText('Обращения')).toHaveValue('');
  });
});
