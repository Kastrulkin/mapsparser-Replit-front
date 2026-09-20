import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { AgentApprovalDecisionPanel } from './detail';
import { EmployeeTestResultPanel } from './employee';
import { getRequestErrorMessage } from './normalization';
import { ApprovalPayloadSummary } from './runs';
import type { AgentApproval, AgentRun } from './types';

const draftApproval = (payload_json: Record<string, unknown>): AgentApproval => ({
  id: 'approval-1',
  status: 'pending',
  approval_type: 'drafts',
  title: 'Approve drafted outreach',
  payload_json,
});

const snapshotApproval = () => draftApproval({
  artifact_type: 'message_drafts', count: 1, snapshot_version: 1,
  items: [{ id: 'draft-1', lead_name: 'Мария', channel: 'email', review_recipient: 'owner@example.invalid', review_text: 'Snapshot before approval' }],
});

const activeRun: AgentRun = { id: 'run-1', status: 'waiting_approval', blueprint_id: 'blueprint-1' };

const incompleteSnapshots: Array<{ name: string; payload: Record<string, unknown> }> = [
  { name: 'missing version', payload: { items: [{ review_text: 'Legacy text' }] } },
  { name: 'non-array items', payload: { snapshot_version: 1, items: { review_text: 'Not a list' } } },
  { name: 'empty items', payload: { snapshot_version: 1, items: [] } },
  { name: 'blank review text', payload: { snapshot_version: 1, items: [{ review_text: '  \n ' }] } },
  { name: 'incomplete item after a valid item', payload: { snapshot_version: 1, items: [{ review_text: 'Valid text' }, null] } },
];

describe.each(['detail', 'employee'])('%s draft approval admission', (surface) => {
  const panel = (approval: AgentApproval, actionLoading: boolean, onApprove: () => void, onReject: () => void) => (
    surface === 'detail'
      ? <AgentApprovalDecisionPanel approval={approval} actionLoading={actionLoading} onApprove={onApprove} onReject={onReject} />
      : <EmployeeTestResultPanel activeRun={activeRun} pendingApproval={approval} actionLoading={actionLoading} onApprove={onApprove} onReject={onReject} onRunAgain={vi.fn()} />
  );

  it.each(incompleteSnapshots)('blocks confirmation but preserves rejection for $name', async ({ payload }) => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    const user = userEvent.setup();
    render(panel(draftApproval(payload), false, onApprove, onReject));

    expect(screen.getByText('Проверка черновиков устарела или неполна. Пересоздайте проверку перед утверждением.')).toBeVisible();
    const approve = screen.getByRole('button', { name: 'Подтвердить публикацию' });
    const reject = screen.getByRole('button', { name: 'Отклонить результат' });
    expect(approve).toBeDisabled();
    expect(reject).toBeEnabled();
    await user.click(approve);
    expect(onApprove).not.toHaveBeenCalled();
    await user.click(reject);
    expect(onReject).toHaveBeenCalledTimes(1);
  });

  it('updates confirmation admission when the reviewed snapshot changes', async () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(panel(draftApproval({}), false, onApprove, onReject));
    expect(screen.getByRole('button', { name: 'Подтвердить публикацию' })).toBeDisabled();

    rerender(panel(snapshotApproval(), false, onApprove, onReject));
    expect(screen.queryByText(/Проверка черновиков устарела или неполна/)).not.toBeInTheDocument();
    expect(screen.getByText('Snapshot before approval')).toBeVisible();
    const approve = screen.getByRole('button', { name: 'Подтвердить публикацию' });
    expect(approve).toBeEnabled();
    await user.click(approve);
    expect(onApprove).toHaveBeenCalledTimes(1);

    rerender(panel(draftApproval({}), false, onApprove, onReject));
    expect(screen.getByRole('button', { name: 'Подтвердить публикацию' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Отклонить результат' })).toBeEnabled();
  });

  it.each([false, true])('keeps both decisions disabled while loading (complete snapshot: %s)', async (complete) => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    const user = userEvent.setup();
    render(panel(complete ? snapshotApproval() : draftApproval({}), true, onApprove, onReject));

    const approve = screen.getByRole('button', { name: 'Подтвердить публикацию' });
    const reject = screen.getByRole('button', { name: 'Отклонить результат' });
    expect(approve).toBeDisabled();
    expect(reject).toBeDisabled();
    await user.click(approve);
    await user.click(reject);
    expect(onApprove).not.toHaveBeenCalled();
    expect(onReject).not.toHaveBeenCalled();
  });

  it('does not require a draft snapshot for other approval types', async () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    const user = userEvent.setup();
    render(panel({ id: 'generic-approval', status: 'pending', approval_type: 'custom', title: 'Manual decision' }, false, onApprove, onReject));

    const approve = screen.getByRole('button', { name: 'Разрешить выполнение' });
    expect(approve).toBeEnabled();
    await user.click(approve);
    expect(onApprove).toHaveBeenCalledTimes(1);
  });
});

describe('ApprovalPayloadSummary draft snapshots', () => {
  it('turns stale snapshot error variants into the recovery instruction while preserving unrelated errors', () => {
    const staleInstruction = 'Черновики или получатели изменились. Отклоните это решение и запустите подготовку заново, затем проверьте новый текст.';

    expect(getRequestErrorMessage(new Error('approval_payload_stale'), 'Fallback')).toBe(staleInstruction);
    expect(getRequestErrorMessage(new Error('Ошибка соединения с сервером: approval_payload_stale'), 'Fallback')).toBe(staleInstruction);
    expect(getRequestErrorMessage(new Error('Ошибка запроса: approval_payload_stale'), 'Fallback')).toBe(staleInstruction);
    expect(getRequestErrorMessage(new Error('other_error'), 'Fallback')).toBe('other_error');
    expect(getRequestErrorMessage(null, 'Fallback')).toBe('Fallback');
  });

  it('shows the immutable review text instead of generated or approved text', () => {
    render(<ApprovalPayloadSummary approval={draftApproval({
      artifact_type: 'message_drafts',
      count: 1,
      snapshot_version: 1,
      items: [{
        id: 'draft-1', lead_name: 'Мария', channel: 'email', review_recipient: 'owner@example.invalid',
        generated_text: 'Generated A', edited_text: 'Edited A', approved_text: 'Approved B', review_text: 'Snapshot A',
      }],
    })} />);

    expect(screen.getByText('Snapshot A')).toBeVisible();
    expect(screen.queryByText('Generated A')).not.toBeInTheDocument();
    expect(screen.queryByText('Edited A')).not.toBeInTheDocument();
    expect(screen.queryByText('Approved B')).not.toBeInTheDocument();
    expect(screen.getByText('Мария · email · owner@example.invalid')).toBeVisible();
    expect(screen.getByText('owner@example.invalid', { exact: false })).toBeVisible();
  });

  it('shows every snapshot item in a scrollable list', () => {
    const items = Array.from({ length: 6 }, (_, index) => ({
      id: `draft-${index + 1}`,
      lead_name: `Получатель ${index + 1}`,
      channel: 'telegram',
      review_text: `Snapshot ${index + 1}`,
    }));
    const { container } = render(<ApprovalPayloadSummary approval={draftApproval({ artifact_type: 'message_drafts', count: 6, snapshot_version: 1, items })} />);

    expect(screen.getByText('Snapshot 1')).toBeVisible();
    expect(screen.getByText('Snapshot 6')).toBeVisible();
    expect(container.querySelector('.overflow-y-auto')).toBeInTheDocument();
  });

  it('renders review text as plain escaped text', () => {
    const { container } = render(<ApprovalPayloadSummary approval={draftApproval({
      artifact_type: 'message_drafts', count: 1, snapshot_version: 1,
      items: [{ id: 'draft-html', lead_name: 'Анна', channel: 'email', review_text: '<strong>Не HTML</strong>' }],
    })} />);

    expect(screen.getByText('<strong>Не HTML</strong>')).toBeVisible();
    expect(container.querySelector('strong')).not.toBeInTheDocument();
  });

  it('asks for a new review when the immutable snapshot is missing or incomplete', () => {
    render(<ApprovalPayloadSummary approval={draftApproval({
      artifact_type: 'message_drafts', count: 1, items: [{ id: 'draft-1', lead_name: 'Мария', channel: 'email' }],
    })} />);

    expect(screen.getByText('Проверка черновиков устарела или неполна. Пересоздайте проверку перед утверждением.')).toBeVisible();
  });

  it('keeps generic approvals as the existing compact summary', () => {
    const approval: AgentApproval = {
      id: 'approval-2', status: 'pending', approval_type: 'finance', title: 'Finance approval',
      payload_json: { artifact_type: 'finance_rows', count: 2, snapshot_version: 1, items: [{ review_text: 'Не показывать' }] },
    };
    render(<ApprovalPayloadSummary approval={approval} />);

    expect(screen.getByText('Результат: finance_rows')).toBeVisible();
    expect(screen.getByText('Ожидают решения: 2')).toBeVisible();
    expect(screen.queryByText('Текст, который будет утверждён')).not.toBeInTheDocument();
    expect(screen.queryByText('Не показывать')).not.toBeInTheDocument();
  });

  it('shows the snapshot before the employee approval control and keeps its callback explicit', async () => {
    const onApprove = vi.fn();
    const user = userEvent.setup();
    const { container } = render(<EmployeeTestResultPanel
      activeRun={activeRun}
      pendingApproval={snapshotApproval()}
      actionLoading={false}
      onApprove={onApprove}
      onReject={vi.fn()}
      onRunAgain={vi.fn()}
    />);

    const snapshot = screen.getByText('Snapshot before approval');
    const approve = screen.getByRole('button', { name: 'Подтвердить публикацию' });
    expect(snapshot.compareDocumentPosition(approve) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(container.textContent).toContain('owner@example.invalid');
    await user.click(approve);
    expect(onApprove).toHaveBeenCalledTimes(1);
  });

  it('shows the snapshot before the detail approval controls and keeps callbacks explicit', async () => {
    const onApprove = vi.fn();
    const user = userEvent.setup();
    const { container } = render(<AgentApprovalDecisionPanel approval={snapshotApproval()} actionLoading={false} onApprove={onApprove} onReject={vi.fn()} />);

    const snapshot = screen.getByText('Snapshot before approval');
    const approve = screen.getByRole('button', { name: 'Подтвердить публикацию' });
    expect(snapshot.compareDocumentPosition(approve) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(container.textContent).toContain('owner@example.invalid');
    await user.click(approve);
    expect(onApprove).toHaveBeenCalledTimes(1);
  });
});
