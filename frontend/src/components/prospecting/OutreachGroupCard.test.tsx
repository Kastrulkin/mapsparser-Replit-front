import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { OutreachGroupCard, type GroupPresentation } from './OutreachGroupCard';
afterEach(cleanup);
const presentation: GroupPresentation = {
  phase: 'companies', status: 'queued', label: 'Ожидает запуска', active: true,
  next_action: { kind: 'control', action: 'pause', label: 'На паузу' },
  metrics: { found: 42, eligible: 0, target: 3, needs_decision: 41, prepared: 0, queued: 0, sent: 0, replies: 0 },
  expenses: { charged: 46, estimate: 65, estimate_only: true },
  achievements: [{ id: 'enriched', label: 'Собраны сведения о компаниях', count: 41 }],
  substeps: [{ id: 'enrichment', label: 'Контакты и сведения', status: 'completed', processed: 41, total: 41 }],
};
it('shows the queue and actual outputs separately from the qualified goal', () => {
  const { container } = render(<OutreachGroupCard name="Индия → Пхукет" presentation={presentation} />);
  expect(screen.getByRole('status')).toHaveTextContent('Ожидает запуска');
  expect(screen.getByText('0 / 3')).toBeInTheDocument();
  expect(screen.getByRole('list', { name: 'Результаты работы' })).toHaveTextContent('41');
  expect(container.querySelector('.animate-spin')).not.toBeInTheDocument();
  expect(screen.getByText('Списано: 46 кр.')).toBeInTheDocument();
});
it('shows the real running substep without expanding technical detail', () => {
  const { container } = render(<OutreachGroupCard name="Поиск" presentation={{ ...presentation, status: 'running', label: 'Выполняется', substeps: [{ id: 'qualification', label: 'Проверяем соответствие', status: 'running', processed: 2, total: 3 }] }} />);
  expect(screen.getAllByRole('status').some(item => item.textContent?.includes('Проверяем соответствие'))).toBe(true);
  expect(container.querySelector('details')).not.toHaveAttribute('open');
});
