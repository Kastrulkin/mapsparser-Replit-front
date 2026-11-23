import { useLatestCallback } from '@/hooks/useLatestCallback';
import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { OperatorPhotoPreview } from '@/components/operator/OperatorPhotoGallery';
import { newAuth } from '@/lib/auth_new';

type Config = { business_id: string; plan_id: string; account_id: string; location: string; time: string; timezone: string; start_date: string };
type Post = { id: string; theme: string; date: string; text: string; status: string; photos: { id: string; url: string }[] };
type Check = { posts: Post[]; preview_hash: string; ready_count: number; checked_files: boolean };
type Renewal = { enabled: boolean; supported?: boolean; last_date?: string; not_before?: string; reason?: string; job?: { status: string; error_text?: string; result_json?: { plan_id?: string; failures?: unknown[] } } };
type State = { status: string; config: Config | null; config_version: number; options: { plans: { id: string; period_start: string; period_end: string }[]; accounts: { id: string; external_id: string; display_name: string }[] }; runs?: { id: string; status: string; started_at: string; output_json: { posts?: { post_id: string; status: string }[] } }[] };
const labels: Record<string,string> = { ready: 'Готов к автопубликации', already_published: 'Уже опубликован — пропустим', already_in_progress: 'Уже в очереди или отправляется — не повторяем', needs_reconciliation: 'Нужна сверка прежней отправки — не повторяем', past_date: 'Прошедшая дата — не публикуем задним числом', needs_approval: 'Не утверждён — пропустим', missing_text: 'Нет текста', wrong_channel: 'Нужна Google-версия', connection_changed: 'Изменилась Google-карточка', approval_changed: 'Текст или фото изменились — подтвердите пост заново', missing_photo: 'Выберите и утвердите фото', photo_unavailable: 'Не удалось прочитать выбранное фото' };

export function GoogleContentAutomation({ businessId }: { businessId: string }) {
  const [state,setState] = useState<(State & {renewal?: Renewal}) | null>(null);
  const [renewalConfirm,setRenewalConfirm] = useState(false);
  const [draft,setDraft] = useState<Config | null>(null);
  const [check,setCheck] = useState<Check | null>(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [confirm,setConfirm] = useState(false);
  const generation = useRef(0);
  const endpoint = '/agent-blueprints/google-content/config?business_id='+encodeURIComponent(businessId);
  const request = async (body?: object) => {
    const response = await newAuth.makeRequest(endpoint,{method:body?'POST':'GET',...(body?{body:JSON.stringify(body)}:{})});
    if (response.success !== true) throw new Error(response.error || 'Не удалось получить настройки');
    return response.result;
  };
  const installState = (result: State & {renewal?: Renewal}) => {
    setState(result);
    const selected = result.options.accounts[0];
    const timezone = 'default_timezone' in result.options && typeof result.options.default_timezone === 'string' ? result.options.default_timezone : 'Asia/Yerevan';
    setDraft(result.config || {business_id:businessId,plan_id:result.options.plans[0]?.id || '',account_id:selected?.id || '',location:selected?.external_id || '',time:'10:00',timezone,start_date:new Date(Date.now()+86400000).toLocaleDateString('en-CA',{timeZone:timezone})});
  };
  const loadConfig = useLatestCallback(async (version: number) => {
    const result = await request();
    if (version === generation.current) installState(result);
  });
  useEffect(() => {
    const version = ++generation.current;
    setState(null);setDraft(null);setCheck(null);setError('');setConfirm(false);setBusy(true);
    void loadConfig(version)
      .catch(reason => {if(version===generation.current) setError(reason instanceof Error?reason.message:'Не удалось загрузить');})
      .finally(() => {if(version===generation.current) setBusy(false);});
    return () => {generation.current += 1;};
    // The authenticated request is scoped to this business; discard late responses.
  },[businessId, loadConfig]);
  const action = async (kind: string) => {
    if (!draft || !state || busy) return;
    const version = generation.current;
    setBusy(true);setError('');
    try {
      const result = await request({action:kind,...(kind==='save'?draft:{}),expected_version:state.config_version,preview_hash:check?.preview_hash,confirm:kind==='enable_renewal'?renewalConfirm:confirm});
      if(version!==generation.current) return;
      if(kind==='preview') {setCheck(result);setConfirm(false);}
      else {installState(result);setCheck(null);setConfirm(false);setRenewalConfirm(false);}
    } catch(reason) {
      if(version===generation.current) {setError(reason instanceof Error?reason.message:'Не удалось сохранить');setCheck(null);setConfirm(false);}
    } finally {if(version===generation.current) setBusy(false);}
  };
  const update = (values: Partial<Config>) => {if(draft) setDraft({...draft,...values});setCheck(null);setConfirm(false);};
  const active = state?.status==='active';
  const changed = JSON.stringify(draft)!==JSON.stringify(state?.config);
  return <section aria-label="Автопубликация в Google" className="mb-6 space-y-4 rounded-xl border bg-card p-4 text-card-foreground">
    <div><h2 className="text-xl font-semibold">Публикации в Google по контент-плану</h2><p className="text-sm text-muted-foreground">Утверждённые версии Google и выбранные фото этого бизнеса. Без новой генерации и публикаций задним числом.</p></div>
    <p role="status">{active?'Включено':state?.status==='paused'?'Приостановлено':state?.config?'Настройки сохранены — публикации ещё не включены':'Сначала выберите план и проверьте публикации'}</p>
    {error && <p role="alert" className="text-destructive">{error}</p>}
    {!state && <p>{busy?'Загружаем настройки…':'Настройки недоступны. Обновите страницу.'}</p>}
    {draft && state && <>
      {!state.options.accounts.length && <p role="alert">Сначала подключите Google-карточку этого бизнеса. До подключения автопубликацию включить нельзя.</p>}
      <fieldset disabled={busy || active} className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-1"><span>Контент-план</span><select aria-label="Контент-план" className="min-h-11 w-full rounded-md border bg-background px-3" value={draft.plan_id} onChange={e=>update({plan_id:e.target.value})}>
          <option value="">Выберите существующий план</option>{state.options.plans.map(p=><option key={p.id} value={p.id}>{p.period_start} — {p.period_end} · {p.id.slice(0,8)}</option>)}
        </select></label>
        <label className="space-y-1"><span>Google-карточка</span><select aria-label="Google-карточка" className="min-h-11 w-full rounded-md border bg-background px-3" value={draft.account_id} onChange={e=>{const selected=state.options.accounts.find(a=>a.id===e.target.value);update({account_id:e.target.value,location:selected?.external_id || ''});}}>
          <option value="">Нет выбранного подключения</option>{state.options.accounts.map(a=><option key={a.id} value={a.id}>{a.display_name} · {a.external_id.split('/').pop()}</option>)}
        </select></label>
        <label className="space-y-1"><span>Время в день публикации</span><input aria-label="Время в день публикации" type="time" className="min-h-11 w-full rounded-md border bg-background px-3" value={draft.time} onChange={e=>update({time:e.target.value})}/></label>
        <label className="space-y-1"><span>Часовой пояс</span><select aria-label="Часовой пояс публикаций" className="min-h-11 w-full rounded-md border bg-background px-3" value={draft.timezone} onChange={e=>update({timezone:e.target.value})}>{['Asia/Yerevan','Asia/Tbilisi','Asia/Bangkok','Europe/Berlin','Europe/Copenhagen','Europe/Tallinn','Europe/Moscow'].map(zone=><option key={zone} value={zone}>{zone}</option>)}</select></label>
        <label className="space-y-1"><span>Начать с даты</span><input aria-label="Начать с даты" type="date" className="min-h-11 w-full rounded-md border bg-background px-3" value={draft.start_date} onChange={e=>update({start_date:e.target.value})}/></label>
      </fieldset>
      <p className="text-sm text-muted-foreground">Время проверяется существующим планировщиком: запуск возможен с небольшой задержкой. Прошедшие даты не догоняются. Уже опубликованные и неопределённые отправки не повторяются.</p>
      <div className="flex flex-wrap gap-2">
        {!active && <Button disabled={busy || !draft.plan_id || !draft.account_id || !changed} onClick={()=>void action('save')}>Сохранить настройки</Button>}
        <Button variant="outline" disabled={busy || !state.config || changed} onClick={()=>void action('preview')}>Проверить посты и фото без публикации</Button>
        {active && <Button variant="outline" disabled={busy} onClick={()=>void action('pause')}>Приостановить автопубликацию</Button>}
      </div>
      {active && <p className="text-sm">Расписание: {draft.time}, {draft.timezone}, с {draft.start_date}. Пауза прекращает новые постановки; уже переданная отправщику публикация может завершиться.</p>}
      {state.config && state.renewal?.supported !== false && <div className="space-y-3 border-t pt-4">
        <h3 className="font-semibold">Следующий контент-план</h3>
        <p className="text-sm">Последний пост: {state.renewal?.last_date || 'дата не определена'}. Подготовка продолжения — не раньше {state.renewal?.not_before || 'завершения плана'}, после подтверждённой публикации, в {draft.time} по выбранному часовому поясу.</p>
        <p className="text-sm text-muted-foreground">Новый план на 30 дней: актуальные услуги и цены, обновление запросов и отзывов, отраслевые ориентиры и ваши правки. Использование старых данных будет отмечено. Английские тексты, проверка повторов и фактов; действуют лимиты генерации. Новый план — только вам на утверждение, без автоматического подключения к публикациям.</p>
        <p role="status">{state.renewal?.enabled?'Подготовка следующего плана включена':'Подготовка следующего плана выключена'}</p>
        {state.renewal?.reason==='last_publication_unconfirmed' && <p role="alert">Последняя публикация не подтверждена. Продолжение пока не запускается.</p>}
        {state.renewal?.job && <p>Подготовка: {state.renewal.job.status==='waiting_for_review'?'Ждёт вашей проверки':state.renewal.job.status==='failed'?'Ошибка — требуется проверка':state.renewal.job.status}. {state.renewal.job.error_text || ''}</p>}
        {state.renewal?.job?.result_json?.plan_id && <a className="underline" href={'/dashboard/content?business_id='+businessId+'&plan_id='+state.renewal.job.result_json.plan_id}>Открыть продолжение на проверку</a>}
        {!state.renewal?.enabled && <>
          <label className="flex min-h-11 items-start gap-3"><input type="checkbox" checked={renewalConfirm} disabled={busy || !active} onChange={e=>setRenewalConfirm(e.target.checked)}/><span>Разрешаю подготовить следующий план после окончания текущего. Результат — мне на утверждение.</span></label>
          <Button disabled={busy || !active || !renewalConfirm || changed} onClick={()=>void action('enable_renewal')}>Включить подготовку следующего плана</Button>
        </>}
      </div>}
      {check && <div className="space-y-4">
        <h3 className="font-semibold">Проверено: {check.posts.length} постов · готовы: {check.ready_count}</h3>
        {check.posts.map(p=><article key={p.id} className="space-y-2 border-t pt-3">
          <h4 className="font-medium">{p.date} · {p.theme}</h4><p>{labels[p.status] || p.status}</p>
          <div className="grid max-w-sm grid-cols-2 gap-2">{p.photos.map(img=><OperatorPhotoPreview key={img.id} photo={{asset_id:img.id,name:p.theme}}/>)}</div>
          <details><summary className="min-h-11 cursor-pointer py-2">Показать текст Google</summary><p className="whitespace-pre-wrap">{p.text}</p></details>
        </article>)}
        {!active && <div className="space-y-3 border-t pt-4">
          <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={confirm} disabled={busy || !check.ready_count} onChange={e=>setConfirm(e.target.checked)}/><span>Разрешаю публиковать утверждённые версии этого плана в выбранной Google-карточке по расписанию.</span></label>
          <Button disabled={busy || !confirm || !check.ready_count || changed} onClick={()=>void action('activate')}>Включить автопубликацию</Button>
        </div>}
      </div>}
      {state.runs?.length ? <details><summary className="min-h-11 cursor-pointer py-2">Последние проверки очереди ({state.runs.length})</summary>{state.runs.map(r=><p key={r.id}>{r.started_at} · {r.status==='completed'?'Очередь проверена':r.status==='failed'?'Нужна проверка':r.status} · {r.output_json.posts?.length || 0} постов. Результат размещения смотрите в контент-плане.</p>)}</details>:null}
    </>}
  </section>;
}
