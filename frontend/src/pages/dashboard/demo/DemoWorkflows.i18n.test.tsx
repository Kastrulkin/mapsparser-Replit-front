import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';

import { LanguageProvider, type Language } from '@/i18n/LanguageContext';
import { DemoAgentsPage } from './DemoAgentsPage';
import { DemoContentPlanPage } from './DemoContentPlanPage';

const languages: Language[] = ['en', 'fr', 'es', 'el', 'de', 'th', 'ar', 'ha', 'tr'];

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe('safe multilingual demo workflows', () => {
  it.each(languages)('renders content and agents without Russian fallback for %s', async (language) => {
    window.localStorage.setItem('language', language);
    const content = render(<MemoryRouter><LanguageProvider><DemoContentPlanPage /></LanguageProvider></MemoryRouter>);
    expect((await screen.findAllByRole('heading')).length).toBeGreaterThan(0);
    expect(content.container.textContent).not.toMatch(/[А-Яа-яЁё]/);
    content.unmount();

    const agents = render(<LanguageProvider><DemoAgentsPage /></LanguageProvider>);
    expect((await screen.findAllByRole('heading')).length).toBeGreaterThan(0);
    expect(agents.container.textContent).not.toMatch(/[А-Яа-яЁё]/);
  });

  it('creates a content-plan draft entirely in session storage', async () => {
    window.localStorage.setItem('language', 'en');
    render(<MemoryRouter><LanguageProvider><DemoContentPlanPage /></LanguageProvider></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button', { name: 'Create plan' }));
    fireEvent.click(screen.getByRole('button', { name: 'Show preview plan' }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Edited demo draft' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save to plan' }));
    expect(screen.getByText('Edited demo draft')).toBeInTheDocument();
    expect(window.sessionStorage.getItem('localos:demo-content-plan:v1')).toBe('saved');
  });

  it('runs an agent example and exposes the human approval boundary', async () => {
    window.localStorage.setItem('language', 'en');
    render(<LanguageProvider><DemoAgentsPage /></LanguageProvider>);
    fireEvent.click(await screen.findByRole('button', { name: 'Run an example' }));
    expect(screen.getByText('The agent is preparing a result…')).toBeInTheDocument();
    expect(screen.getByText('The agent never publishes replies without a manual review.')).toBeInTheDocument();
  });
});
