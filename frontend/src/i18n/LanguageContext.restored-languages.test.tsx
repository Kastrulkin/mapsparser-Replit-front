import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { LanguageProvider } from './LanguageContext';
import { useLanguage, type Language } from './LanguageContext.logic';

const LanguageControl = ({ target }: { target: Language }) => {
  const { language, setLanguage, t } = useLanguage();
  return (
    <div>
      <span data-testid="current-language">{language}</span>
      <span data-testid="home-title">{t.header.whatWeDo}</span>
      <button type="button" onClick={() => setLanguage(target)}>Select language</button>
    </div>
  );
};

afterEach(() => {
  window.localStorage.clear();
  window.history.replaceState({}, '', '/');
});

describe.each(['hy', 'kk'] satisfies Language[])('%s restored language', (language) => {
  it('loads from a shared pricing URL over a saved preference', async () => {
    window.localStorage.setItem('language', 'ru');
    window.history.replaceState({}, '', `/pricing?lang=${language}`);
    render(<LanguageProvider><LanguageControl target={language} /></LanguageProvider>);
    expect(await screen.findByTestId('current-language')).toHaveTextContent(language);
    expect(screen.getByTestId('home-title')).not.toBeEmptyDOMElement();
  });

  it('keeps the current route, parameters, and fragment when selected', async () => {
    window.localStorage.setItem('language', 'ru');
    window.history.replaceState({ from: 'test' }, '', '/pricing?ref=partner#plans');
    render(<LanguageProvider><LanguageControl target={language} /></LanguageProvider>);
    fireEvent.click(await screen.findByRole('button', { name: 'Select language' }));
    expect(window.location.pathname).toBe('/pricing');
    expect(window.location.search).toBe(`?ref=partner&lang=${language}`);
    expect(window.location.hash).toBe('#plans');
    expect(window.history.state).toEqual({ from: 'test' });
    await waitFor(() => expect(screen.getByTestId('current-language')).toHaveTextContent(language));
  });
});
