import { useState, useEffect, useRef, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { useSearchParams } from 'react-router-dom';
import { useLanguage } from '@/i18n/LanguageContext';

interface SubscriptionTier {
  id: string;
  name: string;
  price: number;
  currency: string;
  period: string;
  features: string[];
  stripe_price_id?: string;
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
      // Очищаем параметр из URL
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

  // Если пользователь пришёл из лендинга с выбранным тарифом и флагом payment=required,
  // автоматически запускаем создание checkout-сессии для этого тарифа.
  useEffect(() => {
    if (autoCheckoutStartedRef.current) return;
    if (processing) return;
    if (paymentStatus !== 'required') return;

    const tierId = selectedTierFromUrl || 'starter';
    if (!tierId) return;

    // Если подписка уже активна на этом тарифе — не запускаем оплату повторно
    if (subscription && subscription.status === 'active' && subscription.tier === tierId) {
      return;
    }

    autoCheckoutStartedRef.current = true;
    handleSubscribe(tierId);
  }, [paymentStatus, selectedTierFromUrl, subscription, processing]);

  const handleSubscribe = async (tierId: string) => {
    if (!businessId) {
      toast({
        title: t.error,
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
        // Перенаправляем на Stripe Checkout
        window.location.href = data.url;
      } else {
        toast({
          title: t.error,
          description: data.error || (language === 'ru' ? 'Не удалось создать сессию оплаты' : 'Failed to create payment session'),
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: t.error,
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
        return <Badge className="bg-green-500">{language === 'ru' ? 'Активна' : 'Active'}</Badge>;
      case 'pending':
        return <Badge className="bg-yellow-500">{language === 'ru' ? 'Ожидает оплаты' : 'Pending Payment'}</Badge>;
      case 'cancelled':
        return <Badge className="bg-red-500">{language === 'ru' ? 'Отменена' : 'Cancelled'}</Badge>;
      default:
        return <Badge className="bg-gray-500">{language === 'ru' ? 'Неактивна' : 'Inactive'}</Badge>;
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center">{language === 'ru' ? 'Загрузка...' : 'Loading...'}</div>
        </CardContent>
      </Card>
    );
  }

  const isModerationPending = subscription?.moderation_status === 'pending';

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>{t.dashboard.subscription.currentSubscription}</CardTitle>
          <CardDescription>
            {t.dashboard.subscription.manage}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {subscription && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{t.dashboard.subscription.plan}:</span>
                <span className="text-sm">{getTierName(subscription.tier)}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{t.dashboard.subscription.status}:</span>
                {getStatusBadge(subscription.status)}
              </div>
              {subscription.trial_ends_at && (
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{t.dashboard.subscription.trialUntil}:</span>
                  <span className="text-sm">
                    {new Date(subscription.trial_ends_at).toLocaleDateString(language === 'ru' ? 'ru-RU' : 'en-US')}
                  </span>
                </div>
              )}
              {subscription.subscription_ends_at && (
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{t.dashboard.subscription.subscriptionUntil}:</span>
                  <span className="text-sm">
                    {new Date(subscription.subscription_ends_at).toLocaleDateString(language === 'ru' ? 'ru-RU' : 'en-US')}
                  </span>
                </div>
              )}
            </div>
          )}

          {!subscription && (
            <div className="text-center py-4">
              <p className="text-sm text-gray-600 mb-4">
                {t.dashboard.subscription.noSubscription}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t.dashboard.subscription.availablePlans}</CardTitle>
          <CardDescription>
            {t.dashboard.subscription.choosePlan}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-stretch">
            {tiers.map((tier) => {
              const isCurrentTier = subscription?.tier === tier.id;
              const isActive = subscription?.status === 'active' && isCurrentTier;

              return (
                <Card
                  key={tier.id}
                  className={`${isCurrentTier ? 'border-indigo-500 border-2' : ''} h-full`}
                >
                  <div className="flex flex-col h-full">
                    {/* Верхний невидимый блок: заголовок + особенности */}
                    <div className="flex-1 flex flex-col">
                      <CardHeader>
                        <CardTitle className="text-xl">{tier.name}</CardTitle>
                        <div className="mt-2">
                          {tier.id === 'elite' ? (
                            <>
                              <span className="text-3xl font-bold">7%</span>
                              <span className="text-gray-500">{t.dashboard.subscription.fromReferrals}</span>
                            </>
                          ) : (
                            <>
                              <span className="text-3xl font-bold">{tier.currency}{tier.price}</span>
                              <span className="text-gray-500">{tier.period}</span>
                            </>
                          )}
                        </div>
                        {tier.id === 'elite' && (
                          <p className="text-xs text-gray-500 mt-2">
                            {t.dashboard.subscription.after3Months}
                          </p>
                        )}
                      </CardHeader>
                      <CardContent className="space-y-4 flex-1">
                        <ul className="space-y-2">
                          {tier.features.map((feature, idx) => (
                            <li key={idx} className="text-sm flex items-start">
                              <span className="text-green-500 mr-2">✓</span>
                              <span>{feature}</span>
                            </li>
                          ))}
                        </ul>
                      </CardContent>
                    </div>

                    {/* Нижний невидимый блок: кнопка */}
                    <CardFooter className="mt-auto pt-2">
                      <Button
                        className="w-full"
                        variant={isCurrentTier ? 'outline' : 'default'}
                        disabled={isActive || processing || isModerationPending || tier.id === 'elite'}
                        onClick={() => {
                          if (tier.id === 'elite') {
                            toast({
                              title: t.dashboard.subscription.eliteFeature5, // Use manager title or similar
                              description: t.dashboard.subscription.after3Months,
                            });
                          } else {
                            handleSubscribe(tier.id);
                          }
                        }}
                      >
                        {tier.id === 'elite'
                          ? t.dashboard.subscription.contactUs
                          : isActive
                            ? t.dashboard.subscription.currentPlan
                            : isCurrentTier
                              ? t.dashboard.subscription.update
                              : processing
                                ? t.dashboard.subscription.processing
                                : t.dashboard.subscription.select}
                      </Button>
                    </CardFooter>
                  </div>
                </Card>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
