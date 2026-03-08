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
  const { t } = useLanguage();
  const [botToken, setBotToken] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [saving, setSaving] = useState(false);
  const [configured, setConfigured] = useState(false);
  const [maskedToken, setMaskedToken] = useState<string | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    setBotToken('');
    setShowToken(false);
    setConfigured(Boolean(business?.telegram_bot_token_configured));
    setMaskedToken(business?.telegram_bot_token_masked || null);
  }, [business?.id, business?.telegram_bot_token_configured, business?.telegram_bot_token_masked]);

  useEffect(() => {
    const fetchStatus = async () => {
      if (!businessId) {
        setConfigured(false);
        setMaskedToken(null);
        return;
      }
      try {
        setLoadingStatus(true);
        const token = localStorage.getItem('auth_token');
        const response = await fetch(`/api/business/telegram-bot/status?business_id=${encodeURIComponent(businessId)}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });
        const data = await response.json();
        if (response.ok && data?.success) {
          setConfigured(Boolean(data.configured));
          setMaskedToken(data.masked_token || null);
        }
      } catch {
        // no-op: fallback is business payload state
      } finally {
        setLoadingStatus(false);
      }
    };
    fetchStatus();
  }, [businessId]);

  const handleSave = async () => {
    if (!businessId) {
      toast({
        title: t.common.error,
        description: t.dashboard.settings.telegram2.selectBusiness,
        variant: 'destructive',
      });
      return;
    }

    if (!botToken) {
      toast({
        title: t.common.error,
        description: t.dashboard.settings.telegram2.errorEmpty,
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
        setBotToken('');
        setShowToken(false);
        setConfigured(true);
        setMaskedToken('Сохранён');
        toast({
          title: t.common.success,
          description: t.dashboard.settings.telegram2.successSave,
        });
      } else {
        toast({
          title: t.common.error,
          description: data.error || t.dashboard.settings.telegram2.errorSave,
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: t.common.error,
        description: t.dashboard.settings.telegram2.errorSave,
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    if (!businessId) return;
    try {
      setLoadingStatus(true);
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`/api/business/telegram-bot/status?business_id=${encodeURIComponent(businessId)}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      const data = await response.json();
      if (response.ok && data?.success && data.configured) {
        toast({
          title: 'Подключение активно',
          description: `Telegram bot token подключён (${data.masked_token || 'скрыт'})`,
        });
      } else {
        toast({
          title: t.common.error,
          description: 'Токен Telegram бота не подключён или недоступен.',
          variant: 'destructive',
        });
      }
    } catch (e: any) {
      toast({
        title: t.common.error,
        description: e?.message || 'Не удалось проверить подключение Telegram бота.',
        variant: 'destructive',
      });
    } finally {
      setLoadingStatus(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bot className="h-5 w-5" />
          {t.dashboard.settings.telegram2.title}
        </CardTitle>
        <CardDescription>
          {t.dashboard.settings.telegram2.description}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Alert>
          <AlertDescription>
            {t.dashboard.settings.telegram2.subtitle}
            {t.dashboard.settings.telegram2.alert}
          </AlertDescription>
        </Alert>

        <div className="space-y-2">
          <Label htmlFor="telegram-bot-token">{t.dashboard.settings.telegram2.tokenLabel}</Label>
          <div className="text-xs text-gray-500">
            {loadingStatus
              ? 'Проверка статуса токена...'
              : configured
                ? `Токен подключён (${maskedToken || 'скрыт'})`
                : 'Токен пока не подключён'}
          </div>
          <div className="relative">
            <Input
              id="telegram-bot-token"
              type={showToken ? 'text' : 'password'}
              placeholder={t.dashboard.settings.telegram2.tokenPlaceholder}
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
            {t.dashboard.settings.telegram2.tokenHelp}
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
              {t.dashboard.settings.telegram2.saving}
            </>
          ) : (
            t.dashboard.settings.telegram2.saveButton
          )}
        </Button>

        <Button
          type="button"
          variant="outline"
          onClick={handleTestConnection}
          disabled={loadingStatus || !businessId}
          className="w-full"
        >
          {loadingStatus ? 'Проверка...' : 'Проверить подключение'}
        </Button>
      </CardContent>
    </Card>
  );
};
