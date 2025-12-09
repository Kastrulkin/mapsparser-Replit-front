import { useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import FinancialMetrics from '@/components/FinancialMetrics';
import ROICalculator from '@/components/ROICalculator';
import TransactionForm from '@/components/TransactionForm';
import TransactionTable from '@/components/TransactionTable';

export const FinancePage = () => {
  const { user, currentBusinessId } = useOutletContext<any>();
  const [showTransactionForm, setShowTransactionForm] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Финансы</h1>
          <p className="text-gray-600 mt-1">Управляйте финансовыми показателями и транзакциями</p>
        </div>
        <Button 
          onClick={() => setShowTransactionForm(!showTransactionForm)}
          className="bg-green-600 hover:bg-green-700"
        >
          {showTransactionForm ? 'Скрыть форму' : '+ Добавить транзакцию'}
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
            setSuccess('Транзакция добавлена успешно!');
            setTimeout(() => setSuccess(null), 3000);
            setRefreshKey((k) => k + 1);
          }}
          onCancel={() => setShowTransactionForm(false)}
        />
      )}

      <FinancialMetrics />
      <ROICalculator />
      <div className="flex justify-end mb-2">
        <Button 
          onClick={() => setShowTransactionForm(true)}
          className="bg-green-600 hover:bg-green-700"
        >
          + Добавить транзакцию
        </Button>
      </div>
      <TransactionTable currentBusinessId={currentBusinessId} refreshKey={refreshKey} />
    </div>
  );
};

