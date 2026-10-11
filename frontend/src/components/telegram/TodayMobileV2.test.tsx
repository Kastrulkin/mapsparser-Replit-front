import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AnimatePresence } from 'framer-motion';
import { useState, type ReactElement } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { LanguageContext, type Language } from '@/i18n/LanguageContext.logic';
import { en } from '@/i18n/locales/en';
import { getTodayPageCopy } from '@/i18n/todayPageCopy';
import { TodayMobileV2 } from './TodayMobileV2';

// Navigation and scope assertions use real final styles without a wall-clock entrance animation.
// Browser checks retain the normal animation; no visibility assertion is replaced here.
function renderToday(ui: ReactElement, language: Language = 'ru') {
  return render(
    <LanguageContext.Provider value={{ language, setLanguage: vi.fn(), t: en }}>
      <AnimatePresence initial={false}>{ui}</AnimatePresence>
    </LanguageContext.Provider>,
  );
}

const languages: Language[] = ['ru', 'en', 'fr', 'es', 'el', 'de', 'th', 'ar', 'ha', 'tr', 'hy'];

const preferredContentCopy = {
  en: {
    title: 'Content plan',
    reason: 'Open the selected area and continue working.',
    cta: 'Open content plan',
  },
  es: {
    title: 'Plan de contenido',
    reason: 'Abre el área seleccionada y continúa trabajando.',
    cta: 'Abrir plan de contenido',
  },
};

describe('TodayMobileV2', () => {
  it.each(languages)('uses nonempty localized top action copy for %s', (language) => {
    const pageCopy = getTodayPageCopy(language);
    renderToday(
      <TodayMobileV2
        data={{ focus_action: { title: 'API title', reason: 'API reason' } }}
        loading={false}
        slowLoading={false}
        command=""
        setCommand={vi.fn()}
        ask={vi.fn()}
        openTarget={vi.fn()}
        openProgress={vi.fn()}
        track={vi.fn()}
      />,
      language,
    );

    expect(pageCopy.now.trim().length).toBeGreaterThan(0);
    expect(screen.getByText(pageCopy.now)).toBeVisible();
  });

  it.each(['en', 'es'] satisfies Language[])(
    'localizes the preferred content action for %s',
    async (language) => {
      const openTarget = vi.fn();
      const expected = preferredContentCopy[language];
      renderToday(
        <TodayMobileV2
          data={{
            preference: {
              primary_flow: 'content',
              available_flows: ['content'],
            },
          }}
          loading={false}
          slowLoading={false}
          command=""
          setCommand={vi.fn()}
          ask={vi.fn()}
          openTarget={openTarget}
          openProgress={vi.fn()}
          track={vi.fn()}
        />,
        language,
      );

      expect(screen.getByRole('heading', { name: expected.title })).toBeVisible();
      expect(screen.getByText(expected.reason)).toBeVisible();
      const action = screen.getByRole('button', { name: expected.cta });
      expect(action).toBeVisible();
      await userEvent.tab();
      expect(action).toHaveFocus();
      await userEvent.click(action);
      expect(openTarget).toHaveBeenCalledWith('content', undefined);
    },
  );

  it('preserves high-priority API copy, identity, route, and scope in Spanish', async () => {
    const openTarget = vi.fn();
    const trackProduct = vi.fn();
    renderToday(
      <TodayMobileV2
        data={{
          preference: { primary_flow: 'content', available_flows: ['content'] },
          focus_action: {
            id: 'api-focus-100',
            priority: 100,
            title: 'API title verbatim',
            reason: 'API reason verbatim',
            expected_outcome: 'API outcome verbatim',
            cta_label: 'API CTA verbatim',
            screen: 'finance',
            target_scope: { kind: 'business', id: 'business-api' },
          },
        }}
        loading={false}
        slowLoading={false}
        command=""
        setCommand={vi.fn()}
        ask={vi.fn()}
        openTarget={openTarget}
        openProgress={vi.fn()}
        track={vi.fn()}
        trackProduct={trackProduct}
      />,
      'es',
    );

    expect(screen.getByRole('heading', { name: 'API title verbatim' })).toBeVisible();
    expect(screen.getByText('API reason verbatim')).toBeVisible();
    expect(screen.getByText(/API outcome verbatim/)).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'API CTA verbatim' }));
    expect(openTarget).toHaveBeenCalledWith('finance', {
      kind: 'business',
      id: 'business-api',
    });
    expect(trackProduct).toHaveBeenCalledWith('mission_open', 'api-focus-100');
  });

  it('keeps urgent routing above a localized preferred action', async () => {
    const openTarget = vi.fn();
    renderToday(
      <TodayMobileV2
        data={{
          preference: { primary_flow: 'content', available_flows: ['content'] },
          work_sections: {
            needs_decision: [{
              id: 'urgent-api',
              title: 'Urgent API title',
              description: 'Urgent API reason',
              flow: 'maps',
              urgency: 'urgent',
              business_id: 'business-urgent',
            }],
          },
        }}
        loading={false}
        slowLoading={false}
        command=""
        setCommand={vi.fn()}
        ask={vi.fn()}
        openTarget={openTarget}
        openProgress={vi.fn()}
        track={vi.fn()}
      />,
      'es',
    );

    expect(screen.getByRole('heading', { name: 'Urgent API title' })).toBeVisible();
    expect(screen.queryByRole('heading', { name: preferredContentCopy.es.title })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Resolver tarea' }));
    expect(openTarget).toHaveBeenCalledWith('cards', {
      kind: 'business',
      id: 'business-urgent',
    });
  });

  it('keeps an edited command when context changes from Russian to Spanish', async () => {
    const LocaleHarness = () => {
      const [language, setLanguage] = useState<Language>('ru');
      const [command, setCommand] = useState('Черновик');
      return (
        <LanguageContext.Provider value={{ language, setLanguage, t: en }}>
          <button type="button" onClick={() => setLanguage('es')}>Cambiar idioma</button>
          <TodayMobileV2
            data={{ focus_action: { title: 'API title', reason: 'API reason' } }}
            loading={false}
            slowLoading={false}
            command={command}
            setCommand={setCommand}
            ask={vi.fn()}
            openTarget={vi.fn()}
            openProgress={vi.fn()}
            track={vi.fn()}
          />
        </LanguageContext.Provider>
      );
    };
    render(<LocaleHarness />);
    const command = screen.getByRole('textbox');
    await userEvent.type(command, ' команды');

    await userEvent.click(screen.getByRole('button', { name: 'Cambiar idioma' }));

    expect(screen.getByRole('textbox')).toHaveValue('Черновик команды');
    expect(screen.getByText(getTodayPageCopy('es').now)).toBeVisible();
  });

  it('keeps hook order stable while loading becomes ready in English', async () => {
    const props = {
      slowLoading: false,
      command: '',
      setCommand: vi.fn(),
      ask: vi.fn(),
      openTarget: vi.fn(),
      openProgress: vi.fn(),
      track: vi.fn(),
    };
    const view = renderToday(
      <TodayMobileV2 data={null} loading {...props} />,
      'en',
    );
    expect(view.container.querySelector('[aria-busy="true"]')).toBeInTheDocument();

    view.rerender(
      <LanguageContext.Provider value={{ language: 'en', setLanguage: vi.fn(), t: en }}>
        <AnimatePresence initial={false}>
          <TodayMobileV2
            data={{ focus_action: { title: 'API title', reason: 'API reason' } }}
            loading={false}
            {...props}
          />
        </AnimatePresence>
      </LanguageContext.Provider>,
    );

    await waitFor(() => expect(screen.getByText(getTodayPageCopy('en').now)).toBeVisible());
  });

  it('opens the preferred content plan in its own location', async () => {
    const openTarget = vi.fn();
    renderToday(<TodayMobileV2
      data={{ scope: { kind: 'network', id: 'network-1' },
        preference: { primary_flow: 'content', available_flows: ['overview', 'content'] },
        focus_action: { title: 'Обычная задача', priority: 20 },
        work_sections: { continue_work: [{ id: 'post-1', flow: 'content', title: 'Пост на неделю', business_id: 'business-2' }] } }}
      loading={false} slowLoading={false} command="" setCommand={vi.fn()} ask={vi.fn()}
      openTarget={openTarget} openProgress={vi.fn()} track={vi.fn()} />);
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Контент-план' })).toBeVisible());
    await userEvent.click(screen.getByRole('button', { name: 'Открыть контент-план' }));
    expect(openTarget).toHaveBeenCalledWith('content', { kind: 'business', id: 'business-2' });
  });

  it('keeps urgent work above the preferred content plan', async () => {
    renderToday(<TodayMobileV2
      data={{ preference: { primary_flow: 'content', available_flows: ['content'] },
        work_sections: { needs_decision: [{ id: 'failed-1', title: 'Ошибка обновления', flow: 'maps', urgency: 'urgent' }] } }}
      loading={false} slowLoading={false} command="" setCommand={vi.fn()} ask={vi.fn()}
      openTarget={vi.fn()} openProgress={vi.fn()} track={vi.fn()} />);
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Ошибка обновления' })).toBeVisible());
    expect(screen.queryByRole('heading', { name: 'Контент-план', level: 2 })).not.toBeInTheDocument();
  });

  it('keeps the ЛокалОС assignment field visible in Russian', () => {
    renderToday(
      <TodayMobileV2
        data={{ scope: { kind: 'business', id: 'business-1', name: 'Тестовый бизнес' } }}
        loading={false}
        slowLoading={false}
        command=""
        setCommand={vi.fn()}
        ask={vi.fn()}
        openTarget={vi.fn()}
        openProgress={vi.fn()}
        track={vi.fn()}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Поручить ЛокалОС' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Например: подготовь ответы')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Поручить ЛокалОС' })).not.toBeInTheDocument();
  });

  it('opens a network card problem directly in the card screen for that location', async () => {
    const openTarget = vi.fn();
    renderToday(
      <TodayMobileV2
        data={{
          scope: { kind: 'network', id: 'network-1', name: 'Сеть салонов' },
          focus_action: { title: 'Обновить данные сети', reason: 'Одна точка отстаёт', screen: 'finance' },
          data_health: { status: 'stale' },
          network_summary: { locations_count: 2, healthy_locations_count: 1, problem_locations_count: 1, finance: { total: 2, fresh: 1, stale: 1, due: 0, missing: 0 } },
          problem_locations: [{ business_id: 'business-2', business_name: 'Север', data_health_status: 'stale', problem_areas: ['maps'], focus_action: { cta_url: '/dashboard/card' }, target_scope: { kind: 'business', id: 'business-2' } }],
          location_breakdown: [{ business_id: 'business-2', business_name: 'Север', data_health: { status: 'stale' }, rhythm: { label: 'Ритм формируется' }, analytics_level: { label: 'Нужны данные', next_unlock: 'Загрузите свежую сводку.' } }],
          analytics_modules: [{ key: 'sales', label: 'Продажи и средний чек', status: 'locked', next_unlock: 'Добавьте данные: продажи и средний чек.' }],
        }}
        loading={false}
        slowLoading={false}
        command=""
        setCommand={vi.fn()}
        ask={vi.fn()}
        openTarget={openTarget}
        openProgress={vi.fn()}
        track={vi.fn()}
      />,
    );

    expect(screen.getByText('Следующий шаг')).toBeInTheDocument();
    await userEvent.click(screen.getByText('Данные для анализа'));
    expect(screen.getByText('Данные по точкам')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: /Север/ }));
    expect(openTarget).toHaveBeenCalledWith('cards', { kind: 'business', id: 'business-2' });
  });

  it('uses natural Russian declension for community message counts', () => {
    renderToday(
      <TodayMobileV2
        data={{
          scope: { kind: 'business', id: 'business-1', name: 'Салон' },
          community_pulse: [{ id: 'topic-1', title: 'Рост цен', source_name: 'Beauty Owners', message_count: 21 }],
        }}
        loading={false}
        slowLoading={false}
        command=""
        setCommand={vi.fn()}
        ask={vi.fn()}
        openTarget={vi.fn()}
        openProgress={vi.fn()}
        track={vi.fn()}
      />,
    );

    expect(screen.getByText(/21 сообщение/)).toBeInTheDocument();
    expect(screen.queryByText(/21 сообщений/)).not.toBeInTheDocument();
  });

  it('shows a useful business history reminder and opens the right business', async () => {
    const openTarget = vi.fn();
    renderToday(
      <TodayMobileV2
        data={{
          scope: { kind: 'business', id: 'business-1', name: 'Органика' },
          profile_reminders: [{
            id: 'business-history:business-1',
            title: 'Расскажите о бизнесе',
            description: 'ЛокалОС будет точнее готовить контент и предложения партнёрам.',
            screen: 'partnerships',
            target_scope: { kind: 'business', id: 'business-1' },
          }],
        }}
        loading={false}
        slowLoading={false}
        command=""
        setCommand={vi.fn()}
        ask={vi.fn()}
        openTarget={openTarget}
        openProgress={vi.fn()}
        track={vi.fn()}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Сделайте ЛокалОС точнее' })).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: /Расскажите о бизнесе/ }));
    expect(openTarget).toHaveBeenCalledWith('partnerships', { kind: 'business', id: 'business-1' });
  });
});
