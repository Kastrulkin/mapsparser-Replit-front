import React, { useState, useEffect } from 'react';
import { getApiEndpoint } from '../config/api';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import { Button } from './ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { useLanguage } from '@/i18n/LanguageContext';

interface NetworkDashboardProps {
  networkId: string;
}

interface NetworkStats {
  total_revenue: number;
  total_orders: number;
  locations_count: number;
  by_services: Array<{ name: string; value: number }>;
  by_masters: Array<{ name: string; value: number }>;
  by_locations: Array<{ name: string; value: number }>;
  ratings: Array<{
    business_id: string;
    name: string;
    rating: number | null;
    reviews_total: number | null;
    reviews_30d: number | null;
    last_sync: string | null;
  }>;
  bad_reviews: Array<{ location_name: string; count: number }>;
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d', '#ffc658', '#ff7c7c', '#8dd1e1', '#d084d0'];

export const NetworkDashboard: React.FC<NetworkDashboardProps> = ({ networkId }) => {
  const [stats, setStats] = useState<NetworkStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState('month');
  const { t, language } = useLanguage();

  useEffect(() => {
    loadNetworkStats();
  }, [networkId, period]);

  const loadNetworkStats = async () => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(getApiEndpoint(`/api/networks/${networkId}/stats?period=${period}`), {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      const data = await response.json();

      if (data.success) {
        setStats(data.stats);
      } else {
        setError(data.error || t.dashboard.network.errorLoading);
      }
    } catch (error) {
      setError(t.error);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat(language === 'ru' ? 'ru-RU' : 'en-US', {
      style: 'currency',
      currency: language === 'ru' ? 'RUB' : 'USD', // Assuming simple switch, though API usually sends raw numbers
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
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
          <Button onClick={() => loadNetworkStats()} variant="outline">
            {t.dashboard.network.tryAgain}
          </Button>
        </div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="text-center text-gray-500">
          <p>{t.dashboard.network.noData}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Заголовок и период */}
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">{t.dashboard.network.title}</h2>
        <Select value={period} onValueChange={(value) => { setPeriod(value); }}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="week">{t.dashboard.network.period.week}</SelectItem>
            <SelectItem value="month">{t.dashboard.network.period.month}</SelectItem>
            <SelectItem value="quarter">{t.dashboard.network.period.quarter}</SelectItem>
            <SelectItem value="year">{t.dashboard.network.period.year}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Общая статистика */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-blue-50 rounded-lg p-4">
          <div className="text-sm text-blue-600 font-medium">{t.dashboard.network.totalRevenue}</div>
          <div className="text-2xl font-bold text-blue-900">{formatCurrency(stats.total_revenue)}</div>
        </div>
        <div className="bg-green-50 rounded-lg p-4">
          <div className="text-sm text-green-600 font-medium">{t.dashboard.network.totalOrders}</div>
          <div className="text-2xl font-bold text-green-900">{stats.total_orders}</div>
        </div>
        <div className="bg-purple-50 rounded-lg p-4">
          <div className="text-sm text-purple-600 font-medium">{t.dashboard.network.locationsCount}</div>
          <div className="text-2xl font-bold text-purple-900">{stats.locations_count}</div>
        </div>
      </div>

      {/* Круговые диаграммы */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Доход по услугам */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t.dashboard.network.revenueByService}</h3>
          {stats.by_services.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={stats.by_services}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name}: ${(Number(percent || 0) * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {stats.by_services.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: number) => `${formatCurrency(value)}`} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-center text-gray-500 py-8">{t.dashboard.network.noData}</div>
          )}
        </div>

        {/* Доход по мастерам */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t.dashboard.network.revenueByMaster}</h3>
          {stats.by_masters.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={stats.by_masters}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name}: ${(Number(percent || 0) * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {stats.by_masters.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: number) => `${formatCurrency(value)}`} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-center text-gray-500 py-8">{t.dashboard.network.noData}</div>
          )}
        </div>
      </div>

      {/* Доход по точкам */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">{t.dashboard.network.revenueByLocation}</h3>
        {stats.by_locations.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={stats.by_locations}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip formatter={(value: number) => `${formatCurrency(value)}`} />
              <Bar dataKey="value" fill="#8884d8" />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="text-center text-gray-500 py-8">{t.dashboard.network.noData}</div>
        )}
      </div>

      {/* Рейтинги и отзывы */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Рейтинги */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t.dashboard.network.ratings}</h3>
          {stats.ratings.length > 0 ? (
            <div className="space-y-2">
              {stats.ratings.map((item, index) => (
                <div key={index} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                  <span className="text-sm font-medium">{item.name}</span>
                  <div className="flex items-center space-x-2">
                    <span className="text-sm text-gray-600">
                      {item.rating != null ? Number(item.rating).toFixed(1) : '—'}
                    </span>
                    <span className="text-xs text-gray-400">
                      ({item.reviews_total ?? 0} {t.dashboard.network.reviews}, {t.dashboard.network.last30Days}: {item.reviews_30d ?? 0})
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-gray-500 py-8">{t.dashboard.network.noData}</div>
          )}
        </div>

        {/* Плохие отзывы */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t.dashboard.network.badReviews}</h3>
          {stats.bad_reviews.length > 0 ? (
            <div className="space-y-2">
              {stats.bad_reviews.map((item, index) => (
                <div key={index} className="flex justify-between items-center p-2 bg-red-50 rounded">
                  <span className="text-sm font-medium">{item.location_name}</span>
                  <span className="text-sm text-red-600 font-bold">{item.count}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-gray-500 py-8">{t.dashboard.network.noBadReviews}</div>
          )}
        </div>
      </div>
    </div>
  );
};
