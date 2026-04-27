import { useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Plus, Wallet } from 'lucide-react';

import { Button } from '@/components/ui/button';
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

export const FinancePage = () => {
  const { currentBusinessId } = useOutletContext<any>();
  const [showTransactionForm, setShowTransactionForm] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const { t } = useLanguage();

  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-10">
      <DashboardPageHeader
        eyebrow="LocalOS"
        title={t.dashboard.finance.title}
        description={t.dashboard.finance.subtitle}
        icon={Wallet}
        actions={
          <Button onClick={() => setShowTransactionForm((prev) => !prev)} className="gap-2">
            <Plus className="h-4 w-4" />
            {showTransactionForm ? t.dashboard.finance.hideForm : t.dashboard.finance.addTransaction}
          </Button>
        }
      />

      <DashboardActionPanel
        title="Следующий шаг"
        description="Добавьте новую транзакцию, если хотите обновить аналитику доходов и ROI. Остальные блоки автоматически подтянут актуальные расчёты."
        status={success ? <span className="font-medium text-emerald-700">{success}</span> : 'Финансовый экран собран вокруг операций, метрик и ROI без лишних промежуточных действий.'}
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

      <FinancialMetrics currentBusinessId={currentBusinessId} />
      <ROICalculator />

      <DashboardSection
        title="Журнал операций"
        description="Все транзакции по текущему бизнесу в одном месте."
      >
        <TransactionTable currentBusinessId={currentBusinessId} refreshKey={refreshKey} />
      </DashboardSection>
    </div>
  );
};
