import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { newAuth } from '@/lib/auth_new';

type Scenario = 'buyer_by_criteria' | 'supplier_by_city';
type Flow = { formKey: string; key: string; blueprintId?: string; versionId?: string; runId?: string };
type Review = { actionId: string; formKey: string };

export function RiderraAcquisitionAutomation({ businessId }: { businessId: string }) {
  const [scenario, setScenario] = useState<Scenario>('buyer_by_criteria');
  const [countries, setCountries] = useState('');
  const [cities, setCities] = useState('');
  const [destination, setDestination] = useState('');
  const [criteria, setCriteria] = useState('');
  const [offer, setOffer] = useState('');
  const [target, setTarget] = useState(100);
  const [budget, setBudget] = useState(500);
  const [cost, setCost] = useState<number | null>(null);
  const [costRefresh, setCostRefresh] = useState(0);
  const [costLoading, setCostLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [summary, setSummary] = useState('');
  const [pending, setPending] = useState<Review | null>(null);
  const [startedId, setStartedId] = useState('');
  const [savedId, setSavedId] = useState('');
  const inFlight = useRef(false);
  const flow = useRef<Flow | null>(null);
  const formKey = JSON.stringify({ businessId, scenario, countries, cities, destination, criteria, offer, target, budget });
  useEffect(() => { setPending(null); setSummary(''); }, [formKey]);
  useEffect(() => {
    let current = true;
    setCostLoading(true); setCost(null); setError('');
    newAuth.makeRequest(`/agent-blueprints/riderra-acquisition-cost?business_id=${encodeURIComponent(businessId)}`)
      .then((result) => { if (current) { if (typeof result.creation_cost?.actual_credits === 'number') setCost(result.creation_cost.actual_credits); else setError('Не удалось получить стоимость настройки. Повторите проверку подключения.'); } })
      .catch((reason) => { if (current) setError(reason instanceof Error ? reason.message : 'Не удалось проверить отправителя и стоимость настройки.'); })
      .finally(() => { if (current) setCostLoading(false); });
    return () => { current = false; };
  }, [businessId, costRefresh]);
  const review = async () => {
    if (inFlight.current || cost === null) return;
    const countryList = countries.split(/[,\n]/).map((value) => value.trim()).filter(Boolean);
    const cityList = cities.split(/[,\n]/).map((value) => value.trim()).filter(Boolean);
    const places = scenario === 'supplier_by_city' ? cityList : countryList;
    const total = scenario === 'supplier_by_city' ? target * cityList.length : target;
    if (!countryList.length || !places.length || !criteria.trim() || !offer.trim() || (scenario === 'buyer_by_criteria' && !destination.trim())) {
      setError('Укажите географию, условия отбора и предложение. Для покупателей также нужно направление.'); return;
    }
    if (!Number.isInteger(target) || target < 1 || total > 1000 || places.length > 20 || new Set(places.map((value) => value.toLowerCase())).size !== places.length || !Number.isInteger(budget) || budget < 1 || budget > 1000) {
      setError('Укажите от 1 до 1000 компаний суммарно, до 20 разных городов/стран и бюджет поиска от 1 до 1000 центов USD.'); return;
    }
    inFlight.current = true; setBusy(true); setError(''); setPending(null); setSummary('Проверяем подключение и условия…');
    try {
      const preflight = await newAuth.makeRequest(`/agent-blueprints/riderra-acquisition-cost?business_id=${encodeURIComponent(businessId)}${scenario === 'buyer_by_criteria' ? `&destination=${encodeURIComponent(destination.trim())}` : ''}`);
      if (preflight.creation_cost?.actual_credits !== cost) { setCost(preflight.creation_cost?.actual_credits ?? null); throw new Error('Стоимость настройки изменилась. Проверьте её и повторите подтверждение.'); }
      if (!flow.current || flow.current.formKey !== formKey) flow.current = { formKey, key: window.crypto.randomUUID() };
      const current = flow.current;
      if (!current.blueprintId || !current.versionId) {
        const requirements = criteria.split('\n').map((value) => value.trim()).filter(Boolean);
        const outreach = {
          audience: scenario === 'supplier_by_city' ? `Transport suppliers operating in any of: ${cityList.join(' or ')}` : criteria.trim().slice(0, 500),
          agency_country: countryList.join(' or '), sold_destination: scenario === 'supplier_by_city' ? cityList[0] : destination.trim(),
          offer: offer.trim(), requirements, search_geography: countryList, language: 'en', mode: 'auto_send', target_count: total,
          billing_mode: 'shared_balance_actual', search_source: 'web',
          queries: places.map((place) => ({ city: place, query: scenario === 'supplier_by_city' ? `${place} passenger transport company ${criteria}` : `${destination} tour operator ${place} ${criteria}` })),
          max_search_calls: 20, max_candidates: Math.min(10000, total * 5), max_qualification_calls: Math.min(10000, total * 5),
          max_draft_attempts: total, search_budget_cents: budget,
        };
        const acquisition = { scenario, relationship_role: scenario === 'supplier_by_city' ? 'supplier' : 'buyer',
          ...(scenario === 'supplier_by_city' ? { target_per_location: target } : {}), reviewed_message: {
            recipient_first_rule: scenario === 'buyer_by_criteria' ? `Begin with sourced evidence of the recipient's ${destination} programme.` : 'Begin with sourced evidence of the supplier service in its selected city.',
            offer: offer.trim(), coverage_claim: 'Riderra works in 40 countries and is not limited to the main destination.',
            closing_question: scenario === 'buyer_by_criteria' ? 'Ask for one upcoming trip to calculate.' : 'Ask for agency net rates and cooperation terms.' } };
        const draft = await newAuth.makeRequest('/agent-blueprints/draft', { method: 'POST', body: JSON.stringify({
          idempotency_key: current.key, business_id: businessId, riderra_creation_cost_ack: cost,
          name: scenario === 'buyer_by_criteria' ? `Покупатели: ${destination}` : `Поставщики: ${cityList.join(' → ')}`,
          description: 'Riderra: фоновый поиск и первое письмо по утверждённым условиям', execution_mode: 'scheduled',
          schedule: { trigger: 'schedule.daily', time: '09:00', timezone: 'Europe/Moscow' }, outreach_config: outreach, riderra_acquisition: acquisition,
        }) });
        if (!draft.blueprint?.id || !draft.version?.id) throw new Error('Сценарий не подтверждён сервером. Повтор не создаст копию.');
        current.blueprintId = draft.blueprint.id; current.versionId = draft.version.id; setSavedId(draft.blueprint.id);
      }
      setSummary('Безопасная проверка сценария. Письма ещё не отправляются.');
      if (!current.runId) {
        const preview = await newAuth.makeRequest(`/agent-blueprints/${current.blueprintId}/runs`, { method: 'POST', body: JSON.stringify({
          idempotency_key: `${current.key}:preview`, blueprint_version_id: current.versionId,
          input: { preview_mode: true, external_side_effects_allowed: false },
        }) });
        current.runId = preview.run?.id;
        if (!current.runId) throw new Error('Сервер не подтвердил безопасную проверку.');
      }
      let passed = false;
      for (let attempt = 0; attempt < 30; attempt += 1) {
        const result = await newAuth.makeRequest(`/agent-runs/${current.runId}`);
        const status = result.run?.status;
        if (status === 'completed' || status === 'waiting_approval') { passed = true; break; }
        if (status === 'failed' || status === 'rejected' || status === 'cancelled') throw new Error(result.run?.error_text || 'Безопасная проверка не пройдена.');
        await new Promise((resolve) => window.setTimeout(resolve, 2000));
      }
      if (!passed) throw new Error('Проверка ещё выполняется. Сценарий сохранён: повторите проверку позже, копия не создастся.');
      const result = await newAuth.makeRequest(`/agent-blueprints/${current.blueprintId}/versions/${current.versionId}/riderra-acquisition-review`, { method: 'POST', body: '{}' });
      if (!result.action_id) throw new Error('Условия запуска не подтверждены сервером.');
      setSummary(result.summary); setPending({ actionId: result.action_id, formKey });
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Проверка не завершена.'); setSummary(''); }
    finally { inFlight.current = false; setBusy(false); }
  };
  const start = async () => {
    if (inFlight.current || !pending || pending.formKey !== formKey || !flow.current?.blueprintId || !flow.current.versionId) return;
    inFlight.current = true; setBusy(true); setError('');
    try {
      const result = await newAuth.makeRequest(`/agent-blueprints/${flow.current.blueprintId}/versions/${flow.current.versionId}/riderra-acquisition-start`, { method: 'POST', body: JSON.stringify({ action_id: pending.actionId }) });
      if (result.success !== true) throw new Error('Запуск не подтверждён.');
      setStartedId(flow.current.blueprintId); setPending(null); setSummary('Сценарий включён. Поиск запускается ежедневно в 09:00 UTC+3; проверка контактов и первые письма идут фоном. Уведомления — об ответах и случаях, требующих внимания.');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Запуск не завершён. Можно безопасно повторить.'); }
    finally { inFlight.current = false; setBusy(false); }
  };
  return <section className="space-y-4 rounded-lg border p-4" aria-labelledby="riderra-acquisition-title">
    <div><h2 id="riderra-acquisition-title" className="text-lg font-semibold">Найти клиентов или исполнителей Riderra</h2><p className="text-sm text-muted-foreground">Один раз задайте условия и подтвердите запуск. Лимит — до 200 компаний в день с учётом остальных отправок. Scandi исключён.</p></div>
    {!startedId && <fieldset disabled={busy} className="space-y-4">
      <Label htmlFor="riderra-scenario">Кого искать</Label><select id="riderra-scenario" className="h-10 w-full rounded-md border bg-background px-3" value={scenario} onChange={(event) => { if (event.target.value === 'buyer_by_criteria' || event.target.value === 'supplier_by_city') setScenario(event.target.value); }}><option value="buyer_by_criteria">Покупателей по условиям</option><option value="supplier_by_city">Исполнителей по городам</option></select>
      <div className="grid gap-4 md:grid-cols-2"><div className="space-y-2"><Label htmlFor="riderra-countries">Страны компаний</Label><Input id="riderra-countries" value={countries} onChange={(event) => setCountries(event.target.value)} placeholder="France, Belgium" /></div>
      <div className="space-y-2">{scenario === 'supplier_by_city' ? <><Label htmlFor="riderra-cities">Города по порядку</Label><Textarea id="riderra-cities" value={cities} onChange={(event) => setCities(event.target.value)} placeholder="London, Manchester" /></> : <><Label htmlFor="riderra-destination">Куда отправляют туристов</Label><Input id="riderra-destination" value={destination} onChange={(event) => setDestination(event.target.value)} placeholder="Helsinki" /></>}</div></div>
      <div className="space-y-2"><Label htmlFor="riderra-criteria">Условия отбора</Label><Textarea id="riderra-criteria" value={criteria} onChange={(event) => setCriteria(event.target.value)} placeholder={scenario === 'buyer_by_criteria' ? 'Организуют групповые туры с опубликованной программой в Хельсинки' : 'Лицензированный перевозчик с собственным парком; автобусы и минибасы'} /></div>
      <div className="space-y-2"><Label htmlFor="riderra-offer">Что предлагаем — без неподтверждённых цен</Label><Textarea id="riderra-offer" value={offer} onChange={(event) => setOffer(event.target.value)} placeholder={scenario === 'buyer_by_criteria' ? 'Трансферы и транспорт для групп; готовы рассчитать ближайшую поездку' : 'Ищем транспортных партнёров; просим net-тарифы для агентств и условия работы'} /></div>
      <div className="grid gap-4 md:grid-cols-2"><div className="space-y-2"><Label htmlFor="riderra-target">{scenario === 'supplier_by_city' ? 'Подходящих компаний на город' : 'Подходящих компаний всего'}</Label><Input id="riderra-target" type="number" min={1} max={1000} value={target} onChange={(event) => setTarget(Number(event.target.value))} /></div><div className="space-y-2"><Label htmlFor="riderra-budget">Общий бюджет поиска, центов USD</Label><Input id="riderra-budget" type="number" min={1} max={1000} value={budget} onChange={(event) => setBudget(Number(event.target.value))} /></div></div>
      <p className="text-sm text-muted-foreground">Запуск ежедневно в 09:00 UTC+3. Бюджет и объём общие для всех городов и последующих запусков. Проверки и письма оплачиваются по тарифу LocalOS в пределах согласованных лимитов. {scenario === 'buyer_by_criteria' && 'Ценовой ориентир берётся из текущего 005 прайса.'}</p>
      <p className="text-sm text-muted-foreground">Создание сценария: {cost === null ? 'проверяем стоимость…' : `${cost} кредита`}. Безопасная проверка не отправляет письма. Перед отправками вы отдельно подтвердите точные условия.</p>
    </fieldset>}
    {cost === null && <Button variant="outline" disabled={costLoading || busy} onClick={() => setCostRefresh((value) => value + 1)}>Повторить проверку подключения</Button>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}{summary && <div role="status" className="whitespace-pre-wrap rounded-md bg-muted p-3 text-sm">{summary}</div>}
    {(startedId || savedId) && <a className="inline-block underline" href={`/dashboard/agents?business_id=${encodeURIComponent(businessId)}&blueprint_id=${encodeURIComponent(startedId || savedId)}`}>Открыть сохранённую автоматизацию</a>}
    {!startedId && <Button disabled={busy || cost === null} onClick={() => void (pending?.formKey === formKey ? start() : review())}>{busy ? 'Проверяем…' : pending?.formKey === formKey ? 'Подтвердить и запустить фоном' : savedId ? 'Продолжить проверку' : 'Создать и проверить сценарий'}</Button>}
  </section>;
}
