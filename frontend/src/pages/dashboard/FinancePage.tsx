import { Link, useOutletContext } from 'react-router-dom';
import { Cable, Wallet } from 'lucide-react';

import { Button } from '@/components/ui/button';
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

export const FinancePage = () => {
  const { currentBusinessId } = useOutletContext<{ currentBusinessId?: string | null }>();

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-10">
      <DashboardPageHeader
        eyebrow="LocalOS"
        title="Финансы"
        description="Короткий обзор денег, загрузки и ближайшего управленческого шага."
        icon={Wallet}
      />

      <FinanceFirstStep
        currentBusinessId={currentBusinessId}
        setupTools={(
          <div className="space-y-6">
            <FinanceThresholdsPanel currentBusinessId={currentBusinessId} />
            <FinanceImportPanel currentBusinessId={currentBusinessId} />
            <DashboardSection
              title="CRM-подключения"
              description="YCLIENTS и Altegio подключаются в настройках. После синхронизации данные попадут в тот же финансовый обзор."
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
                <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">Записи и оплаты</div>
                <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">Услуги и мастера</div>
                <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">Кресла и кабинеты</div>
              </div>
            </DashboardSection>
          </div>
        )}
        legacyTools={(
          <div className="space-y-6">
            <FinancialMetrics currentBusinessId={currentBusinessId} />
            <ROICalculator />
            <DashboardSection
              title="Журнал операций"
              description="Все транзакции по текущему бизнесу в одном месте."
            >
              <TransactionTable currentBusinessId={currentBusinessId} />
            </DashboardSection>
          </div>
        )}
      />
    </div>
  );
};
