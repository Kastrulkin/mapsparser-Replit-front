import { useCallback, useEffect, useRef, useState } from 'react';
import { newAuth } from '@/lib/auth_new';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

type Config = { riderra_shortage_only?: boolean; evidence_terms: string[]; language: string; audience: string; offer: string; queries: { query: string; city: string }[]; max_search_calls: number; max_candidates: number; batch_size: number; search_budget_cents: number };
type Task = { id: string; revision: string; stage: string; status: string; config: Config; state: { started?: boolean; search_calls?: number; lead_ids?: string[]; blocker?: string; inflight_search?: boolean; qualifications?: Record<string, { status: string; reason?: string }>; campaign_results?: Record<string, { status: string; campaign_id?: string; lead_id?: string; reason_code?: string }> } };

export function OutreachContinuation({ businessId }: { businessId: string }) {
  const [enabled, setEnabled] = useState(false);
  const [supportsShortage, setSupportsShortage] = useState(false);
  const [shortageOnly, setShortageOnly] = useState(false);
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const [items, setItems] = useState<Task[]>([]);
  const [editing, setEditing] = useState(false);
  const [audience, setAudience] = useState('');
  const [offer, setOffer] = useState('');
  const [query, setQuery] = useState('');
  const [city, setCity] = useState('');
  const [budget, setBudget] = useState(100);
  const scope = useRef(0);
  const [language, setLanguage] = useState('en');
  const [evidenceTerms, setEvidenceTerms] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    return newAuth.makeRequest(`/partnership/continuations?business_id=${encodeURIComponent(businessId)}`);
  }, [businessId]);
  useEffect(() => {
    let active = true;
    scope.current += 1;
    setItems([]); setEnabled(false); setSupportsShortage(false); setShortageOnly(false); setError(''); setEditing(false); setBusy(false);
    const refresh = async () => {
      try { const result = await load(); if (active) { setItems(result.items || []); setEnabled(result.enabled === true); setSupportsShortage(result.supports_shortage_replenishment === true); setError(''); } }
      catch { if (active) setError('Не удалось загрузить задачи. Повторите попытку.'); }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15000);
    return () => { scope.current += 1; active = false; window.clearInterval(timer); };
  }, [load]);
  const mutate = async (path: string, body: object) => {
    const epoch = scope.current;
    setBusy(true); setError('');
    try {
      await newAuth.makeRequest(path, { method: 'POST', body: JSON.stringify({ business_id: businessId, ...body }) });
      if (epoch !== scope.current) return;
      const result = await load(); if (epoch === scope.current) { setItems(result.items || []); setEditing(false); }
    } catch { if (epoch === scope.current) setError('Действие не выполнено. Обновите список и проверьте условия задачи.'); }
    finally { if (epoch === scope.current) setBusy(false); }
  };
  if (!enabled) return error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null;
  return <section aria-labelledby="outreach-continuation-title" className="space-y-3 rounded-lg border p-4">
    <h2 id="outreach-continuation-title" className="text-lg font-semibold">Поиск и подготовка обращений</h2>
    <p className="text-sm text-muted-foreground">LocalOS сохраняет прогресс поиска и проверки контактов. Обращения проходят отдельное согласование перед отправкой.</p>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {items.map(task => <div key={task.id} className="space-y-2 border-t pt-3">
      <h3 className="font-medium">{task.config.audience}</h3>
      <p role="status" className="text-sm">{task.stage}</p>
      <p className="text-sm tabular-nums">Поисков: {task.state.search_calls || 0} / {task.config.max_search_calls}. Новых компаний: {task.state.lead_ids?.length || 0} / {task.config.max_candidates}.</p>
      <details><summary className="cursor-pointer text-sm">Условия подготовки</summary>
        <p className="whitespace-pre-wrap text-sm">{task.config.offer}</p>
        {task.config.riderra_shortage_only && <p className="text-sm">Поиск начнётся только при подтверждённой нехватке готовых кандидатов Riderra.</p>}
        <ul className="text-sm">{task.config.queries.map((q, i) => <li key={i}>{q.query} — {q.city}</li>)}</ul>
        <p className="text-sm">Бюджет поиска: до {(task.config.search_budget_cents / 100).toFixed(2)} USD. Запуск разрешает поиск и проверку контактов в указанном объёме. Поддержка конкретной аудитории проверяется по источникам.</p>
      </details>
      {Object.keys(task.state.campaign_results || {}).length > 0 && <details><summary className="cursor-pointer text-sm">Результаты подготовки</summary><ul className="text-sm">{Object.entries(task.state.campaign_results || {}).map(([id, result]) => <li key={id}>{result.campaign_id ? <a className="underline" href={`/dashboard/partnerships?lead=${encodeURIComponent(result.lead_id || "")}`}>Проверить кампанию</a> : `Нужна проверка: ${result.reason_code || result.status}`}</li>)}</ul></details>}
      {task.status !== 'completed' && task.status !== 'cancelled' && <div className="flex flex-wrap gap-2">
        {task.status === 'waiting_for_review' && task.state.inflight_search && <Button variant="outline" disabled={busy} onClick={() => void mutate(`/partnership/continuations/${task.id}`, { action: 'acknowledge_search', revision: task.revision })}>Учесть использованный поиск и снять неопределённость</Button>}
        {['waiting_for_review', 'failed'].includes(task.status) && !task.state.inflight_search && !['search_budget_exhausted', 'audience_and_drafts_review_required', 'access_revoked', 'qualification_result_uncertain', 'campaign_result_uncertain', 'model_budget_exhausted'].includes(task.state.blocker || '') && <Button disabled={busy} onClick={() => void mutate(`/partnership/continuations/${task.id}`, { action: task.state.started ? 'resume' : 'start', revision: task.revision })}>{task.state.started ? 'Продолжить подготовку' : 'Начать подготовку'}</Button>}
        {['waiting_for_review', 'failed'].includes(task.status) && [...Object.values(task.state.qualifications || {}), ...Object.values(task.state.campaign_results || {})].some(item => ['checking', 'preparing', 'failed'].includes(item.status)) && <Button variant="outline" disabled={busy} onClick={() => void mutate(`/partnership/continuations/${task.id}`, { action: 'retry_failed', revision: task.revision })}>Сверить и повторить прерванные шаги</Button>}
        {(task.status === 'queued'  || task.status === 'running') && <Button variant="outline" disabled={busy} onClick={() => void mutate(`/partnership/continuations/${task.id}`, { action: 'pause', revision: task.revision })}>Пауза</Button>}
        <Button variant="ghost" disabled={busy} onClick={() => void mutate(`/partnership/continuations/${task.id}`, { action: 'stop', revision: task.revision })}>Остановить подготовку</Button>
      </div>}
    </div>)}
    {!editing ? <Button variant={items.length ? 'outline' : 'default'} onClick={() => { setRequestId(crypto.randomUUID()); setEditing(true); }}>Настроить поиск</Button> : <form className="space-y-3" onSubmit={event => { event.preventDefault(); void mutate('/partnership/continuations', { request_id: requestId, config: { audience, offer, language, riderra_shortage_only: supportsShortage && shortageOnly, evidence_terms: evidenceTerms.split(',').map(value => value.trim()).filter(Boolean), queries: city.split("\n").map(value => value.trim()).filter(Boolean).map(value => ({ query, city: value })), max_search_calls: city.split("\n").filter(value => value.trim()).length, max_candidates: Math.min(100, city.split("\n").filter(value => value.trim()).length * 5), batch_size: 5, search_budget_cents: budget } }); }}>
      <div><Label htmlFor="continuation-audience">Кого ищем</Label><Input id="continuation-audience" required maxLength={500} value={audience} onChange={e => setAudience(e.target.value)} placeholder="Например, турагентства, продающие Пхукет" /></div>
      <div><Label htmlFor="continuation-offer">Что предлагаем</Label><Textarea id="continuation-offer" required maxLength={2000} value={offer} onChange={e => setOffer(e.target.value)} /></div>
      <div><Label htmlFor="continuation-query">Поисковый запрос</Label><Input id="continuation-query" required maxLength={300} value={query} onChange={e => setQuery(e.target.value)} placeholder="Travel agency" /></div>
      <div><Label htmlFor="continuation-city">Города поиска — по одному на строку</Label><Textarea id="continuation-city" required maxLength={2400} value={city} onChange={e => setCity(e.target.value)} placeholder="Delhi" /></div>
      <div><Label htmlFor="continuation-language">Язык письма</Label><Input id="continuation-language" required value={language} onChange={e => setLanguage(e.target.value)} placeholder="en или ru" /></div>
      {supportsShortage && <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={shortageOnly} onChange={event => setShortageOnly(event.target.checked)} />Пополнять базу только при нехватке готовых кандидатов Riderra</label>}
      <details><summary className="cursor-pointer text-sm">Бюджет и проверка аудитории</summary><Label htmlFor="continuation-evidence">Что искать на сайте компании</Label><Input id="continuation-evidence" value={evidenceTerms} onChange={e => setEvidenceTerms(e.target.value)} placeholder="Например, Phuket, Thailand" /><Label htmlFor="continuation-budget">Общий бюджет поиска, центы USD</Label><Input id="continuation-budget" type="number" min={1} max={1000} required value={budget} onChange={e => setBudget(Number(e.target.value))} /></details>
      <p className="text-sm text-muted-foreground">До пяти новых компаний на город, максимум 20 городов. LocalOS последовательно проверит группы и сохранит черновики. Бюджет поиска общий; вызовы моделей оплачиваются отдельно и ограничены 20 проверками и 20 попытками подготовки. Сначала будет показан план.</p>
      <div className="flex gap-2"><Button disabled={busy}>Проверить план</Button><Button type="button" variant="ghost" onClick={() => setEditing(false)}>Отмена</Button></div>
    </form>}
  </section>;
}
