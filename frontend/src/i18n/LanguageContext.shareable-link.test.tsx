import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { LanguageProvider } from './LanguageContext';
import { useLanguage } from './LanguageContext.logic';

const LanguageControl = () => {
  const { language, setLanguage } = useLanguage();

  return (
    <div>
      <span data-testid="current-language">{language}</span>
      <button type="button" onClick={() => setLanguage('fr')}>Français</button>
    </div>
  );
};

afterEach(() => {
  window.localStorage.clear();
  window.history.replaceState({}, '', '/');
});

describe('shareable language links', () => {
  it('updates the current URL when a visitor selects a language', async () => {
    window.localStorage.setItem('language', 'ru');
    window.history.replaceState({ from: 'test' }, '', '/pricing?ref=partner#plans');

    render(<LanguageProvider><LanguageControl /></LanguageProvider>);
    fireEvent.click(await screen.findByRole('button', { name: 'Français' }));

    expect(window.location.pathname).toBe('/pricing');
    expect(window.location.search).toBe('?ref=partner&lang=fr');
    expect(window.location.hash).toBe('#plans');
    expect(window.history.state).toEqual({ from: 'test' });
    await waitFor(() => expect(screen.getByTestId('current-language')).toHaveTextContent('fr'));
  });

  it('uses the language in a shared homepage URL over a saved preference', async () => {
    window.localStorage.setItem('language', 'ru');
    window.history.replaceState({}, '', '/?lang=fr');

    render(<LanguageProvider><LanguageControl /></LanguageProvider>);

    expect(await screen.findByTestId('current-language')).toHaveTextContent('fr');
  });
});
