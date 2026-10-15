import { fireEvent, render, screen, waitFor } from '@testing-library/react';
vi.mock('@/i18n/LanguageContext.logic', () => ({ useLanguage: () => ({ language: 'ru' }) }));
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { ComponentProps } from 'react';
import { AgentSettingsPage } from './settings-v2';

type Scope = ComponentProps<typeof AgentSettingsPage>['scope'];
const makeScope = (key = 'maps_card_check'): Scope => ({
  selectedBlueprint: { id: 'checker', business_id: 'meliora', name: 'Проверка карточек', category: 'local_seo', status: 'active', execution_mode: 'manual', metadata_json: { template_key: key } },
  blueprintDetails: { versions: [], runs: [], execution_mode: 'manual' }, agentReview: null, agentConnectionPlan: null, agentBindingStatus: [], sourceCatalog: [], actionLoading: false, error: null,
  selectedExecutionMode: 'manual', scheduleTime: '09:00', scheduleTimezone: 'Europe/Moscow', setupDataSources: 'profile', setupExtractionRules: 'facts', setupProcessingRules: 'rules', setupOutputFormat: 'report', setupManualControl: 'approval',
  saveExecutionMode: vi.fn(async () => true), saveAgentSetup: vi.fn(async () => true), addInternalSourceByKey: vi.fn(), addTextSource: vi.fn(), addFileSource: vi.fn(), sourceName: '', sourceText: '', setSourceName: vi.fn(), setSourceText: vi.fn(), setWorkspaceMode: vi.fn(), showAdvancedAgentTools: false, startRun: vi.fn(), activateVersion: vi.fn(), deleteSelectedAgent: vi.fn(),
});
const mount = (scope: Scope) => render(<MemoryRouter><AgentSettingsPage scope={scope} supportTools={<p>Company support</p>} onOpenResult={vi.fn()} /></MemoryRouter>);

describe('Agent settings focused sections', () => {
  it('shows four sections, relevant map data and no generic connection or editing forms', () => {
    mount(makeScope());
    for (const name of ['Когда запускать', 'Данные и доступы', 'Результат и согласование']) expect(screen.getByRole('heading', { name })).toBeVisible();
    expect(screen.getByText('Дополнительно', { exact: true })).toBeVisible();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.queryByText('Какие данные использовать')).not.toBeInTheDocument();
    expect(screen.queryByText('Подключите таблицу с поездками')).not.toBeInTheDocument();
    expect(screen.getByText('Company support')).not.toBeVisible();
    expect(screen.queryByRole('button', { name: 'Настроить необходимые подключения' })).not.toBeInTheDocument();
  });
  it('stages schedule edits, cancels without saving, and submits exact draft while retaining the settings route', async () => {
    const s = makeScope(); mount(s);
    fireEvent.click(screen.getByRole('button', { name: 'Изменить способ запуска' }));
    fireEvent.click(screen.getByRole('radio', { name: 'По расписанию' }));
    fireEvent.change(screen.getByLabelText('Время'), { target: { value: '10:30' } });
    fireEvent.click(screen.getByRole('button', { name: 'Отмена' }));
    expect(s.saveExecutionMode).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Изменить способ запуска' }));
    fireEvent.click(screen.getByRole('radio', { name: 'По расписанию' }));
    expect(screen.getByLabelText('Время')).toHaveValue('09:00');
    fireEvent.change(screen.getByLabelText('Время'), { target: { value: '11:15' } });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить изменения' }));
    await waitFor(() => expect(s.saveExecutionMode).toHaveBeenCalledWith({ mode: 'scheduled', time: '11:15', timezone: 'Europe/Moscow' }, true));
    await waitFor(() => expect(screen.queryByRole('radio')).not.toBeInTheDocument());
    expect(s.setWorkspaceMode).not.toHaveBeenCalled();
  });
  it('keeps failed save draft and error visible; hides schedule for initial map setup', async () => {
    const s = makeScope(); s.saveExecutionMode = vi.fn(async () => false); mount(s);
    fireEvent.click(screen.getByRole('button', { name: 'Изменить способ запуска' }));
    fireEvent.click(screen.getByRole('radio', { name: 'Один раз' }));
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить изменения' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось сохранить');
    expect(screen.getByRole('radio', { name: 'Один раз' })).toBeChecked();
  });
  it('does not submit unchanged settings or reset agent readiness', () => {
    const s = makeScope(); mount(s);
    fireEvent.click(screen.getByRole('button', { name: 'Изменить способ запуска' }));
    expect(screen.getByRole('button', { name: 'Сохранить изменения' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить изменения' }));
    expect(s.saveExecutionMode).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('radio', { name: 'Один раз' }));
    expect(screen.getByRole('button', { name: 'Сохранить изменения' })).toBeEnabled();
    fireEvent.click(screen.getByRole('radio', { name: 'По кнопке' }));
    expect(screen.getByRole('button', { name: 'Сохранить изменения' })).toBeDisabled();
  });
  it('does not offer unsupported scheduled initial setup', () => {
    mount(makeScope('maps_initial_setup'));
    fireEvent.click(screen.getByRole('button', { name: 'Изменить способ запуска' }));
    expect(screen.queryByRole('radio', { name: 'По расписанию' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Время')).not.toBeInTheDocument();
  });
  it('preserves generic rules when saving only result preferences', async () => {
    const s = makeScope('custom'); mount(s);
    fireEvent.click(screen.getByRole('button', { name: 'Изменить формат результата' }));
    fireEvent.change(screen.getByLabelText('Какой результат подготовить'), { target: { value: 'Table' } });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить изменения' }));
    await waitFor(() => expect(s.saveAgentSetup).toHaveBeenCalledWith({ dataSources: 'profile', extractionRules: 'facts', processingRules: 'rules', outputFormat: 'Table', manualControl: 'approval' }));
  });
});
