import { useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { ChevronDown, Plus, Wallet } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import FinanceFirstStep from '@/components/FinanceFirstStep';
import FinanceCrmPanel from '@/components/FinanceCrmPanel';
import FinanceImportPanel from '@/components/FinanceImportPanel';
import FinanceThresholdsPanel from '@/components/FinanceThresholdsPanel';
import FinancialMetrics from '@/components/FinancialMetrics';
import ROICalculator from '@/components/ROICalculator';
import TransactionForm from '@/components/TransactionForm';
import TransactionTable from '@/components/TransactionTable';
import { useLanguage } from '@/i18n/LanguageContext';
import {
  DashboardActionPanel,
  DashboardPageHeader,
  DashboardSection,
} from '@/components/dashboard/DashboardPrimitives';
import { cn } from '@/lib/utils';

export const FinancePage = () => {
  const { currentBusinessId } = useOutletContext<{ currentBusinessId?: string | null }>();
  const [showTransactionForm, setShowTransactionForm] = useState(false);
  const [showLegacyTools, setShowLegacyTools] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const { t } = useLanguage();

  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-10">
      <DashboardPageHeader
        eyebrow="LocalOS"
        title="Финансы: первый шаг к прибыльному бизнесу"
        description="Соберите базовую картину за 3 месяца: плюс или минус, точка безубыточности, дневная цель, загрузка мастеров, кресла и выручка на кресло-час."
        icon={Wallet}
        actions={
          <Button onClick={() => setShowTransactionForm((prev) => !prev)} className="gap-2">
            <Plus className="h-4 w-4" />
            {showTransactionForm ? t.dashboard.finance.hideForm : t.dashboard.finance.addTransaction}
          </Button>
        }
      />

      <DashboardActionPanel
        title="48 часов до первой финансовой картины"
        description="Начните не с красивого графика, а с управленческого мини-учёта: сколько заработали, сколько съели расходы, какие услуги и рабочие места реально дают деньги."
        status={success ? <span className="font-medium text-emerald-700">{success}</span> : 'Главный экран ниже уже считает P&L, маржу, красные зоны, рабочие места и качество данных.'}
        tone={success ? 'sky' : 'default'}
        actions={
          <Button onClick={() => setShowTransactionForm((prev) => !prev)} className="gap-2">
            <Plus className="h-4 w-4" />
            {showTransactionForm ? t.dashboard.finance.hideForm : t.dashboard.finance.addTransaction}
          </Button>
        }
      />

      {showTransactionForm ? (
        <DashboardSection title={t.dashboard.finance.addTransaction} description="Добавьте операцию один раз, и таблица с метриками обновится автоматически.">
          <TransactionForm
            onSuccess={() => {
              setShowTransactionForm(false);
              setSuccess(t.dashboard.finance.successAdded);
              setTimeout(() => setSuccess(null), 3000);
              setRefreshKey((k) => k + 1);
            }}
            onCancel={() => setShowTransactionForm(false)}
          />
        </DashboardSection>
      ) : null}

      <FinanceFirstStep key={`finance-first-step-${currentBusinessId || 'none'}-${refreshKey}`} currentBusinessId={currentBusinessId} />
      <FinanceThresholdsPanel currentBusinessId={currentBusinessId} onChanged={() => setRefreshKey((k) => k + 1)} />
      <FinanceImportPanel currentBusinessId={currentBusinessId} onImported={() => setRefreshKey((k) => k + 1)} />
      <FinanceCrmPanel currentBusinessId={currentBusinessId} onSynced={() => setRefreshKey((k) => k + 1)} />

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
