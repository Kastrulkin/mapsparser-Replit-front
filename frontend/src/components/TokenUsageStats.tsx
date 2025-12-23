import React, { useState, useEffect } from 'react';
import { useToast } from '../hooks/use-toast';
import { newAuth } from '../lib/auth_new';

interface TokenStats {
  total: {
    total_tokens: number;
    prompt_tokens: number;
    completion_tokens: number;
    requests_count: number;
  };
  by_user: Array<{
    user_id: string;
    email: string;
    name: string;
    total_tokens: number;
    prompt_tokens: number;
    completion_tokens: number;
    requests_count: number;
  }>;
  by_business: Array<{
    business_id: string;
    business_name: string;
    owner_id: string;
    owner_email: string;
    total_tokens: number;
    prompt_tokens: number;
    completion_tokens: number;
    requests_count: number;
  }>;
  by_task_type: Array<{
    task_type: string;
    total_tokens: number;
    prompt_tokens: number;
    completion_tokens: number;
    requests_count: number;
  }>;
}

export const TokenUsageStats: React.FC = () => {
  const [stats, setStats] = useState<TokenStats | null>(null);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      setLoading(true);
      const token = await newAuth.getToken();
      if (!token) {
        toast({
          title: 'Ошибка',
          description: 'Требуется авторизация',
          variant: 'destructive',
        });
        return;
      }

      const response = await fetch('/api/admin/token-usage', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Ошибка загрузки статистики');
      }

      const data = await response.json();
      if (data.success) {
        setStats(data);
      }
    } catch (error: any) {
      console.error('Ошибка загрузки статистики токенов:', error);
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось загрузить статистику',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('ru-RU').format(num);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Загрузка статистики...</p>
        </div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <p className="text-gray-500 text-center">Статистика недоступна</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Общая статистика */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Общая статистика</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-blue-50 rounded-lg p-4">
            <p className="text-sm text-gray-600 mb-1">Всего токенов</p>
            <p className="text-2xl font-bold text-blue-600">{formatNumber(stats.total.total_tokens)}</p>
          </div>
          <div className="bg-green-50 rounded-lg p-4">
            <p className="text-sm text-gray-600 mb-1">Промпт токены</p>
            <p className="text-2xl font-bold text-green-600">{formatNumber(stats.total.prompt_tokens)}</p>
          </div>
          <div className="bg-purple-50 rounded-lg p-4">
            <p className="text-sm text-gray-600 mb-1">Completion токены</p>
            <p className="text-2xl font-bold text-purple-600">{formatNumber(stats.total.completion_tokens)}</p>
          </div>
          <div className="bg-orange-50 rounded-lg p-4">
            <p className="text-sm text-gray-600 mb-1">Запросов</p>
            <p className="text-2xl font-bold text-orange-600">{formatNumber(stats.total.requests_count)}</p>
          </div>
        </div>
      </div>

      {/* По пользователям */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">По пользователям</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Пользователь</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Всего токенов</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Промпт</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Completion</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Запросов</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {stats.by_user.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                    Нет данных
                  </td>
                </tr>
              ) : (
                stats.by_user.map((user) => (
                  <tr key={user.user_id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <p className="text-sm font-medium text-gray-900">{user.name || user.email}</p>
                        <p className="text-sm text-gray-500">{user.email}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium text-gray-900">
                      {formatNumber(user.total_tokens)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-500">
                      {formatNumber(user.prompt_tokens)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-500">
                      {formatNumber(user.completion_tokens)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-500">
                      {formatNumber(user.requests_count)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* По бизнесам */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">По бизнесам</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Бизнес</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Владелец</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Всего токенов</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Промпт</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Completion</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Запросов</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {stats.by_business.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-gray-500">
                    Нет данных
                  </td>
                </tr>
              ) : (
                stats.by_business.map((business) => (
                  <tr key={business.business_id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <p className="text-sm font-medium text-gray-900">{business.business_name}</p>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <p className="text-sm text-gray-500">{business.owner_email}</p>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium text-gray-900">
                      {formatNumber(business.total_tokens)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-500">
                      {formatNumber(business.prompt_tokens)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-500">
                      {formatNumber(business.completion_tokens)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-500">
                      {formatNumber(business.requests_count)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* По типам задач */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">По типам задач</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Тип задачи</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Всего токенов</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Промпт</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Completion</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Запросов</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {stats.by_task_type.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                    Нет данных
                  </td>
                </tr>
              ) : (
                stats.by_task_type.map((task) => (
                  <tr key={task.task_type}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <p className="text-sm font-medium text-gray-900">{task.task_type}</p>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium text-gray-900">
                      {formatNumber(task.total_tokens)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-500">
                      {formatNumber(task.prompt_tokens)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-500">
                      {formatNumber(task.completion_tokens)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-500">
                      {formatNumber(task.requests_count)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

