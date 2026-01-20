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
import { cn } from '@/lib/utils';
import { DESIGN_TOKENS } from '@/lib/design-tokens';
import { Settings, Sparkles, MessageSquare, Share2, Network } from 'lucide-react';

export const SettingsPage = () => {
  const { user, currentBusinessId, currentBusiness } = useOutletContext<any>();
  const { t } = useLanguage();

  const SectionHeader = ({ icon: Icon, title }: { icon: any, title: string }) => (
    <div className="flex items-center gap-2 mb-6 border-b border-gray-100/50 pb-4">
      <div className="p-2 rounded-lg bg-primary/10 text-primary">
        <Icon className="w-5 h-5" />
      </div>
      <h2 className="text-xl font-bold text-gray-900 tracking-tight">{title}</h2>
    </div>
  );

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-10">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold text-gray-900 tracking-tight flex items-center gap-3">
          <Settings className="w-8 h-8 text-primary" />
          {t.dashboard.settings.title}
        </h1>
        <p className="text-gray-500 text-lg ml-11">{t.dashboard.settings.subtitle}</p>
      </div>

      {/* Блок 1: Текущая подписка */}
      <div className={cn(DESIGN_TOKENS.glass.default, "rounded-2xl p-8 hover:shadow-2xl transition-all duration-500")}>
        <SectionHeader icon={Sparkles} title={t.dashboard.subscription.manage} />
        <SubscriptionManagement businessId={currentBusinessId} business={currentBusiness} />
      </div>

      {/* Блок 2: Мессенджеры */}
      <div className={cn(DESIGN_TOKENS.glass.default, "rounded-2xl p-8 hover:shadow-2xl transition-all duration-500")}>
        <SectionHeader icon={MessageSquare} title={t.dashboard.settings.messengers} />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <TelegramConnection currentBusinessId={currentBusinessId} />
          <WhatsAppConnection currentBusinessId={currentBusinessId} business={currentBusiness} />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-8 pt-8 border-t border-gray-100/50">
          <WABACredentials businessId={currentBusinessId} business={currentBusiness} />
          <TelegramBotCredentials businessId={currentBusinessId} business={currentBusiness} />
        </div>
      </div>

      {/* Блок 3: Интеграции */}
      <div className={cn(DESIGN_TOKENS.glass.default, "rounded-2xl p-8 hover:shadow-2xl transition-all duration-500")}>
        <SectionHeader icon={Share2} title="Integrations" />
        <ExternalIntegrations currentBusinessId={currentBusinessId} />
      </div>

      {/* Блок 4: AI Agent */}
      <div className="relative group">
        <div className="absolute -inset-1 bg-gradient-to-r from-purple-600 to-indigo-600 rounded-2xl blur opacity-20 group-hover:opacity-40 transition duration-1000"></div>
        <div className={cn(DESIGN_TOKENS.glass.default, "relative rounded-2xl p-1")}>
          <AIAgentSettings businessId={currentBusinessId} business={currentBusiness} />
        </div>
      </div>

      {/* Блок 5: Управление сетью */}
      <div className={cn(DESIGN_TOKENS.glass.default, "rounded-2xl p-8 hover:shadow-2xl transition-all duration-500")}>
        <SectionHeader icon={Network} title="Network Management" />
        <NetworkManagement />
      </div>
    </div>
  );
};

