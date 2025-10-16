import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';

interface FinancialMetricsProps {
  onRefresh?: () => void;
}

interface MetricsData {
  period: {
    start_date: string;
    end_date: string;
    period_type: string;
  };
  metrics: {
    total_revenue: number;
    total_orders: number;
    average_check: number;
    new_clients: number;
    returning_clients: number;
    retention_rate: number;
  };
  growth: {
    revenue_growth: number;
    orders_growth: number;
  };
}

const FinancialMetrics: React.FC<FinancialMetricsProps> = ({ onRefresh }) => {
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState('month');

  const loadMetrics = async (selectedPeriod: string = period) => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`http://localhost:8000/api/finance/metrics?period=${selectedPeriod}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      const data = await response.json();

      if (data.success) {
        setMetrics(data);
      } else {
        setError(data.error || 'Ошибка загрузки метрик');
      }
    } catch (error) {
      setError('Ошибка соединения с сервером');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMetrics();
  }, []);

  const handlePeriodChange = (newPeriod: string) => {
    setPeriod(newPeriod);
    loadMetrics(newPeriod);
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  const formatPercentage = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
  };

  const getGrowthColor = (value: number) => {
    if (value > 0) return 'text-green-600';
    if (value < 0) return 'text-red-600';
    return 'text-gray-600';
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-20 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="text-center">
          <div className="text-red-600 mb-4">❌ {error}</div>
          <Button onClick={() => loadMetrics()} variant="outline">
            Попробовать снова
          </Button>
        </div>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="text-center text-gray-500">
          <p>Нет данных для отображения</p>
          <Button onClick={() => loadMetrics()} variant="outline" className="mt-2">
            Обновить
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-lg font-semibold text-gray-900">📊 Финансовые метрики</h3>
        <div className="flex gap-2">
          <Select value={period} onValueChange={handlePeriodChange}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="week">Неделя</SelectItem>
              <SelectItem value="month">Месяц</SelectItem>
              <SelectItem value="quarter">Квартал</SelectItem>
              <SelectItem value="year">Год</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={() => loadMetrics()} variant="outline" size="sm">
            🔄
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-blue-50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-blue-600 font-medium">Общая выручка</p>
              <p className="text-2xl font-bold text-blue-900">
                {formatCurrency(metrics.metrics.total_revenue)}
              </p>
              <p className={`text-sm ${getGrowthColor(metrics.growth.revenue_growth)}`}>
                {formatPercentage(metrics.growth.revenue_growth)} к прошлому периоду
              </p>
            </div>
            <div className="text-3xl">💰</div>
          </div>
        </div>

        <div className="bg-green-50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-green-600 font-medium">Заказов</p>
              <p className="text-2xl font-bold text-green-900">
                {metrics.metrics.total_orders}
              </p>
              <p className={`text-sm ${getGrowthColor(metrics.growth.orders_growth)}`}>
                {formatPercentage(metrics.growth.orders_growth)} к прошлому периоду
              </p>
            </div>
            <div className="text-3xl">📦</div>
          </div>
        </div>

        <div className="bg-purple-50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-purple-600 font-medium">Средний чек</p>
              <p className="text-2xl font-bold text-purple-900">
                {formatCurrency(metrics.metrics.average_check)}
              </p>
            </div>
            <div className="text-3xl">💳</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-orange-50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-orange-600 font-medium">Новых клиентов</p>
              <p className="text-xl font-bold text-orange-900">
                {metrics.metrics.new_clients}
              </p>
            </div>
            <div className="text-2xl">🆕</div>
          </div>
        </div>

        <div className="bg-indigo-50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-indigo-600 font-medium">Повторных клиентов</p>
              <p className="text-xl font-bold text-indigo-900">
                {metrics.metrics.returning_clients}
              </p>
            </div>
            <div className="text-2xl">🔄</div>
          </div>
        </div>

        <div className="bg-pink-50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-pink-600 font-medium">Удержание клиентов</p>
              <p className="text-xl font-bold text-pink-900">
                {metrics.metrics.retention_rate.toFixed(1)}%
              </p>
            </div>
            <div className="text-2xl">❤️</div>
          </div>
        </div>
      </div>

      <div className="mt-4 text-sm text-gray-500 text-center">
        Период: {metrics.period.start_date} — {metrics.period.end_date}
      </div>
    </div>
  );
};

export default FinancialMetrics;
