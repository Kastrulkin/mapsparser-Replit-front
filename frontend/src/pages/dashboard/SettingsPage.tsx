import { Link, useLocation, useOutletContext } from 'react-router-dom';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useLanguage } from '@/i18n/LanguageContext';
import TelegramConnection from '@/components/TelegramConnection';
import WhatsAppConnection from '@/components/WhatsAppConnection';
import { WABACredentials } from '@/components/WABACredentials';
import { TelegramBotCredentials } from '@/components/TelegramBotCredentials';
import { NetworkManagement } from '@/components/NetworkManagement';
import { ExternalIntegrations } from '@/components/ExternalIntegrations';
import FinanceCrmPanel from '@/components/FinanceCrmPanel';
import { Bot, Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DashboardActionPanel,
  DashboardCompactMetricsRow,
  DashboardPageHeader,
  DashboardSection,
} from '@/components/dashboard/DashboardPrimitives';

type SettingsBusiness = {
  network_id?: string | number | null;
  telegram_bot_token?: string | null;
  telegram_chat_id?: string | null;
  waba_phone_id?: string | null;
  waba_access_token?: string | null;
};

export const SettingsPage = () => {
  const location = useLocation();
  const channelsRef = useRef<HTMLElement | null>(null);
  const integrationsRef = useRef<HTMLElement | null>(null);
  const telegramPublishRef = useRef<HTMLDivElement | null>(null);
  const [socialReadinessRefreshKey, setSocialReadinessRefreshKey] = useState(0);
  const { currentBusinessId, currentBusiness } = useOutletContext<{
    currentBusinessId?: string | null;
    currentBusiness?: SettingsBusiness | null;
  }>();
  const { t } = useLanguage();

  const hasNetwork = Boolean(currentBusiness?.network_id);
  const hasTelegramBot = Boolean(String(currentBusiness?.telegram_bot_token || '').trim());
  const hasWhatsappCredentials = Boolean(
    String(currentBusiness?.waba_phone_id || '').trim() || String(currentBusiness?.waba_access_token || '').trim(),
  );
  const focusTarget = useMemo(() => {
    const searchParams = new URLSearchParams(location.search);
    return searchParams.get('focus') || location.hash.replace(/^#/, '');
  }, [location.hash, location.search]);
  const channelsFocused = focusTarget === 'channels' || focusTarget === 'telegram';
  const telegramPublishFocused = focusTarget === 'telegram';
  const integrationFocusTargets = new Set(['integrations', 'vk', 'google_business', 'instagram', 'facebook', 'meta']);
  const integrationsFocused = integrationFocusTargets.has(focusTarget);

  useEffect(() => {
    if (!channelsFocused && !integrationsFocused) return;
    window.setTimeout(() => {
      if (channelsFocused) {
        if (telegramPublishFocused && telegramPublishRef.current) {
          telegramPublishRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
          return;
        }
        channelsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }
      integrationsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
  }, [channelsFocused, integrationsFocused, telegramPublishFocused]);

  return (
    <div className="mx-auto max-w-6xl space-y-7 pb-10">
      <DashboardPageHeader
        eyebrow="LocalOS"
        title={t.dashboard.settings.title}
        description={t.dashboard.settings.subtitle}
        icon={Settings}
      />

      <DashboardActionPanel
        title="Настройки без лишнего шума"
        description="Сначала подключите каналы связи, затем внешние кабинеты, после этого включайте ИИ-агента и сетевые сценарии. Так проще понять, что уже готово к работе, а где ещё нужен ручной шаг."
        tone="sky"
        status={
          <div className="grid gap-2 text-sm sm:grid-cols-3">
            <div><span className="font-semibold text-slate-950">1.</span> Каналы связи</div>
            <div><span className="font-semibold text-slate-950">2.</span> Данные и интеграции</div>
            <div><span className="font-semibold text-slate-950">3.</span> Автоматизация</div>
          </div>
        }
      />

      <DashboardCompactMetricsRow
        items={[
          {
            label: 'Каналы связи',
            value: hasTelegramBot || hasWhatsappCredentials ? 'Подключаются' : 'Не настроены',
            hint: 'Telegram и WhatsApp управляются из одного экрана.',
            tone: hasTelegramBot || hasWhatsappCredentials ? 'positive' : 'warning',
          },
          {
            label: 'Интеграции',
            value: 'Внешние кабинеты',
            hint: 'Подключайте сервисы, которые усиливают работу карточки.',
          },
          {
            label: 'ИИ-агент',
            value: 'Раздел Агенты',
            hint: 'Тон, ограничения, сценарии и подтверждения собраны на странице агентов.',
          },
          {
            label: 'Сеть',
            value: hasNetwork ? 'Есть сеть' : 'Одна точка',
            hint: hasNetwork ? 'Можно управлять точками и материнским контуром.' : 'Сетевые настройки появятся при объединении точек.',
            tone: hasNetwork ? 'positive' : 'default',
          },
        ]}
      />

      <DashboardSection
        ref={channelsRef}
        title={t.dashboard.settings.messengers}
        className={channelsFocused ? 'scroll-mt-24 border-sky-300 ring-2 ring-sky-100' : 'scroll-mt-24'}
        description="Подключите каналы, через которые LocalOS будет общаться с клиентами и обрабатывать обращения."
      >
        {channelsFocused ? (
          <div className="mb-5 rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm leading-6 text-sky-900">
            <div>
              Для публикаций в Telegram заполните bot token и канал/чат для публикаций. После сохранения LocalOS обновит готовность каналов для контент-плана.
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button type="button" size="sm" asChild>
                <Link to="/dashboard/card?tab=news&mode=plan">Вернуться в контент-план</Link>
              </Button>
              <span className="text-xs font-medium text-sky-800">
                Следующий безопасный шаг: предпросмотр → подтверждение → расписание.
              </span>
            </div>
          </div>
        ) : null}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <TelegramConnection currentBusinessId={currentBusinessId} />
          <WhatsAppConnection currentBusinessId={currentBusinessId} business={currentBusiness} />
        </div>
        <div className="mt-5 grid grid-cols-1 gap-5 border-t border-slate-100 pt-5 lg:grid-cols-2">
          <WABACredentials businessId={currentBusinessId} business={currentBusiness} />
          <div
            ref={telegramPublishRef}
            data-testid="social-settings-telegram-publish-card"
            className={telegramPublishFocused ? 'scroll-mt-24 rounded-3xl ring-2 ring-sky-100' : 'scroll-mt-24'}
          >
            <TelegramBotCredentials
              businessId={currentBusinessId}
              business={currentBusiness}
              onSaved={() => setSocialReadinessRefreshKey((value) => value + 1)}
            />
          </div>
        </div>
      </DashboardSection>

      <DashboardSection
        ref={integrationsRef}
        title="Интеграции"
        className={integrationsFocused ? 'scroll-mt-24 border-sky-300 ring-2 ring-sky-100' : 'scroll-mt-24'}
        description={integrationsFocused
          ? 'Подключите внешние кабинеты, чтобы посты из контент-плана можно было ставить в расписание и публиковать по API после подтверждения.'
          : 'Внешние кабинеты и сервисы, которые помогают подтягивать данные и автоматизировать рутину.'}
      >
        {integrationsFocused ? (
          <div className="mb-5 rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm leading-6 text-sky-900">
            <div>
              Для публикаций подключите нужный внешний кабинет. Если вы пришли из контент-плана, LocalOS подсветит первый заблокированный канал: VK, Google Business Profile или Meta. Telegram-бот находится выше в разделе каналов связи; Яндекс/2ГИС остаются контролируемым или ручным размещением, если API недоступен.
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button type="button" size="sm" asChild>
                <Link to="/dashboard/card?tab=news&mode=plan">Вернуться в контент-план</Link>
              </Button>
              <span className="text-xs font-medium text-sky-800">
                После подключения проверьте готовность API-каналов без публикации.
              </span>
            </div>
          </div>
        ) : null}
        <div className="space-y-5">
          <ExternalIntegrations
            currentBusinessId={currentBusinessId}
            readinessRefreshKey={socialReadinessRefreshKey}
            focusedPlatform={focusTarget}
          />
          <FinanceCrmPanel currentBusinessId={currentBusinessId} surface="embedded" />
        </div>
      </DashboardSection>

      <DashboardSection
        title="ИИ-агент"
        description="Готовые и кастомные агенты теперь управляются из одного продуктового раздела."
      >
        <DashboardActionPanel
          title="ИИ-агенты теперь на странице “Агенты”"
          description="Там собраны агент для записи, маркетинговый агент, persona-настройки, кастомные workflow agents, подтверждения и история запусков."
          tone="sky"
          status={(
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
              <Bot className="h-4 w-4" />
              Единый центр управления
            </div>
          )}
          actions={(
            <Button type="button" asChild>
              <Link to="/dashboard/agents">Открыть агентов</Link>
            </Button>
          )}
        />
      </DashboardSection>

      <DashboardSection
        title="Управление сетью"
        description="Настройки материнской точки, структуры сети и правил работы между локациями."
      >
        <NetworkManagement />
      </DashboardSection>
    </div>
  );
};
