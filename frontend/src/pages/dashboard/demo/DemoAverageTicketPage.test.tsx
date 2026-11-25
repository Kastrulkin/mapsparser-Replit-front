import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import type { Language } from '@/i18n/LanguageContext.logic';
import { demoAverageTicketCopy } from '@/i18n/demoAverageTicketCopy';
import { newAuth } from '@/lib/auth_new';
import { DemoAverageTicketPage } from './DemoAverageTicketPage';

vi.mock('@/lib/auth_new', () => ({
  newAuth: { makeRequest: vi.fn() },
}));

const languages: Language[] = ['ru', 'en', 'fr', 'es', 'el', 'de', 'th', 'ar', 'ha', 'tr', 'hy', 'kk'];
const fetchSpy = vi.fn();
const normalizeWhitespace = (value: string) => value.replace(/\s+/g, ' ').trim();

beforeEach(() => {
  fetchSpy.mockReset();
  vi.stubGlobal('fetch', fetchSpy);
});

afterEach(() => {
  window.localStorage.clear();
  vi.unstubAllGlobals();
  vi.mocked(newAuth.makeRequest).mockReset();
});

describe('DemoAverageTicketPage', () => {
  it.each(languages)('shows, toggles, and hides a local example in %s', async (language) => {
    window.localStorage.setItem('language', language);
    render(<LanguageProvider><DemoAverageTicketPage /></LanguageProvider>);
    const copy = demoAverageTicketCopy[language];
    const formattedMainPrice = `${new Intl.NumberFormat(language).format(1500)} ₽`;
    const formattedTotal = `${new Intl.NumberFormat(language).format(1800)} ₽`;

    expect(await screen.findByText(copy.fictitious, { exact: true })).toBeInTheDocument();
    expect(screen.getByText((content) => normalizeWhitespace(content) === normalizeWhitespace(formattedMainPrice))).toBeInTheDocument();
    expect(screen.getByText((content) => normalizeWhitespace(content) === normalizeWhitespace(formattedTotal))).toBeInTheDocument();
    expect(screen.getByRole('button', { name: copy.showScript })).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(screen.getByRole('button', { name: copy.showScript }));
    expect(screen.getByText(copy.scriptTitle, { exact: true })).toBeInTheDocument();
    expect(screen.getByText(copy.script, { exact: true })).toBeInTheDocument();
    expect(screen.getByText(copy.safety, { exact: true })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: copy.hideScript })).toHaveAttribute('aria-expanded', 'true');
    expect(newAuth.makeRequest).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: copy.hideScript }));
    expect(screen.queryByText(copy.scriptTitle, { exact: true })).not.toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('has copy for all supported demo languages', () => {
    expect(Object.keys(demoAverageTicketCopy).sort()).toEqual([...languages].sort());
    languages.forEach((language) => {
      expect(demoAverageTicketCopy[language].script).toBeTruthy();
      expect(demoAverageTicketCopy[language].fictitious).toBeTruthy();
    });
  });
});
