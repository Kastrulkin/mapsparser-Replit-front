import { useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { Cable, ChevronDown, Wallet } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import FinanceFirstStep from '@/components/FinanceFirstStep';
import FinanceImportPanel from '@/components/FinanceImportPanel';
import FinanceThresholdsPanel from '@/components/FinanceThresholdsPanel';
import FinancialMetrics from '@/components/FinancialMetrics';
import ROICalculator from '@/components/ROICalculator';
import TransactionTable from '@/components/TransactionTable';
import {
  DashboardPageHeader,
  DashboardSection,
} from '@/components/dashboard/DashboardPrimitives';
import { cn } from '@/lib/utils';

export const FinancePage = () => {
  const { currentBusinessId } = useOutletContext<{ currentBusinessId?: string | null }>();
  const [showSetupTools, setShowSetupTools] = useState(false);
  const [showLegacyTools, setShowLegacyTools] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-10">
      <DashboardPageHeader
        eyebrow="LocalOS"
        title="Финансы: первый шаг к прибыльному бизнесу"
        description="Короткий управленческий обзор: что уже видно по деньгам, где не хватает данных и какое действие сделать следующим."
        icon={Wallet}
      />

      <FinanceFirstStep key={`finance-first-step-${currentBusinessId || 'none'}-${refreshKey}`} currentBusinessId={currentBusinessId} />

      <Collapsible open={showSetupTools} onOpenChange={setShowSetupTools}>
        <DashboardSection
          title="Подключение и настройки данных"
          description="Импорт, CRM и нормы KPI убраны ниже, чтобы первый экран оставался управленческим обзором."
          actions={
            <CollapsibleTrigger asChild>
              <Button variant="outline" className="gap-2">
                {showSetupTools ? 'Скрыть' : 'Открыть'}
                <ChevronDown className={cn('h-4 w-4 transition-transform', showSetupTools ? 'rotate-180' : '')} />
              </Button>
            </CollapsibleTrigger>
          }
        >
          <CollapsibleContent className="space-y-6">
            <FinanceThresholdsPanel currentBusinessId={currentBusinessId} onChanged={() => setRefreshKey((k) => k + 1)} />
            <FinanceImportPanel currentBusinessId={currentBusinessId} onImported={() => setRefreshKey((k) => k + 1)} />

            <DashboardSection
              title="Данные можно подтягивать из CRM"
              description="Подключите YCLIENTS или Altegio в настройках, чтобы LocalOS автоматически получал записи, оплаты, услуги, мастеров и рабочие места для финансовой аналитики."
              actions={
                <Button asChild variant="outline" className="gap-2">
                  <Link to="/dashboard/settings">
                    <Cable className="h-4 w-4" />
                    Открыть настройки
                  </Link>
                </Button>
              }
            >
              <div className="grid gap-3 text-sm text-slate-700 md:grid-cols-3">
                <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                  <div className="font-semibold text-slate-950">Записи и оплаты</div>
                  <div className="mt-1 leading-6">Для выручки, среднего чека, отмен и повторных клиентов.</div>
                </div>
                <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                  <div className="font-semibold text-slate-950">Услуги и мастера</div>
                  <div className="mt-1 leading-6">Чтобы понимать, что продвигать и где проседает эффективность.</div>
                </div>
                <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                  <div className="font-semibold text-slate-950">Кресла и кабинеты</div>
                  <div className="mt-1 leading-6">Для загрузки, простоя и выручки на рабочее место.</div>
                </div>
              </div>
            </DashboardSection>
          </CollapsibleContent>
        </DashboardSection>
      </Collapsible>

      <Collapsible open={showLegacyTools} onOpenChange={setShowLegacyTools}>
        <DashboardSection
          title="Старые финансовые инструменты"
          description="Журнал операций, прежние метрики и ROI оставлены ниже как справочные инструменты, но основной сценарий теперь находится выше."
          actions={
            <CollapsibleTrigger asChild>
              <Button variant="outline" className="gap-2">
                {showLegacyTools ? 'Скрыть' : 'Показать'}
                <ChevronDown className={cn('h-4 w-4 transition-transform', showLegacyTools ? 'rotate-180' : '')} />
              </Button>
            </CollapsibleTrigger>
          }
        >
          <CollapsibleContent className="space-y-6">
            <FinancialMetrics currentBusinessId={currentBusinessId} />
            <ROICalculator />
            <DashboardSection
              title="Журнал операций"
              description="Все транзакции по текущему бизнесу в одном месте."
            >
              <TransactionTable currentBusinessId={currentBusinessId} refreshKey={refreshKey} />
            </DashboardSection>
          </CollapsibleContent>
        </DashboardSection>
      </Collapsible>
    </div>
  );
};
