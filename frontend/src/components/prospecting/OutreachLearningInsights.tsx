import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, BarChart3, RefreshCw, ShieldAlert, Sparkles } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { newAuth } from '@/lib/auth_new';

type StrategyStat = {
  id: string;
  dimensions_json?: {
    segment?: string;
    recipient_role?: string;
    signal_kind?: string;
    evidence_id?: string;
    channel?: string;
    angle?: string;
    day_offset?: number;
    sequence_index?: number;
    founder_story?: string;
    founder_proof?: string;
    offer?: string;
    cta?: string;
  };
  sent_count?: number;
  delivered_count?: number;
  reply_count?: number;
  positive_reply_count?: number;
  question_count?: number;
  hard_no_count?: number;
  unsubscribe_count?: number;
  complaint_count?: number;
  meeting_count?: number;
  converted_count?: number;
  no_reply_count?: number;
  sample_status?: 'insufficient_data' | 'preliminary' | 'reliable';
  confidence?: number;
  positive_reply_rate?: number;
  meeting_rate?: number;
  conversion_rate?: number;
  no_reply_rate?: number;
  health_adjusted_score?: number;
  sender_health_score?: number;
  sender_health_status?: string;
  recommendation_status?: string;
};

type OutreachLearningInsightsProps = {
  businessId?: string | null;
  workstreamType?: 'localos_sales' | 'client_partnership';
};

const sampleLabel: Record<string, string> = {
  insufficient_data: 'Данных мало',
  preliminary: 'Предварительно',
  reliable: 'Надёжная выборка',
};

const recommendationLabel: Record<string, string> = {
  insufficient_data: 'Накопить данные',
  candidate_for_reuse: 'Кандидат для нового теста',
  review_safety: 'Проверить отказы и жалобы',
  review_sender_health: 'Сначала восстановить отправителя',
  no_positive_signal: 'Положительного сигнала нет',
};

const percent = (value?: number) => `${Math.round(Number(value || 0) * 100)}%`;

export function OutreachLearningInsights({
  businessId,
  workstreamType = 'client_partnership',
}: OutreachLearningInsightsProps) {
  const [stats, setStats] = useState<StrategyStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (workstreamType === 'client_partnership' && !businessId) {
      setStats([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const query = new URLSearchParams({ workstream_type: workstreamType });
      if (businessId) query.set('business_id', businessId);
      const payload = await newAuth.makeRequest(`/outreach/learning/strategy-stats?${query.toString()}`);
      setStats(Array.isArray(payload?.stats) ? payload.stats : []);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить обучение');
    } finally {
      setLoading(false);
    }
  }, [businessId, workstreamType]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="space-y-4 rounded-3xl border border-slate-200/80 bg-white/95 p-5 shadow-sm" aria-labelledby="outreach-learning-title">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-violet-700" />
            <h2 id="outreach-learning-title" className="text-lg font-semibold text-slate-950">Что работает</h2>
          </div>
          <p className="mt-1 max-w-3xl text-pretty text-sm leading-6 text-slate-600">
            LocalOS сравнивает связки «сегмент → сигнал → founder story → предложение → канал → номер касания → результат». Факты другого получателя не копируются.
          </p>
        </div>
        <Button variant="outline" onClick={() => void load()} disabled={loading} className="min-h-10 bg-white">
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> Обновить
        </Button>
      </div>

      {error ? (
        <div className="flex gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-950">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {error}
        </div>
      ) : null}

      {!loading && stats.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
          <Sparkles className="mx-auto h-6 w-6 text-slate-400" />
          <div className="mt-2 font-semibold text-slate-900">Пока нет сопоставимой выборки</div>
          <p className="mx-auto mt-1 max-w-xl text-sm leading-6 text-slate-600">
            Первые выводы появятся после доставленных касаний и зафиксированных ответов. До 20 доставок вариант не будет назван победителем.
          </p>
        </div>
      ) : null}

      {stats.length > 0 ? (
        <div className="grid gap-3 lg:grid-cols-2">
          {stats.slice(0, 12).map((item) => {
            const dimensions = item.dimensions_json || {};
            const unsafe = ['review_safety', 'review_sender_health'].includes(String(item.recommendation_status || ''));
            return (
              <article key={item.id} className={`rounded-2xl border p-4 ${unsafe ? 'border-amber-200 bg-amber-50/60' : 'border-slate-200 bg-slate-50/70'}`}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="font-semibold text-slate-950">
                      {dimensions.segment || 'Сегмент не указан'} · {dimensions.channel || 'канал не указан'}
                    </div>
                    <div className="mt-1 text-sm text-slate-600">
                      Касание №{Number(dimensions.sequence_index || 0) + 1} · день {dimensions.day_offset || 0} · {dimensions.angle || 'угол не указан'}
                    </div>
                  </div>
                  <Badge variant="outline" className={item.sample_status === 'reliable'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                    : 'border-slate-200 bg-white text-slate-700'}>
                    {sampleLabel[String(item.sample_status || '')] || item.sample_status}
                  </Badge>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
                  <div className="rounded-lg bg-white p-2 ring-1 ring-slate-200"><div className="text-xs text-slate-500">Доставлено</div><div className="mt-1 text-lg font-semibold tabular-nums">{item.delivered_count || item.sent_count || 0}</div></div>
                  <div className="rounded-lg bg-white p-2 ring-1 ring-slate-200"><div className="text-xs text-slate-500">Ответы</div><div className="mt-1 text-lg font-semibold tabular-nums">{item.reply_count || 0}</div></div>
                  <div className="rounded-lg bg-white p-2 ring-1 ring-slate-200"><div className="text-xs text-slate-500">Интерес</div><div className="mt-1 text-lg font-semibold tabular-nums text-emerald-700">{item.positive_reply_count || 0} · {percent(item.positive_reply_rate)}</div></div>
                  <div className="rounded-lg bg-white p-2 ring-1 ring-slate-200"><div className="text-xs text-slate-500">Встречи</div><div className="mt-1 text-lg font-semibold tabular-nums">{item.meeting_count || 0} · {percent(item.meeting_rate)}</div></div>
                  <div className="rounded-lg bg-white p-2 ring-1 ring-slate-200"><div className="text-xs text-slate-500">Конверсии</div><div className="mt-1 text-lg font-semibold tabular-nums text-violet-700">{item.converted_count || 0} · {percent(item.conversion_rate)}</div></div>
                  <div className="rounded-lg bg-white p-2 ring-1 ring-slate-200"><div className="text-xs text-slate-500">Без ответа</div><div className="mt-1 text-lg font-semibold tabular-nums text-slate-700">{item.no_reply_count || 0} · {percent(item.no_reply_rate)}</div></div>
                </div>

                <div className="mt-3 space-y-1 rounded-lg bg-white px-3 py-2 text-xs leading-5 text-slate-700 ring-1 ring-slate-200">
                  <div><span className="font-semibold text-slate-900">Сигнал:</span> {dimensions.signal_kind || 'не указан'}</div>
                  <div><span className="font-semibold text-slate-900">Опыт:</span> {dimensions.founder_proof || dimensions.founder_story || 'не указан'}</div>
                  <div><span className="font-semibold text-slate-900">Предложение:</span> {dimensions.offer || 'не указано'}</div>
                  <div><span className="font-semibold text-slate-900">Следующий шаг:</span> {dimensions.cta || 'не указан'}</div>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                  <Badge variant="outline" className={['healthy', 'warning'].includes(String(item.sender_health_status || 'healthy')) ? 'bg-white' : 'border-amber-300 bg-amber-50 text-amber-900'}>
                    {unsafe ? <ShieldAlert className="mr-1 h-3.5 w-3.5" /> : null}
                    Аккаунт: {item.sender_health_status || 'healthy'} · {item.sender_health_score ?? 100}/100
                  </Badge>
                  <span className="text-slate-600">Надёжность оценки: <span className="font-semibold tabular-nums">{percent(item.confidence)}</span></span>
                  <span className="font-semibold text-rose-700">Отказы: {item.hard_no_count || 0} · отписки: {item.unsubscribe_count || 0} · жалобы: {item.complaint_count || 0}</span>
                </div>

                <div className={`mt-3 rounded-lg px-3 py-2 text-sm ${unsafe ? 'bg-amber-100 text-amber-950' : 'bg-white text-slate-700'}`}>
                  {recommendationLabel[String(item.recommendation_status || '')] || 'Накапливаем данные'}. Новая рекомендация не может обойти approval.
                </div>
              </article>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
