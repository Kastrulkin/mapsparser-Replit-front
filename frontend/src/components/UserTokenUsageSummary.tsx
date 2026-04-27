import { useEffect, useMemo, useState } from 'react';
import { BarChart3, Coins, Calendar } from 'lucide-react';
import { cn } from '@/lib/utils';
import { DESIGN_TOKENS } from '@/lib/design-tokens';
import { useLanguage } from '@/i18n/LanguageContext';

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

const CATEGORY_LABELS_RU: Record<string, string> = {
  services_optimization: 'Оптимизация услуг',
  news_generation: 'Новости',
  ai_agents: 'ИИ-агенты',
  reviews: 'Отзывы',
  other: 'Прочее',
};
const CATEGORY_LABELS_EN: Record<string, string> = {
  services_optimization: 'Service optimization',
  news_generation: 'News',
  ai_agents: 'AI agents',
  reviews: 'Reviews',
  other: 'Other',
};

const TOKENS_PER_CREDIT = 1000;
const num = (value: number | null | undefined) => Number(value || 0).toLocaleString('ru-RU');
const credits = (value: number | null | undefined) =>
  (Number(value || 0) / TOKENS_PER_CREDIT).toLocaleString('ru-RU', {
    maximumFractionDigits: 2,
  });
const CREDIT_LIMITS: Record<string, number> = {
  starter: 240,
  starter_monthly: 240,
  professional: 1000,
  pro: 1000,
  pro_monthly: 1000,
};

const formatDateLocalized = (value: string | null | undefined, locale: string) => {
  if (!value) return null;
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return null;
  return dt.toLocaleDateString(locale === 'ru' ? 'ru-RU' : 'en-US');
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
  const { language } = useLanguage();
  const isRu = language === 'ru';
  const [months, setMonths] = useState<number>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<TokenUsageResponse | null>(null);
  const [billingNextDate, setBillingNextDate] = useState<string | null>(null);
  const [creditsBalance, setCreditsBalance] = useState<number | null>(null);
  const [billingTariffId, setBillingTariffId] = useState<string | null>(null);

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
        const payload = await response.json().catch(() => ({}));
        if (response.status === 404) {
          setData(null);
          setCreditsBalance(null);
          setBillingNextDate(null);
          setBillingTariffId(null);
          return;
        }
        if (!response.ok || payload?.error) {
          throw new Error(payload?.error || (isRu ? 'Ошибка загрузки кредитов' : 'Failed to load credits'));
        }
        setData(payload);

        // Prefer billing next date from billing API for "Кредиты до"
        const billingParams = new URLSearchParams();
        if (businessId) billingParams.set('business_id', businessId);
        const billingResp = await fetch(`/api/billing/status?${billingParams.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const billingPayload = await billingResp.json();
        if (billingResp.ok && typeof billingPayload?.credits_balance === 'number') {
          setCreditsBalance(Number(billingPayload.credits_balance));
        } else {
          setCreditsBalance(null);
        }
        if (billingResp.ok && billingPayload?.subscription?.tariff_id) {
          setBillingTariffId(String(billingPayload.subscription.tariff_id));
        } else {
          setBillingTariffId(null);
        }
        if (billingResp.ok && billingPayload?.subscription?.next_billing_date) {
          setBillingNextDate(billingPayload.subscription.next_billing_date);
        } else {
          setBillingNextDate(null);
        }
      } catch (e: any) {
        setError(e?.message || (isRu ? 'Ошибка загрузки кредитов' : 'Failed to load credits'));
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [businessId, isRu, months]);

  const categories = useMemo(() => {
    const list = data?.by_category || [];
    return [...list].sort((a, b) => (b.total_tokens || 0) - (a.total_tokens || 0));
  }, [data]);

  const creditsExpireLabel = useMemo(() => {
    if ((subscriptionTier || '').toLowerCase() === 'promo') {
      return isRu ? 'Бессрочно' : 'No expiration';
    }
    return (
      formatDateLocalized(billingNextDate, language) ||
      formatDateLocalized(subscriptionEndsAt, language) ||
      formatDateLocalized(trialEndsAt, language) ||
      (isRu ? 'Дата будет привязана к оплате' : 'Date will be linked to billing')
    );
  }, [billingNextDate, isRu, language, subscriptionEndsAt, subscriptionTier, trialEndsAt]);

  const periodLimit = useMemo(() => {
    const key = String((billingTariffId || subscriptionTier || '').toLowerCase());
    return CREDIT_LIMITS[key] ?? null;
  }, [billingTariffId, subscriptionTier]);

  const spentCurrentBillingPeriod = useMemo(() => {
    if (periodLimit == null || creditsBalance == null) return null;
    return Math.max(0, periodLimit - creditsBalance);
  }, [periodLimit, creditsBalance]);

  const labels = useMemo(() => ({
    title: isRu ? 'Счётчик кредитов' : 'Credits usage',
    creditsUntil: isRu ? 'Кредиты до:' : 'Credits valid until:',
    months1: isRu ? 'За 1 месяц' : 'Last 1 month',
    months3: isRu ? 'За 3 месяца' : 'Last 3 months',
    months6: isRu ? 'За 6 месяцев' : 'Last 6 months',
    months12: isRu ? 'За 12 месяцев' : 'Last 12 months',
    leftInPeriod: isRu ? 'Осталось в текущем расчётном периоде' : 'Remaining in current billing period',
    spentMonth: isRu ? 'Потрачено в календарном месяце' : 'Spent this calendar month',
    spentBillingPeriod: isRu ? 'Потрачено в текущем расчётном периоде' : 'Spent in current billing period',
    spentSelected: isRu ? 'Потрачено за выбранный период' : 'Spent in selected period',
    creditsWord: isRu ? 'кредитов' : 'credits',
    requests: isRu ? 'Запросов' : 'Requests',
    availableInPeriod: isRu ? 'доступно в текущем периоде' : 'available in current period',
    noData: isRu ? 'Пока нет данных по расходу кредитов.' : 'No credit usage data yet.',
  }), [isRu]);
  const categoryLabels = isRu ? CATEGORY_LABELS_RU : CATEGORY_LABELS_EN;

  return (
    <div className={cn(DESIGN_TOKENS.glass.default, 'rounded-2xl p-8 hover:shadow-2xl transition-all duration-500')}>
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-6">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-indigo-600" />
          <h2 className="text-xl font-bold text-gray-900">{labels.title}</h2>
        </div>
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <span className="font-medium">{labels.creditsUntil}</span> {creditsExpireLabel}
        </div>
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-gray-500" />
          <select
            value={months}
            onChange={(e) => setMonths(Number(e.target.value))}
            className="h-9 rounded-lg border border-gray-200 px-3 text-sm bg-white"
          >
            <option value={1}>{labels.months1}</option>
            <option value={3}>{labels.months3}</option>
            <option value={6}>{labels.months6}</option>
            <option value={12}>{labels.months12}</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="rounded-xl border border-emerald-100 bg-emerald-50/70 p-4">
          <div className="text-sm text-emerald-700 mb-1">{labels.leftInPeriod}</div>
          <div className="text-2xl font-bold text-emerald-900 flex items-center gap-2">
            <Coins className="w-5 h-5" />
            {loading ? '...' : num(creditsBalance)}
          </div>
          <div className="text-xs text-emerald-700 mt-1">
            {periodLimit ? `${isRu ? 'из' : 'of'} ${num(periodLimit)} ${labels.creditsWord}` : labels.availableInPeriod}
          </div>
        </div>
        <div className="rounded-xl border border-indigo-100 bg-indigo-50/70 p-4">
          <div className="text-sm text-indigo-700 mb-1">{labels.spentMonth}</div>
          <div className="text-2xl font-bold text-indigo-900 flex items-center gap-2">
            <Coins className="w-5 h-5" />
            {loading ? '...' : credits(data?.month_total?.total_tokens)}
          </div>
          <div className="text-xs text-indigo-700 mt-1">{labels.creditsWord}</div>
          <div className="text-xs text-indigo-700 mt-1">{labels.requests}: {loading ? '...' : num(data?.month_total?.requests_count)}</div>
        </div>
        <div className="rounded-xl border border-orange-100 bg-orange-50/70 p-4">
          <div className="text-sm text-orange-700 mb-1">{labels.spentBillingPeriod}</div>
          <div className="text-2xl font-bold text-orange-900">
            {loading ? '...' : spentCurrentBillingPeriod == null ? '—' : num(spentCurrentBillingPeriod)}
          </div>
          <div className="text-xs text-orange-700 mt-1">{labels.creditsWord}</div>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white/80 p-4">
          <div className="text-sm text-gray-600 mb-1">{labels.spentSelected}</div>
          <div className="text-2xl font-bold text-gray-900">{loading ? '...' : credits(data?.period_total?.total_tokens)}</div>
          <div className="text-xs text-gray-500 mt-1">{labels.creditsWord}</div>
          <div className="text-xs text-gray-500 mt-1">{labels.requests}: {loading ? '...' : num(data?.period_total?.requests_count)}</div>
        </div>
      </div>

      <div className="space-y-2">
        {categories.length === 0 && !loading ? (
          <div className="text-sm text-gray-500">{labels.noData}</div>
        ) : (
          categories.map((item) => (
            <div key={item.category} className="flex items-center justify-between rounded-lg border border-gray-100 bg-white/70 px-3 py-2">
              <span className="text-sm font-medium text-gray-700">{categoryLabels[item.category] || item.category}</span>
              <span className="text-sm font-semibold text-gray-900">{loading ? '...' : credits(item.total_tokens)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
