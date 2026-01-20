import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { useLanguage } from '@/i18n/LanguageContext';
import {
  DollarSign,
  Package,
  CreditCard,
  ArrowUpRight,
  ArrowDownRight,
  RefreshCw,
  Users,
  Repeat,
  Heart,
  TrendingUp,
  PieChart as PieChartIcon,
  Wallet
} from 'lucide-react';
import { cn } from '../lib/utils';
import { DESIGN_TOKENS } from '../lib/design-tokens';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';

interface FinancialMetricsProps {
  onRefresh?: () => void;
  currentBusinessId?: string | null;
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

interface BreakdownData {
  period: {
    start_date: string;
    end_date: string;
    period_type: string;
  };
  by_services: Array<{ name: string; value: number }>;
  by_masters: Array<{ name: string; value: number }>;
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#6366f1', '#14b8a6', '#f97316', '#a855f7'];

const FinancialMetrics: React.FC<FinancialMetricsProps> = ({ onRefresh, currentBusinessId }) => {
  const { t } = useLanguage();
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [breakdown, setBreakdown] = useState<BreakdownData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState('month');

  const loadMetrics = async (selectedPeriod: string = period) => {
    if (!currentBusinessId) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const baseUrl = window.location.origin;
      const businessParam = currentBusinessId ? `&business_id=${currentBusinessId}` : '';

      // Загружаем метрики
      const metricsResponse = await fetch(`${baseUrl}/api/finance/metrics?period=${selectedPeriod}${businessParam}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      const metricsData = await metricsResponse.json();

      if (metricsData.success) {
        setMetrics(metricsData);
      } else {
        setError(metricsData.error || 'Ошибка загрузки метрик');
      }

      // Загружаем разбивку по услугам и мастерам
      const breakdownResponse = await fetch(`${baseUrl}/api/finance/breakdown?period=${selectedPeriod}${businessParam}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      const breakdownData = await breakdownResponse.json();

      if (breakdownData.success) {
        setBreakdown(breakdownData);
      }
    } catch (error) {
      setError('Ошибка соединения с сервером');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMetrics();
  }, [currentBusinessId]);

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

  const formatPercentage = (value: number | string | null | undefined) => {
    if (value == null) return '0%';
    const num = Number(value);
    if (isNaN(num)) return '0%';
    return `${num >= 0 ? '+' : ''}${num.toFixed(1)}%`;
  };

  const getGrowthColor = (value: number | null | undefined) => {
    if (value == null) return 'text-gray-400';
    if (value > 0) return 'text-emerald-500';
    if (value < 0) return 'text-rose-500';
    return 'text-gray-400';
  };

  if (loading) {
    return (
      <Card className="border-none shadow-sm bg-white/50 backdrop-blur-sm">
        <CardContent className="p-6">
          <div className="animate-pulse space-y-4">
            <div className="h-8 bg-gray-200/50 rounded w-1/3 mb-6"></div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-32 bg-gray-200/50 rounded-xl"></div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-red-100 bg-red-50/50">
        <CardContent className="p-6 text-center">
          <div className="text-red-500 mb-4 flex items-center justify-center gap-2">
            <div className="p-2 bg-red-100 rounded-full">
              <ArrowDownRight className="w-5 h-5" />
            </div>
            {error}
          </div>
          <Button onClick={() => loadMetrics()} variant="outline" className="bg-white hover:bg-red-50">
            Попробовать снова
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!metrics) {
    return (
      <Card>
        <CardContent className="p-8 text-center text-gray-500">
          <p>Нет данных для отображения</p>
          <Button onClick={() => loadMetrics()} variant="outline" className="mt-4">
            Обновить
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Section */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white/70 backdrop-blur-md p-6 rounded-2xl shadow-sm border border-white/20">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-blue-500/10 rounded-xl text-blue-600">
            <TrendingUp className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-gray-900">{t.dashboard.finance.metrics.title}</h3>
            <p className="text-sm text-gray-500">
              {t.dashboard.finance.metrics.period} {metrics.period.start_date} — {metrics.period.end_date}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Select value={period} onValueChange={handlePeriodChange}>
            <SelectTrigger className="w-32 bg-white/80 border-gray-200">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="week">Неделя</SelectItem>
              <SelectItem value="month">{t.dashboard.finance.metrics.month}</SelectItem>
              <SelectItem value="quarter">{t.dashboard.network.period.quarter}</SelectItem>
              <SelectItem value="year">{t.dashboard.network.period.year}</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={() => loadMetrics()} variant="outline" size="icon" className="bg-white/80">
            <RefreshCw className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Main Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Revenue */}
        <div className={cn(
          "relative overflow-hidden rounded-2xl p-6 transition-all duration-300 hover:-translate-y-1",
          "bg-white/60 backdrop-blur-xl border border-white/40 shadow-sm hover:shadow-md",
          "group"
        )}>
          <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 rounded-full blur-2xl -mr-16 -mt-16 group-hover:bg-blue-500/10 transition-colors" />

          <div className="flex justify-between items-start mb-4 relative z-10">
            <div className="p-3 bg-blue-100/50 rounded-xl text-blue-600">
              <DollarSign className="w-6 h-6" />
            </div>
            <div className={cn("flex items-center gap-1 text-sm font-medium px-2 py-1 rounded-lg bg-white/50", getGrowthColor(metrics.growth.revenue_growth))}>
              {metrics.growth.revenue_growth > 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
              {formatPercentage(metrics.growth.revenue_growth)}
            </div>
          </div>

          <div className="relative z-10">
            <p className="text-sm text-gray-500 font-medium mb-1">{t.dashboard.finance.metrics.totalRevenue}</p>
            <h3 className="text-2xl font-bold text-gray-900 tracking-tight">
              {formatCurrency(metrics.metrics.total_revenue)}
            </h3>
          </div>
        </div>

        {/* Orders */}
        <div className={cn(
          "relative overflow-hidden rounded-2xl p-6 transition-all duration-300 hover:-translate-y-1",
          "bg-white/60 backdrop-blur-xl border border-white/40 shadow-sm hover:shadow-md",
          "group"
        )}>
          <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-2xl -mr-16 -mt-16 group-hover:bg-emerald-500/10 transition-colors" />

          <div className="flex justify-between items-start mb-4 relative z-10">
            <div className="p-3 bg-emerald-100/50 rounded-xl text-emerald-600">
              <Package className="w-6 h-6" />
            </div>
            <div className={cn("flex items-center gap-1 text-sm font-medium px-2 py-1 rounded-lg bg-white/50", getGrowthColor(metrics.growth.orders_growth))}>
              {metrics.growth.orders_growth > 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
              {formatPercentage(metrics.growth.orders_growth)}
            </div>
          </div>

          <div className="relative z-10">
            <p className="text-sm text-gray-500 font-medium mb-1">{t.dashboard.finance.metrics.totalOrders}</p>
            <h3 className="text-2xl font-bold text-gray-900 tracking-tight">
              {metrics.metrics.total_orders}
            </h3>
          </div>
        </div>

        {/* Avg Check */}
        <div className={cn(
          "relative overflow-hidden rounded-2xl p-6 transition-all duration-300 hover:-translate-y-1",
          "bg-white/60 backdrop-blur-xl border border-white/40 shadow-sm hover:shadow-md",
          "group"
        )}>
          <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/5 rounded-full blur-2xl -mr-16 -mt-16 group-hover:bg-purple-500/10 transition-colors" />

          <div className="flex justify-between items-start mb-4 relative z-10">
            <div className="p-3 bg-purple-100/50 rounded-xl text-purple-600">
              <CreditCard className="w-6 h-6" />
            </div>
          </div>

          <div className="relative z-10">
            <p className="text-sm text-gray-500 font-medium mb-1">{t.dashboard.finance.metrics.avgCheck}</p>
            <h3 className="text-2xl font-bold text-gray-900 tracking-tight">
              {formatCurrency(metrics.metrics.average_check)}
            </h3>
          </div>
        </div>
      </div>

      <div className="text-xs text-center text-gray-400 font-medium tracking-wide">
        {t.dashboard.finance.metrics.crmNote}
      </div>

      {/* Secondary Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="flex items-center gap-4 p-4 rounded-xl bg-orange-50/50 border border-orange-100/50 hover:bg-orange-50 transition-colors">
          <div className="p-3 bg-white rounded-lg shadow-sm text-orange-500">
            <Users className="w-5 h-5" />
          </div>
          <div>
            <p className="text-sm text-gray-500">{t.dashboard.finance.metrics.newClients}</p>
            <p className="text-lg font-bold text-gray-900">{metrics.metrics.new_clients}</p>
          </div>
        </div>

        <div className="flex items-center gap-4 p-4 rounded-xl bg-indigo-50/50 border border-indigo-100/50 hover:bg-indigo-50 transition-colors">
          <div className="p-3 bg-white rounded-lg shadow-sm text-indigo-500">
            <Repeat className="w-5 h-5" />
          </div>
          <div>
            <p className="text-sm text-gray-500">{t.dashboard.finance.metrics.returningClients}</p>
            <p className="text-lg font-bold text-gray-900">{metrics.metrics.returning_clients}</p>
          </div>
        </div>

        <div className="flex items-center gap-4 p-4 rounded-xl bg-pink-50/50 border border-pink-100/50 hover:bg-pink-50 transition-colors">
          <div className="p-3 bg-white rounded-lg shadow-sm text-pink-500">
            <Heart className="w-5 h-5" />
          </div>
          <div>
            <p className="text-sm text-gray-500">{t.dashboard.finance.metrics.clientRetention}</p>
            <p className="text-lg font-bold text-gray-900">{formatPercentage(metrics.metrics.retention_rate)}</p>
          </div>
        </div>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Services Chart */}
        <Card className="border-0 shadow-sm bg-white/60 backdrop-blur-xl">
          <CardHeader>
            <CardTitle className="text-base font-semibold text-gray-700 flex items-center gap-2">
              <PieChartIcon className="w-4 h-4 text-gray-400" />
              {t.dashboard.finance.metrics.revenueByService}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {breakdown && breakdown.by_services.length > 0 ? (
              <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={breakdown.by_services}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {breakdown.by_services.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} strokeWidth={0} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                      formatter={(value: number) => `${formatCurrency(value)}`}
                    />
                    <Legend iconType="circle" />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-[300px] flex items-center justify-center text-gray-400 bg-gray-50/50 rounded-xl">
                {t.dashboard.finance.metrics.noServiceData}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Masters Chart */}
        <Card className="border-0 shadow-sm bg-white/60 backdrop-blur-xl">
          <CardHeader>
            <CardTitle className="text-base font-semibold text-gray-700 flex items-center gap-2">
              <Users className="w-4 h-4 text-gray-400" />
              {t.dashboard.finance.metrics.revenueByMaster}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {breakdown && breakdown.by_masters.length > 0 ? (
              <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={breakdown.by_masters}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {breakdown.by_masters.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} strokeWidth={0} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                      formatter={(value: number) => `${formatCurrency(value)}`}
                    />
                    <Legend iconType="circle" />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-[300px] flex items-center justify-center text-gray-400 bg-gray-50/50 rounded-xl">
                {t.dashboard.finance.metrics.noMasterData}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default FinancialMetrics;
