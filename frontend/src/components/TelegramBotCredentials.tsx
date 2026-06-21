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
  const [chatId, setChatId] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [saving, setSaving] = useState(false);
  const [configured, setConfigured] = useState(false);
  const [maskedToken, setMaskedToken] = useState<string | null>(null);
  const [configuredChatId, setConfiguredChatId] = useState<string | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    setBotToken('');
    setChatId('');
    setShowToken(false);
    setConfigured(Boolean(business?.telegram_bot_token_configured));
    setMaskedToken(business?.telegram_bot_token_masked || null);
    setConfiguredChatId(business?.telegram_chat_id || null);
  }, [business?.id, business?.telegram_bot_token_configured, business?.telegram_bot_token_masked, business?.telegram_chat_id]);

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
          setConfiguredChatId(data.telegram_chat_id || null);
          setChatId(data.telegram_chat_id || '');
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

    if (!configured && !botToken.trim()) {
      toast({
        title: t.common.error,
        description: t.dashboard.settings.telegram2.errorEmpty,
        variant: 'destructive',
      });
      return;
    }

    if (!chatId.trim()) {
      toast({
        title: t.common.error,
        description: 'Укажите telegram_chat_id канала или чата для публикаций.',
        variant: 'destructive',
      });
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem('auth_token');
      const payload: { business_id: string; telegram_chat_id: string; telegram_bot_token?: string } = {
        business_id: businessId,
        telegram_chat_id: chatId.trim(),
      };
      if (botToken.trim()) {
        payload.telegram_bot_token = botToken.trim();
      }
      const response = await fetch('/api/business/profile', {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      const data = await response.json();

      if (response.ok) {
        setBotToken('');
        setShowToken(false);
        setConfigured(true);
        setMaskedToken('Сохранён');
        setConfiguredChatId(chatId.trim());
        toast({
          title: t.common.success,
          description: 'Telegram подключён для публикаций из контент-плана.',
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
        setConfiguredChatId(data.telegram_chat_id || null);
        toast({
          title: 'Подключение активно',
          description: data.telegram_chat_id
            ? `Telegram bot token подключён (${data.masked_token || 'скрыт'}), chat_id сохранён.`
            : 'Telegram bot token подключён, но для публикаций нужен telegram_chat_id.',
        });
      } else {
        toast({
          title: t.common.error,
          description: 'Токен Telegram бота не подключён или недоступен.',
          variant: 'destructive',
        });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Не удалось проверить подключение Telegram бота.';
      toast({
        title: t.common.error,
        description: message,
        variant: 'destructive',
      });
    } finally {
      setLoadingStatus(false);
    }
  };

  return (
    <Card className="rounded-3xl border-slate-200/80 bg-white shadow-sm">
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-2 text-slate-950">
          <span className="flex h-9 w-9 items-center justify-center rounded-2xl bg-slate-100 text-slate-700">
            <Bot className="h-4 w-4" />
          </span>
          {t.dashboard.settings.telegram2.title}
        </CardTitle>
        <CardDescription className="leading-6">
          {t.dashboard.settings.telegram2.description}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Alert className="rounded-2xl border-slate-200 bg-slate-50/80">
          <AlertDescription>
            {t.dashboard.settings.telegram2.subtitle}
            {t.dashboard.settings.telegram2.alert}
          </AlertDescription>
        </Alert>

        <div className="space-y-2">
          <Label htmlFor="telegram-bot-token">{t.dashboard.settings.telegram2.tokenLabel}</Label>
          <div className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${configured ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200' : 'bg-slate-100 text-slate-600 ring-1 ring-slate-200'}`}>
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
          <p className="text-xs text-slate-500">
            {t.dashboard.settings.telegram2.tokenHelp}
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="telegram-chat-id">Канал или чат для публикаций</Label>
          <div className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${configuredChatId ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200' : 'bg-amber-50 text-amber-700 ring-1 ring-amber-200'}`}>
            {configuredChatId ? `chat_id сохранён: ${configuredChatId}` : 'Для постов из контент-плана нужен telegram_chat_id'}
          </div>
          <Input
            id="telegram-chat-id"
            placeholder="@channelname или -1001234567890"
            value={chatId}
            onChange={(event) => setChatId(event.target.value)}
            disabled={saving}
          />
          <p className="text-xs text-slate-500">
            Для канала добавьте бота администратором и укажите username канала или числовой chat_id. Без этого LocalOS подготовит пост, но не сможет отправить его по API.
          </p>
        </div>

        <div className="flex flex-col gap-2 border-t border-slate-100 pt-4 sm:flex-row sm:justify-end">
          <Button
            type="button"
            variant="outline"
            onClick={handleTestConnection}
            disabled={loadingStatus || !businessId}
          >
            {loadingStatus ? 'Проверка...' : 'Проверить подключение'}
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving || (!configured && !botToken.trim()) || !chatId.trim()}
            className="bg-slate-900 text-white hover:bg-slate-800"
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
        </div>
      </CardContent>
    </Card>
  );
};
