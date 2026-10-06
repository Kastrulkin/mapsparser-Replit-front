import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { DialogAgentBuilder } from './builder_dialog';

const renderBuilder = (overrides: { actionLoading?: boolean; error?: string } = {}) => render(
  <DialogAgentBuilder
    input="Найди компании"
    reply=""
    session={null}
    actionLoading={overrides.actionLoading || false}
    error={overrides.error}
    onInputChange={vi.fn()}
    onReplyChange={vi.fn()}
    onStart={vi.fn()}
    onSendReply={vi.fn()}
    onCreate={vi.fn()}
    selectedConnectionBindings={{}}
    selectedProviderRoutes={{}}
    acceptedCompilerPlan={false}
    acceptedProviderRoutes={false}
    executionMode="manual"
    executionModeConfirmed={false}
    scheduleTime="10:00"
    scheduleTimezone="Europe/Moscow"
    onAcceptCompilerPlan={vi.fn()}
    onAcceptProviderRoutes={vi.fn()}
    onExecutionModeChange={vi.fn()}
    onExecutionModeConfirm={vi.fn()}
    onScheduleTimeChange={vi.fn()}
    onScheduleTimezoneChange={vi.fn()}
    onSelectConnectionBinding={vi.fn()}
    onSelectProviderRoute={vi.fn()}
  />,
);

describe('DialogAgentBuilder feedback', () => {
  it('explains what LocalOS is doing while compiling a task', () => {
    renderBuilder({ actionLoading: true });
    expect(screen.getByRole('status')).toHaveTextContent('LocalOS разбирает задачу');
  });

  it('shows a failed compilation inside the builder', () => {
    renderBuilder({ error: 'Проверка задачи не вернулась.' });
    expect(screen.getByRole('alert')).toHaveTextContent('Проверка задачи не вернулась.');
  });
});
