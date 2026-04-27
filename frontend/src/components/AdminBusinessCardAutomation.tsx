import { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { newAuth } from '@/lib/auth_new';
import { Bot, CalendarClock, MessageSquareReply, Newspaper, RefreshCcw } from 'lucide-react';

type AutomationSettings = {
  news_enabled?: boolean;
  news_interval_hours?: number;
  news_schedule_mode?: string | null;
  news_schedule_days?: number[] | null;
  news_schedule_time?: string | null;
  news_content_source?: string | null;
  news_next_run_at?: string | null;
  news_last_run_at?: string | null;
  news_last_status?: string | null;
  review_sync_enabled?: boolean;
  review_sync_interval_hours?: number;
  review_sync_schedule_mode?: string | null;
  review_sync_schedule_days?: number[] | null;
  review_sync_schedule_time?: string | null;
  review_sync_next_run_at?: string | null;
  review_sync_last_run_at?: string | null;
  review_sync_last_status?: string | null;
  review_reply_enabled?: boolean;
  review_reply_interval_hours?: number;
  review_reply_trigger?: string | null;
  review_reply_next_run_at?: string | null;
  review_reply_last_run_at?: string | null;
  review_reply_last_status?: string | null;
  digest_enabled?: boolean;
  digest_time?: string | null;
  digest_last_sent_on?: string | null;
};

type AutomationEvent = {
  id: string;
  action_type: 'news' | 'review_sync' | 'review_reply';
  status: 'success' | 'noop' | 'error' | string;
  triggered_by?: string;
  message?: string;
  created_at?: string;
};

type SnapshotResponse = {
  settings?: AutomationSettings;
  counters?: {
    pending_news_drafts?: number;
    pending_review_reply_drafts?: number;
  };
  recent_events?: AutomationEvent[];
};

type Props = {
  businessId: string;
  businessName: string;
};

const NEWS_INTERVALS = [
  { value: 'off', label: 'Выключено' },
  { value: 'wed_0900_services', label: 'По средам в 09:00 из услуг' },
  { value: '72', label: 'Каждые 3 дня' },
  { value: '168', label: 'Раз в неделю' },
  { value: '336', label: 'Раз в 2 недели' },
];

const REVIEW_SYNC_INTERVALS = [
  { value: 'off', label: 'Выключено' },
  { value: 'mon_wed_0830', label: 'Пн и Ср в 08:30' },
  { value: '24', label: 'Каждый день' },
  { value: '72', label: 'Каждые 3 дня' },
  { value: '168', label: 'Раз в неделю' },
];

const REVIEW_REPLY_INTERVALS = [
  { value: 'off', label: 'Выключено' },
  { value: 'after_review_sync', label: 'После завершения парсинга отзывов' },
  { value: '24', label: 'Каждый день' },
  { value: '72', label: 'Каждые 3 дня' },
  { value: '168', label: 'Раз в неделю' },
];

const automationRowClassName = 'flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between';
const automationTextClassName = 'min-w-0 max-w-2xl';
const automationActionsClassName = 'grid w-full gap-3 sm:grid-cols-[minmax(220px,1fr)_auto] sm:items-end lg:w-[520px] lg:shrink-0';
const automationSelectClassName = 'min-w-0';
const automationRunButtonClassName = 'w-full whitespace-nowrap sm:w-auto';

const DIGEST_OPTIONS = [
  { value: 'off', label: 'Выключено' },
  { value: '08:00', label: 'Каждое утро в 08:00' },
];

function toSelectValue(enabled: boolean | undefined, interval: number | undefined, fallback: string) {
  if (!enabled) return 'off';
  return String(interval || fallback);
}

function matchesDays(value: number[] | null | undefined, expected: number[]) {
  const normalized = Array.isArray(value) ? [...value].sort((a, b) => a - b) : [];
  return normalized.length === expected.length && normalized.every((item, index) => item === expected[index]);
}

function toNewsValue(settings: AutomationSettings) {
  if (!settings.news_enabled) return 'off';
  if (settings.news_schedule_mode === 'weekly' && matchesDays(settings.news_schedule_days, [3]) && (settings.news_schedule_time || '09:00') === '09:00' && (settings.news_content_source || 'services') === 'services') {
    return 'wed_0900_services';
  }
  return String(settings.news_interval_hours || 168);
}

function toReviewSyncValue(settings: AutomationSettings) {
  if (!settings.review_sync_enabled) return 'off';
  if (settings.review_sync_schedule_mode === 'weekly' && matchesDays(settings.review_sync_schedule_days, [1, 3]) && (settings.review_sync_schedule_time || '08:30') === '08:30') {
    return 'mon_wed_0830';
  }
  return String(settings.review_sync_interval_hours || 24);
}

function toReviewReplyValue(settings: AutomationSettings) {
  if (!settings.review_reply_enabled) return 'off';
  if ((settings.review_reply_trigger || 'schedule') === 'after_review_sync') {
    return 'after_review_sync';
  }
  return String(settings.review_reply_interval_hours || 24);
}

function toDigestValue(settings: AutomationSettings) {
  if (!settings.digest_enabled) return 'off';
  return String(settings.digest_time || '08:00');
}

function statusBadgeVariant(status?: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'success') return 'default';
  if (status === 'error') return 'destructive';
  if (status === 'noop') return 'secondary';
  return 'outline';
}

function formatDateTime(value?: string | null) {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleString('ru-RU');
}

export const AdminBusinessCardAutomation = ({ businessId, businessName }: Props) => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [runningAction, setRunningAction] = useState<string | null>(null);
  const [settings, setSettings] = useState<AutomationSettings>({});
  const [events, setEvents] = useState<AutomationEvent[]>([]);
  const [counters, setCounters] = useState<SnapshotResponse['counters']>({});
  const { toast } = useToast();

  const newsValue = useMemo(
    () => toNewsValue(settings),
    [settings],
  );
  const reviewSyncValue = useMemo(
    () => toReviewSyncValue(settings),
    [settings],
  );
  const reviewReplyValue = useMemo(
    () => toReviewReplyValue(settings),
    [settings],
  );
  const digestValue = useMemo(
    () => toDigestValue(settings),
    [settings],
  );

  const loadSnapshot = async () => {
    if (!businessId) return;
    try {
      setLoading(true);
      const data = await newAuth.makeRequest(`/admin/businesses/${businessId}/card-automation`);
      setSettings(data.settings || {});
      setEvents(Array.isArray(data.recent_events) ? data.recent_events : []);
      setCounters(data.counters || {});
    } catch (error: any) {
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось загрузить настройки автоматизации',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSnapshot();
  }, [businessId]);

  const applyInterval = (
    action: 'news' | 'review_sync' | 'review_reply',
    rawValue: string,
  ) => {
    if (action === 'news') {
      if (rawValue === 'off') {
        setSettings((prev) => ({ ...prev, news_enabled: false }));
        return;
      }
      if (rawValue === 'wed_0900_services') {
        setSettings((prev) => ({
          ...prev,
          news_enabled: true,
          news_interval_hours: 168,
          news_schedule_mode: 'weekly',
          news_schedule_days: [3],
          news_schedule_time: '09:00',
          news_content_source: 'services',
        }));
        return;
      }
      setSettings((prev) => ({
        ...prev,
        news_enabled: true,
        news_interval_hours: Number(rawValue || 168),
        news_schedule_mode: 'interval',
        news_schedule_days: null,
        news_schedule_time: null,
        news_content_source: prev.news_content_source || 'services',
      }));
      return;
    }

    if (action === 'review_sync') {
      if (rawValue === 'off') {
        setSettings((prev) => ({ ...prev, review_sync_enabled: false }));
        return;
      }
      if (rawValue === 'mon_wed_0830') {
        setSettings((prev) => ({
          ...prev,
          review_sync_enabled: true,
          review_sync_interval_hours: 48,
          review_sync_schedule_mode: 'weekly',
          review_sync_schedule_days: [1, 3],
          review_sync_schedule_time: '08:30',
        }));
        return;
      }
      setSettings((prev) => ({
        ...prev,
        review_sync_enabled: true,
        review_sync_interval_hours: Number(rawValue || 24),
        review_sync_schedule_mode: 'interval',
        review_sync_schedule_days: null,
        review_sync_schedule_time: null,
      }));
      return;
    }

    if (rawValue === 'off') {
      setSettings((prev) => ({ ...prev, review_reply_enabled: false }));
      return;
    }
    if (rawValue === 'after_review_sync') {
      setSettings((prev) => ({
        ...prev,
        review_reply_enabled: true,
        review_reply_interval_hours: 24,
        review_reply_trigger: 'after_review_sync',
      }));
      return;
    }
    setSettings((prev) => ({
      ...prev,
      review_reply_enabled: true,
      review_reply_interval_hours: Number(rawValue || 24),
      review_reply_trigger: 'schedule',
    }));
  };

  const applyDigest = (rawValue: string) => {
    if (rawValue === 'off') {
      setSettings((prev) => ({ ...prev, digest_enabled: false }));
      return;
    }
    setSettings((prev) => ({
      ...prev,
      digest_enabled: true,
      digest_time: rawValue,
    }));
  };

  const saveSettings = async () => {
    try {
      setSaving(true);
      const payload = {
        news_enabled: Boolean(settings.news_enabled),
        news_interval_hours: Number(settings.news_interval_hours || 168),
        review_sync_enabled: Boolean(settings.review_sync_enabled),
        review_sync_interval_hours: Number(settings.review_sync_interval_hours || 24),
        review_reply_enabled: Boolean(settings.review_reply_enabled),
        review_reply_interval_hours: Number(settings.review_reply_interval_hours || 24),
        news_schedule_mode: settings.news_schedule_mode || 'interval',
        news_schedule_days: settings.news_schedule_days || [],
        news_schedule_time: settings.news_schedule_time || null,
        news_content_source: settings.news_content_source || 'services',
        review_sync_schedule_mode: settings.review_sync_schedule_mode || 'interval',
        review_sync_schedule_days: settings.review_sync_schedule_days || [],
        review_sync_schedule_time: settings.review_sync_schedule_time || null,
        review_reply_trigger: settings.review_reply_trigger || 'schedule',
        digest_enabled: Boolean(settings.digest_enabled),
        digest_time: settings.digest_time || '08:00',
      };
      const data = await newAuth.makeRequest(`/admin/businesses/${businessId}/card-automation`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      setSettings(data.settings || {});
      setEvents(Array.isArray(data.recent_events) ? data.recent_events : []);
      setCounters(data.counters || {});
      toast({
        title: 'Сохранено',
        description: 'Расписания автоматизации обновлены',
      });
    } catch (error: any) {
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось сохранить расписание',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const runNow = async (actionType: 'news' | 'review_sync' | 'review_reply') => {
    try {
      setRunningAction(actionType);
      const data = await newAuth.makeRequest(`/admin/businesses/${businessId}/card-automation/run`, {
        method: 'POST',
        body: JSON.stringify({ action_type: actionType }),
      });
      setSettings(data.settings || {});
      setEvents(Array.isArray(data.recent_events) ? data.recent_events : []);
      setCounters(data.counters || {});
      toast({
        title: 'Запуск выполнен',
        description: data.result?.message || 'Операция выполнена',
      });
    } catch (error: any) {
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось запустить операцию',
        variant: 'destructive',
      });
    } finally {
      setRunningAction(null);
    }
  };

  return (
    <Card className="border-primary/20">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bot className="w-5 h-5 text-primary" />
          Автоматизация карточки
        </CardTitle>
        <CardDescription>
          Суперадмин задаёт расписание для бизнеса {businessName}: как часто обновлять отзывы, готовить draft-ответы и создавать draft-новости.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-lg border border-border/60 p-4">
            <div className="text-sm text-muted-foreground">Draft новостей</div>
            <div className="mt-1 text-2xl font-semibold">{counters?.pending_news_drafts ?? 0}</div>
          </div>
          <div className="rounded-lg border border-border/60 p-4">
            <div className="text-sm text-muted-foreground">Draft ответов</div>
            <div className="mt-1 text-2xl font-semibold">{counters?.pending_review_reply_drafts ?? 0}</div>
          </div>
          <div className="rounded-lg border border-border/60 p-4">
            <div className="text-sm text-muted-foreground">Последнее обновление</div>
            <div className="mt-1 text-sm font-medium">{formatDateTime(settings.review_sync_last_run_at || settings.news_last_run_at || settings.review_reply_last_run_at)}</div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-border/60 p-4">
            <div className={automationRowClassName}>
              <div className={automationTextClassName}>
                <div className="flex items-center gap-2 font-medium">
                  <Newspaper className="w-4 h-4 text-primary" />
                  Новости по расписанию
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  Система создаёт черновики новостей в `UserNews`. Публикация остаётся ручной. Для weekly-режима можно зафиксировать выпуск по средам.
                </p>
              </div>
              <div className={automationActionsClassName}>
                <div className={automationSelectClassName}>
                  <Label className="mb-2 block text-xs text-muted-foreground">Частота</Label>
                  <Select value={newsValue} onValueChange={(value) => applyInterval('news', value)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите частоту" />
                    </SelectTrigger>
                    <SelectContent>
                      {NEWS_INTERVALS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  variant="outline"
                  onClick={() => void runNow('news')}
                  disabled={runningAction === 'news'}
                  className={automationRunButtonClassName}
                  title="Сразу создать один новый черновик новости"
                >
                  <RefreshCcw className="mr-2 h-4 w-4" />
                  Запустить сейчас
                </Button>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
              <span>Следующий запуск: {formatDateTime(settings.news_next_run_at)}</span>
              <span>Последний статус: {settings.news_last_status || '—'}</span>
            </div>
          </div>

          <div className="rounded-xl border border-border/60 p-4">
            <div className={automationRowClassName}>
              <div className={automationTextClassName}>
                <div className="flex items-center gap-2 font-medium">
                  <CalendarClock className="w-4 h-4 text-primary" />
                  Сбор новых отзывов
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  Система ставит обновление карточки в очередь и подтягивает новые отзывы из карты. Для weekly-режима можно задать точные дни и время.
                </p>
              </div>
              <div className={automationActionsClassName}>
                <div className={automationSelectClassName}>
                  <Label className="mb-2 block text-xs text-muted-foreground">Частота</Label>
                  <Select value={reviewSyncValue} onValueChange={(value) => applyInterval('review_sync', value)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите частоту" />
                    </SelectTrigger>
                    <SelectContent>
                      {REVIEW_SYNC_INTERVALS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  variant="outline"
                  onClick={() => void runNow('review_sync')}
                  disabled={runningAction === 'review_sync'}
                  className={automationRunButtonClassName}
                  title="Сразу поставить сбор отзывов в очередь"
                >
                  <RefreshCcw className="mr-2 h-4 w-4" />
                  Запустить сейчас
                </Button>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
              <span>Следующий запуск: {formatDateTime(settings.review_sync_next_run_at)}</span>
              <span>Последний статус: {settings.review_sync_last_status || '—'}</span>
            </div>
          </div>

          <div className="rounded-xl border border-border/60 p-4">
            <div className={automationRowClassName}>
              <div className={automationTextClassName}>
                <div className="flex items-center gap-2 font-medium">
                  <MessageSquareReply className="w-4 h-4 text-primary" />
                  Draft-ответы на отзывы
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  Система берёт новые отзывы без ответа и заранее готовит черновики для команды. Можно запускать по расписанию или сразу после успешного парсинга отзывов.
                </p>
              </div>
              <div className={automationActionsClassName}>
                <div className={automationSelectClassName}>
                  <Label className="mb-2 block text-xs text-muted-foreground">Частота</Label>
                  <Select value={reviewReplyValue} onValueChange={(value) => applyInterval('review_reply', value)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите частоту" />
                    </SelectTrigger>
                    <SelectContent>
                      {REVIEW_REPLY_INTERVALS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  variant="outline"
                  onClick={() => void runNow('review_reply')}
                  disabled={runningAction === 'review_reply'}
                  className={automationRunButtonClassName}
                  title="Сразу подготовить draft-ответы на новые отзывы"
                >
                  <RefreshCcw className="mr-2 h-4 w-4" />
                  Запустить сейчас
                </Button>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
              <span>Следующий запуск: {formatDateTime(settings.review_reply_next_run_at)}</span>
              <span>Последний статус: {settings.review_reply_last_status || '—'}</span>
            </div>
          </div>

          <div className="rounded-xl border border-border/60 p-4">
            <div className={automationRowClassName}>
              <div className={automationTextClassName}>
                <div className="flex items-center gap-2 font-medium">
                  <Bot className="w-4 h-4 text-primary" />
                  Утренний Telegram-дайджест
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  LocalOS присылает владельцу в Telegram утренний список: что сегодня запланировано и что уже успело выполниться по автоматизации.
                </p>
              </div>
              <div className={automationActionsClassName}>
                <div className={automationSelectClassName}>
                  <Label className="mb-2 block text-xs text-muted-foreground">Когда слать</Label>
                  <Select value={digestValue} onValueChange={applyDigest}>
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите режим" />
                    </SelectTrigger>
                    <SelectContent>
                      {DIGEST_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
              <span>Последняя отправка: {settings.digest_last_sent_on || '—'}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            В этом режиме автоматика только готовит материалы. Публикация и отправка остаются под ручным контролем.
          </p>
          <Button onClick={() => void saveSettings()} disabled={saving || loading}>
            {saving ? 'Сохраняем...' : 'Сохранить расписание'}
          </Button>
        </div>

        <div className="space-y-3">
          <div className="text-sm font-medium">Последние запуски</div>
          {loading ? (
            <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">Загружаем историю...</div>
          ) : events.length === 0 ? (
            <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
              Пока нет запусков. После первого выполнения здесь появится журнал автоматизации.
            </div>
          ) : (
            <div className="space-y-2">
              {events.map((event) => (
                <div key={event.id} className="flex flex-col gap-2 rounded-lg border border-border/60 p-3 md:flex-row md:items-center md:justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">
                        {event.action_type === 'news'
                          ? 'Новости'
                          : event.action_type === 'review_sync'
                            ? 'Сбор отзывов'
                            : 'Draft-ответы'}
                      </span>
                      <Badge variant={statusBadgeVariant(event.status)}>{event.status}</Badge>
                      <Badge variant="outline">
                        {event.triggered_by === 'superadmin'
                          ? 'superadmin'
                          : event.triggered_by === 'review_sync_completed'
                            ? 'after sync'
                            : event.triggered_by === 'parser'
                              ? 'parser'
                              : 'scheduler'}
                      </Badge>
                    </div>
                    <div className="text-sm text-muted-foreground">{event.message || '—'}</div>
                  </div>
                  <div className="text-xs text-muted-foreground">{formatDateTime(event.created_at)}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};
