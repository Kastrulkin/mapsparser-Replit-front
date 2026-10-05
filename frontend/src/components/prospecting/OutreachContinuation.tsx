import { useCallback, useEffect, useRef, useState } from 'react';
import { newAuth } from '@/lib/auth_new';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { AlertCircle, ArrowRight, BadgeCheck, Coins, FilterX, Loader2, Search, Users } from 'lucide-react';
import type { SearchTaskGroup } from './partnershipSearchGroups';

type Config = { mode?: 'find_only' | 'prepare_only' | 'auto_send'; billing_mode?: 'fixed_per_call' | 'shared_balance_actual'; search_call_cap_cents?: number; target_count?: number; agency_country?: string; sold_destination?: string; max_qualification_calls?: number; max_draft_attempts?: number; riderra_shortage_only?: boolean; evidence_terms: string[]; language: string; audience: string; offer: string; queries: { query: string; city: string }[]; max_search_calls: number; max_candidates: number; batch_size: number; search_budget_cents: number };
type Task = { id: string; display_name?: string; created_at?: string; updated_at?: string; report?: { found?: number; imported?: number; awaiting_check?: number; checking?: number; checked?: number; verification_failed?: number; excluded?: number; duplicates?: number; eligible: number; shortfall?: number; prepared: number; queued?: number; confirmed_sent?: number; replies?: number; delivery_uncertain?: number; ai_needs_review?: number; credit_limit?: number; credit_estimate_only?: boolean; credits_charged?: number }; revision: string; stage: string; status: string; config: Config; state: { started?: boolean; search_calls?: number; lead_ids?: string[]; blocker?: string; inflight_search?: boolean; search_credit_reservation_id?: string; qualifications?: Record<string, { status: string; reason?: string }>; campaign_results?: Record<string, { status: string; campaign_id?: string; lead_id?: string; reason_code?: string }> } };

export function OutreachContinuation({ businessId, onTasksChange }: { businessId: string; onTasksChange?: (tasks: SearchTaskGroup[]) => void }) {
  const [enabled, setEnabled] = useState(false);
  const [supportsShortage, setSupportsShortage] = useState(false);
  const [shortageOnly, setShortageOnly] = useState(false);
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const [items, setItems] = useState<Task[]>([]);
  const [editing, setEditing] = useState(false);
  const [audience, setAudience] = useState('');
  const [offer, setOffer] = useState('');
  const [mode, setMode] = useState<'find_only' | 'prepare_only' | 'auto_send'>('prepare_only');
  const [query, setQuery] = useState('');
  const [city, setCity] = useState('');
  const [searchCreditsPerCall, setSearchCreditsPerCall] = useState(5);
  const [maxSearchCalls, setMaxSearchCalls] = useState(10);
  const [targetCount, setTargetCount] = useState(100);
  const [agencyCountry, setAgencyCountry] = useState('');
  const [soldDestination, setSoldDestination] = useState('');
  const scope = useRef(0);
  const [language, setLanguage] = useState('en');
  const [evidenceTerms, setEvidenceTerms] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState<{ actionId: string; config: Config; creditLimit: number } | null>(null);
  const [renamingId, setRenamingId] = useState('');
  const [newName, setNewName] = useState('');
  const load = useCallback(async () => {
    return newAuth.makeRequest(`/partnership/continuations?business_id=${encodeURIComponent(businessId)}`);
  }, [businessId]);
  useEffect(() => {
    let active = true;
    scope.current += 1;
    setItems([]); setEnabled(false); setSupportsShortage(false); setShortageOnly(false); setError(''); setEditing(false); setBusy(false); setReview(null); setRenamingId(''); setMode('prepare_only'); setAudience(''); setOffer(''); setQuery(''); setCity(''); setAgencyCountry(''); setSoldDestination('');
    const refresh = async () => {
      try { const result = await load(); if (active) { setItems(result.items || []); onTasksChange?.(result.items || []); setEnabled(result.enabled === true); setSupportsShortage(result.supports_shortage_replenishment === true); setError(''); } }
      catch { if (active) setError('Не удалось загрузить задачи. Повторите попытку.'); }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15000);
    return () => { scope.current += 1; active = false; window.clearInterval(timer); };
  }, [load, onTasksChange]);
  const mutate = async (path: string, body: object) => {
    const epoch = scope.current;
    setBusy(true); setError('');
    try {
      await newAuth.makeRequest(path, { method: 'POST', body: JSON.stringify({ business_id: businessId, ...body }) });
      if (epoch !== scope.current) return;
      const result = await load(); if (epoch === scope.current) { setItems(result.items || []); onTasksChange?.(result.items || []); setEditing(false); }
    } catch { if (epoch === scope.current) setError('Действие не выполнено. Обновите список и проверьте условия задачи.'); }
    finally { if (epoch === scope.current) setBusy(false); }
  };
  const preview = async (config: Config) => {
    setBusy(true); setError('');
    try {
      const result = await newAuth.makeRequest('/partnership/continuations', {
        method: 'POST', body: JSON.stringify({ business_id: businessId, operation: 'preview', request_id: requestId, config }),
      });
      if (!result.approval?.action_id) throw new Error('approval_missing');
      setReview({ actionId: result.approval.action_id, config: result.config, creditLimit: result.credit_quote.total_max });
    } catch { setError('Не удалось показать условия. Проверьте поля и повторите попытку.'); }
    finally { setBusy(false); }
  };
  const confirmReview = async () => {
    if (!review) return;
    setBusy(true); setError('');
    try {
      const result = await newAuth.makeRequest(`/operator/actions/${encodeURIComponent(review.actionId)}/confirm`, {
        method: 'POST', body: JSON.stringify({ business_id: businessId }),
      });
      if (result.operator_result?.status !== 'completed') throw new Error('start_blocked');
      const refreshed = await load();
      setItems(refreshed.items || []); onTasksChange?.(refreshed.items || []);
      setReview(null); setEditing(false);
    } catch { setError('Поиск не запущен. Обновите условия или проверьте доступный баланс.'); }
    finally { setBusy(false); }
  };
  if (!enabled) return error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null;
  return <section aria-labelledby="outreach-continuation-title" className="space-y-3 rounded-lg border p-4">
    <h2 id="outreach-continuation-title" className="text-lg font-semibold">Поиск компаний и обращения</h2>
    <p className="text-sm text-muted-foreground">Найдите компании, проверьте контакты и выберите подходящих. Письма отправляются только по отдельно согласованным правилам.</p>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {items.map(task => <div key={task.id} className="space-y-3 border-t pt-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-base font-semibold">{task.display_name || task.config.audience}</h3>
        <div role="status" aria-live="polite" className="flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-medium">
          {['queued', 'running'].includes(task.status) && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          <span>{task.status === 'running' ? 'Идёт поиск' : task.status === 'queued' ? 'В очереди' : task.status === 'completed' ? (task.report?.eligible ?? 0) < (task.config.target_count ?? task.config.max_candidates) ? 'Завершён · недобор' : 'Поиск завершён' : task.status === 'cancelled' ? 'Поиск остановлен' : task.status === 'failed' ? 'Ошибка поиска' : task.state.started ? 'На паузе' : 'Ожидает запуска'}</span>
        </div>
      </div>
      <p className={task.state.blocker ? 'flex items-start gap-2 text-sm text-amber-800' : 'text-sm text-muted-foreground'}>{task.state.blocker && <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />}{task.stage.replace(/DeepSeek/gi, 'ИИ')}</p>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3" aria-label="Результаты поиска">
        <div className="flex items-center gap-3 rounded-lg bg-muted/50 px-3 py-2"><Search className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" /><div><strong className="block text-lg leading-tight tabular-nums">{task.report?.found ?? task.report?.imported ?? 0}</strong><span className="text-xs text-muted-foreground">Найдено всего</span></div></div>
        <div className="flex items-center gap-3 rounded-lg bg-muted/50 px-3 py-2"><Users className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" /><div><strong className="block text-lg leading-tight tabular-nums">{task.report?.imported ?? task.state.lead_ids?.length ?? 0}</strong><span className="text-xs text-muted-foreground">Новые кандидаты</span></div></div>
        <div className="flex items-center gap-3 rounded-lg bg-muted/50 px-3 py-2"><BadgeCheck className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" /><div><strong className="block text-lg leading-tight tabular-nums">{task.report?.eligible ?? 0} / {task.config.target_count ?? task.config.max_candidates}</strong><span className="text-xs text-muted-foreground">Подтверждены · цель</span></div></div>
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-1.5"><FilterX className="h-4 w-4" aria-hidden="true" />Исключено {task.report?.excluded ?? 0} <span className="text-xs">(дубли {task.report?.duplicates ?? 0})</span></span>
        <span className="inline-flex items-center gap-1.5"><Coins className="h-4 w-4" aria-hidden="true" />Списано {task.report?.credits_charged ?? 0} кр. {task.report?.credit_limit != null && <span className="text-xs">· {task.report.credit_estimate_only ? 'ориентир до' : 'лимит'} {task.report.credit_limit} кр.</span>}</span>
      </div>
      <details className="text-sm"><summary className="cursor-pointer text-muted-foreground">Ход проверки и расходы</summary>
        <div className="mt-2 space-y-1 text-muted-foreground">
          <p>Ждут проверки: {task.report?.awaiting_check ?? 0} · Проверяются: {task.report?.checking ?? 0} · Не удалось проверить: {task.report?.verification_failed ?? 0}</p>
          <p>Поисковых запросов: {task.state.search_calls || 0} из {task.config.max_search_calls}</p>
          <p>{task.report?.credit_estimate_only ? 'Ориентир расходов, списание только за выполненные действия.' : 'Расходы в пределах согласованного лимита.'}</p>
        </div>
      </details>
      {task.config.mode !== 'find_only' && <p className="text-sm tabular-nums">Подготовлено: {task.report?.prepared || 0}. В очереди: {task.report?.queued ?? '—'}. Подтверждённо отправлено: {task.report?.confirmed_sent ?? '—'}. Ответов: {task.report?.replies ?? '—'}.</p>}
      {!!task.report?.delivery_uncertain && <p className="text-sm">Нужна сверка доставки: {task.report.delivery_uncertain}.</p>}
      {!!task.report?.ai_needs_review && <p className="text-sm">Писем на рассмотрении: {task.report.ai_needs_review}. Остальные разрешённые письма продолжают обрабатываться.</p>}
      <div className="flex flex-wrap items-center gap-3 text-sm"><a className="inline-flex min-h-10 items-center gap-1.5 font-medium underline" href={`/dashboard/partnerships?business_id=${encodeURIComponent(businessId)}&search_task_id=${encodeURIComponent(task.id)}`}>Посмотреть кандидатов <ArrowRight className="h-4 w-4" aria-hidden="true" /></a><button className="min-h-10 underline" type="button" onClick={() => { setRenamingId(task.id); setNewName(task.display_name || task.config.audience); }}>Переименовать</button></div>
      {renamingId === task.id && <form className="flex flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); if (newName.trim()) { void mutate(`/partnership/continuations/${task.id}`, { action: 'rename', revision: task.revision, display_name: newName.trim() }); setRenamingId(''); } }}><Input aria-label="Название поиска" maxLength={120} value={newName} onChange={(event) => setNewName(event.target.value)} /><Button type="submit" disabled={busy || !newName.trim()}>Сохранить название</Button></form>}
      <details><summary className="cursor-pointer text-sm">Условия поиска</summary>
        <p className="text-sm">{task.config.mode === 'find_only' ? 'Только найти и проверить' : task.config.mode === 'auto_send' ? 'Аутрич по согласованным AI-правилам' : 'Найти и подготовить письма'}</p>
        <p className="whitespace-pre-wrap text-sm">{task.config.offer}</p>
        {task.config.riderra_shortage_only && <p className="text-sm">Поиск начнётся только при подтверждённой нехватке готовых кандидатов Riderra.</p>}
        <ul className="text-sm">{task.config.queries.map((q, i) => <li key={i}>{q.query} — {q.city}</li>)}</ul>
        <p className="text-sm">Поисковые вызовы: до {task.config.billing_mode === 'shared_balance_actual' ? Math.ceil((task.config.search_call_cap_cents ?? 50) / 10) : Math.ceil(task.config.search_budget_cents / task.config.max_search_calls / 10)} кредитов за вызов. Проверка кандидата: 1 кредит. {task.config.billing_mode === 'shared_balance_actual' ? 'Средства резервируются на один вызов, затем списывается подтверждённая стоимость и остаток освобождается.' : 'Запуск разрешает работу только в указанных лимитах.'}</p>
      </details>
      {Object.keys(task.state.campaign_results || {}).length > 0 && <details><summary className="cursor-pointer text-sm">Результаты подготовки</summary><ul className="text-sm">{Object.entries(task.state.campaign_results || {}).map(([id, result]) => <li key={id}>{result.campaign_id ? <a className="underline" href={`/dashboard/partnerships?lead=${encodeURIComponent(result.lead_id || "")}`}>Проверить кампанию</a> : `Нужна проверка: ${result.reason_code || result.status}`}</li>)}</ul></details>}
      {task.status !== 'cancelled' && <div className="flex flex-wrap gap-2">
        {task.status === 'waiting_for_review' && task.state.inflight_search && task.config.billing_mode !== 'shared_balance_actual' && <Button variant="outline" disabled={busy} onClick={() => void mutate(`/partnership/continuations/${task.id}`, { action: 'acknowledge_search', revision: task.revision })}>Учесть поиск и списать до {Math.ceil(task.config.search_budget_cents / task.config.max_search_calls / 10)} кредитов</Button>}
        {task.status === 'waiting_for_review' && task.state.inflight_search && task.config.billing_mode === 'shared_balance_actual' && <p className="text-sm">Проверяем результат вызова у провайдера. До подтверждения стоимости списания не будет.</p>}
        {task.status === 'waiting_for_review' && task.state.blocker === 'search_provider_minimum_exceeds_call_limit' && task.config.billing_mode !== 'shared_balance_actual' && <Button disabled={busy} onClick={() => void mutate(`/partnership/continuations/${task.id}`, { action: 'use_shared_balance', revision: task.revision })}>Показать новые условия оплаты с общего баланса</Button>}
        {['waiting_for_review', 'failed'].includes(task.status) && !task.state.inflight_search && !['search_budget_exhausted', 'search_provider_minimum_exceeds_call_limit', 'audience_and_drafts_review_required', 'access_revoked', 'qualification_result_uncertain', 'campaign_result_uncertain', 'model_budget_exhausted', 'candidate_budget_exhausted', 'sources_or_budget_exhausted'].includes(task.state.blocker || '') && <Button disabled={busy} onClick={() => void mutate(`/partnership/continuations/${task.id}`, { action: task.state.started ? 'resume' : 'start', revision: task.revision })}>{task.state.started ? 'Продолжить поиск' : 'Начать поиск'}</Button>}
        {['waiting_for_review', 'failed', 'completed'].includes(task.status) && [...Object.values(task.state.qualifications || {}), ...Object.values(task.state.campaign_results || {})].some(item => ['checking', 'preparing', 'failed'].includes(item.status)) && <Button variant="outline" disabled={busy} onClick={() => void mutate(`/partnership/continuations/${task.id}`, { action: 'retry_failed', revision: task.revision })}>Повторить неудавшиеся проверки</Button>}
        {(task.status === 'queued'  || task.status === 'running') && <Button variant="outline" disabled={busy} onClick={() => void mutate(`/partnership/continuations/${task.id}`, { action: 'pause', revision: task.revision })}>Пауза</Button>}
        {task.status !== 'completed' && !task.state.search_credit_reservation_id && <Button variant="ghost" disabled={busy} onClick={() => void mutate(`/partnership/continuations/${task.id}`, { action: 'stop', revision: task.revision })}>Остановить поиск</Button>}
      </div>}
    </div>)}
    {!editing ? <Button variant={items.length ? 'outline' : 'default'} onClick={() => { setRequestId(crypto.randomUUID()); setReview(null); setEditing(true); }}>Новый поиск</Button> : review ? <div className="space-y-3 rounded-lg border bg-muted/30 p-4"><h3 className="font-medium">Проверьте условия поиска</h3><p>Ищем {review.config.target_count} новых подходящих компаний: {review.config.agency_country} → {review.config.sold_destination}. {review.config.mode === 'find_only' ? 'Только поиск и проверка, без писем.' : 'Подготовка обращений по заданным условиям.'}</p><p>Ориентир расходов — до {review.creditLimit} кредитов с общего баланса; списание только по выполненным действиям.</p><p>До подтверждения поиск не запущен.</p><div className="flex gap-2"><Button disabled={busy} onClick={() => void confirmReview()}>Начать поиск</Button><Button variant="outline" disabled={busy} onClick={() => { setReview(null); setRequestId(crypto.randomUUID()); }}>Изменить условия</Button></div></div> : <form className="space-y-3" onSubmit={event => { event.preventDefault(); void preview({ mode, billing_mode: 'shared_balance_actual', search_call_cap_cents: searchCreditsPerCall * 10, audience, offer, language, target_count: targetCount, agency_country: agencyCountry, sold_destination: soldDestination, riderra_shortage_only: supportsShortage && shortageOnly, evidence_terms: evidenceTerms.split(',').map(value => value.trim()).filter(Boolean), queries: city.split("\n").map(value => value.trim()).filter(Boolean).map(value => ({ query, city: value })), max_search_calls: maxSearchCalls, max_candidates: targetCount * 5, max_qualification_calls: targetCount * 5, max_draft_attempts: targetCount, batch_size: 50, search_budget_cents: searchCreditsPerCall * 10 * maxSearchCalls }); }}>
      <fieldset className="space-y-2"><legend className="mb-2 font-medium">Что выполнить</legend>
        {([{ value: 'find_only', label: 'Только найти и проверить компании' }, { value: 'prepare_only', label: 'Найти и подготовить письма' }, ...(supportsShortage ? [{ value: 'auto_send', label: 'Полный аутрич по отдельно согласованным правилам' }] : [])] as const).map(option => <label key={option.value} className="flex items-start gap-2 text-sm"><input type="radio" name="continuation-mode" checked={mode === option.value} onChange={() => setMode(option.value as typeof mode)} />{option.label}</label>)}
        {mode === 'auto_send' && <p className="text-sm text-muted-foreground">Сначала сохраните поиск. Затем согласуйте в чате правила писем: допустимые утверждения, отправителя и лимиты. До этого отправка заблокирована.</p>}
      </fieldset>
      <fieldset className="space-y-3"><legend className="mb-2 font-medium">1. Кого и сколько найти</legend>
      <div><Label htmlFor="continuation-audience">Кого ищем</Label><Input id="continuation-audience" required maxLength={500} value={audience} onChange={e => setAudience(e.target.value)} placeholder="Например, турагентства, продающие Пхукет" /></div>
      <div><Label htmlFor="continuation-target">Сколько новых подходящих компаний найти</Label><Input id="continuation-target" type="number" min={1} max={1000} required value={targetCount} onChange={e => setTargetCount(Number(e.target.value))} /></div>
      <div><Label htmlFor="continuation-country">Страна компаний</Label><Input id="continuation-country" value={agencyCountry} onChange={e => setAgencyCountry(e.target.value)} placeholder="Индия" /></div>
      <div><Label htmlFor="continuation-destination">Какое направление они продают</Label><Input id="continuation-destination" value={soldDestination} onChange={e => setSoldDestination(e.target.value)} placeholder="Пхукет" /></div>
      </fieldset><fieldset className="space-y-3"><legend className="mb-2 font-medium">2. Где искать</legend>
      <div><Label htmlFor="continuation-query">Поисковый запрос</Label><Input id="continuation-query" required maxLength={300} value={query} onChange={e => setQuery(e.target.value)} placeholder="Travel agency" /></div>
      <div><Label htmlFor="continuation-city">Города поиска — по одному на строку</Label><Textarea id="continuation-city" required maxLength={2400} value={city} onChange={e => setCity(e.target.value)} placeholder="Delhi" /></div>
      </fieldset>{mode !== 'find_only' && <fieldset className="space-y-3"><legend className="mb-2 font-medium">3. Какие письма подготовить</legend>
      <div><Label htmlFor="continuation-offer">Что предлагаем</Label><Textarea id="continuation-offer" required maxLength={2000} value={offer} onChange={e => setOffer(e.target.value)} /></div>
      <div><Label htmlFor="continuation-language">Язык письма</Label><Input id="continuation-language" required value={language} onChange={e => setLanguage(e.target.value)} placeholder="en или ru" /></div>
      </fieldset>}
      {supportsShortage && <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={shortageOnly} onChange={event => setShortageOnly(event.target.checked)} />Пополнять базу только при нехватке готовых кандидатов Riderra</label>}
      <details><summary className="cursor-pointer text-sm">Лимиты и проверка аудитории</summary><Label htmlFor="continuation-evidence">Что искать на сайте компании</Label><Input id="continuation-evidence" value={evidenceTerms} onChange={e => setEvidenceTerms(e.target.value)} placeholder="Например, Phuket, Thailand" /><Label htmlFor="continuation-searches">Не более поисковых запросов</Label><Input id="continuation-searches" type="number" min={1} max={20} required value={maxSearchCalls} onChange={e => { const calls = Number(e.target.value); setMaxSearchCalls(calls); setSearchCreditsPerCall(value => Math.min(value, Math.floor(100 / Math.max(1, calls)))); }} /><Label htmlFor="continuation-budget">Кредитов на один поисковый вызов</Label><Input id="continuation-budget" type="number" min={1} max={Math.floor(100 / Math.max(1, maxSearchCalls))} required value={searchCreditsPerCall} onChange={e => setSearchCreditsPerCall(Number(e.target.value))} /></details>
      <p className="text-sm text-muted-foreground">Цель — {targetCount} новых подходящих компаний с подтверждённым контактом. Дубли и неподходящие записи не засчитываются. Ориентир при полном использовании разрешённых действий — до {maxSearchCalls * searchCreditsPerCall + targetCount * 5} кредитов с общего баланса. Поиск списывается по подтверждённой стоимости, проверка — по 1 кредиту; при нехватке средств поиск остановится. {mode !== 'find_only' ? `Подготовка писем оплачивается отдельно; до ${targetCount} попыток.` : 'Письма не готовятся и не отправляются.'} Сначала будет показан план.</p>
      <div className="flex gap-2"><Button disabled={busy}>Проверить план</Button><Button type="button" variant="ghost" onClick={() => setEditing(false)}>Отмена</Button></div>
    </form>}
  </section>;
}
