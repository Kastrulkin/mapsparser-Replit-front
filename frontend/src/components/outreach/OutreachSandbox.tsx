import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, CheckCircle2, FlaskConical, MessageCircleReply, Save, Sparkles } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { newAuth } from '@/lib/auth_new';

type SenderMode = 'localos' | 'partner_business' | 'localos_for_partner';

interface WorkstreamOption {
  id: string;
  lead_id: string;
  lead_name: string;
  workstream_type: 'localos_sales' | 'client_partnership';
  business_name?: string | null;
  lifecycle_status?: string | null;
  allowed_sender_modes: SenderMode[];
}

interface Choice {
  id?: string;
  text?: string;
  strategy?: string;
  statement?: string;
  source?: string;
}

interface TouchPreview {
  sequence_index: number;
  channel: string;
  day_offset: number;
  angle: string;
  subject?: string | null;
  text: string;
  quality_gate?: {
    score?: number;
    max_score?: number;
    passed?: boolean;
  };
}

interface DecisionPreview {
  action?: string;
  fit_score?: number;
  signal_score?: number;
  readiness_score?: number;
  priority_score?: number;
  reason_codes?: string[];
}

interface OutreachPreview {
  status: string;
  sender_mode: SenderMode;
  decision?: DecisionPreview;
  offers?: Choice[];
  trust_strategies?: Choice[];
  selected_offer?: Choice;
  selected_trust?: Choice;
  touches?: TouchPreview[];
  missing?: string[];
  evidence?: Array<{ id?: string; fact?: string; source_url?: string }>;
  quality_gate?: { score?: number; max_score?: number; passed?: boolean };
}

interface SandboxPreviewResponse {
  success: boolean;
  error?: string;
  dry_run?: boolean;
  external_dispatch_performed?: boolean;
  preview?: OutreachPreview;
  room_preview?: Record<string, unknown>;
}

interface ReplySimulation {
  classification?: { classification?: string; stops_campaign?: boolean };
  future_touches_stopped?: boolean;
  relationship_memory_preview?: {
    summary?: string;
    next_step?: string;
    negotiation_stage?: string;
  };
  room_preview?: {
    status?: string;
    visibility?: string;
    next_step?: string;
  };
}

const senderLabels: Record<SenderMode, string> = {
  localos: 'LocalOS ищет клиента',
  partner_business: 'Бизнес пишет партнёру',
  localos_for_partner: 'От имени бизнеса через LocalOS',
};

const actionLabels: Record<string, string> = {
  write_now: 'Можно готовить обращение',
  observe: 'Пока наблюдать',
  needs_contact: 'Нужен контакт',
  needs_sender_setup: 'Настройте отправителя',
  needs_evidence: 'Нужны факты о получателе',
  excluded: 'Обращение заблокировано',
};

async function authorizedFetch(url: string, options?: RequestInit): Promise<Response> {
  const token = await newAuth.getToken();
  if (!token) {
    throw new Error('Нужно войти в LocalOS');
  }
  return fetch(url, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
}

export const OutreachSandbox: React.FC<{ businessId: string }> = ({ businessId }) => {
  const [workstreams, setWorkstreams] = useState<WorkstreamOption[]>([]);
  const [workstreamId, setWorkstreamId] = useState('');
  const [senderMode, setSenderMode] = useState<SenderMode | ''>('');
  const [offerId, setOfferId] = useState('');
  const [trustStrategy, setTrustStrategy] = useState('');
  const [preview, setPreview] = useState<OutreachPreview | null>(null);
  const [reply, setReply] = useState('');
  const [simulation, setSimulation] = useState<ReplySimulation | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const { toast } = useToast();

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const response = await authorizedFetch(
          `/api/outreach/sandbox/workstreams?business_id=${encodeURIComponent(businessId || '')}`,
        );
        const data = await response.json();
        if (!response.ok || !data.success) {
          throw new Error(data.error || 'Не удалось загрузить лиды');
        }
        if (active) {
          setWorkstreams(data.workstreams || []);
        }
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : 'Не удалось загрузить лиды');
        }
      }
    };
    load();
    return () => {
      active = false;
    };
  }, [businessId]);

  const selectedWorkstream = useMemo(
    () => workstreams.find((item) => item.id === workstreamId),
    [workstreamId, workstreams],
  );

  const chooseWorkstream = (value: string) => {
    const selected = workstreams.find((item) => item.id === value);
    setWorkstreamId(value);
    setSenderMode(selected?.allowed_sender_modes[0] || '');
    setOfferId('');
    setTrustStrategy('');
    setPreview(null);
    setSimulation(null);
    setError('');
  };

  const chooseSenderMode = (value: string) => {
    if (value === 'localos' || value === 'partner_business' || value === 'localos_for_partner') {
      setSenderMode(value);
      setPreview(null);
    }
  };

  const generatePreview = async () => {
    if (!workstreamId || !senderMode) return;
    setLoading(true);
    setError('');
    setSimulation(null);
    try {
      const response = await authorizedFetch('/api/outreach/sandbox/preview', {
        method: 'POST',
        body: JSON.stringify({
          workstream_id: workstreamId,
          sender_mode: senderMode,
          offer_id: offerId || undefined,
          trust_strategy: trustStrategy || undefined,
        }),
      });
      const data: SandboxPreviewResponse = await response.json();
      if (!response.ok || !data.success || !data.preview) {
        throw new Error(data.error || 'Не удалось подготовить preview');
      }
      setPreview(data.preview);
      setOfferId(data.preview.selected_offer?.id || '');
      setTrustStrategy(data.preview.selected_trust?.strategy || '');
    } catch (previewError) {
      setError(previewError instanceof Error ? previewError.message : 'Не удалось подготовить preview');
    } finally {
      setLoading(false);
    }
  };

  const simulateReply = async () => {
    if (!workstreamId || !senderMode || !reply.trim()) return;
    setLoading(true);
    try {
      const response = await authorizedFetch('/api/outreach/sandbox/simulate-reply', {
        method: 'POST',
        body: JSON.stringify({
          workstream_id: workstreamId,
          sender_mode: senderMode,
          offer_id: offerId || undefined,
          trust_strategy: trustStrategy || undefined,
          reply,
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Не удалось смоделировать ответ');
      }
      setSimulation(data);
    } catch (replyError) {
      setError(replyError instanceof Error ? replyError.message : 'Не удалось смоделировать ответ');
    } finally {
      setLoading(false);
    }
  };

  const saveDraft = async () => {
    if (!workstreamId || !senderMode || !preview) return;
    setSaving(true);
    try {
      const response = await authorizedFetch(`/api/outreach/workstreams/${workstreamId}/preview`, {
        method: 'POST',
        body: JSON.stringify({
          sender_mode: senderMode,
          offer_id: offerId || undefined,
          trust_strategy: trustStrategy || undefined,
          save: true,
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success || !data.campaign) {
        throw new Error(data.error || 'Черновик не сохранён');
      }
      toast({
        title: 'Черновик сохранён',
        description: `Версия ${data.campaign.version}. Ничего не отправлено.`,
      });
    } catch (saveError) {
      toast({
        title: 'Не удалось сохранить',
        description: saveError instanceof Error ? saveError.message : 'Повторите попытку',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const decision = preview?.decision;
  const canSave = preview?.status === 'ready' || preview?.status === 'needs_channel_setup';

  return (
    <div className="min-h-0 flex-1 overflow-auto rounded-xl border bg-background p-4 sm:p-6">
      <div className="mx-auto max-w-5xl space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-balance text-xl font-semibold tracking-tight">Аутрич-песочница</h2>
            <p className="mt-1 max-w-2xl text-pretty text-sm text-muted-foreground">
              Проверьте решение, отправителя, предложение, цепочку и реакцию на ответ до сохранения кампании.
            </p>
          </div>
          <Badge variant="outline" className="w-fit gap-1.5 py-1.5">
            <FlaskConical className="h-3.5 w-3.5" />
            Dry-run · без отправки
          </Badge>
        </div>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">1. Кому и от чьего имени пишем</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Лид</Label>
              <Select value={workstreamId} onValueChange={chooseWorkstream}>
                <SelectTrigger><SelectValue placeholder="Выберите лида" /></SelectTrigger>
                <SelectContent>
                  {workstreams.map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      {item.lead_name}{item.business_name ? ` · ${item.business_name}` : ' · LocalOS'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {workstreams.length === 0 && !error ? (
                <p className="text-sm text-muted-foreground">В доступном бизнесе пока нет лидов для проверки.</p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label>Отправитель</Label>
              <Select
                value={senderMode}
                onValueChange={chooseSenderMode}
                disabled={!selectedWorkstream}
              >
                <SelectTrigger><SelectValue placeholder="Сначала выберите лида" /></SelectTrigger>
                <SelectContent>
                  {(selectedWorkstream?.allowed_sender_modes || []).map((mode) => (
                    <SelectItem key={mode} value={mode}>{senderLabels[mode]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="md:col-span-2">
              <Button
                onClick={generatePreview}
                disabled={!workstreamId || !senderMode || loading}
                className="min-h-10 active:scale-[0.96]"
              >
                <Sparkles className="mr-2 h-4 w-4" />
                {loading ? 'Проверяем…' : 'Проверить и подготовить цепочку'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {error ? (
          <div className="flex gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        ) : null}

        {preview ? (
          <>
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">2. Решение LocalOS</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={decision?.action === 'write_now' ? 'default' : 'secondary'}>
                    {actionLabels[decision?.action || ''] || decision?.action || preview.status}
                  </Badge>
                  {[
                    { key: 'fit', label: 'Совместимость', value: decision?.fit_score },
                    { key: 'signal', label: 'Сигнал', value: decision?.signal_score },
                    { key: 'readiness', label: 'Готовность', value: decision?.readiness_score },
                    { key: 'priority', label: 'Приоритет', value: decision?.priority_score },
                  ].map((score) => {
                    const value = score.value;
                    return typeof value === 'number' ? (
                      <span key={score.key} className="rounded-md bg-muted px-2 py-1 text-xs tabular-nums">
                        {score.label}: {value}
                      </span>
                    ) : null;
                  })}
                </div>
                {(decision?.reason_codes || []).length > 0 ? (
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    {(decision?.reason_codes || []).map((reason) => <li key={reason}>• {reason}</li>)}
                  </ul>
                ) : null}
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Предложение</Label>
                    <Select value={offerId} onValueChange={setOfferId}>
                      <SelectTrigger><SelectValue placeholder="Нет подтверждённого предложения" /></SelectTrigger>
                      <SelectContent>
                        {(preview.offers || []).map((offer) => (
                          <SelectItem key={offer.id} value={offer.id || ''}>{offer.text}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Почему нам можно доверять</Label>
                    <Select value={trustStrategy} onValueChange={setTrustStrategy}>
                      <SelectTrigger><SelectValue placeholder="Нет доступной стратегии доверия" /></SelectTrigger>
                      <SelectContent>
                        {(preview.trust_strategies || []).map((trust) => (
                          <SelectItem key={trust.strategy} value={trust.strategy || ''}>
                            {trust.strategy}: {trust.statement}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                {(preview.offers || []).length > 1 || (preview.trust_strategies || []).length > 1 ? (
                  <Button variant="outline" onClick={generatePreview} disabled={loading} className="min-h-10 active:scale-[0.96]">
                    Пересобрать с выбранной стратегией
                  </Button>
                ) : null}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">3. Как будет выглядеть цепочка</CardTitle>
              </CardHeader>
              <CardContent>
                {(preview.touches || []).length > 0 ? (
                  <div className="space-y-3">
                    {(preview.touches || []).map((touch) => (
                      <div key={touch.sequence_index} className="max-w-3xl rounded-2xl rounded-tl-sm border bg-muted/40 p-4">
                        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <Badge variant="outline">День {touch.day_offset}</Badge>
                          <span>{touch.channel}</span>
                          <span>{touch.angle}</span>
                          <span className="tabular-nums">
                            Проверка: {touch.quality_gate?.score || 0}/{touch.quality_gate?.max_score || 18}
                          </span>
                        </div>
                        {touch.subject ? <div className="mb-2 text-sm font-medium">Тема: {touch.subject}</div> : null}
                        <p className="whitespace-pre-wrap text-pretty text-sm leading-6">{touch.text}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed p-5 text-sm text-muted-foreground">
                    Цепочка не создана. Исправьте причины выше: LocalOS не подставляет общий шаблон вместо фактов.
                  </div>
                )}
              </CardContent>
            </Card>

            {(preview.touches || []).length > 0 ? (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">4. Что произойдёт после ответа</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Textarea
                    value={reply}
                    onChange={(event) => setReply(event.target.value)}
                    placeholder="Например: Да, интересно. Пришлите детали в Telegram."
                    className="min-h-24"
                  />
                  <Button variant="outline" onClick={simulateReply} disabled={!reply.trim() || loading} className="min-h-10 active:scale-[0.96]">
                    <MessageCircleReply className="mr-2 h-4 w-4" />
                    Смоделировать ответ
                  </Button>
                  {simulation ? (
                    <div className="rounded-lg border bg-muted/30 p-4 text-sm">
                      <div className="flex items-center gap-2 font-medium">
                        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                        Ответ: {simulation.classification?.classification || 'не определён'}
                      </div>
                      <p className="mt-2 text-muted-foreground">
                        Следующие касания: {simulation.future_touches_stopped ? 'будут остановлены' : 'останутся без изменений'}.
                        {' '}Следующий шаг: {simulation.relationship_memory_preview?.next_step || 'проверить ответ вручную'}.
                      </p>
                      <p className="mt-1 text-muted-foreground">
                        Комната: {simulation.room_preview?.status || 'prepared'}, доступ: {simulation.room_preview?.visibility || 'private'}.
                      </p>
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            ) : null}

            <div className="sticky bottom-3 flex flex-col gap-3 rounded-xl border bg-background/95 p-4 shadow-lg backdrop-blur sm:flex-row sm:items-center sm:justify-between">
              <p className="text-pretty text-sm text-muted-foreground">
                Песочница ничего не сохраняет. Черновик создаётся только по кнопке и не отправляется без отдельного approval.
              </p>
              <Button onClick={saveDraft} disabled={!canSave || saving} className="min-h-10 shrink-0 active:scale-[0.96]">
                <Save className="mr-2 h-4 w-4" />
                {saving ? 'Сохраняем…' : 'Сохранить как черновик'}
              </Button>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
};
