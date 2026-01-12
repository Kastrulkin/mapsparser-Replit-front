import { useOutletContext } from 'react-router-dom';
import { useLanguage } from '@/i18n/LanguageContext';
import TelegramConnection from '@/components/TelegramConnection';
import WhatsAppConnection from '@/components/WhatsAppConnection';
import { WABACredentials } from '@/components/WABACredentials';
import { TelegramBotCredentials } from '@/components/TelegramBotCredentials';
import { AIAgentSettings } from '@/components/AIAgentSettings';
import { NetworkManagement } from '@/components/NetworkManagement';
import { SubscriptionManagement } from '@/components/SubscriptionManagement';
import { ExternalIntegrations } from '@/components/ExternalIntegrations';

export const SettingsPage = () => {
  const { user, currentBusinessId, currentBusiness } = useOutletContext<any>();

  const { t } = useLanguage();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t.dashboard.settings.title}</h1>
        <p className="text-gray-600 mt-1">{t.dashboard.settings.subtitle}</p>
      </div>

      {/* Блок 1: Текущая подписка и доступные тарифы */}
      <div className="bg-white rounded-lg border-2 border-primary p-6 shadow-lg" style={{
        boxShadow: '0 4px 6px -1px rgba(251, 146, 60, 0.3), 0 2px 4px -1px rgba(251, 146, 60, 0.2)'
      }}>
        <SubscriptionManagement businessId={currentBusinessId} business={currentBusiness} />
      </div>

      {/* Блок 2: Подключения к Telegram и WhatsApp */}
      <div className="bg-white rounded-lg border-2 border-primary p-6 shadow-lg" style={{
        boxShadow: '0 4px 6px -1px rgba(251, 146, 60, 0.3), 0 2px 4px -1px rgba(251, 146, 60, 0.2)'
      }}>
        <h2 className="text-xl font-bold text-gray-900 mb-4">{t.dashboard.settings.messengers}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <TelegramConnection currentBusinessId={currentBusinessId} />
          <WhatsAppConnection currentBusinessId={currentBusinessId} business={currentBusiness} />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
          <WABACredentials businessId={currentBusinessId} business={currentBusiness} />
          <TelegramBotCredentials businessId={currentBusinessId} business={currentBusiness} />
        </div>
      </div>

      {/* Блок 3: Интеграции с внешними источниками */}
      <div className="bg-white rounded-lg border-2 border-primary p-6 shadow-lg" style={{
        boxShadow: '0 4px 6px -1px rgba(251, 146, 60, 0.3), 0 2px 4px -1px rgba(251, 146, 60, 0.2)'
      }}>
        <ExternalIntegrations currentBusinessId={currentBusinessId} />
      </div>

      {/* Блок 4: Настройки ИИ агента */}
      <div className="bg-white rounded-lg border-2 border-primary p-6 shadow-lg" style={{
        boxShadow: '0 4px 6px -1px rgba(251, 146, 60, 0.3), 0 2px 4px -1px rgba(251, 146, 60, 0.2)'
      }}>
        <AIAgentSettings businessId={currentBusinessId} business={currentBusiness} />
      </div>

      {/* Блок 5: Управление сетью */}
      <div className="bg-white rounded-lg border-2 border-primary p-6 shadow-lg" style={{
        boxShadow: '0 4px 6px -1px rgba(251, 146, 60, 0.3), 0 2px 4px -1px rgba(251, 146, 60, 0.2)'
      }}>
        <NetworkManagement />
      </div>
    </div>
  );
};

