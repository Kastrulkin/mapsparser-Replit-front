import { useCallback, useEffect, useRef, useState } from 'react';
import { newAuth } from '@/lib/auth_new';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { OutreachGroupCard, type GroupPresentation } from './OutreachGroupCard';
import type { SearchTaskGroup } from './partnershipSearchGroups';

type Config = { requirements?: string[]; search_geography?: string[]; mode?: 'find_only' | 'prepare_only' | 'auto_send'; billing_mode?: 'fixed_per_call' | 'shared_balance_actual'; search_call_cap_cents?: number; target_count?: number; agency_country?: string; sold_destination?: string; max_qualification_calls?: number; max_draft_attempts?: number; riderra_shortage_only?: boolean; evidence_terms: string[]; language: string; audience: string; offer: string; queries: { query: string; city: string }[]; max_search_calls: number; max_candidates: number; batch_size: number; search_budget_cents: number };
type Task = { presentation?: GroupPresentation; id: string; display_name?: string; created_at?: string; updated_at?: string; report?: { found?: number; imported?: number; awaiting_check?: number; checking?: number; checked?: number; verification_failed?: number; excluded?: number; duplicates?: number; eligible: number; shortfall?: number; prepared: number; queued?: number; confirmed_sent?: number; replies?: number; delivery_uncertain?: number; ai_needs_review?: number; credit_limit?: number; credit_estimate_only?: boolean; credits_charged?: number }; revision: string; stage: string; status: string; config: Config; state: { history?: { action: string; at?: string }[]; started?: boolean; search_calls?: number; lead_ids?: string[]; blocker?: string; inflight_search?: boolean; search_credit_reservation_id?: string; qualifications?: Record<string, { status: string; reason?: string }>; campaign_results?: Record<string, { status: string; campaign_id?: string; lead_id?: string; reason_code?: string }> } };

export function OutreachContinuation({ businessId, selectedTaskId, onTasksChange, onTaskConfirmed, compact = false }: { businessId: string; selectedTaskId?: string; compact?: boolean; onTasksChange?: (tasks: SearchTaskGroup[]) => void; onTaskConfirmed?: (taskId: string) => void }) {
  const [enabled, setEnabled] = useState(false);
  const [supportsShortage, setSupportsShortage] = useState(false);
  const [shortageOnly, setShortageOnly] = useState(false);
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const [items, setItems] = useState<Task[]>([]);
  const [editing, setEditing] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [audience, setAudience] = useState('');
  const [offer, setOffer] = useState('');
  const [mode, setMode] = useState<'find_only' | 'prepare_only' | 'auto_send'>('prepare_only');
  const [query, setQuery] = useState('');
  const [city, setCity] = useState('');
  const [searchCreditsPerCall, setSearchCreditsPerCall] = useState(5);
  const [maxSearchCalls, setMaxSearchCalls] = useState(10);
  const [targetCount, setTargetCount] = useState(100);
  const [agencyCountry, setAgencyCountry] = useState('');
  const [requirements, setRequirements] = useState('');
  const returnFocus = useRef<HTMLButtonElement | null>(null);
  const [soldDestination, setSoldDestination] = useState('');
  const scope = useRef(0);
  const [language, setLanguage] = useState('en');
  const [evidenceTerms, setEvidenceTerms] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState<{ actionId: string; config: Config; creditLimit: number; createsNewSearch?: boolean } | null>(null);
  const [renamingId, setRenamingId] = useState('');
  const [newName, setNewName] = useState('');
  const load = useCallback(async () => {
    return newAuth.makeRequest(`/partnership/continuations?business_id=${encodeURIComponent(businessId)}`);
  }, [businessId]);
  useEffect(() => {
    let active = true;
    let working = false;
    let hasData = false;
    let inFlight = false;
    scope.current += 1;
    setFieldErrors({}); setItems([]); setEnabled(false); setSupportsShortage(false); setShortageOnly(false); setError(''); setEditing(false); setEditingTask(null); setBusy(false); setReview(null); setRenamingId(''); setMode('prepare_only'); setAudience(''); setOffer(''); setQuery(''); setCity(''); setAgencyCountry(''); setSoldDestination(''); setRequirements('');
    const refresh = async () => {
      if (inFlight) return;
      inFlight = true;
      try { const result = await load(); if (active) { hasData = true; working = (result.items || []).some((item: Task) => item.presentation?.active); setItems(result.items || []); onTasksChange?.(result.items || []); setEnabled(result.enabled === true); setSupportsShortage(result.supports_shortage_replenishment === true); setError(''); } }
      catch { if (active) setError(hasData ? 'Не удалось обновить состояние. Сохранённые данные показаны ниже.' : 'Не удалось загрузить задачи. Повторите попытку.'); }
      finally { inFlight = false; }
    };
    void refresh();
    let lastRefresh = Date.now();
    const tick = () => {
      const interval = working && !document.hidden ? 3000 : 15000;
      if (Date.now() - lastRefresh >= interval) { lastRefresh = Date.now(); void refresh(); }
    };
    const focusRefresh = () => { if (!document.hidden) { lastRefresh = Date.now(); void refresh(); } };
    const timer = window.setInterval(tick, 1000);
    document.addEventListener('visibilitychange', focusRefresh);
    window.addEventListener('focus', focusRefresh);
    return () => { scope.current += 1; active = false; window.clearInterval(timer); document.removeEventListener('visibilitychange', focusRefresh); window.removeEventListener('focus', focusRefresh); };
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
    const errors: Record<string, string> = {};
    if (!config.audience.trim()) errors.audience = 'Укажите, кого найти.';
    if (!config.search_geography?.length || config.search_geography.length > 20 || config.search_geography.some(value => value.length > 120)) errors.geography = 'Укажите до 20 мест поиска, до 120 символов каждое.';
    if ((config.requirements?.length || 0) > 10 || config.requirements?.some(value => value.length > 300)) errors.requirements = 'Не более 10 требований, до 300 символов каждое.';
    setFieldErrors(errors);
    if (Object.keys(errors).length) return;
    const epoch = scope.current;
    setBusy(true); setError('');
    try {
      const result = await newAuth.makeRequest(editingTask ? `/partnership/continuations/${editingTask.id}` : '/partnership/continuations', {
        method: 'POST', body: JSON.stringify({ business_id: businessId, operation: 'preview', request_id: requestId, config }),
      });
      if (epoch !== scope.current) return;
      if (!result.approval?.action_id) throw new Error('approval_missing');
      setReview({ actionId: result.approval.action_id, config: result.config, creditLimit: result.credit_quote.total_max, createsNewSearch: result.creates_new_search === true });
    } catch { if (epoch === scope.current) setError('Не удалось показать условия. Проверьте поля и повторите попытку.'); }
    finally { if (epoch === scope.current) setBusy(false); }
  };
  const confirmReview = async () => {
    if (!review) return;
    const epoch = scope.current;
    setBusy(true); setError('');
    try {
      const result = await newAuth.makeRequest(`/operator/actions/${encodeURIComponent(review.actionId)}/confirm`, {
        method: 'POST', body: JSON.stringify({ business_id: businessId }),
      });
      if (epoch !== scope.current) return;
      if (result.operator_result?.status !== 'completed') throw new Error('start_blocked');
      const refreshed = await load();
      if (epoch !== scope.current) return;
      setItems(refreshed.items || []); onTasksChange?.(refreshed.items || []);
      setReview(null); setEditing(false); setEditingTask(null);
      const confirmedTaskId = result.operator_result?.task?.id || result.operator_result?.job_id;
      if (confirmedTaskId) onTaskConfirmed?.(confirmedTaskId);
    } catch { if (epoch === scope.current) setError('Поиск не запущен. Обновите условия или проверьте доступный баланс.'); }
    finally { if (epoch === scope.current) setBusy(false); }
  };
  if (!enabled) return error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null;
  return <section aria-labelledby="outreach-continuation-title" className="space-y-3 rounded-lg border p-4">
    <h2 hidden={compact} id="outreach-continuation-title" className="text-lg font-semibold">Поиск компаний и обращения</h2>
    <p hidden={compact} className="text-sm text-muted-foreground">Найдите компании, проверьте контакты и выберите подходящих. Письма отправляются только по отдельно согласованным правилам.</p>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {items.filter(task => selectedTaskId ? task.id === selectedTaskId : !compact).map(task => <div key={task.id} className={compact ? "space-y-3" : "space-y-3 border-t pt-4"}>
      <OutreachGroupCard compact={compact} name={task.display_name || task.config.audience} presentation={task.presentation} busy={busy} onAction={(action) => {
        if (action.kind === 'draft_resume') void mutate(`/partnership/continuations/${task.id}`, { action: 'resume_letters', revision: task.revision });
        else void mutate(`/partnership/continuations/${task.id}`, { action: action.action, revision: task.revision });
      }} />
      <details open={!compact}><summary className="min-h-10 cursor-pointer py-2 text-sm">История и настройки поиска</summary><div className="space-y-3">
      <details><summary className="min-h-10 cursor-pointer py-2 text-sm">История поиска</summary>
        <div className="space-y-2 py-2 text-sm text-muted-foreground">
          <p>{task.stage.replace(/DeepSeek/gi, 'ИИ')}</p>
          <p>Новые записи: {task.report?.imported ?? 0} · Исключено: {task.report?.excluded ?? 0} · Дубли: {task.report?.duplicates ?? 0}</p>
          <p>Ждут проверки: {task.report?.awaiting_check ?? 0} · Проверяются: {task.report?.checking ?? 0} · Не удалось проверить: {task.report?.verification_failed ?? 0}</p>
          {!!task.state.history?.length && <ol className="space-y-1">{task.state.history.map((entry, index) => <li key={index}>{({ start: 'Поиск запущен', resume: 'Работа продолжена', pause: 'На паузе', stop: 'Поиск остановлен', rename: 'Название изменено' }[entry.action] || 'Условия обновлены')}{entry.at ? ` · ${new Date(entry.at).toLocaleString('ru-RU')}` : ''}</li>)}</ol>}
          <p>Поисковых запросов: {task.state.search_calls || 0} из {task.config.max_search_calls}</p>
        </div>
      </details>
      {!['running', 'queued', 'cancelled'].includes(task.status) && <Button variant="outline" disabled={busy} onClick={(event) => {
        returnFocus.current = event.currentTarget;
        setFieldErrors({}); setError(''); setEditingTask(task); setEditing(true); setReview(null); setRequestId(crypto.randomUUID());
        setAudience(task.config.audience); setAgencyCountry(task.config.agency_country || ''); setSoldDestination(task.config.sold_destination || '');
        setOffer(task.config.offer || ''); setLanguage(task.config.language); setMode(task.config.mode || 'find_only');
        setTargetCount(task.config.target_count || 10); setMaxSearchCalls(task.config.max_search_calls);
        setSearchCreditsPerCall(Math.ceil((task.config.search_call_cap_cents || 50) / 10));
        setQuery(task.config.queries[0]?.query || ''); setCity(task.config.queries.map(value => value.city).join('\n'));
        setEvidenceTerms((task.config.evidence_terms || []).join(','));
        setRequirements((task.config.requirements ?? (task.config.sold_destination ? [`Продают туры на ${task.config.sold_destination}`] : [])).join('\n'));
        setCity((task.config.search_geography ?? (task.config.agency_country ? [task.config.agency_country] : task.config.queries.map(value => value.city))).join('\n'));
      }}>Изменить условия поиска</Button>}
      <button className="min-h-10 text-sm underline" type="button" onClick={() => { setRenamingId(task.id); setNewName(task.display_name || task.config.audience); }}>Переименовать</button>
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
        {['waiting_for_review', 'failed', 'completed'].includes(task.status) && [...Object.values(task.state.qualifications || {}), ...Object.values(task.state.campaign_results || {})].some(item => ['failed'].includes(item.status)) && <Button variant="outline" disabled={busy} onClick={() => void mutate(`/partnership/continuations/${task.id}`, { action: 'retry_failed', revision: task.revision })}>Повторить неудавшиеся проверки</Button>}
        {task.status !== 'completed' && !task.state.search_credit_reservation_id && <Button variant="ghost" disabled={busy} onClick={() => void mutate(`/partnership/continuations/${task.id}`, { action: 'stop', revision: task.revision })}>Остановить поиск</Button>}
      </div>}
      </div></details>
    </div>)}
    <Button variant={items.length ? 'outline' : 'default'} onClick={(event) => { returnFocus.current = event.currentTarget; setRequestId(crypto.randomUUID()); setReview(null); setEditingTask(null); setAudience(''); setOffer(''); setQuery(''); setCity(''); setAgencyCountry(''); setSoldDestination(''); setRequirements(''); setError(''); setFieldErrors({}); setTargetCount(10); setMaxSearchCalls(3); setSearchCreditsPerCall(5); setLanguage('en'); setEvidenceTerms(''); setShortageOnly(false); setMode('find_only'); setEditing(true); }}>Новый поиск</Button>
    <Dialog open={editing} onOpenChange={(open) => { if (!busy) setEditing(open); }}><DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl" onCloseAutoFocus={(event) => { event.preventDefault(); returnFocus.current?.focus(); }}>
      <DialogTitle>{review ? 'Проверьте условия' : editingTask ? 'Изменить условия поиска' : 'Новый поиск'}</DialogTitle>
      <DialogDescription>Задайте аудиторию и требования. Работа начнётся после подтверждения.</DialogDescription>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {review ? <div className="space-y-3 rounded-lg border bg-muted/30 p-4"><h3 className="font-medium">Проверьте условия поиска</h3><p>Ищем {review.config.target_count} новых подходящих компаний: {review.config.audience}. География: {(review.config.search_geography ?? [review.config.agency_country]).filter(Boolean).join(', ')}. {review.config.mode === 'find_only' ? 'Только поиск и проверка, без писем.' : 'Подготовка обращений по заданным условиям.'}</p><p>Ориентир расходов — до {review.creditLimit} кредитов с общего баланса; списание только по выполненным действиям.</p><p>Требования: {(review.config.requirements ?? (review.config.sold_destination ? [`Продают туры на ${review.config.sold_destination}`] : [])).join('; ') || 'Соответствие указанной аудитории'}.</p>{review.createsNewSearch && <p role="status">Будет создан новый поиск. Предыдущие результаты и расходы сохраняются.</p>}<p>До подтверждения поиск не запущен.</p><div className="flex gap-2"><Button disabled={busy} onClick={() => void confirmReview()}>{editingTask && !review.createsNewSearch ? 'Согласовать и продолжить' : 'Начать новый поиск'}</Button><Button variant="outline" disabled={busy} onClick={() => { setReview(null); setRequestId(crypto.randomUUID()); }}>Изменить условия</Button></div></div> : <form className="space-y-3" onSubmit={event => { event.preventDefault(); void preview({ mode, billing_mode: 'shared_balance_actual', search_call_cap_cents: searchCreditsPerCall * 10, audience, offer, language, target_count: targetCount, agency_country: city === agencyCountry ? agencyCountry : '', sold_destination: requirements === `Продают туры на ${soldDestination}` ? soldDestination : '', requirements: requirements.split('\n').map(value => value.trim()).filter(Boolean), search_geography: city.split('\n').map(value => value.trim()).filter(Boolean), riderra_shortage_only: supportsShortage && shortageOnly, evidence_terms: evidenceTerms.split(',').map(value => value.trim()).filter(Boolean), queries: editingTask && requirements === (editingTask.config.requirements ?? (editingTask.config.sold_destination ? [`Продают туры на ${editingTask.config.sold_destination}`] : [])).join('\n') && audience === editingTask.config.audience && query === (editingTask.config.queries[0]?.query || '') && city === (editingTask.config.search_geography ?? (editingTask.config.agency_country ? [editingTask.config.agency_country] : editingTask.config.queries.map(value => value.city))).join('\n') ? editingTask.config.queries : query.trim() && (!editingTask || query !== (editingTask.config.queries[0]?.query || '')) ? city.split("\n").map(value => value.trim()).filter(Boolean).map(value => ({ query, city: value })) : [], max_search_calls: maxSearchCalls, max_candidates: Math.max(targetCount * 5, editingTask?.config.max_candidates || 0), max_qualification_calls: Math.max(targetCount * 5, editingTask?.config.max_qualification_calls || 0), max_draft_attempts: targetCount, batch_size: 50, search_budget_cents: searchCreditsPerCall * 10 * maxSearchCalls }); }}>
      <fieldset className="space-y-2"><legend className="mb-2 font-medium">Что получить</legend>
        {([{ value: 'find_only', label: 'Контакты подходящих компаний или специалистов' }, { value: 'prepare_only', label: 'Контакты и индивидуальные письма' }, ...(editingTask?.config.mode === 'auto_send' ? [{ value: 'auto_send', label: 'По действующим правилам отправки' }] : [])] as const).map(option => <label key={option.value} className="flex items-start gap-2 text-sm"><input type="radio" name="continuation-mode" checked={mode === option.value} onChange={() => setMode(option.value as typeof mode)} />{option.label}</label>)}
        {mode === 'auto_send' && <p className="text-sm text-muted-foreground">Сначала сохраните поиск. Затем согласуйте в чате правила писем: допустимые утверждения, отправителя и лимиты. До этого отправка заблокирована.</p>}
      </fieldset>
      <fieldset className="space-y-3"><legend className="mb-2 font-medium">1. Кого и сколько найти</legend>
      <div><Label htmlFor="continuation-audience">Кого ищем</Label><Input aria-invalid={Boolean(fieldErrors.audience)} aria-describedby={fieldErrors.audience ? 'continuation-audience-error' : undefined} id="continuation-audience" required maxLength={500} value={audience} onChange={e => setAudience(e.target.value)} placeholder="Например, сантехники, поставщики косметики или потенциальные клиенты" />{fieldErrors.audience && <p id="continuation-audience-error" role="alert" className="text-sm text-destructive">{fieldErrors.audience}</p>}</div>
      <div><Label htmlFor="continuation-target">Сколько найти</Label><Input id="continuation-target" type="number" min={1} max={1000} required value={targetCount} onChange={e => setTargetCount(Number(e.target.value))} /></div>
      <div><Label htmlFor="continuation-city">Где ищем</Label><Textarea aria-invalid={Boolean(fieldErrors.geography)} aria-describedby={fieldErrors.geography ? 'continuation-city-error' : undefined} id="continuation-city" required maxLength={2400} value={city} onChange={e => setCity(e.target.value)} placeholder="Страна, регион или город — по одному на строку" />{fieldErrors.geography && <p id="continuation-city-error" role="alert" className="text-sm text-destructive">{fieldErrors.geography}</p>}</div>
      <div><Label htmlFor="continuation-requirements">Требования</Label><Textarea aria-invalid={Boolean(fieldErrors.requirements)} aria-describedby={fieldErrors.requirements ? 'continuation-requirements-error' : undefined} id="continuation-requirements" maxLength={3010} value={requirements} onChange={e => setRequirements(e.target.value)} placeholder="Например, выезжают на дом; работают с юридическими лицами. До 10 требований — по одному на строку." />{fieldErrors.requirements && <p id="continuation-requirements-error" role="alert" className="text-sm text-destructive">{fieldErrors.requirements}</p>}</div>
      </fieldset>{mode !== 'find_only' && <fieldset className="space-y-3"><legend className="mb-2 font-medium">2. Какие письма подготовить</legend>
      <div><Label htmlFor="continuation-offer">Что предлагаем</Label><Textarea id="continuation-offer" required maxLength={2000} value={offer} onChange={e => setOffer(e.target.value)} /></div>
      <div><Label htmlFor="continuation-language">Язык письма</Label><Input id="continuation-language" required value={language} onChange={e => setLanguage(e.target.value)} placeholder="en или ru" /></div>
      </fieldset>}
      {supportsShortage && <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={shortageOnly} onChange={event => setShortageOnly(event.target.checked)} />Пополнять базу только при нехватке готовых кандидатов Riderra</label>}
      <details><summary className="cursor-pointer text-sm">Настройки поиска и ограничения</summary><Label htmlFor="continuation-query">Поисковый запрос</Label><Input id="continuation-query" maxLength={300} value={query} onChange={e => setQuery(e.target.value)} placeholder="Можно оставить пустым — составим из аудитории и требований" /><Label htmlFor="continuation-evidence">Что искать на сайте компании</Label><Input id="continuation-evidence" value={evidenceTerms} onChange={e => setEvidenceTerms(e.target.value)} placeholder="Например, оптовые поставки, выезд на дом" /><Label htmlFor="continuation-searches">Не более поисковых запросов</Label><Input id="continuation-searches" type="number" min={1} max={20} required value={maxSearchCalls} onChange={e => { const calls = Number(e.target.value); setMaxSearchCalls(calls); setSearchCreditsPerCall(value => Math.min(value, Math.floor(100 / Math.max(1, calls)))); }} /><Label htmlFor="continuation-budget">Кредитов на один поисковый вызов</Label><Input id="continuation-budget" type="number" min={1} max={Math.floor(100 / Math.max(1, maxSearchCalls))} required value={searchCreditsPerCall} onChange={e => setSearchCreditsPerCall(Number(e.target.value))} /></details>
      <p className="text-sm text-muted-foreground">Ориентир — до {maxSearchCalls * searchCreditsPerCall + targetCount * 5} кредитов за поиск и проверку. Списание по выполненным действиям с общего баланса. {mode !== 'find_only' ? 'Письма оплачиваются отдельно. Отправка требует отдельного согласования.' : 'Без писем и отправки.'}</p>
      <div className="flex gap-2"><Button disabled={busy}>Проверить план</Button><Button type="button" variant="ghost" onClick={() => setEditing(false)}>Отмена</Button></div>
    </form>}
    </DialogContent></Dialog>
  </section>;
}
