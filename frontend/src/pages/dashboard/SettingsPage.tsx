import { useOutletContext } from 'react-router-dom';
import { useLanguage } from '@/i18n/LanguageContext';
import TelegramConnection from '@/components/TelegramConnection';
import WhatsAppConnection from '@/components/WhatsAppConnection';
import { WABACredentials } from '@/components/WABACredentials';
import { TelegramBotCredentials } from '@/components/TelegramBotCredentials';
import { AIAgentSettings } from '@/components/AIAgentSettings';
import { NetworkManagement } from '@/components/NetworkManagement';
import { ExternalIntegrations } from '@/components/ExternalIntegrations';
import { Settings } from 'lucide-react';
import {
  DashboardActionPanel,
  DashboardCompactMetricsRow,
  DashboardPageHeader,
  DashboardSection,
} from '@/components/dashboard/DashboardPrimitives';

export const SettingsPage = () => {
  const { currentBusinessId, currentBusiness } = useOutletContext<any>();
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
            value: 'Настройки поведения',
            hint: 'Тон, ограничения и сценарии работы собраны в одном блоке.',
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
        <ExternalIntegrations currentBusinessId={currentBusinessId} />
      </DashboardSection>

      <DashboardSection
        title="ИИ-агент"
        description="Определите, как агент отвечает, какие задачи берёт на себя и где должен оставаться ручной контроль."
        contentClassName="p-0"
      >
        <AIAgentSettings businessId={currentBusinessId} business={currentBusiness} />
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
