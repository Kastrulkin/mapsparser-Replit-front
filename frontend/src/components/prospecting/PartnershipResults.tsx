import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { newAuth } from '@/lib/auth_new';
import { mobileJsonHeaders, readMobileJson } from '@/lib/mobileDataClient';

type Scope = { kind?: string; id?: string | null };
type Agreement = { revision?: number; status?: string; terms?: Record<string, string>; terms_version?: number; instruction?: string; instruction_terms_version?: number; instruction_draft?: string; history?: Array<{ command: string; at: string; previous?: { instruction?: string; terms?: Record<string, string> } }> };
type Partner = { id: string; name: string; business_name: string; client_business_id: string; company_id?: string; agreement_json: Agreement; partnership_launched_at?: string; partnership_outcome_json?: { mechanic?: string; result?: unknown } };
type Results = { items: Partner[]; locations?: Array<{ id: string; name: string }>; counts: { partners: number; launched: number; preparing: number; needs_decision: number } };
const fields = [
  ['details', 'О чём договорились'], ['our_actions', 'Что делаем мы'], ['partner_actions', 'Что делает партнёр'],
  ['client_benefit', 'Выгода клиента'], ['validity', 'Сроки действия'], ['responsible', 'Ответственный'], ['contact', 'Контакт ответственного'],
  ['trigger', 'Когда предлагать клиенту'], ['record_result', 'Где отмечать результат'], ['promo_code', 'Промокод'],
];

export function PartnershipResults({ scope, mobile = false, openWork }: { scope: Scope; mobile?: boolean; openWork: (businessId?: string) => void }) {
  const [result, setResult] = useState<Results | null>(null);
  const [selected, setSelected] = useState('');
  const [terms, setTerms] = useState<Record<string, string>>({});
  const [instruction, setInstruction] = useState('');
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [chooseLocation, setChooseLocation] = useState(false);
  const version = useRef(0);
  const query = new URLSearchParams({ scope_type: scope.kind || 'business', scope_id: scope.id || '' });
  const request = async (path: string, options: RequestInit = {}) => mobile
    ? fetch(`/api${path}`, { ...options, headers: mobileJsonHeaders() }).then(readMobileJson<Results>)
    : newAuth.makeRequest(path, options);
  const load = async (current = version.current) => {
    if (!scope.id) { setLoading(false); return; }
    try {
      const data = await request(`/partnership/results?${query}`);
      if (!Array.isArray(data?.items) || !data?.counts) throw new Error('Не удалось прочитать договорённости. Повторите загрузку.');
      if (current === version.current) { setResult(data); setError(''); }
    } catch (failure) { if (current === version.current) { setResult(null); setSelected(''); setTerms({}); setInstruction(''); setError(failure instanceof Error ? failure.message : 'Не удалось загрузить договорённости'); } }
    finally { if (current === version.current) setLoading(false); }
  };
  useEffect(() => {
    version.current += 1; setResult(null); setSelected(''); setTerms({}); setInstruction(''); setError(''); setBusy(false); setLoading(true); setChooseLocation(false);
    void load();
    return () => { version.current += 1; };
  }, [scope.kind, scope.id]);
  const partner = result?.items.find(item => item.id === selected);
  const agreement = partner?.agreement_json || {};
  const open = (item: Partner) => { setSelected(item.id); setTerms(item.agreement_json?.terms || {}); setInstruction(item.agreement_json?.instruction_draft || ''); setEditing(!item.agreement_json?.terms); };
  const change = async (command: string) => {
    if (!partner) return;
    const current = version.current;
    setBusy(true); setError('');
    try {
      await request(`/partnership/results/${encodeURIComponent(partner.id)}`, { method: 'POST', body: JSON.stringify({ scope_type: scope.kind, scope_id: scope.id, command, revision: agreement.revision || 0, terms, text: instruction }) });
      if (current !== version.current) return;
      await load(current); setEditing(false);
    } catch (failure) { if (current === version.current) setError(failure instanceof Error ? failure.message : 'Не удалось сохранить'); }
    finally { if (current === version.current) setBusy(false); }
  };
  useEffect(() => { setInstruction(agreement.instruction_draft || ''); }, [selected, agreement.revision]);
  const confirmed = (result?.items || []).filter(item => item.agreement_json?.status === 'confirmed');
  const pending = (result?.items || []).filter(item => item.agreement_json?.status !== 'confirmed');
  const stale = agreement.status !== 'confirmed' || agreement.instruction_terms_version !== agreement.terms_version;
  return <section className="space-y-4 rounded-2xl bg-background p-4 text-foreground shadow-sm" aria-label="Результаты партнёрств">
    {error ? <div role="alert">{error}<Button variant="outline" onClick={() => void load()}>Повторить</Button></div> : null}
    {loading ? <p role="status">Загружаем договорённости…</p> : null}
    {!scope.id ? <p>Выберите бизнес или сеть.</p> : null}
    {partner ? <>
      <Button variant="ghost" className="min-h-11" onClick={() => setSelected('')}>Назад к партнёрам</Button>
      <h2 className="text-xl font-semibold text-balance">{partner.name}</h2><p>{partner.business_name}</p>
      <p>{agreement.status === 'confirmed' ? 'Договорённость подтверждена' : 'Условия требуют подтверждения'}. Это внутренняя запись, не подписание договора.</p>
      {editing ? <div className="space-y-3">{fields.map(([key, label]) => <label key={key} className="block text-sm">{label}<textarea className="mt-1 min-h-20 w-full rounded-md border bg-background p-3" value={terms[key] || ''} onChange={event => setTerms({ ...terms, [key]: event.target.value })} /></label>)}<Button disabled={busy} onClick={() => void change('save')}>Сохранить условия</Button></div> : <>
        <dl className="space-y-3">{fields.filter(([key]) => Boolean(agreement.terms?.[key])).map(([key, label]) => <div key={key}><dt className="text-sm text-muted-foreground">{label}</dt><dd className="whitespace-pre-wrap text-pretty">{agreement.terms?.[key] || 'Не указано'}</dd></div>)}</dl>
        <Button variant="outline" disabled={busy} onClick={() => setEditing(true)}>Изменить условия</Button>
        {agreement.status !== 'confirmed' && agreement.terms?.details ? <Button disabled={busy} onClick={() => void change('confirm')}>Подтвердить договорённость</Button> : null}
      </>}
      <h3 className="text-lg font-semibold">Инструкция сотрудникам</h3>
      {agreement.instruction && !stale ? <><p className="whitespace-pre-wrap">{agreement.instruction}</p><Button variant="outline" onClick={() => void navigator.clipboard.writeText(agreement.instruction || '').catch(() => setError('Не удалось скопировать. Выделите текст инструкции вручную.'))}>Скопировать инструкцию</Button></> : <p>{agreement.instruction ? 'Условия изменились. Инструкцию нужно обновить.' : 'Утверждённой инструкции пока нет.'}</p>}
      <Button variant="outline" disabled={busy || agreement.status !== 'confirmed' || editing} onClick={() => void change('prepare_instruction')}>Подготовить инструкцию</Button>
      {agreement.instruction_draft ? <div className="space-y-2"><label className="block">Черновик — проверьте перед передачей сотрудникам<textarea className="mt-2 min-h-64 w-full rounded-md border bg-background p-3" value={instruction} onChange={event => setInstruction(event.target.value)} /></label><Button variant="outline" disabled={busy} onClick={() => void change('save_instruction')}>Сохранить черновик</Button><Button disabled={busy || instruction !== agreement.instruction_draft || agreement.status !== 'confirmed'} onClick={() => void change('approve_instruction')}>Утвердить инструкцию</Button></div> : null}
      <details><summary className="min-h-11 cursor-pointer py-3">История и результаты</summary>{partner.partnership_launched_at ? <p>Запущено: {partner.partnership_launched_at}</p> : <p>Запуск ещё не отмечен</p>}{partner.partnership_outcome_json?.result ? <pre className="whitespace-pre-wrap break-words text-sm">{JSON.stringify(partner.partnership_outcome_json.result, null, 2)}</pre> : <p>Результаты ещё не внесены</p>}{agreement.history?.map((entry, index) => <div key={index} className="py-2"><p>{entry.at}</p>{entry.previous?.terms?.details ? <p>{entry.previous.terms.details}</p> : null}{entry.previous?.instruction ? <p className="whitespace-pre-wrap">{entry.previous.instruction}</p> : null}</div>)}<Button variant="outline" onClick={() => openWork(partner.client_business_id)}>Перейти к рабочим вкладкам</Button></details>
    </> : result ? <>
      <h2 className="text-xl font-semibold"><span className="tabular-nums">{result.counts.partners}</span> подтверждённых партнёров</h2>
      <p className="tabular-nums">Запущено: {result.counts.launched} · Готовится к запуску: {result.counts.preparing} · Требуют решения: {result.counts.needs_decision}</p>
      {scope.kind === 'network' ? <><Button variant="outline" onClick={() => setChooseLocation(!chooseLocation)}>Работа по точкам</Button>{chooseLocation ? <div>{result.locations?.map(location => <Button key={location.id} variant="ghost" className="block min-h-11" onClick={() => openWork(location.id)}>{location.name}</Button>)}</div> : null}</> : null}
      {!confirmed.length ? <div><p>Подтверждённых партнёрств пока нет.</p><Button className="mt-3" onClick={() => scope.kind === 'network' ? setChooseLocation(true) : openWork()}>Перейти к поиску и переговорам</Button></div> : confirmed.map(item => <button key={item.id} className="block min-h-11 w-full border-b py-4 text-left active:scale-[0.96]" onClick={() => open(item)}><b>{item.name}</b><p className="text-sm text-muted-foreground">{item.business_name} · {item.partnership_launched_at ? 'Запущено' : 'Готовится к запуску'}</p><p className="text-pretty">{item.agreement_json.terms?.details}</p><span className="text-sm underline">Условия и инструкция</span></button>)}
      {pending.length ? <details><summary className="min-h-11 cursor-pointer py-3">Зафиксировать договорённость ({pending.length})</summary>{pending.map(item => <Button key={item.id} variant="ghost" className="block min-h-11" onClick={() => open(item)}>{item.name} · {item.business_name}</Button>)}</details> : null}
    </> : null}
  </section>;
}
