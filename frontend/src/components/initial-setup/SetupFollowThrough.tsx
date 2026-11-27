import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { DiskImportPanel } from '@/components/DiskImportPanel';
import { Textarea } from '@/components/ui/textarea';
import { OperatorVoiceInput } from '@/components/operator/OperatorVoice';
import { api } from '@/services/api';
import { setupUrl, visibleError } from './useInitialBusinessSetup';

type Post = {
  id: string;
  theme: string;
  version: string;
  draft_text?: string;
  finished: boolean;
  approved: boolean;
  draft_job?: { status: string };
};
type Opportunities = {
  status?: string;
  city?: string;
  has_location?: boolean;
  partner_search_unavailable?: boolean;
  gap_reported?: boolean;
  partners?: { id: string; name: string; category?: string; distance_m: number; url?: string }[];
  creators?: { name: string; platform: string; url: string }[];
  suggested_categories?: string[];
};
type Plan = {
  id: string;
  title: string;
  version: string;
  topics: string[];
  items?: Post[];
  finished?: boolean;
  reviewed: boolean;
  needs_text: number;
  needs_post_review: number;
};
type Progress = {
  step: 'opportunities' | 'facts' | 'maps' | 'plan' | 'generating' | 'photos' | 'review' | 'texts' | 'socials' | 'monthly';
  plan: Plan | null;
  fact_count: number;
  facts?: { id: string; text: string }[];
  facts_version?: string;
  opportunities?: Opportunities;
  working?: boolean;
  photos: { total: number; analyzed: number };
  job: { status: string } | null;
  can_edit: boolean;
  can_plan: boolean;
  viewer_is_owner: boolean;
  timezone: string | null;
  monthly: { active: boolean; can_enable: boolean; can_pause: boolean };
};

function setupPath(path: string, businessId: string, params: Record<string, string> = {}) {
  return path + '?' + new URLSearchParams({ business_id: businessId, ...params });
}

export function SetupFollowThrough({ businessId }: { businessId: string }) {
  const [progress, setProgress] = useState<Progress | null>(null);
  const [factText, setFactText] = useState('');
  const [edit, setEdit] = useState<{post: Post; text: string} | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const request = useRef(0);
  const endpoint = setupUrl(businessId) + '/next-steps';
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const revision = ++request.current;
    try {
      const response = await api.get(endpoint, { signal });
      if (revision === request.current && !signal?.aborted) {
        setProgress(response.data);
        setError('');
      }
    } catch (reason) {
      if (revision === request.current && !signal?.aborted) setError(visibleError(reason));
    }
  }, [endpoint]);

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);

  const pending = progress?.step === 'generating';
  const refreshing = pending || progress?.step === 'opportunities' || progress?.working;
  useEffect(() => {
    const controller = new AbortController();
    const update = () => void refresh(controller.signal);
    if (!busy) window.addEventListener('focus', update);
    const interval = !busy && (refreshing || progress?.monthly?.active)
      ? window.setInterval(update, refreshing ? 2_500 : 30_000) : undefined;
    return () => {
      controller.abort();
      window.removeEventListener('focus', update);
      window.clearInterval(interval);
    };
  }, [refresh, refreshing, busy, progress?.monthly?.active]);

  async function act(action: string, data: Record<string, unknown> = {}) {
    if (busy) return false;
    const revision = ++request.current;
    setBusy(true);
    setError('');
    try {
      const response = await api.post(endpoint, { action, ...data });
      if (revision === request.current) setProgress(response.data);
      return true;
    } catch (reason) {
      if (revision === request.current) setError(visibleError(reason));
      return false;
    } finally {
      setBusy(false);
    }
  }

  const returnPath = setupPath('/dashboard/operator', businessId, { setup: '1' });
  const link = (path: string, params?: Record<string, string>) =>
    setupPath(path, businessId, { ...params, return_to: returnPath });
  const plan = progress?.plan;
  const opportunities = progress?.opportunities;
  const calendarPath = link('/dashboard/content', { section: 'calendar', ...(plan ? { plan_id: plan.id } : {}) });
  const photoPath = link('/dashboard/content', { section: 'media' });
  const planLink = <Button size="sm" variant="outline" asChild><Link to={calendarPath}>Открыть контент-план</Link></Button>;
  const failed = progress?.job?.status === 'failed' || progress?.job?.status === 'cancelled';
  const actionButton = (action: string, label: string, secondary = false) =>
    <Button size="sm" variant={secondary ? 'ghost' : 'outline'} disabled={busy} onClick={() => void act(action)}>{label}</Button>;

  if (!progress && !error) return null;

  return <section aria-label="Следующий шаг настройки" aria-busy={busy || refreshing} className="space-y-2 rounded-md bg-muted/50 px-3 py-2.5">
    {error && <div className="flex flex-wrap items-center gap-1"><p role="alert" className="text-xs text-destructive">{error}</p>
      <Button size="sm" variant="ghost" disabled={busy} onClick={() => void refresh()}>Обновить</Button></div>}
    {failed && progress?.can_edit && progress.can_plan && <div className="flex flex-wrap items-center gap-1">
      <p className="text-xs text-muted-foreground">Подготовку плана можно повторить.</p>{actionButton('retry', 'Повторить подготовку')}
    </div>}
    {progress?.step === 'opportunities' && <p role="status" className="flex items-center gap-2">
      <Loader2 aria-hidden="true" className="h-4 w-4 motion-safe:animate-spin" />Ищем партнёров и блогеров…
    </p>}
    {opportunities?.status === 'needs_city' && <div className="flex flex-wrap items-center gap-1">
      <p className="text-xs text-muted-foreground">Для местных подборок напишите в чат «Город: …».</p>
      {progress?.can_edit && actionButton('refresh_opportunities', 'Проверить город', true)}
    </div>}
    {opportunities?.status === 'failed' && <div className="flex flex-wrap items-center gap-1">
      <p className="text-xs text-muted-foreground">Подборки прервались.</p>
      {progress?.can_edit && actionButton('refresh_opportunities', 'Повторить подборки', true)}
    </div>}
    {opportunities?.status === 'ready' && <details className="rounded border bg-background px-3 py-2 [&[open]>summary>svg]:rotate-180">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 [&::-webkit-details-marker]:hidden">
        <span>Продвижение рядом · {opportunities.partners?.length || 0} партнёров · {opportunities.creators?.length || 0} блогеров</span>
        <ChevronDown aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />
      </summary>
      <div className="mt-2 space-y-2 text-xs">
        <p className="font-medium">Геомаркетинг</p>
        <p>Для совместных акций проверьте ближайшие компании по этим направлениям: {opportunities.suggested_categories?.join(', ')}.</p>
        {opportunities.partners?.length ? <p>Начните с ближайших. Согласуйте обмен рекомендациями и дайте партнёру ссылку на карточку компании.</p>
          : <p>Проверьте метку и вход на карте. Добавьте фото входа и ориентир, если по адресу трудно найти дверь.</p>}
        <p className="font-medium">Потенциальные партнёры</p>
        {opportunities.partners?.length ? <ul className="list-disc pl-4">
          {opportunities.partners.map(item => <li key={item.id}>{item.url
            ? <a className="underline" href={item.url} target="_blank" rel="noreferrer">{item.name}</a>
            : item.name} · {item.distance_m} м</li>)}</ul>
          : <p>{!opportunities.has_location ? 'Нужна точка на карте для поиска поблизости.'
            : opportunities.partner_search_unavailable ? 'Поиск на картах недоступен. В базе рядом совпадений нет.'
              : 'Подходящих компаний рядом пока нет.'}</p>}
        <p className="font-medium">Потенциальные блогеры</p>
        {opportunities.creators?.length ? <ul className="list-disc pl-4">
          {opportunities.creators.map(item => <li key={item.url}><a className="underline" href={item.url} target="_blank" rel="noreferrer">{item.name}</a></li>)}</ul>
          : <p>В базе для города {opportunities.city} пока нет подходящих блогеров.{opportunities.gap_reported && ' Команда получила задачу на поиск.'}</p>}
      </div>
    </details>}
    {progress?.step === 'facts' && <>
      <p className="font-medium">Проверим факты для контента</p>
      {progress.facts?.length ? <ul className="list-disc space-y-1 pl-4 text-xs">{progress.facts.map(fact => <li key={fact.id}>{fact.text}</li>)}</ul>
        : <p className="text-xs text-muted-foreground">Расскажите, что важно знать о вашей работе или услугах.</p>}
      {progress.can_edit && <>
        <Textarea aria-label="Факт о компании" placeholder="Добавьте факт о компании" maxLength={700}
          value={factText} onChange={event => setFactText(event.target.value)} />
        <OperatorVoiceInput businessId={businessId} channel="web" contextKey="setup-fact" compact disabled={busy}
          directSubmit={false} draftLabel="Факт о компании" submitLabel="Добавить в поле"
          onSubmit={async text => setFactText(text.slice(0,700))} />
        <div className="flex flex-wrap gap-1">
          <Button size="sm" variant="outline" disabled={busy || !factText.trim()}
            onClick={async () => { if (await act('add_fact', {text:factText})) setFactText(''); }}>Сохранить новый факт</Button>
          <Button size="sm" disabled={busy || Boolean(factText.trim())}
            onClick={() => void act('confirm_facts', {version:progress.facts_version})}>
            {progress.fact_count ? 'Факты верны' : 'Продолжить по услугам'}
          </Button>
        </div>
      </>}
    </>}
    {progress?.step === 'maps' && <>
      <p className="font-medium">Обновим карточки на картах</p>
      <p className="text-xs text-muted-foreground">Подключите карты или внесите правки из отчёта вручную.</p>
      <div className="flex flex-wrap gap-1">
        <Button size="sm" variant="outline" asChild><Link to={link('/dashboard/settings', { focus: 'integrations' })}>Подключить карты</Link></Button>
        {progress.can_edit && actionButton('maps_done', 'Перейти к контенту', true)}
      </div>
    </>}
    {progress?.step === 'plan' && <>
      <p className="font-medium">Подготовим первый контент-план</p>
      <p className="text-xs text-muted-foreground">{progress.fact_count
        ? 'Подберём темы по сохранённым фактам и услугам.'
        : 'Подберём темы по услугам. Факты о компании помогут сделать план точнее.'}</p>
      <div className="flex flex-wrap gap-1">
        {progress.can_edit && progress.can_plan && !failed && actionButton('generate', 'Подготовить план')}
        {!progress.can_plan && <Button size="sm" variant="outline" asChild><Link to={link('/dashboard/profile', { focus: 'subscription' })}>Доступ к контенту</Link></Button>}
        <Button size="sm" variant="ghost" asChild><Link to={link('/dashboard/profile', { section: 'knowledge' })}>Проверить факты</Link></Button>
      </div>
    </>}
    {pending && <p role="status" className="flex items-center gap-2">
      <Loader2 aria-hidden="true" className="h-4 w-4 motion-safe:animate-spin" />Подбираем темы для контент-плана…
    </p>}
    {progress?.step === 'photos' && <>
      <p className="font-medium">{progress.photos.total ? 'Распознаем фото' : 'Добавим фото для постов'}</p>
      <p className="text-xs text-muted-foreground">Фото можно взять из папки на Яндекс Диске или Google Drive.</p>
      {progress.can_edit && <details className="rounded border bg-background px-2 py-1">
        <summary className="cursor-pointer py-1">Подключить папку с фото</summary>
        <DiskImportPanel businessId={businessId} onImported={() => void refresh()} />
      </details>}
      <div className="flex flex-wrap gap-1"><Button size="sm" variant="outline" asChild><Link to={photoPath}>Открыть медиатеку</Link></Button>
        {progress.can_edit && actionButton('photos_skipped', 'Проверить план без фото', true)}</div>
    </>}
    {progress?.step === 'review' && plan && <>
      <p className="font-medium">План ждёт утверждения</p>
      <details className="[&[open]>summary>svg]:rotate-180">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 rounded py-1 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
          {plan.title}<ChevronDown aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />
        </summary>
        <ul className="mb-2 list-disc space-y-1 pl-4 text-xs">{plan.topics.map((topic, index) => <li key={index}>{topic}</li>)}</ul>
        {progress.viewer_is_owner && progress.can_edit && <Button size="sm" variant="outline" disabled={busy || !plan.topics.length}
          onClick={() => void act('approve', {plan_id:plan.id, version:plan.version})}>Утвердить темы</Button>}
      </details>
      {planLink}
    </>}
    {plan?.reviewed && Boolean(plan.items?.length) && <details open={progress?.step === 'texts' ? true : undefined}
      className="rounded border bg-background px-3 py-2 [&[open]>summary>svg]:rotate-180">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 [&::-webkit-details-marker]:hidden">
        <span>Посты · {plan.items?.filter(item => item.finished).length} из {plan.items?.length} опубликовано</span>
        <ChevronDown aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />
      </summary>
      {progress.can_edit && progress.can_plan && progress.step === 'texts' && plan.needs_text > 1 && !progress.working &&
        <Button size="sm" variant="outline" className="mt-2" disabled={busy}
          onClick={() => void act('draft_posts', {version:plan.version})}>Подготовить тексты</Button>}
      <div className="divide-y text-xs">
        {plan.items?.map(item => {
          const running = item.draft_job?.status === 'queued' || item.draft_job?.status === 'running';
          const values = {item_id:item.id, version:item.version};
          return <details key={item.id} className="py-2">
            <summary className="cursor-pointer">{item.theme} · {item.finished ? 'Опубликовано' : item.approved ? 'Утверждён' : running ? 'Готовим текст' : item.draft_text ? 'Черновик' : 'Нужен текст'}</summary>
            {item.draft_text && <p className="my-2 whitespace-pre-wrap">{item.draft_text}</p>}
            {item.draft_job?.status === 'failed' && <p role="status">Текст не подготовился. Можно повторить или ввести свой.</p>}
            {running && <p role="status" className="flex items-center gap-2"><Loader2 aria-hidden="true" className="h-4 w-4 motion-safe:animate-spin" />Готовим пост…</p>}
            {edit?.post.id === item.id ? <div className="space-y-1">
              <Textarea aria-label={'Текст поста ' + item.theme} value={edit.text} maxLength={12000}
                onChange={event => setEdit({post:edit.post,text:event.target.value})} />
              <Button size="sm" variant="outline" disabled={busy || !edit.text.trim()} onClick={async () => {
                if (await act('edit_post', {item_id:edit.post.id,version:edit.post.version,text:edit.text})) setEdit(null);
              }}>Сохранить текст</Button>
              <Button size="sm" variant="ghost" onClick={() => setEdit(null)}>Отмена</Button>
            </div> : progress.can_edit && !item.finished && !running && <div className="mt-2 flex flex-wrap gap-1">
              {!item.draft_text && <Button size="sm" variant="outline" disabled={busy}
                onClick={() => void act('draft_post', values)}>Подготовить текст</Button>}
              <Button size="sm" variant="ghost" disabled={busy} onClick={() => setEdit({post:item,text:item.draft_text || ''})}>
                {item.draft_text ? 'Редактировать' : 'Написать текст'}
              </Button>
              {item.draft_text && <Button size="sm" variant="ghost" onClick={async () => {
                try { await navigator.clipboard.writeText(item.draft_text || ''); } catch { setError('Не удалось скопировать текст.'); }
              }}>Скопировать текст</Button>}
              {progress.viewer_is_owner && item.draft_text && !item.approved && <Button size="sm" variant="outline"
                disabled={busy} onClick={() => void act('approve_post', values)}>Утвердить текст</Button>}
              {progress.viewer_is_owner && item.approved && <Button size="sm" variant="outline"
                disabled={busy} onClick={() => void act('post_published', values)}>Отметить опубликованным</Button>}
            </div>}
          </details>;
        })}
      </div>
    </details>}
    {progress?.step === 'texts' && plan && <>
      <p className="font-medium">{plan.needs_text ? 'Подготовим тексты к утверждённым темам' : 'Проверим тексты постов'}</p>
      <div className="flex flex-wrap gap-1">{planLink}{progress.can_edit && actionButton('texts_deferred', 'Проверить тексты позже', true)}</div>
    </>}
    {progress?.step === 'socials' && <>
      <p className="font-medium">Подключим соцсети</p>
      <div className="flex flex-wrap gap-1">
        <Button size="sm" variant="outline" asChild><Link to={link('/dashboard/settings', { focus: 'channels' })}>Подключить соцсети</Link></Button>
        {progress.can_edit && actionButton('socials_deferred', 'Готовить для ручной публикации', true)}
      </div>
    </>}
    {progress?.step === 'monthly' && <>
      <p className="font-medium">{progress.monthly.active ? 'Подготовка следующего плана включена' : 'Подготовить следующий план автоматически'}</p>
      {progress.monthly.active
        ? <p className="text-xs text-muted-foreground">Когда все посты будут опубликованы, здесь появятся новые темы на утверждение.</p>
        : <p className="text-xs text-muted-foreground">LocalOS подготовит черновик из актуальных фактов. Темы утверждает владелец.</p>}
      {progress.viewer_is_owner && !progress.monthly.can_enable && !progress.monthly.active && <p className="text-xs text-muted-foreground">Расписание доступно на тарифе «Управление».</p>}
      {progress.monthly.can_enable && !progress.monthly.active && !progress.timezone && <Button size="sm" variant="outline" asChild>
        <Link to={link('/dashboard/profile')}>Указать часовой пояс</Link></Button>}
      <div className="flex flex-wrap gap-1">{planLink}
        {progress.monthly.can_enable && !progress.monthly.active && progress.timezone && actionButton('enable_monthly', 'Включить после завершения плана')}
        {progress.monthly.can_pause && actionButton('pause_monthly', 'Приостановить', true)}
      </div>
    </>}
  </section>;
}
