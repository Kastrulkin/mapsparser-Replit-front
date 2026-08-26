import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ErrorBoundary } from '@/components/ErrorBoundary';
import { LanguageProvider } from '@/i18n/LanguageContext';
import Index from './Index';

describe('public landing DOM ownership', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'ru');
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)));
  });

  it('stays usable when an Android translator moves the audit button label', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    render(
      <MemoryRouter initialEntries={['/']}>
        <LanguageProvider>
          <ErrorBoundary>
            <Index />
          </ErrorBoundary>
        </LanguageProvider>
      </MemoryRouter>,
    );

    const email = await screen.findByLabelText('Email');
    const mapsUrl = screen.getByLabelText('Ссылка на карточку');
    const submit = screen.getAllByRole('button', { name: 'Получить аудит' })
      .find((button) => button.getAttribute('type') === 'submit');
    expect(submit).toBeDefined();
    const label = submit!.querySelector('span');
    expect(label).not.toBeNull();
    const labelNode = Array.from(label!.childNodes).find((node) => (
      node.nodeType === Node.TEXT_NODE && node.textContent?.includes('Получить аудит')
    ));

    expect(labelNode).toBeDefined();
    const translatedWrapper = document.createElement('font');
    translatedWrapper.setAttribute('data-external-translation', 'true');
    label!.insertBefore(translatedWrapper, labelNode!);
    translatedWrapper.appendChild(labelNode!);

    fireEvent.change(email, { target: { value: 'irina@example.test' } });
    fireEvent.change(mapsUrl, { target: { value: 'https://yandex.ru/maps/org/test/1' } });
    fireEvent.click(submit!);

    expect(screen.queryByText('Что-то пошло не так')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Отправляем…' })).toBeDisabled();
    consoleError.mockRestore();
  });
});
