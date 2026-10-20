import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ContentReferenceAnalysis, type EditorialReference } from './ContentReferenceAnalysis';
import { ContentSourceEvidence, type SourceResearch } from './ContentSourceResearch';

const report: SourceResearch = {
  schema_version: 1, title: 'Проверка сохранённого плана', reviewed_at: '2026-10-20', summary: 'Обнаружены повторяющиеся темы.',
  methodology: 'Ручное чтение источников.', historical_evidence: 'Совпадение не доказывает использование при генерации.',
  limitations: ['Дата публикации неизвестна.'], next_steps: ['Подтвердить исходные факты.'], stale_post_ids: [],
  findings: [{ title: 'Есть частичное соответствие', text: 'В посте есть деталь, но нет истории.', source_ids: ['source'], post_ids: ['post'] }],
  sources: [{ reference_id: 'source', name: 'Фабрика', url: 'https://example.com/case', page_title: 'История образца', checked_at: '2026-10-20',
    publication_note: 'Дата публикации не указана.', quote: 'Test the sample first', observation: 'Прочитаны этапы.', conclusion: 'Нужна проверка образца.',
    post_ids: ['post'], application: 'В текущем посте нет примерки.', limits: 'Не подтверждает возможности клиента.', retrieval: 'Доступный текст страницы.' }],
  posts: [{ post_id: 'post', title: 'Сохранённый пост', post_created_at: '2026-09-28', post_updated_at: '2026-10-15', scheduled_for: '2026-10-21',
    post_excerpt: 'Исходный текст.', theme: 'Конструкция', assessment: 'Частичное соответствие.', next_step: 'Получить подтверждение.' }],
};
const source: EditorialReference = { id: 'source', source_name: 'Фабрика', source_url: 'https://example.com/case', techniques: ['Старое общее правило'], scope: 'industry', owned: false, enabled: true, moderation: 'default', version: 1 };

describe('source approaches before planning', () => {
  it('puts the observed example, citation, approach and adaptation together', () => {
    const updated = { ...report, purpose: 'pre_plan_source_research', sources: [{ ...report.sources[0], application: 'Предлагаем показать собственную проверку образца.', suggested_example: 'Что проверяем до запуска?', agreement_question: 'Какие этапы подтверждены?' }] };
    render(<ContentReferenceAnalysis items={[source]} industryLabel="Пошив" canManage={false} busy={false} ru onToggle={vi.fn()} onRemove={vi.fn()} research={updated} />);
    fireEvent.click(screen.getByRole('button', { name: 'Фабрика', exact: true }));
    expect(screen.getByText('«Test the sample first»')).toBeVisible();
    expect(screen.getByText('Как пишет источник')).toBeVisible();
    expect(screen.getByText('Предлагаем показать собственную проверку образца.')).toBeVisible();
    expect(screen.getByText(/Наш учебный пример, не готовый пост/)).toBeVisible();
    expect(screen.getByText(/Какие этапы подтверждены/)).toBeVisible();
    fireEvent.click(screen.getByText('Дата, контекст и границы вывода'));
    expect(screen.getByText(/20.10.2026.*Дата публикации не указана/)).toBeVisible();
  });
  it('labels missing evidence rather than inventing it', () => {
    render(<ContentSourceEvidence report={report} referenceId="missing" ru />);
    expect(screen.getByText(/датированный разбор ещё не сохранён/)).toBeVisible();
    expect(screen.queryByRole('blockquote')).not.toBeInTheDocument();
  });
  it('does not show a plan audit even if an older report contains one', () => {
    render(<ContentReferenceAnalysis items={[source]} industryLabel="Пошив" canManage={false} busy={false} ru onToggle={vi.fn()} onRemove={vi.fn()} research={{ ...report, stale_post_ids: ['post'] }} />);
    expect(screen.queryByText('Обнаружены повторяющиеся темы.')).not.toBeInTheDocument();
    expect(screen.queryByText('Сохранённый пост')).not.toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.queryByRole('tab')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Фабрика', exact: true }));
    expect(screen.queryByText('В текущем посте нет примерки.')).not.toBeInTheDocument();
    expect(screen.getByText(/согласование ещё впереди/)).toBeVisible();
    expect(screen.queryByRole('button', { name: /генер|сохранить|опубликовать/i })).not.toBeInTheDocument();
  });
});
