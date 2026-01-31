import { useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import FinancialMetrics from '@/components/FinancialMetrics';
import ROICalculator from '@/components/ROICalculator';
import TransactionForm from '@/components/TransactionForm';
import TransactionTable from '@/components/TransactionTable';
import { useLanguage } from '@/i18n/LanguageContext';

export const FinancePage = () => {
  const { user, currentBusinessId } = useOutletContext<any>();
  const [showTransactionForm, setShowTransactionForm] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const { t } = useLanguage();

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t.dashboard.finance.title}</h1>
          <p className="text-gray-600 mt-1">{t.dashboard.finance.subtitle}</p>
        </div>
        <Button
          onClick={() => setShowTransactionForm(!showTransactionForm)}
          className="bg-green-600 hover:bg-green-700"
        >
          {showTransactionForm ? t.dashboard.finance.hideForm : `+ ${t.dashboard.finance.addTransaction}`}
        </Button>
      </div>

      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">
          {success}
        </div>
      )}

      {showTransactionForm && (
        <TransactionForm
          onSuccess={() => {
            setShowTransactionForm(false);
            setSuccess(t.dashboard.finance.successAdded);
            setTimeout(() => setSuccess(null), 3000);
            setRefreshKey((k) => k + 1);
          }}
          onCancel={() => setShowTransactionForm(false)}
        />
      )}

      <FinancialMetrics currentBusinessId={currentBusinessId} />
      <ROICalculator />
      <div className="flex justify-end mb-2">
        <Button
          onClick={() => setShowTransactionForm(true)}
          className="bg-green-600 hover:bg-green-700"
        >
          {`+ ${t.dashboard.finance.addTransaction}`}
        </Button>
      </div>
      <TransactionTable currentBusinessId={currentBusinessId} refreshKey={refreshKey} />
    </div>
  );
};

