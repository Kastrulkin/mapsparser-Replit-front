import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { CompiledPreviewSimulationPanel, DomainRequestItem } from './runs';
import type { AgentRunObservability } from './types';

type DomainRequest = NonNullable<NonNullable<AgentRunObservability['domain_requests']>['items']>[number];

const renderSheetRequest = (applyState: string) => {
  const item: DomainRequest = {
    kind: 'sheet_operation_request',
    title: 'Обновить таблицу заявок',
    summary: 'Подтверждённая запись в Google Sheets',
    approval_state: 'approved',
    apply_state: applyState,
  };
  render(
    <DomainRequestItem
      item={item}
      runId="run-sheet-1"
      actionLoading={false}
      onApplyFinanceRequests={() => undefined}
    />,
  );
};

describe('Google Sheets domain request presentation', () => {
  it.each([
    ['provider_request_queued', 'Ожидает записи'],
    ['provider_executing', 'Запись выполняется'],
    ['provider_reconciliation_required', 'Результат требует сверки'],
    ['approval_invalid', 'Подтверждение недействительно'],
  ])('shows %s instead of the prior approval state', (applyState, expectedStatus) => {
    renderSheetRequest(applyState);

    expect(screen.getByText(expectedStatus)).toBeInTheDocument();
    expect(screen.queryByText('Подтверждено')).not.toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('explains that an uncertain write may have happened', () => {
    renderSheetRequest('provider_reconciliation_required');

    expect(screen.getByText('Запись могла выполниться; сверьте таблицу.')).toBeInTheDocument();
  });

  it('does not describe an unknown effect as a safe completed preview', () => {
    render(<CompiledPreviewSimulationPanel steps={[]} safePreview externalActionsPerformed={false} externalActionsUncertain />);
    expect(screen.getByText('результат внешнего действия не подтверждён')).toBeInTheDocument();
    expect(screen.queryByText('внешних действий не было')).not.toBeInTheDocument();
  });
});
