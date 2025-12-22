import { useOutletContext } from 'react-router-dom';
import TelegramConnection from '@/components/TelegramConnection';
import WhatsAppConnection from '@/components/WhatsAppConnection';
import { WABACredentials } from '@/components/WABACredentials';
import { TelegramBotCredentials } from '@/components/TelegramBotCredentials';
import { AIAgentSettings } from '@/components/AIAgentSettings';
import { NetworkManagement } from '@/components/NetworkManagement';
import { SubscriptionManagement } from '@/components/SubscriptionManagement';

export const SettingsPage = () => {
  const { user, currentBusinessId, currentBusiness } = useOutletContext<any>();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Настройки</h1>
        <p className="text-gray-600 mt-1">Управляйте настройками аккаунта и интеграциями</p>
      </div>

      <SubscriptionManagement businessId={currentBusinessId} business={currentBusiness} />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <TelegramConnection currentBusinessId={currentBusinessId} />
        <WhatsAppConnection currentBusinessId={currentBusinessId} business={currentBusiness} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <WABACredentials businessId={currentBusinessId} business={currentBusiness} />
        <TelegramBotCredentials businessId={currentBusinessId} business={currentBusiness} />
      </div>

      <AIAgentSettings businessId={currentBusinessId} business={currentBusiness} />

      <NetworkManagement />
    </div>
  );
};

