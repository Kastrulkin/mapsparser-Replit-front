import { useState, useEffect, useRef } from 'react';
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

const TIERS: SubscriptionTier[] = [
  {
    id: 'starter',
    name: 'Starter (Начальный)',
    price: 5,
    features: [
      'Подключитесь к профессиональной сети Beautybot',
      'Начните использовать ChatGPT для лидогенерации',
      'Идеально для тех, кто ищет новые каналы привлечения клиентов'
    ]
  },
  {
    id: 'professional',
    name: 'Профессиональный',
    price: 55,
    features: [
      'Работайте над карточкой, подскажем каждый шаг',
      'Оптимизируйте процесс на основе лучших практик',
      'Генерация новостей',
      'Генерация ответов на отзывы'
    ]
  },
  {
    id: 'concierge',
    name: 'Консьерж',
    price: 310,
    features: [
      'Карточка компании на картах',
      'Коммуникация с клиентами',
      'Допродажи и кросс-продажи',
      'Оптимизация бизнес-процессов',
      'Выделенный менеджер'
    ]
  },
  {
    id: 'elite',
    name: 'Особый (Elite)',
    price: 0,
    features: [
      'Привлечение клиентов онлайн',
      'Коммуникация с клиентами',
      'Привлечение клиентов оффлайн',
      'Оптимизация бизнес-процессов',
      'Выделенный менеджер'
    ]
  }
];

export const SubscriptionManagement = ({ businessId, business }: { businessId: string | null; business: any }) => {
  const [subscription, setSubscription] = useState<BusinessSubscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const { toast } = useToast();
  const [searchParams] = useSearchParams();
  const paymentStatus = searchParams.get('payment');
  const selectedTierFromUrl = searchParams.get('tier');
  const autoCheckoutStartedRef = useRef(false);
  const { language } = useLanguage();

  useEffect(() => {
    if (paymentStatus === 'success') {
      toast({
        title: 'Оплата успешна!',
        description: 'Ваша подписка активирована.',
      });
      // Очищаем параметр из URL
      window.history.replaceState({}, '', window.location.pathname);
    } else if (paymentStatus === 'cancelled') {
      toast({
        title: 'Оплата отменена',
        description: 'Вы можете выбрать тариф позже.',
        variant: 'destructive',
      });
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [paymentStatus, toast]);

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
        title: 'Ошибка',
        description: 'Бизнес не выбран',
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
          title: 'Ошибка',
          description: data.error || 'Не удалось создать сессию оплаты',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Ошибка при создании сессии оплаты',
        variant: 'destructive',
      });
    } finally {
      setProcessing(false);
    }
  };

  const getTierName = (tierId: string) => {
    if (language === 'ru') {
      switch (tierId) {
        case 'starter':
          return 'Начальный';
        case 'professional':
          return 'Профессиональный';
        case 'concierge':
          return 'Консьерж';
        case 'elite':
          return 'Особый';
        default:
          return tierId;
      }
    }
    // Для всех не-русских языков используем английские названия
    switch (tierId) {
      case 'starter':
        return 'Starter';
      case 'professional':
        return 'Professional';
      case 'concierge':
        return 'Concierge';
      case 'elite':
        return 'Elite';
      default:
        return tierId;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge className="bg-green-500">Активна</Badge>;
      case 'pending':
        return <Badge className="bg-yellow-500">Ожидает оплаты</Badge>;
      case 'cancelled':
        return <Badge className="bg-red-500">Отменена</Badge>;
      default:
        return <Badge className="bg-gray-500">Неактивна</Badge>;
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center">Загрузка...</div>
        </CardContent>
      </Card>
    );
  }

  const currentTier = TIERS.find(t => t.id === subscription?.tier);
  const isModerationPending = subscription?.moderation_status === 'pending';

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Текущая подписка</CardTitle>
          <CardDescription>
            Управляйте своей подпиской и тарифом
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {subscription && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">Тариф:</span>
                <span className="text-sm">{getTierName(subscription.tier)}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">Статус:</span>
                {getStatusBadge(subscription.status)}
              </div>
              {subscription.trial_ends_at && (
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Триал до:</span>
                  <span className="text-sm">
                    {new Date(subscription.trial_ends_at).toLocaleDateString('ru-RU')}
                  </span>
                </div>
              )}
              {subscription.subscription_ends_at && (
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Подписка до:</span>
                  <span className="text-sm">
                    {new Date(subscription.subscription_ends_at).toLocaleDateString('ru-RU')}
                  </span>
                </div>
              )}
            </div>
          )}

          {!subscription && (
            <div className="text-center py-4">
              <p className="text-sm text-gray-600 mb-4">
                У вас нет активной подписки. Выберите тариф ниже.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Доступные тарифы</CardTitle>
          <CardDescription>
            Выберите подходящий тариф для вашего бизнеса
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-stretch">
            {TIERS.map((tier) => {
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
                        <CardTitle className="text-xl">{getTierName(tier.id)}</CardTitle>
                        <div className="mt-2">
                          {tier.id === 'elite' ? (
                            <>
                              <span className="text-3xl font-bold">7%</span>
                              <span className="text-gray-500"> от оплат привлечённых клиентов</span>
                            </>
                          ) : (
                            <>
                              <span className="text-3xl font-bold">${tier.price}</span>
                              <span className="text-gray-500">/месяц</span>
                            </>
                          )}
                        </div>
                        {tier.id === 'elite' && (
                          <p className="text-xs text-gray-500 mt-2">
                            Доступно после 3 месяцев подписки или по рекомендации
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
                              title: 'Особый тариф',
                              description:
                                'Для подключения тарифа Elite свяжитесь с нами. Доступно после 3 месяцев подписки или по рекомендации.',
                            });
                          } else {
                            handleSubscribe(tier.id);
                          }
                        }}
                      >
                        {tier.id === 'elite'
                          ? 'Связаться с нами'
                          : isActive
                          ? 'Текущий тариф'
                          : isCurrentTier
                          ? 'Обновить'
                          : processing
                          ? 'Обработка...'
                          : 'Выбрать'}
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

