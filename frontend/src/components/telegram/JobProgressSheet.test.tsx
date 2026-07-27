import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import JobProgressSheet from './JobProgressSheet';

describe('JobProgressSheet', () => {
  it('shows a real stage and lets the user close a running job', () => {
    const close = vi.fn();
    render(<JobProgressSheet job={{ id: 'job-1', kind: 'content_plan_generate', status: 'running', progress: 35, stage: 'Сверяем услуги и спрос', available_actions: ['cancel'] }} onClose={close} />);

    expect(screen.getByText('Сверяем услуги и спрос')).toBeInTheDocument();
    expect(screen.getByText('35%')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Закрыть' }));
    expect(close).toHaveBeenCalledOnce();
  });

  it('offers retry only when the backend allows it', () => {
    const retry = vi.fn();
    render(<JobProgressSheet job={{ id: 'job-2', kind: 'content_draft_generate', status: 'failed', progress: 100, error: 'Сервис не ответил', available_actions: ['retry'] }} onClose={() => undefined} onRetry={retry} />);

    fireEvent.click(screen.getByRole('button', { name: 'Повторить' }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
