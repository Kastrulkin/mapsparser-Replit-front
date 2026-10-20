import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ContentReferenceAnalysis, type EditorialReference } from './ContentReferenceAnalysis';

const source: EditorialReference = {
  id: 'one', source_name: 'Пример ателье', source_url: 'https://example.com/cases',
  techniques: ['Показывать общий вид и детали отделки'], enabled: true,
  scope: 'industry', owned: false, moderation: 'default', version: 1,
};
const base = { industryLabel: 'Пошив одежды', canManage: true, busy: false, ru: true,
  onToggle: vi.fn(), onRemove: vi.fn() };

describe('sources before the content plan', () => {
  it('presents one source-led flow without separate conclusion and source tabs', () => {
    render(<ContentReferenceAnalysis {...base} items={[source]} />);
    expect(screen.getByText('Перед составлением контент-плана')).toBeVisible();
    expect(screen.queryByRole('tab')).not.toBeInTheDocument();
    expect(screen.getByText(/Обсуждаем подходы с владельцем/)).toBeVisible();
    expect(screen.getByText(/Датированное исследование страниц пока не сохранено/)).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: source.source_name, exact: true }));
    expect(screen.getByRole('button', { name: source.source_name, exact: true })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('link')).toHaveAttribute('href', source.source_url);
  });
  it('opens one source at a time and keeps keyboard focus on the stable source button', () => {
    render(<ContentReferenceAnalysis {...base} items={[source, { ...source, id: 'two', source_name: 'Другая мастерская' }]} />);
    const first = screen.getByRole('button', { name: source.source_name, exact: true });
    fireEvent.click(first);
    fireEvent.click(screen.getByRole('button', { name: 'Другая мастерская', exact: true }));
    expect(first).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getAllByRole('link')).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Другая мастерская', exact: true })).toHaveAttribute('aria-expanded', 'true');
  });
  it('keeps an excluded source readable and preserves its enable control', () => {
    render(<ContentReferenceAnalysis {...base} items={[{ ...source, enabled: false }]} />);
    fireEvent.click(screen.getByRole('button', { name: source.source_name, exact: true }));
    fireEvent.click(screen.getByText('Использование ориентира в новых черновиках'));
    expect(screen.getByText(/исключён из подготовки/)).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Включить Пример ателье' }));
    expect(base.onToggle).toHaveBeenCalledWith({ ...source, enabled: false });
  });
  it('does not interpret availability as owner approval', () => {
    render(<ContentReferenceAnalysis {...base} items={[source]} />);
    fireEvent.click(screen.getByRole('button', { name: source.source_name, exact: true }));
    fireEvent.click(screen.getByText('Использование ориентира в новых черновиках'));
    expect(screen.getByText(/не означает согласование подхода/)).toBeVisible();
    expect(screen.queryByText('Согласовано')).not.toBeInTheDocument();
  });
  it('blocks unsafe source links without inventing missing research', () => {
    render(<ContentReferenceAnalysis {...base} items={[{ ...source, source_url: 'javascript:alert(1)', techniques: [] }]} />);
    fireEvent.click(screen.getByRole('button', { name: source.source_name, exact: true }));
    expect(screen.getByText(/цитаты и дата изучения страницы ещё не добавлены/)).toBeVisible();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });
  it('retains read-only permissions', () => {
    render(<ContentReferenceAnalysis {...base} canManage={false} items={[source]} />);
    fireEvent.click(screen.getByRole('button', { name: source.source_name, exact: true }));
    fireEvent.click(screen.getByText('Использование ориентира в новых черновиках'));
    expect(screen.getByRole('button', { name: 'Отключить Пример ателье' })).toBeDisabled();
  });
  it('offers a practical start for an empty set', () => {
    render(<ContentReferenceAnalysis {...base} items={[]} />);
    expect(screen.getByText(/Добавьте публичную ссылку/)).toBeVisible();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
