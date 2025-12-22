import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { useSearchParams } from 'react-router-dom';

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
    id: 'basic',
    name: 'STARTER',
    price: 5,
    features: [
      'Подключитесь к профессиональной сети Beautybot',
      'Начните использовать ChatGPT для лидогенерации',
      'Идеально для тех, кто ищет новые каналы привлечения клиентов'
    ]
  },
  {
    id: 'pro',
    name: 'PROFESSIONAL (Most Popular)',
    price: 65,
    features: [
      'Полный набор инструментов для растущего бизнеса',
      'Управление клиентами и автоматизация переписки',
      'Интеграция с CRM',
      'Выбирают 70% специалистов'
    ]
  },
  {
    id: 'enterprise',
    name: 'CONCIERGE',
    price: 310,
    features: [
      'Мы делаем всё за вас',
      'Персональная настройка и приоритетная поддержка',
      'Стратегия развития вашего бизнеса',
      'Идеально для амбициозных лидеров'
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
    return TIERS.find(t => t.id === tierId)?.name || tierId;
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
          {isModerationPending && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <p className="text-sm text-yellow-800">
                ⏳ Ваш бизнес ожидает модерации. После одобрения вы сможете выбрать тариф.
              </p>
            </div>
          )}

          {subscription && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Тариф:</span>
                <span className="text-sm">{getTierName(subscription.tier)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Статус:</span>
                {getStatusBadge(subscription.status)}
              </div>
              {subscription.trial_ends_at && (
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Триал до:</span>
                  <span className="text-sm">
                    {new Date(subscription.trial_ends_at).toLocaleDateString('ru-RU')}
                  </span>
                </div>
              )}
              {subscription.subscription_ends_at && (
                <div className="flex items-center justify-between">
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
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {TIERS.map((tier) => {
              const isCurrentTier = subscription?.tier === tier.id;
              const isActive = subscription?.status === 'active' && isCurrentTier;

              return (
                <Card key={tier.id} className={isCurrentTier ? 'border-indigo-500 border-2' : ''}>
                  <CardHeader>
                    <CardTitle className="text-xl">{tier.name}</CardTitle>
                    <div className="mt-2">
                      <span className="text-3xl font-bold">${tier.price}</span>
                      <span className="text-gray-500">/месяц</span>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <ul className="space-y-2">
                      {tier.features.map((feature, idx) => (
                        <li key={idx} className="text-sm flex items-start">
                          <span className="text-green-500 mr-2">✓</span>
                          <span>{feature}</span>
                        </li>
                      ))}
                    </ul>
                    <Button
                      className="w-full"
                      variant={isCurrentTier ? 'outline' : 'default'}
                      disabled={isActive || processing || isModerationPending}
                      onClick={() => handleSubscribe(tier.id)}
                    >
                      {isActive
                        ? 'Текущий тариф'
                        : isCurrentTier
                        ? 'Обновить'
                        : processing
                        ? 'Обработка...'
                        : 'Выбрать'}
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          <div className="mt-6 p-4 bg-blue-50 rounded-lg">
            <p className="text-sm text-blue-800">
              💡 <strong>Специальное предложение:</strong> Первый месяц полного доступа (как в тарифе "Профессиональный") 
              всего за $5! После первого месяца функции вернутся к базовому тарифу, если вы не перейдёте на тариф $65.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

