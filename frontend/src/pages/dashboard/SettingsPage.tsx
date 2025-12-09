import { useOutletContext } from 'react-router-dom';
import TelegramConnection from '@/components/TelegramConnection';
import { NetworkManagement } from '@/components/NetworkManagement';

export const SettingsPage = () => {
  const { user, currentBusinessId } = useOutletContext<any>();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Настройки</h1>
        <p className="text-gray-600 mt-1">Управляйте настройками аккаунта и интеграциями</p>
      </div>

      <NetworkManagement />

      <TelegramConnection currentBusinessId={currentBusinessId} />
    </div>
  );
};

