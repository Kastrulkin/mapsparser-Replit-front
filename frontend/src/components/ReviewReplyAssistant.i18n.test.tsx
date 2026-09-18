import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';
import ReviewReplyAssistant from './ReviewReplyAssistant';

vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    makeRequest: vi.fn(),
  },
}));

const ContextRoute = () => <Outlet context={{ user: { id: 'demo-user', demo_mode: true }, currentBusinessId: 'demo-business', onBusinessChange: vi.fn() }} />;
const AuthenticatedContextRoute = () => <Outlet context={{ user: { id: 'owner-user', demo_mode: false }, currentBusinessId: 'demo-business', onBusinessChange: vi.fn() }} />;

const unansweredDraftReview = {
  id: 'unanswered-draft-review',
  author_name: 'Мария Тестова',
  text: 'Спасибо, но запись перенесли без предупреждения.',
  rating: 2,
  published_at: '2026-09-19T12:00:00Z',
  source: 'yandex',
  has_response: false,
  reply_draft_id: 'reply-draft-1',
  reply_draft_text: 'Мария, спасибо за отзыв. Мы уточним детали и вернёмся с решением.',
  reply_draft_status: 'draft',
};

let originalClipboardDescriptor: PropertyDescriptor | undefined;

describe('ReviewReplyAssistant localization', () => {
  beforeEach(() => {
    originalClipboardDescriptor = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
    window.localStorage.clear();
    window.localStorage.setItem('language', 'el');
    vi.mocked(newAuth.makeRequest).mockImplementation((url: string) => {
      if (url.includes('/external/reviews')) return Promise.resolve({
        success: true,
        reviews: [{
          id: 'demo-review',
          author_name: 'Сергей Новиков',
          text: 'DEMO Яндекс Карты: отзыв о груминге, аккуратности мастера и удобстве записи.',
          rating: 5,
          published_at: '2026-06-20T12:00:00Z',
          source: 'yandex',
          response_text: 'Спасибо большое за добрые слова! Нам важно ваше мнение.',
        }],
      });
      return Promise.resolve({ success: true, examples: [] });
    });
  });

  afterEach(() => {
    if (originalClipboardDescriptor) {
      Object.defineProperty(navigator, 'clipboard', originalClipboardDescriptor);
      return;
    }
    Reflect.deleteProperty(navigator, 'clipboard');
  });

  it('renders the review workflow in Greek without a missing tones dictionary crash', async () => {
    render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<ReviewReplyAssistant businessName="Roga i Kopyta" aggregateScope="network" />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'Απαντήσεις σε κριτικές' })).toBeInTheDocument();
    expect(await screen.findByText('Κριτική επίδειξης για την περιποίηση, την προσοχή του ειδικού και την εύκολη κράτηση.')).toBeInTheDocument();
    expect(screen.queryByText(/DEMO Яндекс Карты/)).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/[А-Яа-яЁё]/);
    expect(vi.mocked(newAuth.makeRequest).mock.calls.some(([url]) => url === '/review-examples')).toBe(false);
  });

  it.each([
    ['ru', 'Сгенерировать ответ', 'Предложение ответа:', 'Публикация в карты вручную: скопируйте ответ и вставьте его в кабинете площадки.', 'Копировать', 'Скопировано'],
    ['en', 'Generate response', 'Response suggestion:', 'Publish to maps manually: copy the response and paste it in the platform dashboard.', 'Copy', 'Copied'],
    ['el', 'Δημιουργία απάντησης', 'Πρόταση απάντησης:', 'Δημοσιεύστε στους χάρτες χειροκίνητα: αντιγράψτε την απάντηση και επικολλήστε τη στον πίνακα της πλατφόρμας.', 'Αντιγραφή', 'Αντιγράφηκε'],
  ])('uses localized manual-draft copy without writing in %s', async (language, manualHeading, draftStatus, manualPublicationHint, copyLabel, copiedLabel) => {
    window.localStorage.setItem('language', language);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
    vi.mocked(newAuth.makeRequest).mockImplementation((url: string) => {
      if (url.includes('/external/reviews')) {
        return Promise.resolve({ success: true, reviews: [unansweredDraftReview] });
      }
      return Promise.resolve({ success: true, examples: [] });
    });

    render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<AuthenticatedContextRoute />}>
              <Route index element={<ReviewReplyAssistant businessName="LocalOS test business" initialFilter="needs_reply" />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    const manualHeadingElement = await screen.findByRole('heading', { name: manualHeading });
    expect(manualHeadingElement).toBeInTheDocument();
    expect(await screen.findByText(draftStatus)).toBeInTheDocument();
    expect(await screen.findByText(manualPublicationHint)).toBeInTheDocument();
    expect(await screen.findByDisplayValue(unansweredDraftReview.reply_draft_text)).toBeInTheDocument();
    const manualGeneratorCard = manualHeadingElement.parentElement;
    if (!manualGeneratorCard) throw new Error('Manual generator card is missing');
    expect(screen.getAllByRole('button', { name: manualHeading })).toHaveLength(2);
    expect(within(manualGeneratorCard).getByRole('button', { name: manualHeading })).toBeInTheDocument();
    const copyButton = screen.getByRole('button', { name: copyLabel });
    await userEvent.click(copyButton);
    expect(writeText).toHaveBeenCalledWith(unansweredDraftReview.reply_draft_text);
    expect(await screen.findByRole('button', { name: copiedLabel })).toBeInTheDocument();
    expect(screen.queryByText('Quick Generator')).not.toBeInTheDocument();
    expect(screen.queryByText('Черновик LocalOS: draft')).not.toBeInTheDocument();
    const requestMethods = vi.mocked(newAuth.makeRequest).mock.calls.map(([, options]) => (
      options?.method || 'GET'
    ));
    expect(requestMethods).not.toContain('POST');
    expect(requestMethods).not.toContain('PUT');
    expect(requestMethods).not.toContain('PATCH');
    expect(requestMethods).not.toContain('DELETE');
  });
});
