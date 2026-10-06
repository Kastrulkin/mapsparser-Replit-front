import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { PartnershipLeadCard } from './PartnershipPipelineSections';

it('moves an older unverified search candidate into manual selection without requiring a map audit', async () => {
  const moveToPipeline = vi.fn();
  const openLead = vi.fn();
  render(<PartnershipLeadCard
    lead={{ id: 'lead-1', name: 'India Tours', pipeline_status: 'unprocessed', partnership_stage: 'imported', email: 'hello@example.org' }}
    mode="raw"
    searchLabel="Индия → Пхукет · 02.10"
    verification={{ country: { status: 'not_verified' }, destination: { status: 'not_verified' }, contactVerified: false }}
    dragging={false}
    loading={false}
    nextStage=""
    deferredReasonInput=""
    deferredUntilInput=""
    stagePresentation={{ label: 'Кандидат', helper: 'Компания ждёт отбора', variant: 'outline', tone: 'default' }}
    auditPresentation={{ label: 'Не проверено', primary: '', secondary: '', variant: 'outline', tone: 'default' }}
    onMoveToPipeline={moveToPipeline}
    onMoveToStage={vi.fn()}
    onOpenLead={openLead}
    onDeferLead={vi.fn()}
  />);

  expect(screen.getByText(/Это не подтверждает соответствие поиску и не запускает письма/)).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Проверить карточку' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Выбрать для работы' }));
  expect(moveToPipeline).toHaveBeenCalledOnce();
  expect(moveToPipeline).toHaveBeenCalledWith('lead-1');
  expect(openLead).not.toHaveBeenCalled();
});
