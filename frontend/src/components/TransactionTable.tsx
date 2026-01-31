import React, { useEffect, useState } from 'react';
import { useLanguage } from '@/i18n/LanguageContext';
import { Button } from './ui/button';
import { Input } from './ui/input';

interface Transaction {
  id: string;
  business_id?: string | null;
  transaction_date?: string | null;
  amount: number;
  client_type?: string | null;
  services?: string[] | null;
  notes?: string | null;
}

interface TransactionTableProps {
  currentBusinessId?: string | null;
  refreshKey?: number;
}

const TransactionTable: React.FC<TransactionTableProps> = ({ currentBusinessId, refreshKey = 0 }) => {
  const { language, t } = useLanguage();
  const [rows, setRows] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<{ transaction_date: string; amount: string; services: string; notes: string }>({
    transaction_date: '',
    amount: '',
    services: '',
    notes: '',
  });

  const loadTransactions = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem('auth_token');
      const url = new URL(`${window.location.origin}/api/finance/transactions`);
      url.searchParams.set('limit', '100');
      if (currentBusinessId) {
        url.searchParams.set('business_id', currentBusinessId);
      }

      const res = await fetch(url.toString(), {
        headers: {
          Authorization: `Bearer ${token || ''}`,
        },
      });

      const data = await res.json();
      if (res.ok && data.success) {
        setRows(data.transactions || []);
      } else {
        setError(data.error || t.dashboard.finance.transactions.loadError);
      }
    } catch (e) {
      setError(t.common.error);
    } finally {
      setLoading(false);
    }
  };

  const startEdit = (row: Transaction) => {
    setEditingId(row.id);
    setForm({
      transaction_date: row.transaction_date || '',
      amount: String(row.amount || ''),
      services: row.services && Array.isArray(row.services) ? row.services.join(', ') : '',
      notes: row.notes || '',
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
  };

  const saveEdit = async () => {
    if (!editingId) return;
    try {
      setLoading(true);
      const token = localStorage.getItem('auth_token');
      const body: any = {
        transaction_date: form.transaction_date || null,
        amount: parseFloat(form.amount || '0') || 0,
        services: form.services
          ? form.services
            .split(',')
            .map((s) => s.trim())
            .filter(Boolean)
          : [],
        notes: form.notes || '',
      };
      const res = await fetch(`${window.location.origin}/api/finance/transaction/${editingId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token || ''}`,
        },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        setError(data.error || t.common.error);
      } else {
        setEditingId(null);
        await loadTransactions();
      }
    } catch (e) {
      setError(t.common.error);
    } finally {
      setLoading(false);
    }
  };

  const deleteRow = async (id: string) => {
    if (!window.confirm(t.dashboard.finance.transactions.deleteConfirm)) return;
    try {
      setLoading(true);
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/finance/transaction/${id}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token || ''}`,
        },
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        setError(data.error || t.common.error);
      } else {
        await loadTransactions();
      }
    } catch (e) {
      setError(t.common.error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTransactions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentBusinessId, refreshKey]);

  const formatDate = (value?: string | null) => {
    if (!value) return '—';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleDateString(language === 'ru' ? 'ru-RU' : 'en-US');
  };

  const formatMoney = (value: number) =>
    new Intl.NumberFormat(language === 'ru' ? 'ru-RU' : 'en-US', { style: 'currency', currency: 'RUB', minimumFractionDigits: 0 }).format(
      value || 0,
    );

  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-gray-900">{t.dashboard.finance.transactions.title}</h3>
        <div className="text-sm text-gray-500">{t.dashboard.finance.transactions.shownLimit}</div>
      </div>

      {loading && <div className="text-gray-500">{t.dashboard.finance.transactions.loading}</div>}
      {error && <div className="text-red-600 text-sm mb-2">{error}</div>}

      {!loading && !error && rows.length === 0 && (
        <div className="text-gray-500 text-sm">{t.dashboard.finance.transactions.empty}</div>
      )}

      {!loading && !error && rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="min-w-full border border-gray-200 text-sm">
            <thead className="bg-gray-50 text-gray-700">
              <tr>
                <th className="px-3 py-2 border-b text-left">{t.dashboard.finance.transactions.date}</th>
                <th className="px-3 py-2 border-b text-left">{t.dashboard.finance.transactions.name}</th>
                <th className="px-3 py-2 border-b text-right">{t.dashboard.finance.transactions.price}</th>
                <th className="px-3 py-2 border-b text-right">{t.dashboard.finance.transactions.qty}</th>
                <th className="px-3 py-2 border-b text-right">{t.dashboard.finance.transactions.cost}</th>
                <th className="px-3 py-2 border-b text-right">{t.dashboard.finance.transactions.actions}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const name =
                  row.services && Array.isArray(row.services) && row.services.length > 0
                    ? row.services.join(', ')
                    : row.notes || '—';
                const amount = row.amount || 0;
                const quantity = 1;
                const cost = amount * quantity;
                const isEditing = editingId === row.id;
                return (
                  <tr key={row.id} className="hover:bg-gray-50">
                    <td className="px-3 py-2 border-b">
                      {isEditing ? (
                        <Input
                          type="date"
                          value={form.transaction_date}
                          onChange={(e) => setForm({ ...form, transaction_date: e.target.value })}
                        />
                      ) : (
                        formatDate(row.transaction_date)
                      )}
                    </td>
                    <td className="px-3 py-2 border-b">
                      {isEditing ? (
                        <Input
                          value={form.services}
                          onChange={(e) => setForm({ ...form, services: e.target.value })}
                          placeholder={t.dashboard.finance.transactions.servicesPlaceholder}
                        />
                      ) : (
                        name
                      )}
                    </td>
                    <td className="px-3 py-2 border-b text-right">
                      {isEditing ? (
                        <Input
                          type="number"
                          value={form.amount}
                          onChange={(e) => setForm({ ...form, amount: e.target.value })}
                        />
                      ) : (
                        formatMoney(amount)
                      )}
                    </td>
                    <td className="px-3 py-2 border-b text-right">{quantity}</td>
                    <td className="px-3 py-2 border-b text-right font-medium">{formatMoney(cost)}</td>
                    <td className="px-3 py-2 border-b text-right space-x-2">
                      {isEditing ? (
                        <>
                          <Button size="sm" onClick={saveEdit}>
                            {t.common.save}
                          </Button>
                          <Button size="sm" variant="outline" onClick={cancelEdit}>
                            {t.common.cancel}
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button size="sm" variant="outline" onClick={() => startEdit(row)}>
                            {t.dashboard.finance.transactions.edit}
                          </Button>
                          <Button size="sm" variant="destructive" onClick={() => deleteRow(row.id)}>
                            {t.dashboard.finance.transactions.delete}
                          </Button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default TransactionTable;

