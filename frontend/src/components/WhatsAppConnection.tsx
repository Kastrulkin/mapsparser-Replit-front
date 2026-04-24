import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Alert, AlertDescription } from './ui/alert';
import { Loader2, MessageCircle, CheckCircle2, Clock3 } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface WhatsAppConnectionProps {
  currentBusinessId?: string | null;
  business?: any;
}

const WhatsAppConnection: React.FC<WhatsAppConnectionProps> = ({ currentBusinessId, business }) => {
  const [whatsappPhone, setWhatsappPhone] = useState('');
  const [isVerified, setIsVerified] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    if (business) {
      setWhatsappPhone(business.whatsapp_phone || '');
      setIsVerified(business.whatsapp_verified === 1);
    }
  }, [business]);

  const handleSave = async () => {
    if (!currentBusinessId) {
      setError('Сначала выберите бизнес');
      return;
    }

    if (!whatsappPhone) {
      setError('Введите номер WhatsApp');
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch('/api/business/whatsapp/verify', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          business_id: currentBusinessId,
          whatsapp_phone: whatsappPhone
        })
      });

      const data = await response.json();

      if (response.ok) {
        setSuccess('Номер WhatsApp сохранён!');
        setIsVerified(data.verified || false);
        toast({
          title: 'Успешно',
          description: 'Номер WhatsApp сохранён. После верификации вы сможете получать уведомления.',
        });
      } else {
        setError(data.error || 'Ошибка сохранения номера');
        toast({
          title: 'Ошибка',
          description: data.error || 'Не удалось сохранить номер WhatsApp',
          variant: 'destructive',
        });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'неизвестная ошибка';
      const errorMsg = `Ошибка подключения к серверу: ${message}`;
      setError(errorMsg);
      toast({
        title: 'Ошибка',
        description: errorMsg,
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="relative overflow-hidden rounded-3xl border-slate-200/80 bg-white shadow-sm">
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-slate-950">
              <span className="flex h-9 w-9 items-center justify-center rounded-2xl bg-slate-100 text-slate-700">
                <MessageCircle className="h-4 w-4" />
              </span>
              Подключение WhatsApp
            </CardTitle>
            <CardDescription className="mt-2 leading-6">
              Канал для уведомлений и будущей автоматической отправки сообщений клиентам.
            </CardDescription>
          </div>
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700 ring-1 ring-amber-200">
            <Clock3 className="h-3.5 w-3.5" />
            Скоро
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="rounded-2xl border border-amber-200 bg-amber-50/80 p-4 text-sm leading-6 text-amber-900">
          WhatsApp сейчас показан как будущий канал. Настройка номера сохранена в интерфейсе, но отправка будет доступна после подключения WABA/провайдера.
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {success && (
          <Alert>
            <AlertDescription>{success}</AlertDescription>
          </Alert>
        )}

        <div className="space-y-2">
          <label htmlFor="whatsapp-phone" className="text-sm font-medium">
            Номер WhatsApp
          </label>
          <Input
            id="whatsapp-phone"
            type="tel"
            placeholder="+1234567890"
            value={whatsappPhone}
            onChange={(e) => setWhatsappPhone(e.target.value)}
            disabled
          />
          <p className="text-xs text-slate-500">
            Введите номер в международном формате (например, +1234567890)
          </p>
        </div>

        {isVerified && (
          <div className="flex items-center gap-2 text-green-600">
            <CheckCircle2 className="h-4 w-4" />
            <span className="text-sm">WhatsApp номер верифицирован</span>
          </div>
        )}

        <Button
          onClick={handleSave}
          disabled
          className="w-full"
        >
          {saving ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Сохранение...
            </>
          ) : (
            'Сохранить номер'
          )}
        </Button>

        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
          <h4 className="mb-2 text-sm font-semibold text-slate-900">Что даст подключение</h4>
          <ul className="space-y-1 text-sm leading-6 text-slate-600">
            <li>Уведомления о новых заявках из каналов LocalOS</li>
            <li>Передача клиентского контекста в карточку бизнеса</li>
            <li>Напоминания и последующие сообщения после записи</li>
          </ul>
        </div>
      </CardContent>
    </Card>
  );
};

export default WhatsAppConnection;
