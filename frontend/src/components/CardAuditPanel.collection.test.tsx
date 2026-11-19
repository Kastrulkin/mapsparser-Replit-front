import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import CardAuditPanel from './CardAuditPanel';

vi.mock('@/i18n/LanguageContext.logic', () => ({ useLanguage: () => ({ language: 'ru' }) }));
vi.mock('@/hooks/useApiData', () => ({
  useApiData: () => ({ data: { audit: { parse_context: { has_successful_parse: false } } } }),
}));

describe('card audit before the first snapshot', () => {
  it('shows the launch instructions only when there is no active collection', () => {
    const { rerender } = render(<CardAuditPanel businessId="new-client" />);
    expect(screen.getByText(/нажмите «Обновить данные карточки»/)).toBeVisible();

    rerender(<CardAuditPanel businessId="new-client" collectionInProgress />);
    expect(screen.queryByText(/нажмите «Обновить данные карточки»/)).not.toBeInTheDocument();

    rerender(<CardAuditPanel businessId="new-client" collectionFailed />);
    expect(screen.getByRole('status')).toHaveTextContent('Не удалось собрать данные карточки.');
    expect(screen.getByText(/нажмите «Обновить данные карточки»/)).toBeVisible();
  });
});
