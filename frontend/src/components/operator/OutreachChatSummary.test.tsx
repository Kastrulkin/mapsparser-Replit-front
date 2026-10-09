import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { OutreachChatSummary } from './OutreachChatSummary';
import type { GroupPresentation } from '@/components/prospecting/OutreachGroupCard';

const stopped: GroupPresentation = {
  phase: 'companies', status: 'needs_attention', label: 'Требуется действие', active: false,
  reason: 'Источник не вернул компании за отведённое время.',
  next_action: { kind: 'link', label: 'Условия поиска', href: '/dashboard/partnerships' },
  metrics: { found: 0, eligible: 0, target: 3, needs_decision: 0, prepared: 0, queued: 0, sent: 0, replies: 0 },
  expenses: { charged: 1, estimate: 30 },
};
describe('OutreachChatSummary', () => {
  it('shows a stopped real result and offers recovery in chat without starting work', () => {
    const onContinue = vi.fn();
    render(<OutreachChatSummary name="Индия · 09.10" presentation={stopped} onContinue={onContinue} />);
    expect(screen.getByText('Найдено: 0. Подходят: 0 из 3. Письма: 0.')).toBeVisible();
    expect(screen.getByText(stopped.reason!)).toBeVisible();
    expect(screen.getByText('Списано: 1 кр.')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Подготовить письма' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Продолжить в чате' }));
    expect(onContinue).toHaveBeenCalledWith(expect.stringContaining('Ничего не запускай без подтверждения'));
  });
  it('does not present unknown expenses as zero', () => {
    render(<OutreachChatSummary name="Поиск" presentation={{ ...stopped, expenses: {} }} onContinue={() => {}} />);
    expect(screen.getByText('Списано: уточняется')).toBeVisible();
  });
});
