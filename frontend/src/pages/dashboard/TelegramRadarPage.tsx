import { Link, useOutletContext } from 'react-router-dom';
import { Radar } from 'lucide-react';

import { TelegramOpportunityRadar } from '@/components/TelegramOpportunityRadar';
import { Button } from '@/components/ui/button';
import { DashboardActionPanel, DashboardPageHeader } from '@/components/dashboard/DashboardPrimitives';

export const TelegramRadarPage = () => {
  const { currentBusinessId } = useOutletContext<{ currentBusinessId?: string | null }>();

  return (
    <div className="mx-auto max-w-6xl space-y-7 pb-10">
      <DashboardPageHeader
        eyebrow="Telegram"
        title="Радар возможностей"
        description="Рабочий inbox сообщений из выбранных чатов: где ответить экспертно, что сохранить как идею и что закрыть как неважное."
        icon={Radar}
        actions={(
          <Button type="button" variant="outline" asChild>
            <Link to="/dashboard/settings?focus=telegram">Настроить источники</Link>
          </Button>
        )}
      />

      <DashboardActionPanel
        title="Отвечайте только вручную"
        description="OpenClaw читает выбранные чаты и подсвечивает сигналы. LocalOS не пишет в чужие чаты автоматически: вы сами решаете, где ответить, а где сохранить тему для контента."
        tone="sky"
      />

      <TelegramOpportunityRadar businessId={currentBusinessId || null} mode="work" />
    </div>
  );
};
