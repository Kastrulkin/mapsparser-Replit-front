import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useLanguage } from '@/i18n/LanguageContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useToast } from '@/hooks/use-toast';
import { Loader2, Bot, Eye, EyeOff, Info } from 'lucide-react';

interface TelegramBotCredentialsProps {
  businessId: string | null;
  business: any;
  onSaved?: () => void;
}

type TelegramPublishTargetProbe = {
  ready?: boolean;
  status?: string;
  message_ru?: string;
  next_action_ru?: string;
  external_post_published?: boolean;
  send_message_performed?: boolean;
  target_summary_ru?: string;
  target_evidence?: {
    schema?: string;
    bot?: {
      username?: string;
      display_name?: string;
    };
    target?: {
      type?: string;
      display_name?: string;
    };
    permission?: {
      member_status?: string;
      publish_allowed?: boolean;
    };
  };
  checks?: Array<{
    key?: string;
    ok?: boolean;
    label_ru?: string;
    detail_ru?: string;
  }>;
};

export const TelegramBotCredentials = ({ businessId, business, onSaved }: TelegramBotCredentialsProps) => {
  const { t } = useLanguage();
  const [botToken, setBotToken] = useState('');
  const [chatId, setChatId] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [saving, setSaving] = useState(false);
  const [configured, setConfigured] = useState(false);
  const [globalBotConfigured, setGlobalBotConfigured] = useState(false);
  const [publishTransport, setPublishTransport] = useState('missing');
  const [maskedToken, setMaskedToken] = useState<string | null>(null);
  const [configuredChatId, setConfiguredChatId] = useState<string | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [publishTargetProbe, setPublishTargetProbe] = useState<TelegramPublishTargetProbe | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    setBotToken('');
    setChatId('');
    setShowToken(false);
    setConfigured(Boolean(business?.telegram_bot_token_configured));
    setGlobalBotConfigured(false);
    setPublishTransport('missing');
    setMaskedToken(business?.telegram_bot_token_masked || null);
    setConfiguredChatId(business?.telegram_chat_id || null);
    setPublishTargetProbe(null);
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
          setGlobalBotConfigured(Boolean(data.global_bot_configured));
          setPublishTransport(data.publish_transport || 'missing');
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

    if (!configured && !globalBotConfigured && !botToken.trim()) {
      toast({
        title: t.common.error,
        description: 'Для публикаций нужен глобальный бот LocalOS или token вашего Telegram-бота.',
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
        setConfigured(Boolean(payload.telegram_bot_token) || configured);
        setMaskedToken(payload.telegram_bot_token ? 'Сохранён' : maskedToken);
        setPublishTransport(payload.telegram_bot_token ? 'business_bot' : (globalBotConfigured ? 'global_owner_bot' : publishTransport));
        setConfiguredChatId(chatId.trim());
        setPublishTargetProbe(null);
        toast({
          title: t.common.success,
          description: 'Telegram подключён для публикаций из контент-плана.',
        });
        onSaved?.();
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
      setPublishTargetProbe(null);
      const token = localStorage.getItem('auth_token');
      const response = await fetch('/api/business/telegram-bot/publish-target-probe', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ business_id: businessId }),
      });
      const data = await response.json();
      if (response.ok && data?.success) {
        setConfiguredChatId(data.telegram_chat_id || null);
        setPublishTargetProbe(data.probe || null);
        toast({
          title: data.ready ? 'Цель публикации готова' : 'Цель публикации требует внимания',
          description: data.message_ru || data.next_action_ru || 'Проверка Telegram завершена.',
          variant: data.ready ? 'default' : 'destructive',
        });
        onSaved?.();
      } else {
        toast({
          title: t.common.error,
          description: 'Telegram transport или цель публикации недоступны. Проверьте глобальный бот, bot token и chat_id.',
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
      setPublishTargetProbe({
        ready: false,
        status: 'request_failed',
        message_ru: message,
        next_action_ru: 'Проверьте сеть, токен и повторите проверку.',
        external_post_published: false,
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

        <div
          data-testid="telegram-first-api-post-setup"
          className="rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm leading-6 text-blue-900"
        >
          <div className="font-semibold text-blue-950">Первый API-пост начинается с Telegram</div>
          <div className="mt-1">
            Чтобы LocalOS смог опубликовать пост из контент-плана по расписанию, нужен глобальный бот LocalOS + chat_id канала или чата.
            Если хотите свой брендированный бот, добавьте bot token и chat_id. Без цели публикации посты останутся на проверке и не уйдут наружу.
          </div>
          <div className="mt-2 grid gap-2 text-xs sm:grid-cols-2">
            <div
              data-testid="telegram-global-bot-transport-status"
              className={`rounded-xl bg-white px-3 py-2 ring-1 ${configured || globalBotConfigured ? 'text-emerald-800 ring-emerald-100' : 'text-amber-800 ring-amber-100'}`}
            >
              <span className="font-semibold">{configured || globalBotConfigured ? 'Готово: ' : 'Нужно: '}</span>
              {configured ? 'bot token бизнеса' : (globalBotConfigured ? 'глобальный бот LocalOS' : 'bot token или глобальный бот')}
            </div>
            <div className={`rounded-xl bg-white px-3 py-2 ring-1 ${configuredChatId ? 'text-emerald-800 ring-emerald-100' : 'text-amber-800 ring-amber-100'}`}>
              <span className="font-semibold">{configuredChatId ? 'Готово: ' : 'Нужно: '}</span>
              chat_id
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="telegram-bot-token">{t.dashboard.settings.telegram2.tokenLabel}</Label>
          <div className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${configured ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200' : 'bg-slate-100 text-slate-600 ring-1 ring-slate-200'}`}>
            {loadingStatus
              ? 'Проверка статуса токена...'
              : configured
                ? `Токен подключён (${maskedToken || 'скрыт'})`
                : globalBotConfigured
                  ? 'Используется глобальный бот LocalOS'
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
            {globalBotConfigured
              ? 'Для первого API-proof отдельный bot token не обязателен: LocalOS может использовать глобальный бот, если указан chat_id цели публикации.'
              : t.dashboard.settings.telegram2.tokenHelp}
          </p>
          {globalBotConfigured ? (
            <div
              data-testid="telegram-global-bot-save-chat-only"
              className="rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs leading-5 text-emerald-900"
            >
              <div className="font-semibold text-emerald-950">Можно сохранить только chat_id</div>
              <div className="mt-1">
                Глобальный бот LocalOS уже доступен как transport
                {publishTransport ? ` (${publishTransport})` : ''}.
                Добавьте его в канал/группу, укажите chat_id и запустите проверку цели без отправки сообщения.
              </div>
            </div>
          ) : null}
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
          <div
            data-testid="telegram-publish-target-distinction"
            className="rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900"
          >
            <div className="flex items-start gap-2">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
              <div>
                <div className="font-semibold text-amber-950">Важно для живого теста Telegram</div>
                <div className="mt-1">
                  @LocalOspro_bot и miniapp могут управлять LocalOS и слать уведомления, но публикация поста из контент-плана идёт в выбранный chat_id канала или чата. Номер телефона сам по себе не является целью публикации; отправка человеку через Telegram app — отдельный supervised/outreach transport proof.
                </div>
              </div>
            </div>
          </div>
          <p className="text-xs font-medium text-slate-700">
            После сохранения LocalOS сразу обновит готовность каналов для постов из контент-плана.
          </p>
          {publishTargetProbe ? (
            <div
              data-testid="telegram-publish-target-probe-result"
              className={[
                'rounded-xl border px-3 py-2 text-xs leading-5',
                publishTargetProbe.ready
                  ? 'border-emerald-100 bg-emerald-50 text-emerald-900'
                  : 'border-amber-100 bg-amber-50 text-amber-900',
              ].join(' ')}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className={publishTargetProbe.ready ? 'font-semibold text-emerald-950' : 'font-semibold text-amber-950'}>
                    {publishTargetProbe.ready ? 'Telegram цель готова к первому API-proof' : 'Telegram цель ещё не готова к публикации'}
                  </div>
                  <div className="mt-1">
                    {publishTargetProbe.message_ru || 'Проверка завершена без отправки поста наружу.'}
                  </div>
                  {publishTargetProbe.target_summary_ru ? (
                    <div
                      data-testid="telegram-publish-target-evidence"
                      className="mt-2 rounded-lg bg-white px-2 py-1 font-medium text-slate-700"
                    >
                      {publishTargetProbe.target_summary_ru}
                    </div>
                  ) : null}
                </div>
                <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold">
                  {publishTargetProbe.status || 'checked'}
                </span>
              </div>
              {publishTargetProbe.target_evidence?.target?.display_name || publishTargetProbe.target_evidence?.bot?.username ? (
                <div className="mt-2 grid gap-1 sm:grid-cols-3">
                  <div className="rounded-lg bg-white px-2 py-1">
                    <div className="font-semibold text-slate-800">Бот</div>
                    <div className="mt-0.5 text-slate-600">
                      {publishTargetProbe.target_evidence?.bot?.username
                        ? `@${publishTargetProbe.target_evidence.bot.username}`
                        : publishTargetProbe.target_evidence?.bot?.display_name || 'не определён'}
                    </div>
                  </div>
                  <div className="rounded-lg bg-white px-2 py-1">
                    <div className="font-semibold text-slate-800">Цель поста</div>
                    <div className="mt-0.5 text-slate-600">
                      {publishTargetProbe.target_evidence?.target?.display_name || 'не определена'}
                    </div>
                  </div>
                  <div className="rounded-lg bg-white px-2 py-1">
                    <div className="font-semibold text-slate-800">Право писать</div>
                    <div className="mt-0.5 text-slate-600">
                      {publishTargetProbe.target_evidence?.permission?.publish_allowed ? 'подтверждено' : 'не подтверждено'}
                    </div>
                  </div>
                </div>
              ) : null}
              {Array.isArray(publishTargetProbe.checks) && publishTargetProbe.checks.length > 0 ? (
                <div className="mt-2 grid gap-1 sm:grid-cols-3">
                  {publishTargetProbe.checks.slice(0, 3).map((check) => (
                    <div
                      key={`telegram-probe-check:${String(check.key || '')}`}
                      className="rounded-lg bg-white px-2 py-1"
                    >
                      <div className={check.ok ? 'font-semibold text-emerald-800' : 'font-semibold text-amber-800'}>
                        {check.ok ? 'Готово: ' : 'Нужно: '}
                        {check.label_ru || check.key}
                      </div>
                      <div className="mt-0.5 text-slate-600">
                        {check.detail_ru || ''}
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
              <div className="mt-2 font-medium">
                Дальше: {publishTargetProbe.next_action_ru || 'вернитесь в контент-план и проверьте готовность каналов.'}
              </div>
              <div className="mt-1 text-slate-600">
                Проверка не отправляет social post и не заменяет preview → подтверждение → расписание.
                {publishTargetProbe.send_message_performed === false ? ' Сообщение не отправлялось.' : ''}
              </div>
            </div>
          ) : null}
          <div className="rounded-xl border border-sky-100 bg-sky-50 px-3 py-2 text-xs leading-5 text-sky-900">
            <div className="font-semibold text-sky-950">После подключения Telegram</div>
            <div className="mt-1">
              Вернитесь в контент-план, нажмите “Проверить готовность”, откройте предпросмотр и подтвердите публикацию перед расписанием.
            </div>
            <Button type="button" size="sm" variant="outline" className="mt-2 h-7 bg-white px-2 text-[11px]" asChild>
              <Link to="/dashboard/card?tab=news&mode=plan">Открыть контент-план</Link>
            </Button>
          </div>
        </div>

        <div className="flex flex-col gap-2 border-t border-slate-100 pt-4 sm:flex-row sm:justify-end">
          <Button
            type="button"
            variant="outline"
            onClick={handleTestConnection}
            disabled={loadingStatus || !businessId}
          >
            {loadingStatus ? 'Проверка...' : 'Проверить цель публикации'}
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving || (!configured && !globalBotConfigured && !botToken.trim()) || !chatId.trim()}
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
