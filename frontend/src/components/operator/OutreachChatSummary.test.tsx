import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { OutreachChatSummary } from './OutreachChatSummary';
import type { GroupPresentation } from '@/components/prospecting/OutreachGroupCard';
const presentation: GroupPresentation = {
  phase: 'companies', status: 'needs_attention', label: 'Требуется действие', active: false,
  reason: 'Источник поиска недоступен', next_action: { kind: 'control', label: 'Продолжить', action: 'resume' },
  metrics: { found: 41, eligible: 0, target: 3, needs_decision: 41, prepared: 0, queued: 0, sent: 0, replies: 0 },
  expenses: {},
};
describe('OutreachChatSummary', () => {
  it('separates raw candidates, confirmed target and unknown expense; only stages a safe command', () => {
    const onContinue = vi.fn();
    render(<OutreachChatSummary name="Индия → Пхукет" presentation={presentation} onContinue={onContinue} />);
    expect(screen.getByText('41')).toBeInTheDocument();
    expect(screen.getByText('0 / 3')).toBeInTheDocument();
    expect(screen.getByText('уточняется')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Разобрать причину' }));
    expect(onContinue).toHaveBeenCalledWith(expect.stringContaining('Ничего не запускай без подтверждения'));
  });
  it('uses the server billing link when credits are missing', () => {
    render(<OutreachChatSummary name="Поиск" presentation={{ ...presentation, next_action: { kind: 'link', label: 'Пополнить баланс', href: '/dashboard/billing' } }} onContinue={vi.fn()} />);
    expect(screen.getByRole('link', { name: 'Пополнить баланс' })).toHaveAttribute('href', '/dashboard/billing');
    expect(screen.queryByRole('button', { name: 'Разобрать причину' })).not.toBeInTheDocument();
  });
});
