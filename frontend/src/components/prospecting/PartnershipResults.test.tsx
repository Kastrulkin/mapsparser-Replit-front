import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { PartnershipResults } from './PartnershipResults';
const mocks = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: mocks.request } }));
beforeEach(() => mocks.request.mockReset());
it('finds a candidate hidden below agreements and keeps the route to correspondence visible', async () => {
  mocks.request.mockResolvedValue({ counts: { partners: 1, launched: 0, preparing: 0, needs_decision: 0 }, items: [
    { id: 'p1', name: 'Кофейня', business_name: 'Салон', agreement_json: { status: 'confirmed' } },
    { id: 'p2', name: 'Весёлая школа', business_name: 'Салон', agreement_json: {} },
  ] });
  const openWork = vi.fn();
  render(<PartnershipResults scope={{ kind: 'business', id: 'b1' }} openWork={openWork} />);
  fireEvent.change(await screen.findByRole('searchbox'), { target: { value: 'веселая' } });
  expect(screen.getByText('Весёлая школа · Салон')).toBeVisible();
  expect(screen.queryByText('Кофейня')).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'нет совпадений' } });
  expect(screen.getByRole('status')).toHaveTextContent('Ничего не найдено');
  fireEvent.click(screen.getByRole('button', { name: 'Переписка и статусы работы' }));
  expect(openWork).toHaveBeenCalled();
});
it('keeps a historical partner visible without approving missing terms', async () => {
  mocks.request.mockResolvedValue({ counts: { partners: 1, launched: 0, preparing: 0, launch_unrecorded: 1, needs_decision: 1 }, items: [
    { id: 'p1', name: 'YES Apart', business_name: 'Весёлая расчёска', agreement_json: { relationship_status: 'confirmed', status: 'needs_confirmation', source_summary: 'Партнёр подтверждён Александром' } },
  ] });
  render(<PartnershipResults scope={{ kind: 'network', id: 'n1' }} openWork={vi.fn()} />);
  fireEvent.click(await screen.findByText('YES Apart'));
  expect(screen.getByText(/Партнёр подтверждён. Условия нужно уточнить/)).toBeVisible();
  expect(screen.getByRole('button', { name: 'Подготовить инструкцию' })).toBeDisabled();
});
it('shows confirmed partners before candidates and opens their terms', async () => {
  mocks.request.mockResolvedValue({ counts: { partners: 1, launched: 0, preparing: 1, needs_decision: 0 }, items: [
    { id: 'p1', name: 'Кофейня', business_name: 'Салон', agreement_json: { status: 'confirmed', terms: { details: 'Купон на кофе' } } },
    { id: 'p2', name: 'Кандидат', business_name: 'Салон', agreement_json: {} },
  ] });
  render(<PartnershipResults scope={{ kind: 'business', id: 'b1' }} openWork={vi.fn()} />);
  await screen.findByText('1');
  fireEvent.click(screen.getByText('Кофейня'));
  expect(screen.getByText('Купон на кофе')).toBeVisible();
  expect(screen.getByText('Инструкция сотрудникам')).toBeVisible();
  expect(screen.getByText('Утверждённой инструкции пока нет.')).toBeVisible();
});
it('network asks for a point without silently selecting the first', async () => {
  mocks.request.mockResolvedValue({ counts: { partners: 0, launched: 0, preparing: 0, needs_decision: 0 }, items: [], locations: [{ id: 'b2', name: 'Вторая точка' }] });
  const openWork = vi.fn();
  render(<PartnershipResults scope={{ kind: 'network', id: 'n1' }} openWork={openWork} />);
  await screen.findByText('Подтверждённых партнёрств пока нет.');
  expect(openWork).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Перейти к поиску и переговорам'));
  fireEvent.click(screen.getByText('Вторая точка'));
  expect(openWork).toHaveBeenCalledWith('b2');
});
