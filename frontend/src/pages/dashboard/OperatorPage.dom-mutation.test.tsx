import '@testing-library/jest-dom/vitest';
import { act, render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ErrorBoundary } from '@/components/ErrorBoundary';
import { LanguageProvider } from '@/i18n/LanguageContext';
import { api } from '@/services/api';
import { OperatorPage } from './OperatorPage';

vi.mock('@/services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const ContextRoute = () => (
  <Outlet context={{
    currentBusinessId: 'demo-business',
    currentBusiness: { id: 'demo-business', name: 'Тестовый бизнес' },
  }} />
);

const deferredResponse = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve;
  });
  return { promise, resolve };
};

describe('OperatorPage DOM ownership', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'ru');
  });

  it('stays usable when a browser translator moves the loading label', async () => {
    const historyResponse = deferredResponse<{ data: { messages: never[]; conversation: null } }>();
    vi.mocked(api.get).mockReturnValue(historyResponse.promise);
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    render(
      <MemoryRouter initialEntries={['/dashboard/operator']}>
        <LanguageProvider>
          <ErrorBoundary>
            <Routes>
              <Route element={<ContextRoute />}>
                <Route path="/dashboard/operator" element={<OperatorPage />} />
              </Route>
            </Routes>
          </ErrorBoundary>
        </LanguageProvider>
      </MemoryRouter>,
    );

    const loadingLabel = await screen.findByText('Загружаем историю…');
    const textNode = Array.from(loadingLabel.childNodes).find((node) => (
      node.nodeType === Node.TEXT_NODE && node.textContent?.includes('Загружаем историю')
    ));
    const translatedWrapper = document.createElement('font');

    expect(textNode).toBeDefined();
    translatedWrapper.setAttribute('data-external-translation', 'true');
    loadingLabel.insertBefore(translatedWrapper, textNode!);
    translatedWrapper.appendChild(textNode!);

    await act(async () => {
      historyResponse.resolve({ data: { messages: [], conversation: null } });
      await historyResponse.promise;
    });

    expect(screen.queryByText('Что-то пошло не так')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Напишите задачу' })).toBeInTheDocument();
    consoleError.mockRestore();
  });
});
