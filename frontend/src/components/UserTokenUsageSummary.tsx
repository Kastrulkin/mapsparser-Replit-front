import { useEffect, useMemo, useState } from 'react';
import { BarChart3, Coins, Calendar } from 'lucide-react';
import { cn } from '@/lib/utils';
import { DESIGN_TOKENS } from '@/lib/design-tokens';

type TokenUsageResponse = {
  success: boolean;
  period_months: number;
  month_total: {
    total_tokens: number;
    prompt_tokens: number;
    completion_tokens: number;
    requests_count: number;
  };
  period_total: {
    total_tokens: number;
    prompt_tokens: number;
    completion_tokens: number;
    requests_count: number;
  };
  by_category: Array<{
    category: string;
    total_tokens: number;
    prompt_tokens: number;
    completion_tokens: number;
    requests_count: number;
  }>;
};

const CATEGORY_LABELS: Record<string, string> = {
  services_optimization: 'Оптимизация услуг',
  news_generation: 'Новости',
  ai_agents: 'ИИ-агенты',
  reviews: 'Отзывы',
  other: 'Прочее',
};

const TOKENS_PER_CREDIT = 1000;
const num = (value: number | null | undefined) => Number(value || 0).toLocaleString('ru-RU');
const credits = (value: number | null | undefined) =>
  (Number(value || 0) / TOKENS_PER_CREDIT).toLocaleString('ru-RU', {
    maximumFractionDigits: 2,
  });

const formatDateRu = (value?: string | null) => {
  if (!value) return null;
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return null;
  return dt.toLocaleDateString('ru-RU');
};

export const UserTokenUsageSummary = ({
  businessId,
  subscriptionTier,
  subscriptionEndsAt,
  trialEndsAt,
}: {
  businessId: string | null | undefined;
  subscriptionTier?: string | null;
  subscriptionEndsAt?: string | null;
  trialEndsAt?: string | null;
}) => {
  const [months, setMonths] = useState<number>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<TokenUsageResponse | null>(null);

  useEffect(() => {
    const run = async () => {
      const token = localStorage.getItem('auth_token');
      if (!token) return;

      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        params.set('months', String(months));
        if (businessId) params.set('business_id', businessId);
        const response = await fetch(`/api/token-usage?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const payload = await response.json();
        if (!response.ok || payload?.error) {
          throw new Error(payload?.error || 'Ошибка загрузки кредитов');
        }
        setData(payload);
      } catch (e: any) {
        setError(e?.message || 'Ошибка загрузки кредитов');
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [businessId, months]);

  const categories = useMemo(() => {
    const list = data?.by_category || [];
    return [...list].sort((a, b) => (b.total_tokens || 0) - (a.total_tokens || 0));
  }, [data]);

  const creditsExpireLabel = useMemo(() => {
    if ((subscriptionTier || '').toLowerCase() === 'promo') {
      return 'Бессрочно';
    }
    return formatDateRu(subscriptionEndsAt) || formatDateRu(trialEndsAt) || 'Дата будет привязана к оплате';
  }, [subscriptionTier, subscriptionEndsAt, trialEndsAt]);

  return (
    <div className={cn(DESIGN_TOKENS.glass.default, 'rounded-2xl p-8 hover:shadow-2xl transition-all duration-500')}>
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-6">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-indigo-600" />
          <h2 className="text-xl font-bold text-gray-900">Счётчик кредитов</h2>
        </div>
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <span className="font-medium">Кредиты до:</span> {creditsExpireLabel}
        </div>
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-gray-500" />
          <select
            value={months}
            onChange={(e) => setMonths(Number(e.target.value))}
            className="h-9 rounded-lg border border-gray-200 px-3 text-sm bg-white"
          >
            <option value={1}>За 1 месяц</option>
            <option value={3}>За 3 месяца</option>
            <option value={6}>За 6 месяцев</option>
            <option value={12}>За 12 месяцев</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="rounded-xl border border-indigo-100 bg-indigo-50/70 p-4">
          <div className="text-sm text-indigo-700 mb-1">Текущий месяц</div>
          <div className="text-2xl font-bold text-indigo-900 flex items-center gap-2">
            <Coins className="w-5 h-5" />
            {loading ? '...' : credits(data?.month_total?.total_tokens)}
          </div>
          <div className="text-xs text-indigo-700 mt-1">кредитов</div>
          <div className="text-xs text-indigo-700 mt-1">Запросов: {loading ? '...' : num(data?.month_total?.requests_count)}</div>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white/80 p-4">
          <div className="text-sm text-gray-600 mb-1">Выбранный период</div>
          <div className="text-2xl font-bold text-gray-900">{loading ? '...' : credits(data?.period_total?.total_tokens)}</div>
          <div className="text-xs text-gray-500 mt-1">кредитов</div>
          <div className="text-xs text-gray-500 mt-1">Запросов: {loading ? '...' : num(data?.period_total?.requests_count)}</div>
        </div>
      </div>

      <div className="space-y-2">
        {categories.length === 0 && !loading ? (
          <div className="text-sm text-gray-500">Пока нет данных по расходу кредитов.</div>
        ) : (
          categories.map((item) => (
            <div key={item.category} className="flex items-center justify-between rounded-lg border border-gray-100 bg-white/70 px-3 py-2">
              <span className="text-sm font-medium text-gray-700">{CATEGORY_LABELS[item.category] || item.category}</span>
              <span className="text-sm font-semibold text-gray-900">{loading ? '...' : credits(item.total_tokens)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
