import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import ActionPreviewSheet from './ActionPreviewSheet';

describe('ActionPreviewSheet', () => {
  it('shows targets, cost and performs one explicit confirmation', async () => {
    const confirm = vi.fn();
    const cancel = vi.fn();
    const user = userEvent.setup();
    render(<ActionPreviewSheet preview={{ action_id: 'action-1', target_businesses: [{ id: 'business-1', name: 'Intellectum' }], objects: [{ id: 'review-1' }, { id: 'review-2' }], changes: [{ object_id: 'review-1', label: 'Подготовить ответы' }], estimated_credits: 2 }} busy={false} confirmLabel="Подготовить" onCancel={cancel} onConfirm={confirm} />);

    expect(screen.getByRole('dialog', { name: 'Проверьте действие' })).toBeInTheDocument();
    expect(screen.getByText('Intellectum')).toBeInTheDocument();
    expect(screen.getByText('2', { selector: 'b' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Подготовить' }));

    expect(confirm).toHaveBeenCalledTimes(1);
    expect(cancel).not.toHaveBeenCalled();
  });

  it('blocks dismissal while confirmation is running', async () => {
    const cancel = vi.fn();
    const user = userEvent.setup();
    render(<ActionPreviewSheet preview={{ action_id: 'action-1' }} busy onCancel={cancel} onConfirm={() => undefined} />);

    await user.click(screen.getByRole('button', { name: 'Закрыть проверку' }));
    expect(cancel).not.toHaveBeenCalled();
  });

  it('uses the correct Russian form for two publications', () => {
    render(<ActionPreviewSheet preview={{ action_id: 'action-1', changes: [{ object_id: 'plan-1', label: 'Удалить план', items_count: 2 }] }} busy={false} onCancel={() => undefined} onConfirm={() => undefined} />);

    expect(screen.getByText(/2 публикации/)).toBeInTheDocument();
    expect(screen.queryByText(/2 публикаций/)).not.toBeInTheDocument();
  });
});
