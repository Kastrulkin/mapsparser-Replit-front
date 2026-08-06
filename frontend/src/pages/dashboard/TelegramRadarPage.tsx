import { Link, useOutletContext } from 'react-router-dom';
import { Radar } from 'lucide-react';

import { TelegramOpportunityRadar } from '@/components/TelegramOpportunityRadar';
import { TelegramResearchSetup } from '@/components/TelegramResearchSetup';
import { Button } from '@/components/ui/button';
import { DashboardActionPanel, DashboardPageHeader } from '@/components/dashboard/DashboardPrimitives';
import { useLanguage } from '@/i18n/LanguageContext';
import { getDemoWorkspaceCopy } from '@/i18n/demoWorkspaceCopy';

export const TelegramRadarPage = () => {
  const { currentBusinessId, demoMode } = useOutletContext<{ currentBusinessId?: string | null; demoMode?: boolean }>();
  const { language } = useLanguage();
  const copy = getDemoWorkspaceCopy(language).telegram;

  return (
    <div className="mx-auto max-w-6xl space-y-7 pb-10">
      <DashboardPageHeader
        eyebrow="Telegram"
        title={copy.pageTitle}
        description={copy.pageDescription}
        icon={Radar}
        actions={(
          <Button type="button" variant="outline" asChild>
            <Link to="/dashboard/settings?focus=telegram">{copy.connect}</Link>
          </Button>
        )}
      />

      <DashboardActionPanel
        title={copy.manualTitle}
        description={copy.manualDescription}
        tone="sky"
      />

      <TelegramResearchSetup businessId={currentBusinessId || null} mode="sources" demoMode={demoMode} />
      <TelegramOpportunityRadar businessId={currentBusinessId || null} mode="work" demoMode={demoMode} />
    </div>
  );
};
