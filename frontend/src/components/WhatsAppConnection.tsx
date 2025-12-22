import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Alert, AlertDescription } from './ui/alert';
import { Loader2, MessageCircle, CheckCircle2 } from 'lucide-react';
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
    } catch (e: any) {
      const errorMsg = 'Ошибка подключения к серверу: ' + e.message;
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
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageCircle className="h-5 w-5" />
          Подключение WhatsApp
        </CardTitle>
        <CardDescription>
          Укажите номер WhatsApp для получения уведомлений о новых заявках
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
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
            disabled={saving || loading}
          />
          <p className="text-xs text-gray-500">
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
          disabled={saving || loading || !whatsappPhone}
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

        <div className="pt-4 border-t">
          <h4 className="text-sm font-medium mb-2">Возможности:</h4>
          <ul className="list-disc list-inside space-y-1 text-sm text-gray-600">
            <li>🔔 Уведомления о новых заявках из ChatGPT</li>
            <li>📱 Получение информации о клиентах</li>
            <li>⏰ Напоминания о предстоящих записях</li>
          </ul>
        </div>
      </CardContent>
    </Card>
  );
};

export default WhatsAppConnection;

