import { Link, useOutletContext } from 'react-router-dom';
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
  waba_phone_id?: string | null;
  waba_access_token?: string | null;
};

export const SettingsPage = () => {
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
        title={t.dashboard.settings.messengers}
        description="Подключите каналы, через которые LocalOS будет общаться с клиентами и обрабатывать обращения."
      >
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <TelegramConnection currentBusinessId={currentBusinessId} />
          <WhatsAppConnection currentBusinessId={currentBusinessId} business={currentBusiness} />
        </div>
        <div className="mt-5 grid grid-cols-1 gap-5 border-t border-slate-100 pt-5 lg:grid-cols-2">
          <WABACredentials businessId={currentBusinessId} business={currentBusiness} />
          <TelegramBotCredentials businessId={currentBusinessId} business={currentBusiness} />
        </div>
      </DashboardSection>

      <DashboardSection
        title="Интеграции"
        description="Внешние кабинеты и сервисы, которые помогают подтягивать данные и автоматизировать рутину."
      >
        <div className="space-y-5">
          <ExternalIntegrations currentBusinessId={currentBusinessId} />
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
