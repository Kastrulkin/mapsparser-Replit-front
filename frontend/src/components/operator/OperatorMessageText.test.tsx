import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { OperatorMessageText } from './OperatorMessageText';

const text = 'Проверка закончена: найдено подключение Riderra.\n\n' + 'Подробные сохранённые сведения. '.repeat(30);

it('keeps a long completed answer short with details expanded in place', () => {
  render(<OperatorMessageText message={{ role: 'operator', status: 'completed', text }} />);
  expect(screen.getByText('Проверка закончена: найдено подключение Riderra.')).toBeVisible();
  expect(screen.getByText('Подробнее').closest('details')).not.toHaveAttribute('open');
  expect(screen.getByText(/Подробные сохранённые/)).not.toBeVisible();
});

it('keeps the complete approval text visible before the user decides', () => {
  render(<OperatorMessageText message={{ role: 'operator', status: 'approval_required', text }} />);
  expect(screen.queryByText('Подробнее')).not.toBeInTheDocument();
  expect(screen.getByText(/Подробные сохранённые/)).toBeVisible();
});

it('announces the pending state without claiming completion', () => {
  render(<OperatorMessageText message={{ role: 'operator', status: 'running', text: 'Выполняю задачу…' }} />);
  expect(screen.getByRole('status')).toHaveTextContent('Выполняю задачу…');
});
