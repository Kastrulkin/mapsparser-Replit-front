import { useEffect, useState } from 'react';
import { BellRing, CheckCircle2, Lightbulb, MessageSquareReply, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { api } from '@/services/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

type RadarSource = {
  id: string;
  title: string;
  telegram_chat_id: string;
  telegram_username?: string | null;
  is_active: boolean;
};

type RadarOpportunity = {
  id: string;
  chat_title: string;
  message_text: string;
  signal_type: string;
  score: number;
  reason?: string | null;
  reply_draft?: string | null;
  status: string;
  message_link?: string | null;
  created_at?: string | null;
};

const statusLabels: Record<string, string> = {
  new: 'Новые',
  useful: 'Полезно',
  answered: 'Ответил',
  saved_as_content_idea: 'Идея',
  ignored: 'Неинтересно',
};

type Props = {
  businessId?: string | null;
  mode?: 'settings' | 'work';
};

export const TelegramOpportunityRadar = ({ businessId, mode = 'settings' }: Props) => {
  const [sources, setSources] = useState<RadarSource[]>([]);
  const [opportunities, setOpportunities] = useState<RadarOpportunity[]>([]);
  const [title, setTitle] = useState('');
  const [peer, setPeer] = useState('');
  const [keywords, setKeywords] = useState('заказ, посоветуйте, налоги, мастера, продвижение');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const loadRadar = async () => {
    if (!businessId) return;
    setLoading(true);
    setError('');
    try {
      const [sourcesResponse, opportunitiesResponse] = await Promise.all([
        api.get('/telegram-opportunity-radar/sources', { params: { business_id: businessId } }),
        api.get('/telegram-opportunity-radar/opportunities', { params: { business_id: businessId, limit: 20 } }),
      ]);
      setSources(sourcesResponse.data?.sources || []);
      setOpportunities(opportunitiesResponse.data?.opportunities || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить радар');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRadar();
  }, [businessId]);

  const addSource = async () => {
    if (!businessId || !peer.trim()) return;
    setSaving(true);
    setError('');
    try {
      await api.post('/telegram-opportunity-radar/sources', {
        business_id: businessId,
        source: {
          title: title.trim() || peer.trim(),
          telegram_chat_id: peer.trim(),
          telegram_username: peer.trim().startsWith('@') ? peer.trim().slice(1) : '',
          source_type: 'chat',
          monitor_config: {
            keywords: keywords.split(',').map((item) => item.trim()).filter(Boolean),
          },
        },
      });
      setTitle('');
      setPeer('');
      await loadRadar();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось добавить чат');
    } finally {
      setSaving(false);
    }
  };

  const updateStatus = async (opportunityId: string, status: string) => {
    if (!businessId) return;
    await api.post(`/telegram-opportunity-radar/opportunities/${opportunityId}/status`, {
      business_id: businessId,
      status,
    });
    setOpportunities((items) => items.map((item) => (item.id === opportunityId ? { ...item, status } : item)));
  };

  const newCount = opportunities.filter((item) => item.status === 'new').length;
  const isWorkMode = mode === 'work';

  return (
    <Card className="overflow-hidden border-slate-200">
      <CardHeader className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-xl">
              <BellRing className="h-5 w-5 text-sky-600" />
              {isWorkMode ? 'Найденные возможности' : 'Telegram-радар возможностей'}
            </CardTitle>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {isWorkMode
                ? 'Разберите сообщения, где можно ответить экспертно, помочь с выбором или сохранить тему для поста.'
                : 'LocalOS собирает сообщения, где стоит ответить экспертно, помочь с выбором или сохранить тему для поста.'}
            </p>
          </div>
          <Badge variant={newCount > 0 ? 'default' : 'secondary'}>{newCount} новых</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {!businessId ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Выберите бизнес, чтобы настроить мониторинг.
          </div>
        ) : null}

        {!isWorkMode ? (
          <>
            <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
              <div className="space-y-2">
                <Label htmlFor="telegram-radar-peer">Чат или канал</Label>
                <Input
                  id="telegram-radar-peer"
                  value={peer}
                  onChange={(event) => setPeer(event.target.value)}
                  placeholder="@channel или peer id"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="telegram-radar-title">Название для списка</Label>
                <Input
                  id="telegram-radar-title"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Бьюти владельцы"
                />
              </div>
              <div className="flex items-end">
                <Button type="button" className="gap-2" onClick={addSource} disabled={!businessId || !peer.trim() || saving}>
                  <Plus className="h-4 w-4" />
                  Добавить
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="telegram-radar-keywords">Сигналы для OpenClaw</Label>
              <Textarea
                id="telegram-radar-keywords"
                value={keywords}
                onChange={(event) => setKeywords(event.target.value)}
                className="min-h-20"
              />
            </div>
          </>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" size="sm" className="gap-2" onClick={loadRadar} disabled={loading || !businessId}>
            <RefreshCw className="h-4 w-4" />
            Обновить
          </Button>
          <span className="text-xs text-slate-500">
            {isWorkMode
              ? 'Источники и сигналы настраиваются в настройках Telegram.'
              : 'OpenClaw только читает выбранные источники; ответы остаются ручными.'}
          </span>
        </div>

        {error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
        ) : null}

        <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
          <div className="rounded-lg border border-slate-200">
            <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-900">Источники</div>
            <div className="divide-y divide-slate-100">
              {sources.length === 0 ? (
                <div className="px-4 py-6 text-sm text-slate-500">Добавьте первый чат, где ваша экспертиза может быть уместной.</div>
              ) : sources.map((source) => (
                <div key={source.id} className="px-4 py-3">
                  <div className="font-medium text-slate-900">{source.title}</div>
                  <div className="mt-1 text-xs text-slate-500">{source.telegram_username ? `@${source.telegram_username}` : source.telegram_chat_id}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-slate-200">
            <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-900">Найденные сообщения</div>
            <div className="divide-y divide-slate-100">
              {opportunities.length === 0 ? (
                <div className="px-4 py-6 text-sm text-slate-500">Когда OpenClaw найдёт подходящие сообщения, они появятся здесь.</div>
              ) : opportunities.map((item) => (
                <div key={item.id} className="space-y-3 px-4 py-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-medium text-slate-900">{item.chat_title}</div>
                    <Badge variant={item.status === 'new' ? 'default' : 'secondary'}>{statusLabels[item.status] || item.status}</Badge>
                  </div>
                  <div className="text-sm leading-6 text-slate-700">{item.message_text}</div>
                  <div className="text-xs text-slate-500">{item.signal_type} · score {item.score}{item.reason ? ` · ${item.reason}` : ''}</div>
                  {item.reply_draft ? <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">{item.reply_draft}</div> : null}
                  <div className="flex flex-wrap gap-2">
                    <Button type="button" size="sm" variant="outline" className="gap-1" onClick={() => updateStatus(item.id, 'answered')}>
                      <MessageSquareReply className="h-4 w-4" />
                      Ответил
                    </Button>
                    <Button type="button" size="sm" variant="outline" className="gap-1" onClick={() => updateStatus(item.id, 'saved_as_content_idea')}>
                      <Lightbulb className="h-4 w-4" />
                      Идея
                    </Button>
                    <Button type="button" size="sm" variant="outline" className="gap-1" onClick={() => updateStatus(item.id, 'useful')}>
                      <CheckCircle2 className="h-4 w-4" />
                      Полезно
                    </Button>
                    <Button type="button" size="sm" variant="ghost" className="gap-1 text-slate-500" onClick={() => updateStatus(item.id, 'ignored')}>
                      <Trash2 className="h-4 w-4" />
                      Скрыть
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
