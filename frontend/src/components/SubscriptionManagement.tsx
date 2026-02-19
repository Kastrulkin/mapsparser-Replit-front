import { useState, useEffect, useRef, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { useSearchParams } from 'react-router-dom';
import { useLanguage } from '@/i18n/LanguageContext';
import { cn } from '@/lib/utils';
import { DESIGN_TOKENS } from '@/lib/design-tokens';
import { Check, Crown, Sparkles, Zap, Shield, Star, Rocket } from 'lucide-react';

interface SubscriptionTier {
  id: string;
  name: string;
  price: number;
  currency: string;
  period: string;
  features: string[];
  stripe_price_id?: string;
  icon?: any;
  popular?: boolean;
}

interface BusinessSubscription {
  tier: string;
  status: string;
  subscription_ends_at?: string;
  trial_ends_at?: string;
  moderation_status?: string;
}

export const SubscriptionManagement = ({ businessId, business }: { businessId: string | null; business: any }) => {
  const [subscription, setSubscription] = useState<BusinessSubscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const { toast } = useToast();
  const [searchParams] = useSearchParams();
  const paymentStatus = searchParams.get('payment');
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
        period: t.dashboard.subscription.perMonth,
        icon: Rocket,
        features: [
          t.dashboard.subscription.starterFeature1,
          t.dashboard.subscription.starterFeature2,
          t.dashboard.subscription.starterFeature3
        ]
      },
      {
        id: 'professional',
        name: isRu ? 'Профессиональный' : 'Professional',
        price: isRu ? 5000 : 55,
        currency: isRu ? '₽' : '$',
        period: t.dashboard.subscription.perMonth,
        popular: true,
        icon: Zap,
        features: [
          t.dashboard.subscription.profFeature1,
          t.dashboard.subscription.profFeature2,
          t.dashboard.subscription.profFeature3,
          t.dashboard.subscription.profFeature4
        ]
      },
      {
        id: 'concierge',
        name: isRu ? 'Консьерж' : 'Concierge',
        price: isRu ? 25000 : 310,
        currency: isRu ? '₽' : '$',
        period: t.dashboard.subscription.perMonth,
        icon: Crown,
        features: [
          t.dashboard.subscription.conciergeFeature1,
          t.dashboard.subscription.conciergeFeature2,
          t.dashboard.subscription.conciergeFeature3,
          t.dashboard.subscription.conciergeFeature4,
          t.dashboard.subscription.conciergeFeature5
        ]
      },
      {
        id: 'elite',
        name: isRu ? 'Особый (Elite)' : 'Elite',
        price: 0,
        currency: '',
        period: '',
        icon: Shield,
        features: [
          t.dashboard.subscription.eliteFeature1,
          t.dashboard.subscription.eliteFeature2,
          t.dashboard.subscription.eliteFeature3,
          t.dashboard.subscription.eliteFeature4,
          t.dashboard.subscription.eliteFeature5
        ]
      }
    ];
  }, [language, t]);

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
    if (business) {
      setSubscription({
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
    if (autoCheckoutStartedRef.current) return;
    if (processing) return;
    if (paymentStatus !== 'required') return;

    const tierId = selectedTierFromUrl || 'starter';
    if (!tierId) return;

    if (subscription && subscription.status === 'active' && subscription.tier === tierId) {
      return;
    }

    autoCheckoutStartedRef.current = true;
    handleSubscribe(tierId);
  }, [paymentStatus, selectedTierFromUrl, subscription, processing]);

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
      const response = await fetch('/api/stripe/create-checkout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          business_id: businessId,
          tier: tierId
        })
      });

      const data = await response.json();

      if (response.ok && data.url) {
        window.location.href = data.url;
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

  const getTierName = (tierId: string) => {
    const tier = tiers.find(t => t.id === tierId);
    return tier ? tier.name : tierId;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge className="bg-emerald-500 hover:bg-emerald-600 border-0">{language === 'ru' ? 'Активна' : 'Active'}</Badge>;
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
                isActive
                  ? "bg-white/80 border-2 border-emerald-500 shadow-xl scale-[1.02]"
                  : "bg-white/40 border border-white/50 hover:bg-white/60 hover:shadow-lg hover:-translate-y-1",
                isElite && "bg-gradient-to-b from-slate-900 to-slate-800 border-slate-700 text-white"
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
                      {t.dashboard.subscription.fromReferrals}
                    </span>
                  ) : (
                    <span className={cn("text-xs font-medium", isElite ? "text-gray-400" : "text-gray-500")}>
                      {tier.period}
                    </span>
                  )}
                </div>
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
