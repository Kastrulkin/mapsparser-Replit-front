import { useState, useEffect } from 'react';
import { useLanguage } from '@/i18n/LanguageContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useToast } from '@/hooks/use-toast';
import { Loader2, Bot, Eye, EyeOff } from 'lucide-react';

interface TelegramBotCredentialsProps {
  businessId: string | null;
  business: any;
}

export const TelegramBotCredentials = ({ businessId, business }: TelegramBotCredentialsProps) => {
  const [botToken, setBotToken] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    if (business) {
      setBotToken(business.telegram_bot_token || '');
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

    if (!botToken) {
      toast({
        title: 'Ошибка',
        description: 'Введите токен бота',
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
          telegram_bot_token: botToken
        })
      });

      const data = await response.json();

      if (response.ok) {
        toast({
          title: 'Успешно',
          description: 'Токен Telegram бота сохранён',
        });
      } else {
        toast({
          title: 'Ошибка',
          description: data.error || 'Не удалось сохранить токен',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Ошибка при сохранении токена',
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
          <Bot className="h-5 w-5" />
          Токен Telegram бота
        </CardTitle>
        <CardDescription>
          Укажите токен вашего Telegram бота для отправки сообщений клиентам
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Alert>
          <AlertDescription>
            Если у вас есть собственный Telegram бот, укажите здесь его токен.
            Это позволит отправлять сообщения клиентам через ИИ агента со своего бота.
          </AlertDescription>
        </Alert>

        <div className="space-y-2">
          <Label htmlFor="telegram-bot-token">{ t.dashboard.settings.telegram2.tokenLabel}</Label>
          <div className="relative">
            <Input
              id="telegram-bot-token"
              type={showToken ? 'text' : 'password'}
              placeholder="Введите токен бота"
              value={botToken}
              onChange={(e) => setBotToken(e.target.value)}
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
            Токен можно получить у @BotFather в Telegram
          </p>
        </div>

        <Button
          onClick={handleSave}
          disabled={saving || !botToken}
          className="w-full"
        >
          {saving ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Сохранение...
            </>
          ) : (
            'Сохранить токен'
          )}
        </Button>
      </CardContent>
    </Card>
  );
};

