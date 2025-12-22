import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useToast } from '@/hooks/use-toast';
import { Loader2, MessageCircle, Eye, EyeOff } from 'lucide-react';

interface WABACredentialsProps {
  businessId: string | null;
  business: any;
}

export const WABACredentials = ({ businessId, business }: WABACredentialsProps) => {
  const [phoneId, setPhoneId] = useState('');
  const [accessToken, setAccessToken] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    if (business) {
      setPhoneId(business.waba_phone_id || '');
      setAccessToken(business.waba_access_token || '');
    }
  }, [business]);

  const handleSave = async () => {
    if (!businessId) {
      toast({
        title: 'Ошибка',
        description: 'Бизнес не выбран',
        variant: 'destructive',
      });
      return;
    }

    if (!phoneId || !accessToken) {
      toast({
        title: 'Ошибка',
        description: 'Заполните все поля',
        variant: 'destructive',
      });
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch('/api/business/profile', {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          business_id: businessId,
          waba_phone_id: phoneId,
          waba_access_token: accessToken
        })
      });

      const data = await response.json();

      if (response.ok) {
        toast({
          title: 'Успешно',
          description: 'Учётные данные WABA сохранены',
        });
      } else {
        toast({
          title: 'Ошибка',
          description: data.error || 'Не удалось сохранить данные',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Ошибка при сохранении данных',
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
          Учётные данные WhatsApp Business API
        </CardTitle>
        <CardDescription>
          Укажите ваши учётные данные WABA для отправки сообщений со своего номера
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Alert>
          <AlertDescription>
            Если у вас есть собственный аккаунт WhatsApp Business API, укажите здесь ваши учётные данные.
            Это позволит отправлять сообщения клиентам со своего номера через ИИ агента.
          </AlertDescription>
        </Alert>

        <div className="space-y-2">
          <Label htmlFor="waba-phone-id">Phone ID</Label>
          <Input
            id="waba-phone-id"
            type="text"
            placeholder="Введите Phone ID"
            value={phoneId}
            onChange={(e) => setPhoneId(e.target.value)}
            disabled={saving}
          />
          <p className="text-xs text-gray-500">
            Phone ID вашего WhatsApp Business аккаунта
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="waba-access-token">Access Token</Label>
          <div className="relative">
            <Input
              id="waba-access-token"
              type={showToken ? 'text' : 'password'}
              placeholder="Введите Access Token"
              value={accessToken}
              onChange={(e) => setAccessToken(e.target.value)}
              disabled={saving}
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="absolute right-0 top-0 h-full px-3"
              onClick={() => setShowToken(!showToken)}
            >
              {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </Button>
          </div>
          <p className="text-xs text-gray-500">
            Access Token для доступа к WhatsApp Business API
          </p>
        </div>

        <Button
          onClick={handleSave}
          disabled={saving || !phoneId || !accessToken}
          className="w-full"
        >
          {saving ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Сохранение...
            </>
          ) : (
            'Сохранить учётные данные'
          )}
        </Button>
      </CardContent>
    </Card>
  );
};

