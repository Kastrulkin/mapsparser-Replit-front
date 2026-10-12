import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import DemoBusinessKnowledge from './DemoBusinessKnowledge';
vi.mock('@/i18n/LanguageContext.logic', () => ({ useLanguage: () => ({ language: 'ru' }) }));
describe('public demo knowledge', () => {
  it('shows sample facts, rules and text with no private requests or fake downloads', async () => {
    const request = vi.spyOn(globalThis, 'fetch');
    const user = userEvent.setup();
    render(<DemoBusinessKnowledge />);
    expect(screen.getByText('6')).toBeVisible();
    await user.click(screen.getByRole('tab', { name: 'Правила и особенности' }));
    expect(screen.getByText(/Проверить мастера/)).toBeVisible();
    await user.click(screen.getByRole('tab', { name: 'Документы' }));
    expect(screen.getByText('Правила обслуживания.txt')).toBeVisible();
    expect(request).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: /Скачать|Сохранить/ })).not.toBeInTheDocument();
    request.mockRestore();
  });
});
