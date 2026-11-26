import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { api } from '@/services/api';
import { setupUrl, visibleError } from './useInitialBusinessSetup';

type Plan = {
  id: string;
  title: string;
  version: string;
  topics: string[];
  reviewed: boolean;
  needs_text: number;
  needs_post_review: number;
};
type Progress = {
  step: 'maps' | 'plan' | 'generating' | 'photos' | 'review' | 'texts' | 'socials' | 'monthly';
  plan: Plan | null;
  fact_count: number;
  photos: { total: number; analyzed: number };
  job: { status: string } | null;
  can_edit: boolean;
  can_plan: boolean;
  viewer_is_owner: boolean;
  timezone: string | null;
  monthly: { active: boolean; first_month: string | null; can_enable: boolean; can_pause: boolean };
};

function setupPath(path: string, businessId: string, params: Record<string, string> = {}) {
  return path + '?' + new URLSearchParams({ business_id: businessId, ...params });
}

export function SetupFollowThrough({ businessId }: { businessId: string }) {
  const [progress, setProgress] = useState<Progress | null>(null);
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
  useEffect(() => {
    const controller = new AbortController();
    const update = () => void refresh(controller.signal);
    if (!busy) window.addEventListener('focus', update);
    const interval = pending && !busy ? window.setInterval(update, 2_500) : undefined;
    return () => {
      controller.abort();
      window.removeEventListener('focus', update);
      window.clearInterval(interval);
    };
  }, [refresh, pending, busy]);

  async function act(action: string, plan?: Plan) {
    if (busy) return;
    const revision = ++request.current;
    setBusy(true);
    setError('');
    try {
      const response = await api.post(endpoint, { action, ...(plan ? { plan_id: plan.id, version: plan.version } : {}) });
      if (revision === request.current) setProgress(response.data);
    } catch (reason) {
      if (revision === request.current) setError(visibleError(reason));
    } finally {
      setBusy(false);
    }
  }

  const returnPath = setupPath('/dashboard/operator', businessId, { setup: '1' });
  const link = (path: string, params?: Record<string, string>) =>
    setupPath(path, businessId, { ...params, return_to: returnPath });
  const plan = progress?.plan;
  const calendarPath = link('/dashboard/content', { section: 'calendar', ...(plan ? { plan_id: plan.id } : {}) });
  const photoPath = link('/dashboard/content', { section: 'media' });
  const planLink = <Button size="sm" variant="outline" asChild><Link to={calendarPath}>Открыть контент-план</Link></Button>;
  const failed = progress?.job?.status === 'failed' || progress?.job?.status === 'cancelled';
  const actionButton = (action: string, label: string, secondary = false) =>
    <Button size="sm" variant={secondary ? 'ghost' : 'outline'} disabled={busy} onClick={() => void act(action)}>{label}</Button>;

  if (!progress && !error) return null;

  return <section aria-label="Следующий шаг настройки" aria-busy={busy || pending} className="space-y-2 rounded-md bg-muted/50 px-3 py-2.5">
    {error && <div className="flex flex-wrap items-center gap-1"><p role="alert" className="text-xs text-destructive">{error}</p>
      <Button size="sm" variant="ghost" disabled={busy} onClick={() => void refresh()}>Обновить</Button></div>}
    {failed && progress?.can_edit && progress.can_plan && <div className="flex flex-wrap items-center gap-1">
      <p className="text-xs text-muted-foreground">Подготовку плана можно повторить.</p>{actionButton('retry', 'Повторить подготовку')}
    </div>}
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
          onClick={() => void act('approve', plan)}>Утвердить темы</Button>}
      </details>
      {planLink}
    </>}
    {progress?.step === 'texts' && plan && <>
      <p className="font-medium">{plan.needs_text ? 'Подготовим тексты к утверждённым темам' : 'Проверим тексты постов'}</p>
      <div className="flex flex-wrap gap-1"><Button size="sm" variant="outline" asChild><Link to={calendarPath}>
        {plan.needs_text ? 'Открыть темы для подготовки текстов' : 'Открыть тексты на проверку'}
      </Link></Button>{progress.can_edit && actionButton('texts_deferred', 'Проверить тексты позже', true)}</div>
    </>}
    {progress?.step === 'socials' && <>
      <p className="font-medium">Подключим соцсети</p>
      <div className="flex flex-wrap gap-1">
        <Button size="sm" variant="outline" asChild><Link to={link('/dashboard/settings', { focus: 'channels' })}>Подключить соцсети</Link></Button>
        {progress.can_edit && actionButton('socials_deferred', 'Готовить для ручной публикации', true)}
      </div>
    </>}
    {progress?.step === 'monthly' && <>
      <p className="font-medium">{progress.monthly.active ? 'Ежемесячный контент-план включён' : 'Готовить план раз в месяц'}</p>
      {progress.monthly.active
        ? <p className="text-xs text-muted-foreground">Новые темы будут появляться здесь на утверждение.</p>
        : <p className="text-xs text-muted-foreground">LocalOS подготовит черновик из актуальных фактов. Темы утверждает владелец.</p>}
      {progress.viewer_is_owner && !progress.monthly.can_enable && !progress.monthly.active && <p className="text-xs text-muted-foreground">Расписание доступно на тарифе «Управление».</p>}
      {progress.monthly.can_enable && !progress.monthly.active && !progress.timezone && <Button size="sm" variant="outline" asChild>
        <Link to={link('/dashboard/profile')}>Указать часовой пояс</Link></Button>}
      <div className="flex flex-wrap gap-1">{planLink}
        {progress.monthly.can_enable && !progress.monthly.active && progress.timezone && actionButton('enable_monthly', 'Включить раз в месяц')}
        {progress.monthly.can_pause && actionButton('pause_monthly', 'Приостановить', true)}
      </div>
    </>}
  </section>;
}
