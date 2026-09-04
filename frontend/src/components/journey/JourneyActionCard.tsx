import { useRef, useState } from 'react';
import { ArrowRight, Check, Clipboard, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { createJourneyCommandIdempotencyKey, runJourneyCommand, type JourneyAction } from '@/lib/leadJourney';
import { cn } from '@/lib/utils';

const commandLabel: Record<string, string> = {
  mark_sent: 'Сообщение отправлено', record_reply: 'Сохранить ответ', prepare_followup: 'Подготовить follow-up',
  save_terms: 'Сохранить условия', mark_launched: 'Партнёрство запущено', mark_published: 'Размещение вышло',
  add_result: 'Добавить результат', complete: 'Готово', start_next_cycle: 'Начать следующий цикл', open_upgrade: 'Выбрать тариф',
  prepare: 'Подготовить черновик', save_draft: 'Сохранить черновик', schedule: 'Добавить в календарь',
  save_configuration: 'Сохранить настройку', approve: 'Подтвердить план', link_run: 'Проверить завершённый запуск',
};

const primaryCommand = (action: JourneyAction) => action.allowed_commands.find((item) => item !== 'copy') || action.allowed_commands[0] || '';

export const JourneyActionCard = ({ action, businessId, surface = 'web', dark = false, onUpdated }: { action: JourneyAction; businessId: string; surface?: 'web' | 'telegram_mini_app'; dark?: boolean; onUpdated: (nextAction?: JourneyAction) => void }) => {
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const retryKeys = useRef(new Map<string, string>());
  const [outcome, setOutcome] = useState('interested');
  const [details, setDetails] = useState('');
  const [inquiries, setInquiries] = useState('');
  const [sales, setSales] = useState('');
  const [draftText, setDraftText] = useState(typeof action.payload?.draft_text === 'string' ? action.payload.draft_text : typeof action.payload?.content_excerpt === 'string' ? action.payload.content_excerpt : '');
  const [scheduledFor, setScheduledFor] = useState(typeof action.payload?.scheduled_for === 'string' ? action.payload.scheduled_for : '');
  const [views, setViews] = useState('');
  const [useCase, setUseCase] = useState(typeof action.payload?.use_case === 'string' ? action.payload.use_case : 'reviews_without_reply');
  const [expectedResult, setExpectedResult] = useState(typeof action.payload?.expected_result === 'string' ? action.payload.expected_result : 'Подготовленные материалы для проверки');
  const command = primaryCommand(action);

  const execute = async (nextCommand: string) => {
    if (!nextCommand || busy) return;
    setBusy(nextCommand);
    setError('');
    const retryKey = `${action.id}:${action.version}:${nextCommand}`;
    const idempotencyKey = retryKeys.current.get(retryKey) || createJourneyCommandIdempotencyKey();
    retryKeys.current.set(retryKey, idempotencyKey);
    const payload: Record<string, unknown> = {};
    if (nextCommand === 'record_reply') payload.outcome = outcome;
    if (nextCommand === 'save_configuration') {
      payload.use_case = useCase;
      payload.expected_result = expectedResult;
    }
    if (nextCommand === 'approve') payload.confirmed = true;
    if (nextCommand === 'save_terms') payload.details = details;
    if (nextCommand === 'mark_launched') payload.mechanic = details || 'other';
    if (nextCommand === 'mark_published') payload.publication_url = details;
    if (nextCommand === 'save_draft') {
      payload.draft_text = draftText;
      if (action.entity_id) payload.content_plan_item_id = action.entity_id;
    }
    if (nextCommand === 'schedule') {
      payload.scheduled_for = scheduledFor;
      if (action.entity_id) payload.content_plan_item_id = action.entity_id;
    }
    if (nextCommand === 'add_result') {
      payload.inquiries = Number(inquiries || 0);
      payload.sales = Number(sales || 0);
      if (action.flow_type === 'content') payload.views = Number(views || 0);
      payload.note = details;
      if (action.flow_type === 'automation') payload.result_summary = details;
    }
    try {
      const result = await runJourneyCommand({ action, businessId, command: nextCommand, payload, surface, idempotencyKey });
      retryKeys.current.delete(retryKey);
      if (nextCommand === 'open_upgrade') {
        const returnTo = `${window.location.pathname}${window.location.search}`;
        const accessUrl = action.access?.cta_target?.url || '/dashboard/profile?focus=subscription#subscription';
        const separator = accessUrl.includes('?') ? '&' : '?';
        window.location.assign(`${accessUrl}${separator}return_to=${encodeURIComponent(returnTo)}`);
        return;
      }
      onUpdated(result.next_action || undefined);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось сохранить действие');
    } finally {
      setBusy('');
    }
  };

  const copyMessage = async () => {
    const message = typeof action.payload?.message === 'string' ? action.payload.message : typeof action.payload?.message_excerpt === 'string' ? action.payload.message_excerpt : action.description;
    try { await navigator.clipboard.writeText(message); } catch { /* Manual selection remains available in the detail workspace. */ }
    await execute('copy');
  };

  return (
    <article className={cn('rounded-[24px] p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.07),0_16px_44px_-32px_rgba(15,23,42,0.42)]', dark ? 'bg-white/[0.045] text-zinc-100 shadow-[0_0_0_1px_rgba(255,255,255,0.075)]' : 'bg-white text-slate-950')}>
      <div className="flex items-start gap-3"><span className={cn('grid h-10 w-10 shrink-0 place-items-center rounded-[14px]', dark ? 'bg-primary/15 text-primary' : 'bg-orange-50 text-orange-700')}><Check className="h-5 w-5" /></span><div className="min-w-0 flex-1"><div className={cn('text-xs font-semibold uppercase tracking-[0.12em]', dark ? 'text-primary' : 'text-orange-700')}>Что сделать сейчас</div><h3 className="mt-1 text-balance text-lg font-semibold">{action.title}</h3><p className={cn('mt-2 text-pretty text-sm leading-6', dark ? 'text-zinc-400' : 'text-slate-600')}>{action.description}</p>{action.due_at ? <p className="mt-2 text-xs tabular-nums opacity-60">Срок: {new Date(action.due_at).toLocaleString('ru-RU')}</p> : null}</div></div>

      {action.action_type === 'check_reply' ? <div className="mt-4"><Select value={outcome} onValueChange={setOutcome}><SelectTrigger className={cn('min-h-11', dark && 'border-white/10 bg-black/20 text-zinc-200')}><SelectValue /></SelectTrigger><SelectContent><SelectItem value="interested">Интересно</SelectItem><SelectItem value="paid">Просит оплату</SelectItem><SelectItem value="barter">Готов на бартер</SelectItem><SelectItem value="details">Нужны детали</SelectItem><SelectItem value="refused">Отказал</SelectItem><SelectItem value="other">Другое</SelectItem></SelectContent></Select></div> : null}
      {['define_terms', 'mark_launched', 'mark_published', 'waiting_for_publication', 'add_result', 'add_content_result'].includes(action.action_type) ? <Textarea value={details} onChange={(event) => setDetails(event.target.value)} className={cn('mt-4 min-h-24', dark && 'border-white/10 bg-black/20 text-zinc-100')} placeholder={['mark_published', 'waiting_for_publication'].includes(action.action_type) ? 'Ссылка на публикацию' : 'Условия или комментарий'} /> : null}
      {action.action_type === 'review_content' ? <Textarea value={draftText} onChange={(event) => setDraftText(event.target.value)} className={cn('mt-4 min-h-40', dark && 'border-white/10 bg-black/20 text-zinc-100')} placeholder="Проверьте и отредактируйте черновик" /> : null}
      {action.action_type === 'save_to_calendar' ? <Input type="date" value={scheduledFor} onChange={(event) => setScheduledFor(event.target.value)} className={cn('mt-4 min-h-11', dark && 'border-white/10 bg-black/20 text-zinc-100')} aria-label="Дата публикации" /> : null}
      {action.action_type === 'configure_automation' ? <div className="mt-4 grid gap-3"><label className={cn('text-sm font-medium', dark ? 'text-zinc-300' : 'text-slate-700')}>Что поручить<Select value={useCase} onValueChange={setUseCase}><SelectTrigger className={cn('mt-2 min-h-11', dark && 'border-white/10 bg-black/20 text-zinc-200')}><SelectValue /></SelectTrigger><SelectContent><SelectItem value="reviews_without_reply">Собирать отзывы без ответа</SelectItem><SelectItem value="content_drafts">Готовить черновики контента</SelectItem><SelectItem value="map_changes">Проверять изменения карточек</SelectItem><SelectItem value="weekly_summary">Собирать недельную сводку</SelectItem></SelectContent></Select></label><label className={cn('text-sm font-medium', dark ? 'text-zinc-300' : 'text-slate-700')}>Что должно получиться<Input value={expectedResult} onChange={(event) => setExpectedResult(event.target.value)} className={cn('mt-2 min-h-11', dark && 'border-white/10 bg-black/20 text-zinc-100')} /></label></div> : null}
      {action.action_type === 'run_automation' ? <p className={cn('mt-4 rounded-2xl p-4 text-sm leading-6', dark ? 'bg-white/[0.05] text-zinc-300' : 'bg-slate-50 text-slate-600')}>Настройте и запустите ИИ-сотрудника в рабочей области ниже. Затем вернитесь к этому шагу и нажмите «Проверить завершённый запуск».</p> : null}
      {action.action_type === 'review_automation_result' ? <Textarea value={details} onChange={(event) => setDetails(event.target.value)} className={cn('mt-4 min-h-24', dark && 'border-white/10 bg-black/20 text-zinc-100')} placeholder="Что подтверждено результатом запуска" /> : null}
      {action.action_type === 'add_result' ? <div className="mt-3 grid grid-cols-2 gap-2"><Input inputMode="numeric" value={inquiries} onChange={(event) => setInquiries(event.target.value)} placeholder="Обращения" className={cn('min-h-11', dark && 'border-white/10 bg-black/20 text-zinc-100')} /><Input inputMode="numeric" value={sales} onChange={(event) => setSales(event.target.value)} placeholder="Продажи" className={cn('min-h-11', dark && 'border-white/10 bg-black/20 text-zinc-100')} /></div> : null}
      {action.action_type === 'add_content_result' ? <div className="mt-3 grid grid-cols-2 gap-2"><Input inputMode="numeric" value={views} onChange={(event) => setViews(event.target.value)} placeholder="Просмотры" className={cn('min-h-11', dark && 'border-white/10 bg-black/20 text-zinc-100')} /><Input inputMode="numeric" value={inquiries} onChange={(event) => setInquiries(event.target.value)} placeholder="Обращения" className={cn('min-h-11', dark && 'border-white/10 bg-black/20 text-zinc-100')} /></div> : null}
      {error ? <p className={cn('mt-3 text-sm', dark ? 'text-red-300' : 'text-red-700')}>{error}</p> : null}
      <div className="mt-5 flex flex-col gap-2 sm:flex-row">
        {action.allowed_commands.includes('copy') ? <Button type="button" variant="outline" onClick={() => void copyMessage()} disabled={Boolean(busy)} className={cn('min-h-11 gap-2 transition-transform active:scale-[0.96]', dark && 'border-white/10 bg-white/[0.04] text-zinc-200 hover:bg-white/[0.08] hover:text-white')}><Clipboard className="h-4 w-4" />Скопировать</Button> : null}
        {command ? <Button type="button" onClick={() => void execute(command)} disabled={Boolean(busy)} className="min-h-11 gap-2 transition-transform active:scale-[0.96]">{busy === command ? <Loader2 className="h-4 w-4 animate-spin" /> : null}{command === 'complete' ? action.cta_label : commandLabel[command] || action.cta_label}<ArrowRight className="h-4 w-4" /></Button> : null}
        {action.action_type === 'check_reply' && action.allowed_commands.includes('prepare_followup') ? <Button type="button" variant="outline" onClick={() => void execute('prepare_followup')} disabled={Boolean(busy)} className={cn('min-h-11 transition-transform active:scale-[0.96]', dark && 'border-white/10 bg-white/[0.04] text-zinc-200')}>Ответа нет — follow-up</Button> : null}
      </div>
    </article>
  );
};
