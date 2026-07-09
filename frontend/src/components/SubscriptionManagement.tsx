import { useState, useEffect, useRef, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { useSearchParams } from 'react-router-dom';
import { useLanguage } from '@/i18n/LanguageContext';
import { cn } from '@/lib/utils';
import { DESIGN_TOKENS } from '@/lib/design-tokens';
import { Check, Crown, Zap, Shield, Star, Rocket, CreditCard, CalendarClock, Link2Off, RefreshCw } from 'lucide-react';

interface SubscriptionTier {
  id: string;
  name: string;
  price: number;
  currency: string;
  period: string;
  lead?: string;
  features: string[];
  stripe_price_id?: string;
  icon?: any;
  popular?: boolean;
}

interface BusinessSubscription {
  id?: string;
  tier: string;
  status: string;
  subscription_ends_at?: string;
  trial_ends_at?: string;
  moderation_status?: string;
  next_billing_date?: string | null;
  retry_count?: number;
  next_retry_at?: string | null;
  autopay_enabled?: boolean;
  payment_method_linked?: boolean;
  payment_method_summary?: {
    brand?: string | null;
    last4?: string | null;
    label?: string | null;
  } | null;
}

interface BillingAttempt {
  id: string;
  attempt_type: string;
  attempt_no: number;
  status: string;
  payment_id?: string | null;
  error_message?: string | null;
  created_at?: string | null;
}

interface BillingStatusResponse {
  success: boolean;
  subscription: BusinessSubscription | null;
  credits_balance?: number;
  recent_attempts?: BillingAttempt[];
  renewal_status?: {
    state?: string;
    reason?: string;
    next_retry_at?: string | null;
    next_billing_date?: string | null;
  };
}

const paymentProviderForTier = async (tier: SubscriptionTier | undefined): Promise<'yookassa' | 'stripe'> => {
  if (!tier || tier.currency === '₽') {
    return 'yookassa';
  }

  try {
    const providerResp = await fetch('/api/geo/payment-provider');
    const providerData = await providerResp.json();
    return String(providerData?.payment_provider || '').trim().toLowerCase() === 'stripe' ? 'stripe' : 'yookassa';
  } catch {
    return 'yookassa';
  }
};

export const SubscriptionManagement = ({ businessId, business }: { businessId: string | null; business: any }) => {
  const [subscription, setSubscription] = useState<BusinessSubscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [billingLoading, setBillingLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [unlinkingCard, setUnlinkingCard] = useState(false);
  const [unlinkConfirmed, setUnlinkConfirmed] = useState(false);
  const [recentAttempts, setRecentAttempts] = useState<BillingAttempt[]>([]);
  const [renewalStatus, setRenewalStatus] = useState<BillingStatusResponse['renewal_status'] | null>(null);
  const { toast } = useToast();
  const [searchParams] = useSearchParams();
  const paymentStatus = searchParams.get('payment');
  const paymentSource = searchParams.get('source');
  const autoStartCheckout = searchParams.get('autostart') === '1';
  const selectedTierFromUrl = searchParams.get('tier');
  const autoCheckoutStartedRef = useRef(false);
  const { language, t } = useLanguage();

  const tiers: SubscriptionTier[] = useMemo(() => {
    const isRu = language === 'ru';
    return [
      {
        id: 'starter',
        name: isRu ? 'Начальный' : 'Starter',
        price: isRu ? 1200 : 15,
        currency: isRu ? '₽' : '$',
        period: isRu ? '₽/месяц (240 кредитов)' : t.dashboard.subscription.perMonth,
        lead: isRu ? 'Хватит чтобы:' : undefined,
        icon: Rocket,
        features: isRu
          ? [
              'настроить услуги на картах',
              'ответить на отзывы',
              'создать новости для публикации',
              'проверить конкурента',
            ]
          : [
              t.dashboard.subscription.starterFeature1,
              t.dashboard.subscription.starterFeature2,
              t.dashboard.subscription.starterFeature3,
            ],
      },
      {
        id: 'professional',
        name: isRu ? 'Профессиональный' : 'Professional',
        price: isRu ? 5000 : 55,
        currency: isRu ? '₽' : '$',
        period: isRu ? '₽/месяц (1000 кредитов)' : t.dashboard.subscription.perMonth,
        lead: isRu ? 'Хватит чтобы:' : undefined,
        popular: true,
        icon: Zap,
        features: isRu
          ? [
              'постить новости',
              'отвечать на отзывы',
              'проверять конкурентов',
              'подключить ии агентов для общения с клиентами',
              'отслеживать финансовые показатели',
              'управлять компанией через Телеграм',
            ]
          : [
              t.dashboard.subscription.profFeature1,
              t.dashboard.subscription.profFeature2,
              t.dashboard.subscription.profFeature3,
              t.dashboard.subscription.profFeature4,
            ],
      },
      {
        id: 'concierge',
        name: isRu ? 'Консьерж' : 'Concierge',
        price: isRu ? 25000 : 310,
        currency: isRu ? '₽' : '$',
        period: isRu ? '₽/месяц' : t.dashboard.subscription.perMonth,
        lead: isRu ? '(Мы всё делаем за вас)' : undefined,
        icon: Crown,
        features: isRu
          ? [
              'Карточка компании на картах',
              'Коммуникация с клиентами',
              'Допродажи и кросс-продажи',
              'Оптимизация бизнес-процессов',
              'Выделенный менеджер',
            ]
          : [
              t.dashboard.subscription.conciergeFeature1,
              t.dashboard.subscription.conciergeFeature2,
              t.dashboard.subscription.conciergeFeature3,
              t.dashboard.subscription.conciergeFeature4,
              t.dashboard.subscription.conciergeFeature5,
            ],
      },
      {
        id: 'elite',
        name: isRu ? 'Особый (Elite)' : 'Elite',
        price: 0,
        currency: '',
        period: '',
        lead: isRu ? '(Мы делаем всё за вас и даже больше)' : undefined,
        icon: Shield,
        features: isRu
          ? [
              'Привлечение клиентов онлайн',
              'Коммуникация с клиентами',
              'Привлечение клиентов оффлайн',
              'Оптимизация бизнес-процессов',
              'Выделенный менеджер',
            ]
          : [
              t.dashboard.subscription.eliteFeature1,
              t.dashboard.subscription.eliteFeature2,
              t.dashboard.subscription.eliteFeature3,
              t.dashboard.subscription.eliteFeature4,
              t.dashboard.subscription.eliteFeature5,
            ],
      },
    ];
  }, [language, t]);

  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;

  const formatDateTime = (value?: string | null) => {
    if (!value) return language === 'ru' ? '—' : '—';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return value;
    }
    return new Intl.DateTimeFormat(language === 'ru' ? 'ru-RU' : 'en-US', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(parsed);
  };

  const applyBillingStatus = (data: BillingStatusResponse) => {
    if (data.subscription) {
      setSubscription((prev) => ({
        ...(prev || {}),
        ...data.subscription,
        tier: data.subscription.tier || prev?.tier || 'trial',
        status: data.subscription.status || prev?.status || 'inactive',
      }));
    }
    if (Array.isArray(data.recent_attempts)) {
      setRecentAttempts(data.recent_attempts);
    }
    if (data.renewal_status) {
      setRenewalStatus(data.renewal_status);
    }
  };

  const loadBillingStatus = async (options?: { silent?: boolean }) => {
    if (!businessId || !token) return;
    if (!options?.silent) {
      setBillingLoading(true);
    }
    try {
      const params = new URLSearchParams({ business_id: businessId });
      const response = await fetch(`/api/billing/status?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data: BillingStatusResponse = await response.json();
      if (response.ok && data?.success) {
        applyBillingStatus(data);
      }
    } catch {
      // keep graceful fallback to business payload
    } finally {
      if (!options?.silent) {
        setBillingLoading(false);
      }
    }
  };

  useEffect(() => {
    if (paymentStatus === 'success') {
      toast({
        title: language === 'ru' ? 'Оплата успешна!' : 'Payment successful!',
        description: language === 'ru' ? 'Ваша подписка активирована.' : 'Your subscription is activated.',
      });
      window.history.replaceState({}, '', window.location.pathname);
    } else if (paymentStatus === 'cancelled') {
      toast({
        title: language === 'ru' ? 'Оплата отменена' : 'Payment cancelled',
        description: language === 'ru' ? 'Вы можете выбрать тариф позже.' : 'You can choose a plan later.',
        variant: 'destructive',
      });
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [paymentStatus, toast, language]);

  useEffect(() => {
    const isReturnPage = window.location.pathname.endsWith('/billing/return') || searchParams.get('yookassa_return') === '1';
    if (!isReturnPage || !businessId) return;

    if (!token) return;

    let aborted = false;
    (async () => {
      try {
        const params = new URLSearchParams({ business_id: businessId });
        const response = await fetch(`/api/billing/status?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data: BillingStatusResponse = await response.json();
        if (!response.ok || aborted) return;

        const status = data?.subscription?.status;
        applyBillingStatus(data);
        if (status === 'active') {
          toast({
            title: language === 'ru' ? 'Оплата успешна!' : 'Payment successful!',
            description: language === 'ru' ? 'Подписка активирована. Карта сохранена для ежемесячного продления, если вы не отвяжете её в кабинете.' : 'Subscription activated. The card is saved for monthly renewal until you unlink it in your account.',
          });
        } else if (status === 'blocked') {
          toast({
            title: language === 'ru' ? 'Оплата не завершена' : 'Payment not completed',
            description: language === 'ru' ? 'Подписка заблокирована до успешной оплаты.' : 'Subscription is blocked until payment succeeds.',
            variant: 'destructive',
          });
        }
      } catch {
        // ignore return status fetch errors
      } finally {
        if (!aborted) {
          window.history.replaceState({}, '', '/dashboard/profile');
        }
      }
    })();
    return () => {
      aborted = true;
    };
  }, [businessId, language, toast, searchParams]);

  useEffect(() => {
    if (business) {
      setSubscription({
        id: business.subscription_id,
        tier: business.subscription_tier || 'trial',
        status: business.subscription_status || 'inactive',
        subscription_ends_at: business.subscription_ends_at,
        trial_ends_at: business.trial_ends_at,
        moderation_status: business.moderation_status
      });
      setLoading(false);
    }
  }, [business]);

  useEffect(() => {
    void loadBillingStatus();
  }, [businessId]);

  useEffect(() => {
    setUnlinkConfirmed(false);
  }, [businessId, subscription?.id, subscription?.payment_method_linked]);

  useEffect(() => {
    if (autoCheckoutStartedRef.current) return;
    if (processing) return;
    if (paymentStatus !== 'required') return;
    if (paymentSource !== 'pricing' || !autoStartCheckout) return;

    const tierId = selectedTierFromUrl || 'starter';
    if (!tierId) return;

    if (subscription && subscription.status === 'active' && subscription.tier === tierId) {
      return;
    }

    autoCheckoutStartedRef.current = true;
    handleSubscribe(tierId);
  }, [autoStartCheckout, paymentSource, paymentStatus, selectedTierFromUrl, subscription, processing]);

  const handleSubscribe = async (tierId: string) => {
    if (!businessId) {
      toast({
        title: t.common.error,
        description: language === 'ru' ? 'Бизнес не выбран' : 'Business not selected',
        variant: 'destructive',
      });
      return;
    }

    setProcessing(true);
    try {
      const token = localStorage.getItem('auth_token');
      const selectedTier = tiers.find((tier) => tier.id === tierId);
      const paymentProvider = await paymentProviderForTier(selectedTier);

      const response = await fetch('/api/billing/checkout/session/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          provider: paymentProvider,
          entry_point: 'registered_paywall',
          channel: 'web',
          business_id: businessId,
          tariff_id: tierId,
          source: 'dashboard_subscription_management',
        })
      });

      const data = await response.json();

      const redirectUrl = data.confirmation_url || data.url;
      if (response.ok && redirectUrl) {
        window.location.href = redirectUrl;
      } else {
        toast({
          title: t.common.error,
          description: data.error || (language === 'ru' ? 'Не удалось создать сессию оплаты' : 'Failed to create payment session'),
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: t.common.error,
        description: language === 'ru' ? 'Ошибка при создании сессии оплаты' : 'Error creating payment session',
        variant: 'destructive',
      });
    } finally {
      setProcessing(false);
    }
  };

  const handleUnlinkCard = async () => {
    if (!businessId || !token || !subscription?.id) {
      return;
    }

    setUnlinkingCard(true);
    try {
      const response = await fetch('/api/billing/payment-method/unlink', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          business_id: businessId,
          subscription_id: subscription.id,
        }),
      });
      const data = await response.json();
      if (!response.ok || !data?.success) {
        throw new Error(data?.error || (language === 'ru' ? 'Не удалось отвязать карту' : 'Could not unlink the card'));
      }
      applyBillingStatus(data as BillingStatusResponse);
      toast({
        title: language === 'ru' ? 'Автоплатёж отключён' : 'Autopay disabled',
        description: language === 'ru'
          ? 'Текущий оплаченный период сохранён. Следующее продление потребует ручной оплаты.'
          : 'Your current paid period stays active. The next renewal will require a manual payment.',
      });
      setUnlinkConfirmed(false);
    } catch (error) {
      toast({
        title: t.common.error,
        description: error instanceof Error ? error.message : (language === 'ru' ? 'Не удалось отвязать карту' : 'Could not unlink the card'),
        variant: 'destructive',
      });
    } finally {
      setUnlinkingCard(false);
    }
  };

  const normalizeTierId = (tierId?: string | null) => String(tierId || 'starter').replace(/_monthly$/, '') || 'starter';

  const handlePaymentMethodSetup = () => {
    if (!subscription?.tier) {
      return;
    }
    void handleSubscribe(normalizeTierId(subscription.tier));
  };

  const getTierName = (tierId: string) => {
    const normalizedTierId = normalizeTierId(tierId);
    const tier = tiers.find(t => t.id === normalizedTierId);
    return tier ? tier.name : tierId;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge className="bg-emerald-500 hover:bg-emerald-600 border-0">{language === 'ru' ? 'Включена' : 'Active'}</Badge>;
      case 'pending':
        return <Badge className="bg-amber-500 hover:bg-amber-600 border-0">{language === 'ru' ? 'Ожидает оплаты' : 'Pending Payment'}</Badge>;
      case 'cancelled':
        return <Badge className="bg-rose-500 hover:bg-rose-600 border-0">{language === 'ru' ? 'Отменена' : 'Cancelled'}</Badge>;
      default:
        return <Badge className="bg-slate-500 hover:bg-slate-600 border-0">{language === 'ru' ? 'Неактивна' : 'Inactive'}</Badge>;
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-center text-gray-500 animate-pulse">
        {language === 'ru' ? 'Загрузка...' : 'Loading...'}
      </div>
    );
  }

  const isModerationPending = subscription?.moderation_status === 'pending';
  const autopayEnabled = Boolean(subscription?.autopay_enabled);
  const paymentMethodLinked = Boolean(subscription?.payment_method_linked);
  const latestAttempt = recentAttempts[0] || null;
  const periodEndText = subscription?.next_billing_date || subscription?.subscription_ends_at
    ? formatDateTime(subscription?.next_billing_date || subscription?.subscription_ends_at || null)
    : (language === 'ru' ? 'Появится после первой успешной оплаты' : 'Will appear after the first successful payment');
  const nextChargeText = subscription?.next_billing_date && autopayEnabled
    ? formatDateTime(subscription.next_billing_date)
    : paymentMethodLinked
      ? (language === 'ru' ? 'После восстановления подписки' : 'After the subscription is restored')
      : (language === 'ru' ? 'После привязки карты' : 'After card setup');
  const needsPaymentMethod = renewalStatus?.state === 'needs_payment_method' || !paymentMethodLinked;
  const autopayStatusTone = autopayEnabled
    ? 'bg-emerald-500 hover:bg-emerald-600 border-0'
    : needsPaymentMethod
      ? 'bg-amber-500 hover:bg-amber-600 border-0'
      : 'bg-slate-500 hover:bg-slate-600 border-0';
  const autopayStatusLabel = autopayEnabled
    ? (language === 'ru' ? 'Включён' : 'Enabled')
    : needsPaymentMethod
      ? (language === 'ru' ? 'Нужна карта' : 'Card needed')
      : (language === 'ru' ? 'Выключен' : 'Disabled');
  const paymentMethodLabel = subscription?.payment_method_summary?.label
    || (
      subscription?.payment_method_summary?.brand && subscription?.payment_method_summary?.last4
        ? `${subscription.payment_method_summary.brand} •••• ${subscription.payment_method_summary.last4}`
        : paymentMethodLinked
          ? (language === 'ru' ? 'Тестовая карта •••• 4444' : 'Test card •••• 4444')
          : (language === 'ru' ? 'Карта не сохранена' : 'No saved card')
    );
  const cardRemovalCheckboxLabel = paymentMethodLinked
    ? (language === 'ru' ? `Выбрать для удаления: ${paymentMethodLabel}` : `Select for deletion: ${paymentMethodLabel}`)
    : (language === 'ru' ? 'Карта для удаления не сохранена' : 'No saved card to delete');
  const renewalHelpText = (() => {
    if (autopayEnabled) {
      return language === 'ru'
        ? `Оплаченный период действует до ${periodEndText}. Следующее ежемесячное списание пройдёт в эту дату.`
        : `The paid period is active until ${periodEndText}. The next monthly charge will run on that date.`;
    }
    if (paymentMethodLinked) {
      return language === 'ru'
        ? 'Карта сохранена, но автоматическое продление сейчас недоступно.'
        : 'The card is saved, but automatic renewal is not available right now.';
    }
    return language === 'ru'
      ? 'Чтобы включить ежемесячное списание, оплатите текущий тариф через ЮKassa и сохраните карту.'
      : 'To enable monthly charging, pay the current plan through YooKassa and save the card.';
  })();
  const renewalStatusText = (() => {
    switch (renewalStatus?.state) {
      case 'needs_payment_method':
        return language === 'ru'
          ? 'Для ежемесячного списания нужно привязать карту. Оплаченный период будет показан после успешной оплаты.'
          : 'A saved card is required for monthly charging. The paid period will appear after successful payment.';
      case 'retry_pending':
        return language === 'ru'
          ? `Повторная попытка запланирована на ${formatDateTime(renewalStatus.next_retry_at)}`
          : `Retry scheduled for ${formatDateTime(renewalStatus.next_retry_at)}`;
      case 'blocked':
        return language === 'ru'
          ? 'Есть проблема с продлением. Проверьте последнюю попытку списания.'
          : 'There is a renewal issue. Check the latest charge attempt.';
      case 'scheduled':
        return language === 'ru'
          ? `Следующее списание ожидается ${formatDateTime(renewalStatus.next_billing_date || subscription?.next_billing_date || null)}`
          : `Next charge is expected on ${formatDateTime(renewalStatus.next_billing_date || subscription?.next_billing_date || null)}`;
      default:
        return renewalHelpText;
    }
  })();

  const getTierAccent = (tierId: string) => {
    switch (tierId) {
      case 'starter':
        return "border-t-4 border-t-orange-400";
      case 'professional':
        return "border-t-4 border-t-violet-500";
      case 'concierge':
        return "border-t-4 border-t-indigo-500";
      default:
        return "";
    }
  };

  return (
    <div className="space-y-8">
      {/* Current Subscription Status */}
      <div className="bg-white/50 backdrop-blur-sm rounded-xl p-6 border border-white/40">
        <h3 className="text-lg font-bold text-gray-900 mb-4">{t.dashboard.subscription.currentSubscription}</h3>
        {subscription ? (
          <div className="flex flex-wrap gap-6 items-center">
            <div className="flex items-center gap-3 bg-white/60 px-4 py-2 rounded-lg">
              <span className="text-sm font-medium text-gray-500">{t.dashboard.subscription.plan}:</span>
              <span className="text-sm font-bold text-gray-900">{getTierName(subscription.tier)}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium text-gray-500">{t.dashboard.subscription.status}:</span>
              {getStatusBadge(subscription.status)}
            </div>
            {subscription.trial_ends_at && (
              <div className="px-3 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded-full border border-blue-100">
                {t.dashboard.subscription.trialUntil} {new Date(subscription.trial_ends_at).toLocaleDateString(language === 'ru' ? 'ru-RU' : 'en-US')}
              </div>
            )}
            {subscription.subscription_ends_at && (
              <div className="px-3 py-1 bg-green-50 text-green-700 text-xs font-medium rounded-full border border-green-100">
                {t.dashboard.subscription.subscriptionUntil} {new Date(subscription.subscription_ends_at).toLocaleDateString(language === 'ru' ? 'ru-RU' : 'en-US')}
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-gray-500 italic">{t.dashboard.subscription.noSubscription}</p>
        )}
        <p className="mt-4 text-sm leading-6 text-gray-600 [text-wrap:pretty]">
          {language === 'ru'
            ? 'Оплата подписки проходит помесячно. Если вы сохраните карту при первой оплате, LocalOS сможет продлевать подписку автоматически до тех пор, пока вы не отвяжете карту в кабинете.'
            : 'Subscriptions are billed monthly. If you save your card during the first payment, LocalOS can renew the subscription automatically until you unlink the card in your account.'}
        </p>
      </div>

      <div className="overflow-hidden rounded-3xl border border-slate-200/80 bg-white shadow-sm">
        <div className="flex flex-col gap-4 border-b border-slate-100 px-5 py-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              {language === 'ru' ? 'Подписка' : 'Subscription'}
            </div>
            <h3 className="mt-2 text-xl font-semibold leading-7 text-slate-950 [text-wrap:balance]">
              {language === 'ru' ? 'Автоплатёж и отвязка карты' : 'Autopay and card unlinking'}
            </h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600 [text-wrap:pretty]">
              {renewalStatusText}
            </p>
          </div>
          <div className="flex shrink-0 flex-col gap-2 lg:max-w-sm">
            {!paymentMethodLinked ? (
              <>
                <Button
                  className="min-h-11 bg-slate-950 text-white hover:bg-slate-800 active:scale-[0.96] transition-transform"
                  disabled={processing || !subscription?.tier}
                  onClick={handlePaymentMethodSetup}
                >
                  {processing ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <CreditCard className="mr-2 h-4 w-4" />}
                  {language === 'ru' ? 'Оплатить и сохранить карту' : 'Pay and save card'}
                </Button>
                <p className="max-w-sm text-xs leading-5 text-slate-500 [text-wrap:pretty]">
                  {language === 'ru'
                    ? 'Откроется ЮKassa. После успешной оплаты карта будет сохранена для ежемесячного списания.'
                    : 'YooKassa will open. After successful payment, the card will be saved for monthly charging.'}
                </p>
              </>
            ) : (
              <>
                <label className="flex max-w-sm items-start gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm leading-5 text-slate-700">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4 rounded border-slate-300 text-slate-900"
                    checked={unlinkConfirmed}
                    disabled={unlinkingCard}
                    onChange={(event) => setUnlinkConfirmed(event.target.checked)}
                  />
                  <span>{cardRemovalCheckboxLabel}</span>
                </label>
                <Button
                  variant="outline"
                  className="min-h-11 active:scale-[0.96] transition-transform"
                  disabled={unlinkingCard || !unlinkConfirmed}
                  onClick={handleUnlinkCard}
                >
                  {unlinkingCard ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Link2Off className="mr-2 h-4 w-4" />}
                  {language === 'ru' ? 'Удалить карту' : 'Delete card'}
                </Button>
              </>
            )}
          </div>
        </div>
        <div className="grid gap-px bg-slate-100 sm:grid-cols-2 xl:grid-cols-4">
          <div className="bg-white px-5 py-4">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              <CreditCard className="h-4 w-4" />
              <span>{language === 'ru' ? 'Статус' : 'Status'}</span>
            </div>
            <div className="mt-3">
              <Badge className={cn('min-h-7 rounded-full px-3 text-sm', autopayStatusTone)}>
                {autopayStatusLabel}
              </Badge>
            </div>
            <div className="mt-2 text-sm leading-6 text-slate-600 [text-wrap:pretty]">
              {language === 'ru'
                ? 'Карту можно отвязать самостоятельно без обращения в поддержку.'
                : 'You can unlink the card yourself without contacting support.'}
            </div>
          </div>
          <div className="bg-white px-5 py-4">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              <CalendarClock className="h-4 w-4" />
              <span>{language === 'ru' ? 'Период оплачен до' : 'Paid until'}</span>
            </div>
            <div className="mt-2 text-lg font-semibold text-slate-950 tabular-nums">
              {billingLoading ? (language === 'ru' ? 'Загрузка...' : 'Loading...') : periodEndText}
            </div>
            <div className="mt-2 text-sm leading-6 text-slate-600 [text-wrap:pretty]">
              {language === 'ru'
                ? 'До этой даты доступ остаётся активным при успешной оплате периода.'
                : 'Access remains active until this date after a successful period payment.'}
            </div>
          </div>
          <div className="bg-white px-5 py-4">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              <CalendarClock className="h-4 w-4" />
              <span>{language === 'ru' ? 'Следующее списание' : 'Next charge'}</span>
            </div>
            <div className="mt-2 text-lg font-semibold text-slate-950 tabular-nums">
              {billingLoading ? (language === 'ru' ? 'Загрузка...' : 'Loading...') : nextChargeText}
            </div>
            <div className="mt-2 text-sm leading-6 text-slate-600 [text-wrap:pretty]">
              {language === 'ru'
                ? 'После отвязки карты новые автоматические списания не выполняются.'
                : 'After the card is unlinked, no new automatic charges will be made.'}
            </div>
          </div>
          <div className="bg-white px-5 py-4">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              <Check className="h-4 w-4" />
              <span>{language === 'ru' ? 'Сохранённая карта' : 'Saved card'}</span>
            </div>
            <div className="mt-2 text-lg font-semibold text-slate-950 [text-wrap:balance]">
              {paymentMethodLabel}
            </div>
            {latestAttempt ? (
              <div className="mt-2 text-sm leading-6 text-slate-600 [text-wrap:pretty]">
                {language === 'ru'
                  ? `Последняя попытка: ${formatDateTime(latestAttempt.created_at || null)}`
                  : `Last attempt: ${formatDateTime(latestAttempt.created_at || null)}`}
              </div>
            ) : (
              <div className="mt-2 text-sm leading-6 text-slate-600 [text-wrap:pretty]">
                {language === 'ru'
                  ? 'После первой успешной оплаты здесь появится статус сохранённой карты.'
                  : 'The saved card status will appear here after the first successful payment.'}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tiers Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
        {tiers.map((tier) => {
          const isCurrentTier = subscription?.tier === tier.id;
          const isActive = subscription?.status === 'active' && isCurrentTier;
          const isElite = tier.id === 'elite';
          const Icon = tier.icon || Star;

          return (
            <div
              key={tier.id}
              className={cn(
                "relative flex flex-col h-full rounded-2xl p-6 transition-all duration-300 group",
                !isElite && getTierAccent(tier.id),
                isActive
                  ? "bg-white border-2 border-emerald-500 shadow-xl scale-[1.02]"
                  : "bg-white border border-slate-200/90 shadow-sm hover:shadow-lg hover:-translate-y-1",
                isElite && "bg-gradient-to-b from-slate-900 to-slate-800 border border-slate-700 text-white shadow-xl"
              )}
            >
              {tier.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-orange-500 to-pink-500 text-white text-[10px] font-bold uppercase tracking-wider px-3 py-1 rounded-full shadow-lg">
                  {language === 'ru' ? 'Популярный' : 'Popular'}
                </div>
              )}

              <div className="mb-6">
                <div className={cn(
                  "w-12 h-12 rounded-xl flex items-center justify-center mb-4 shadow-sm",
                  isElite ? "bg-white/10 text-yellow-400" : "bg-white text-indigo-600"
                )}>
                  <Icon className="w-6 h-6" />
                </div>
                <h3 className={cn("text-xl font-bold mb-2", isElite ? "text-white" : "text-gray-900")}>
                  {tier.name}
                </h3>

                <div className="flex items-baseline gap-1">
                  {isElite ? (
                    <span className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-yellow-300 to-amber-500">
                      7%
                    </span>
                  ) : (
                    <span className={cn("text-3xl font-bold", isElite ? "text-white" : "text-gray-900")}>
                      {tier.period.startsWith(tier.currency) ? tier.price : `${tier.currency}${tier.price}`}
                    </span>
                  )}
                  {isElite ? (
                    <span className="text-xs text-gray-400 font-medium">
                      {language === 'ru' ? ' от оплат привлечённых клиентов' : t.dashboard.subscription.fromReferrals}
                    </span>
                  ) : (
                    <span className={cn("text-xs font-medium", isElite ? "text-gray-400" : "text-gray-500")}>
                      {tier.period}
                    </span>
                  )}
                </div>
                {tier.lead && (
                  <div className={cn("mt-2 text-sm", isElite ? "text-gray-300" : "text-gray-600")}>
                    {tier.lead}
                  </div>
                )}
              </div>

              <ul className="space-y-3 flex-1 mb-8">
                {tier.features.map((feature, idx) => (
                  <li key={idx} className="flex items-start text-sm">
                    <div className={cn(
                      "mt-0.5 mr-3 flex-shrink-0 w-4 h-4 rounded-full flex items-center justify-center",
                      isElite ? "bg-green-500/20 text-green-400" : "bg-green-100 text-green-600"
                    )}>
                      <Check className="w-2.5 h-2.5" />
                    </div>
                    <span className={isElite ? "text-gray-300" : "text-gray-600"}>{feature}</span>
                  </li>
                ))}
              </ul>

              <Button
                className={cn(
                  "w-full font-semibold transition-all duration-300 rounded-xl py-6",
                  isElite
                    ? "bg-gradient-to-r from-yellow-400 to-amber-600 hover:from-yellow-300 hover:to-amber-500 text-black border-0 shadow-lg shadow-amber-900/20"
                    : isActive
                      ? "bg-emerald-100 text-emerald-700 hover:bg-emerald-200 border-0"
                      : "bg-gray-900 text-white hover:bg-gray-800 shadow-md hover:shadow-xl"
                )}
                disabled={isActive || processing || isModerationPending || (isElite && false)}
                onClick={() => {
                  if (tier.id === 'elite') {
                    toast({
                      title: "Contact Manager",
                      description: "Please contact support to activate Elite plan.",
                    });
                  } else {
                    handleSubscribe(tier.id);
                  }
                }}
              >
                {tier.id === 'elite'
                  ? t.dashboard.subscription.contactUs
                  : isActive
                    ? (
                      <span className="flex items-center gap-2">
                        <Check className="w-4 h-4" /> {t.dashboard.subscription.currentPlan}
                      </span>
                    )
                    : isCurrentTier
                      ? t.dashboard.subscription.update
                      : processing
                        ? <span className="animate-pulse">{t.dashboard.subscription.processing}</span>
                        : t.dashboard.subscription.select}
              </Button>
            </div>
          );
        })}
      </div>
    </div>
  );
};
