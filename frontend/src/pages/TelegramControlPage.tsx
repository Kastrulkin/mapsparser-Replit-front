import { FormEvent, useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  AlertCircle, ArrowLeft, Bot, Building2, Check, ChevronRight, CircleEllipsis,
  ClipboardCheck, Copy, CreditCard, FileText, LayoutGrid, Loader2, MapPinned,
  MessageCircle, Network, Search, Send, Settings, ShieldCheck, Sparkles, Star,
  Users, WandSparkles,
} from 'lucide-react';

type Scope = {
  kind: 'platform' | 'network' | 'business';
  id?: string | null;
  name?: string;
  business_ids?: string[];
  can_switch?: boolean;
};

type AttentionItem = {
  id?: string;
  title?: string;
  description?: string;
  count?: number;
  status?: string;
  severity?: string;
  target_scope?: { id?: string };
};

type Metric = {
  key?: string;
  label?: string;
  value?: string | number | null;
  source?: string;
  source_label?: string;
  updated_at?: string;
};

type Summary = {
  scope?: Scope;
  attention_items?: AttentionItem[];
  metrics?: Metric[];
  data_warnings?: string[];
};

type Catalog = {
  platform?: Scope | null;
  networks?: Array<{ id?: string; name?: string; locations_count?: number }>;
  businesses?: Array<{ id?: string; name?: string; address?: string; network_name?: string }>;
  total_choices?: number;
};

type Bootstrap = {
  success?: boolean;
  error?: string;
  selected_scope?: Scope;
  summary?: Summary;
  catalog?: Catalog;
  web_session_token?: string;
  navigation?: Array<{ key: string; label: string; group: string }>;
};

type Workspace = {
  items?: AttentionItem[];
  counts?: { attention?: number; total?: number };
  summary?: Summary;
  data_warnings?: string[];
};

type Review = {
  id: string;
  business_id?: string;
  location_name?: string;
  source?: string;
  rating?: number;
  author_name?: string;
  text?: string;
  response_text?: string;
  published_at?: string;
  reply_draft_id?: string;
  reply_draft_text?: string;
  reply_draft_status?: string;
};

type ReviewResult = {
  items?: Review[];
  counts?: { total?: number; unanswered?: number; drafts?: number };
  cursor?: string | null;
};

type OperatorMessage = { role: 'user' | 'operator'; text: string };
type Tab = 'today' | 'tasks' | 'reviews' | 'operator' | 'more';

type TelegramWebApp = {
  initData?: string;
  ready?: () => void;
  expand?: () => void;
  openTelegramLink?: (url: string) => void;
  BackButton?: { show: () => void; hide: () => void; onClick: (callback: () => void) => void; offClick: (callback: () => void) => void };
};

declare global {
  interface Window { Telegram?: { WebApp?: TelegramWebApp } }
}

const previewBootstrap: Bootstrap = {
  success: true,
  selected_scope: { kind: 'business', id: 'preview', name: 'Весёлая расчёска', business_ids: ['preview'], can_switch: true },
  summary: {
    attention_items: [
      { id: 'reviews_unanswered', title: '50 отзывов ждут ответа', description: 'LocalOS собрал их в одну очередь.', count: 50, severity: 'high' },
      { id: 'drafts', title: '12 черновиков готовы', description: 'Нужно проверить тон и подтвердить.', count: 12, severity: 'medium' },
    ],
    metrics: [
      { key: 'map', label: 'На карте', value: 296, source_label: 'Яндекс Карты', updated_at: new Date().toISOString() },
      { key: 'loaded', label: 'В LocalOS', value: 164, source_label: 'Отзывы LocalOS', updated_at: new Date().toISOString() },
    ],
  },
  catalog: {
    platform: { kind: 'platform', name: 'Вся платформа' },
    networks: [{ id: 'network', name: 'Сеть «Весёлая расчёска»', locations_count: 2 }],
    businesses: [{ id: 'preview', name: 'Весёлая расчёска', address: 'Москва, Тверская, 7' }], total_choices: 3,
  },
};

const previewReviews: Review[] = [
  { id: '1', business_id: 'preview', location_name: 'Весёлая расчёска', source: 'Яндекс', rating: 5, author_name: 'Анна К.', text: 'Очень понравилась стрижка и отношение мастера. Обязательно вернусь!', published_at: new Date().toISOString() },
  { id: '2', business_id: 'preview', location_name: 'Весёлая расчёска', source: '2ГИС', rating: 3, author_name: 'Игорь', text: 'Пришлось ждать почти 20 минут, но результат хороший.', published_at: new Date().toISOString(), reply_draft_text: 'Игорь, спасибо, что поделились. Извините за ожидание.', reply_draft_id: 'd2' },
];

const spring = { type: 'spring', duration: 0.3, bounce: 0 };
const webApp = () => window.Telegram?.WebApp;
const isPreview = () => ['localhost', '127.0.0.1'].includes(window.location.hostname) && new URLSearchParams(window.location.search).get('preview') === '1';

const readJson = async <T,>(response: Response): Promise<T> => {
  const payload = await response.json();
  if (!response.ok || payload?.success === false) throw new Error(payload?.error || 'Не удалось выполнить запрос.');
  return payload;
};

const scopeQuery = (scope?: Scope) => {
  const params = new URLSearchParams();
  if (scope?.kind) params.set('scope_type', scope.kind);
  if (scope?.id) params.set('scope_id', scope.id);
  return params;
};

const authHeaders = () => ({ 'Content-Type': 'application/json', Authorization: `Bearer ${window.sessionStorage.getItem('localos_mini_session') || ''}` });

export const TelegramControlPage = () => {
  const preview = isPreview();
  const initData = webApp()?.initData || '';
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(preview ? previewBootstrap : null);
  const [workspace, setWorkspace] = useState<Workspace | null>(preview ? { items: previewBootstrap.summary?.attention_items, summary: previewBootstrap.summary } : null);
  const [tab, setTab] = useState<Tab>('today');
  const [module, setModule] = useState('');
  const [loading, setLoading] = useState(!preview);
  const [slowLoading, setSlowLoading] = useState(false);
  const [error, setError] = useState('');
  const [picker, setPicker] = useState(false);
  const [search, setSearch] = useState('');
  const [taskFilter, setTaskFilter] = useState('attention');
  const [reviewStatus, setReviewStatus] = useState('unanswered');
  const [reviews, setReviews] = useState<ReviewResult>(preview ? { items: previewReviews, counts: { total: 164, unanswered: 50, drafts: 12 } } : {});
  const [reviewsLoading, setReviewsLoading] = useState(false);
  const [command, setCommand] = useState('');
  const [operatorBusy, setOperatorBusy] = useState(false);
  const [reviewActionBusy, setReviewActionBusy] = useState('');
  const [messages, setMessages] = useState<OperatorMessage[]>([]);

  const scope = bootstrap?.selected_scope || bootstrap?.summary?.scope;
  const summary = workspace?.summary || bootstrap?.summary;
  const tasks = workspace?.items?.length ? workspace.items : summary?.attention_items || [];
  const catalog = bootstrap?.catalog;
  const hasSwitcher = Boolean(scope?.can_switch || Number(catalog?.total_choices || 0) > 1);

  const loadWorkspace = async (nextScope?: Scope) => {
    if (preview) return;
    const params = scopeQuery(nextScope || scope);
    const result = await fetch(`/api/operator/mobile/workspace?${params.toString()}`, { headers: authHeaders() }).then(readJson<Workspace>);
    setWorkspace(result);
  };

  const loadBootstrap = async (query = '') => {
    if (preview) return;
    if (!initData) { setLoading(false); return; }
    const timer = window.setTimeout(() => setSlowLoading(true), 400);
    try {
      const result = await fetch('/api/operator/telegram/bootstrap', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ init_data: initData, q: query }),
      }).then(readJson<Bootstrap>);
      if (result.web_session_token) window.sessionStorage.setItem('localos_mini_session', result.web_session_token);
      setBootstrap(result);
      if (!query) await loadWorkspace(result.selected_scope);
      setError('');
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось открыть LocalOS.');
    } finally {
      window.clearTimeout(timer); setSlowLoading(false); setLoading(false);
    }
  };

  useEffect(() => { webApp()?.ready?.(); webApp()?.expand?.(); void loadBootstrap(); }, []);
  useEffect(() => {
    if (!picker || !initData || !search.trim()) return;
    const timer = window.setTimeout(() => void loadBootstrap(search.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [picker, search]);

  useEffect(() => {
    const back = webApp()?.BackButton;
    if (!back) return;
    const goBack = () => { if (module) setModule(''); else if (picker) setPicker(false); else setTab('today'); };
    if (module || picker || tab !== 'today') { back.show(); back.onClick(goBack); } else back.hide();
    return () => back.offClick(goBack);
  }, [module, picker, tab]);

  const chooseScope = async (kind: string, id?: string | null) => {
    if (preview) { setPicker(false); return; }
    setLoading(true);
    try {
      const result = await fetch('/api/operator/telegram/scope', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ init_data: initData, scope_type: kind, scope_id: id || null }),
      }).then(readJson<Bootstrap>);
      setBootstrap((current) => ({ ...current, ...result, catalog: current?.catalog }));
      await loadWorkspace(result.selected_scope);
      setPicker(false); setTab('today'); setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось сменить бизнес.'); }
    finally { setLoading(false); }
  };

  const loadReviews = async (status = reviewStatus, append = false) => {
    if (preview) { setReviews({ items: previewReviews, counts: { total: 164, unanswered: 50, drafts: 12 } }); return; }
    setReviewsLoading(true);
    try {
      const params = scopeQuery(scope); params.set('status', status); params.set('limit', '20');
      if (append && reviews.cursor) params.set('cursor', reviews.cursor);
      const result = await fetch(`/api/operator/mobile/reviews?${params.toString()}`, { headers: authHeaders() }).then(readJson<ReviewResult>);
      setReviews((current) => ({ ...result, items: append ? [...(current.items || []), ...(result.items || [])] : result.items }));
      setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить отзывы.'); }
    finally { setReviewsLoading(false); }
  };

  useEffect(() => { if (tab === 'reviews') void loadReviews(reviewStatus); }, [tab, reviewStatus, scope?.kind, scope?.id]);

  const openTask = (item: AttentionItem) => {
    if (item.target_scope?.id) { void chooseScope('business', item.target_scope.id); return; }
    if (String(item.id || '').includes('review')) setTab('reviews'); else setTab('tasks');
  };

  const askOperator = async (event: FormEvent) => {
    event.preventDefault();
    const text = command.trim();
    if (!text) return;
    if (scope?.kind !== 'business' || !scope.id) { setPicker(true); setError('Для команды выберите одну точку.'); return; }
    setMessages((current) => [...current, { role: 'user', text }]); setCommand(''); setOperatorBusy(true); setTab('operator');
    try {
      const result = await fetch('/api/operator/chat', {
        method: 'POST', headers: authHeaders(), body: JSON.stringify({ business_id: scope.id, message: text, channel: 'telegram_mini_app' }),
      }).then(readJson<{ operator_result?: { chat_response?: string; summary?: string } }>);
      setMessages((current) => [...current, { role: 'operator', text: result.operator_result?.chat_response || result.operator_result?.summary || 'Готово. Результ добавлен в задачи.' }]);
      await loadWorkspace();
    } catch (requestError) { setMessages((current) => [...current, { role: 'operator', text: requestError instanceof Error ? requestError.message : 'Не смог разобрать запрос.' }]); }
    finally { setOperatorBusy(false); }
  };

  const generateReviewReply = async (review: Review, confirmed: boolean) => {
    if (preview) return;
    setReviewActionBusy(review.id);
    try {
      const result = await fetch(`/api/operator/mobile/reviews/${review.id}/generate`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null, confirmed }),
      }).then(readJson<{ preview?: unknown; operator_result?: unknown }>);
      if (confirmed && result.operator_result) await loadReviews(reviewStatus);
      setError('');
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось подготовить ответ.');
    } finally { setReviewActionBusy(''); }
  };

  const updateReviewDraft = async (review: Review, replyText: string) => {
    if (preview || !review.reply_draft_id) return;
    setReviewActionBusy(review.id);
    try {
      await fetch(`/api/operator/mobile/review-drafts/${review.reply_draft_id}`, {
        method: 'PUT', headers: authHeaders(), body: JSON.stringify({ reply_text: replyText }),
      }).then(readJson<{ draft?: unknown }>);
      await loadReviews(reviewStatus);
      setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить черновик.'); }
    finally { setReviewActionBusy(''); }
  };

  if (!initData && !preview) return <TelegramGate />;
  if (loading && !bootstrap) return <LoadingScreen slow={slowLoading} />;

  return (
    <main className="min-h-[100dvh] bg-zinc-950 text-zinc-100 antialiased selection:bg-primary/30">
      <div className="pointer-events-none fixed inset-x-0 top-0 h-72 bg-[radial-gradient(circle_at_top,rgba(255,92,51,0.16),transparent_68%)]" />
      <div className="relative mx-auto min-h-[100dvh] max-w-xl pb-[calc(92px+env(safe-area-inset-bottom))]">
        <TopBar scope={scope} hasSwitcher={hasSwitcher} onSwitch={() => setPicker(true)} />
        {error ? <div className="mx-4 mb-4 flex gap-3 rounded-2xl bg-rose-500/10 p-4 text-sm text-rose-100 ring-1 ring-inset ring-rose-400/20"><AlertCircle className="h-5 w-5 shrink-0" />{error}</div> : null}
        <AnimatePresence initial={false} mode="wait">
          <motion.div key={`${tab}-${module}-${picker}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={spring}>
            {picker ? <ScopePicker catalog={catalog} search={search} setSearch={setSearch} choose={chooseScope} /> : null}
            {!picker && tab === 'today' ? <Today summary={summary} tasks={tasks} command={command} setCommand={setCommand} ask={askOperator} openTask={openTask} /> : null}
            {!picker && tab === 'tasks' ? <Tasks items={tasks} filter={taskFilter} setFilter={setTaskFilter} openTask={openTask} /> : null}
            {!picker && tab === 'reviews' ? <Reviews result={reviews} status={reviewStatus} setStatus={setReviewStatus} loading={reviewsLoading} actionBusy={reviewActionBusy} generate={generateReviewReply} updateDraft={updateReviewDraft} loadMore={() => void loadReviews(reviewStatus, true)} /> : null}
            {!picker && tab === 'operator' ? <Operator messages={messages} busy={operatorBusy} command={command} setCommand={setCommand} ask={askOperator} /> : null}
            {!picker && tab === 'more' && !module ? <More onOpen={setModule} platform={scope?.kind === 'platform'} /> : null}
            {!picker && tab === 'more' && module ? <ModuleScreen module={module} tasks={tasks} back={() => setModule('')} /> : null}
          </motion.div>
        </AnimatePresence>
        {!picker ? <BottomNav current={tab} setCurrent={(next) => { setModule(''); setTab(next); }} /> : null}
      </div>
    </main>
  );
};

const TopBar = ({ scope, hasSwitcher, onSwitch }: { scope?: Scope; hasSwitcher: boolean; onSwitch: () => void }) => {
  const Icon = scope?.kind === 'platform' ? ShieldCheck : scope?.kind === 'network' ? Network : Building2;
  const meta = scope?.kind === 'network' ? `${scope.business_ids?.length || 0} точек` : scope?.kind === 'platform' ? 'Вся платформа' : 'Ваш бизнес';
  return <header className="px-4 pb-4 pt-[calc(16px+env(safe-area-inset-top))]">
    <div className="mb-4 flex items-center justify-between"><div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-zinc-500"><span className="grid h-8 w-8 place-items-center rounded-[11px] bg-primary text-[11px] text-white shadow-[0_10px_28px_rgba(255,92,51,0.3)]">LO</span>LocalOS</div><span className="flex items-center gap-2 rounded-full bg-white/[0.05] px-3 py-2 text-[11px] text-zinc-400 ring-1 ring-inset ring-white/[0.07]"><i className="h-1.5 w-1.5 rounded-full bg-emerald-400" />Работает</span></div>
    <button type="button" onClick={onSwitch} disabled={!hasSwitcher} className="flex min-h-14 w-full items-center gap-3 rounded-[20px] bg-white/[0.045] px-3 text-left ring-1 ring-inset ring-white/[0.075] transition-[background-color,transform] active:scale-[0.96] disabled:active:scale-100"><span className="grid h-11 w-11 place-items-center rounded-[14px] bg-primary/15 text-primary"><Icon className="h-5 w-5" /></span><span className="min-w-0 flex-1"><b className="block truncate text-[15px]">{scope?.name || 'LocalOS'}</b><small className="text-xs text-zinc-500">{meta}</small></span>{hasSwitcher ? <ChevronRight className="h-5 w-5 text-zinc-600" /> : null}</button>
  </header>;
};

const Today = ({ summary, tasks, command, setCommand, ask, openTask }: { summary?: Summary; tasks: AttentionItem[]; command: string; setCommand: (value: string) => void; ask: (event: FormEvent) => void; openTask: (item: AttentionItem) => void }) => {
  const primary = tasks[0];
  return <div className="px-4">
    <section className="rounded-[28px] bg-gradient-to-b from-zinc-900 to-zinc-900/70 p-5 shadow-[0_24px_80px_rgba(0,0,0,0.28)] ring-1 ring-inset ring-white/[0.08]"><div className="flex items-center gap-2 text-xs text-zinc-500"><Sparkles className="h-4 w-4 text-primary" />LocalOS уже разобрался</div><div className="mt-4 flex items-start gap-4"><div className="min-w-0 flex-1"><h1 className="text-balance text-[26px] font-semibold leading-8 tracking-[-0.045em]">{primary?.title || 'Всё под контролем'}</h1><p className="mt-2 text-pretty text-sm leading-6 text-zinc-400">{primary?.description || 'Новых решений от вас сейчас не требуется.'}</p></div>{primary?.count ? <b className="rounded-2xl bg-primary/15 px-3 py-2 text-xl tabular-nums text-primary">{primary.count}</b> : <Check className="h-8 w-8 text-emerald-400" />}</div>{primary ? <PrimaryButton onClick={() => openTask(primary)}>Перейти к решению</PrimaryButton> : null}</section>
    <form onSubmit={ask} className="mt-3 rounded-[22px] bg-white/[0.04] p-3 ring-1 ring-inset ring-white/[0.07]"><label className="px-1 text-xs font-medium text-zinc-500">Что сделать?</label><div className="mt-2 flex gap-2"><input value={command} onChange={(event) => setCommand(event.target.value)} placeholder="Например: подготовь ответы" className="min-h-12 min-w-0 flex-1 rounded-2xl bg-black/20 px-4 text-sm outline-none ring-1 ring-inset ring-white/[0.07] placeholder:text-zinc-700 focus:ring-primary/50" /><button aria-label="Отправить" className="grid h-12 w-12 place-items-center rounded-2xl bg-primary text-white transition-transform active:scale-[0.96]"><Send className="h-4 w-4" /></button></div><p className="px-1 pt-2 text-[11px] leading-4 text-zinc-600">DeepSeek поймёт задачу. Внешние действия всегда попросят подтверждение.</p></form>
    {tasks.slice(1, 3).map((item) => <TaskRow key={item.id || item.title} item={item} onClick={() => openTask(item)} />)}
    <section className="mt-6"><h2 className="text-lg font-semibold tracking-[-0.025em]">Что уже сделано</h2><div className="mt-3 grid grid-cols-2 gap-2">{(summary?.metrics || []).slice(0, 4).map((metric) => <div key={metric.key} className="rounded-[20px] bg-white/[0.035] p-4 ring-1 ring-inset ring-white/[0.06]"><small className="text-zinc-600">{metric.label}</small><b className="mt-1 block text-2xl tabular-nums">{metric.value ?? '—'}</b><span className="mt-1 block truncate text-[10px] text-zinc-700">{metric.source_label || metric.source || 'LocalOS'}</span></div>)}</div></section>
  </div>;
};

const Tasks = ({ items, filter, setFilter, openTask }: { items: AttentionItem[]; filter: string; setFilter: (value: string) => void; openTask: (item: AttentionItem) => void }) => {
  const visible = items.filter((item) => filter === 'done' ? item.status === 'completed' : filter === 'working' ? item.status === 'in_progress' : item.status !== 'completed');
  return <Screen title="Задачи" subtitle="Одна очередь: решения, фоновая работа и готовые результаты."><Segments value={filter} setValue={setFilter} options={[['attention', 'Нужно решить'], ['working', 'В работе'], ['done', 'Готово']]} />{visible.length ? visible.map((item) => <TaskRow key={item.id || item.title} item={item} onClick={() => openTask(item)} />) : <Empty icon={ClipboardCheck} title="Здесь пусто" text="LocalOS покажет здесь задачи, когда появится реальная работа." />}</Screen>;
};

const Reviews = ({ result, status, setStatus, loading, actionBusy, generate, updateDraft, loadMore }: { result: ReviewResult; status: string; setStatus: (value: string) => void; loading: boolean; actionBusy: string; generate: (review: Review, confirmed: boolean) => Promise<void>; updateDraft: (review: Review, text: string) => Promise<void>; loadMore: () => void }) => <Screen title="Отзывы" subtitle="Видно каждого клиента, его текст и точку."><Segments value={status} setValue={setStatus} options={[[ 'unanswered', `Без ответа ${result.counts?.unanswered || 0}` ], [ 'drafts', `Черновики ${result.counts?.drafts || 0}` ], [ 'all', 'Все' ]]} />{loading ? <ReviewSkeleton /> : result.items?.length ? result.items.map((review) => <ReviewCard key={review.id} review={review} busy={actionBusy === review.id} generate={generate} updateDraft={updateDraft} />) : <Empty icon={MessageCircle} title="Отзывов нет" text="В этом фильтре пока нет отзывов." />}{result.cursor ? <button onClick={loadMore} className="mt-3 min-h-12 w-full rounded-2xl bg-white/[0.05] text-sm font-semibold ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]">Показать ещё</button> : null}</Screen>;

const ReviewCard = ({ review, busy, generate, updateDraft }: { review: Review; busy: boolean; generate: (review: Review, confirmed: boolean) => Promise<void>; updateDraft: (review: Review, text: string) => Promise<void> }) => {
  const [confirming, setConfirming] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draftText, setDraftText] = useState(review.reply_draft_text || '');
  const prepare = async () => { await generate(review, false); setConfirming(true); };
  return <article className="mb-3 rounded-[24px] bg-white/[0.04] p-4 ring-1 ring-inset ring-white/[0.07]"><div className="flex items-start gap-3"><div className="grid h-10 w-10 place-items-center rounded-[14px] bg-amber-400/10 text-sm font-bold text-amber-300">{review.rating || '—'}</div><div className="min-w-0 flex-1"><b className="block truncate">{review.author_name || 'Гость'}</b><small className="block truncate text-zinc-600">{[review.source, review.location_name, review.published_at ? new Date(review.published_at).toLocaleDateString('ru-RU') : ''].filter(Boolean).join(' · ')}</small></div></div><p className="mt-4 whitespace-pre-wrap text-pretty text-sm leading-6 text-zinc-300">{review.text}</p>{review.response_text ? <ResponseBox label="Опубликованный ответ" text={review.response_text} /> : review.reply_draft_text ? <div className="mt-4 rounded-[18px] bg-black/20 p-3 ring-1 ring-inset ring-white/[0.06]"><div className="flex min-h-11 items-center justify-between"><small className="font-semibold text-primary">Черновик LocalOS</small><div className="flex"><button type="button" onClick={() => setEditing((value) => !value)} className="min-h-11 px-3 text-xs font-semibold text-zinc-400">{editing ? 'Отмена' : 'Изменить'}</button><button type="button" aria-label="Скопировать" onClick={() => void navigator.clipboard.writeText(draftText)} className="grid h-11 w-11 place-items-center text-zinc-500"><Copy className="h-4 w-4" /></button></div></div>{editing ? <><textarea value={draftText} onChange={(event) => setDraftText(event.target.value)} className="min-h-32 w-full resize-none rounded-2xl bg-white/[0.04] p-3 text-sm leading-6 outline-none ring-1 ring-inset ring-white/[0.07] focus:ring-primary/50" /><button disabled={busy} onClick={() => void updateDraft(review, draftText)} className="mt-2 min-h-11 w-full rounded-2xl bg-primary text-sm font-semibold disabled:opacity-50">{busy ? 'Сохраняем…' : 'Сохранить черновик'}</button></> : <p className="text-sm leading-6 text-zinc-300">{draftText}</p>}</div> : confirming ? <div className="mt-4 rounded-[18px] bg-primary/[0.08] p-4 ring-1 ring-inset ring-primary/20"><b className="text-sm">Предпросмотр</b><p className="mt-1 text-xs leading-5 text-zinc-400">1 отзыв · 1 кредит · внешней публикации нет</p><div className="mt-3 flex gap-2"><button onClick={() => setConfirming(false)} className="min-h-11 flex-1 rounded-2xl bg-white/[0.05] text-sm">Отмена</button><button disabled={busy} onClick={() => void generate(review, true)} className="min-h-11 flex-1 rounded-2xl bg-primary text-sm font-semibold disabled:opacity-50">{busy ? 'Готовим…' : 'Подтвердить'}</button></div></div> : <button disabled={busy} onClick={() => void prepare()} className="mt-4 flex min-h-11 w-full items-center justify-center gap-2 rounded-2xl bg-primary/12 text-sm font-semibold text-primary ring-1 ring-inset ring-primary/20 active:scale-[0.96] disabled:opacity-50"><WandSparkles className="h-4 w-4" />{busy ? 'Проверяем…' : 'Подготовить ответ'}</button>}</article>;
};

const ResponseBox = ({ label, text }: { label: string; text: string }) => <div className="mt-4 rounded-[18px] bg-black/20 p-3 ring-1 ring-inset ring-white/[0.06]"><div className="flex items-center justify-between"><small className="font-semibold text-primary">{label}</small><button type="button" aria-label="Скопировать" onClick={() => void navigator.clipboard.writeText(text)} className="grid h-11 w-11 place-items-center text-zinc-500 active:scale-[0.96]"><Copy className="h-4 w-4" /></button></div><p className="text-sm leading-6 text-zinc-300">{text}</p></div>;

const Operator = ({ messages, busy, command, setCommand, ask }: { messages: OperatorMessage[]; busy: boolean; command: string; setCommand: (value: string) => void; ask: (event: FormEvent) => void }) => <Screen title="Оператор" subtitle="Опишите результ обычными словами. LocalOS подберёт безопасный сценарий."><div className="min-h-[42vh] space-y-3">{messages.length ? messages.map((message, index) => <div key={`${message.role}-${index}`} className={`max-w-[88%] rounded-[20px] px-4 py-3 text-sm leading-6 ${message.role === 'user' ? 'ml-auto bg-primary text-white' : 'bg-white/[0.05] text-zinc-300 ring-1 ring-inset ring-white/[0.07]'}`}>{message.text}</div>) : <Empty icon={Bot} title="Что поручить?" text="Например: «Подготовь ответы на плохие отзывы» или «Проверь свежесть карточки»." />}{busy ? <div className="flex items-center gap-2 text-sm text-zinc-500"><Loader2 className="h-4 w-4 animate-spin text-primary" />Разбираю задачу…</div> : null}</div><form onSubmit={ask} className="sticky bottom-24 mt-4 flex gap-2 rounded-[20px] bg-zinc-900 p-2 ring-1 ring-inset ring-white/[0.08]"><input value={command} onChange={(event) => setCommand(event.target.value)} placeholder="Напишите задачу" className="min-h-12 min-w-0 flex-1 bg-transparent px-3 text-sm outline-none placeholder:text-zinc-700" /><button className="grid h-12 w-12 place-items-center rounded-2xl bg-primary active:scale-[0.96]"><Send className="h-4 w-4" /></button></form></Screen>;

const More = ({ onOpen, platform }: { onOpen: (key: string) => void; platform: boolean }) => {
  const items = [
    ['cards', 'Карточки', 'Свежесть и ошибки', MapPinned], ['content', 'Контент', 'Планы и черновики', FileText],
    ['services', 'Услуги', 'Цены и оптимизация', LayoutGrid], ['finance', 'Финансы', 'KPI и предупреждения', CreditCard],
    ['partnerships', 'Партнёрства', 'Лиды и ответы', Users], ['agents', 'ИИ-сотрудники', 'Работа и результаты', Bot],
    ['settings', 'Настройки', 'Связи, тариф и уведомления', Settings],
  ];
  if (platform) items.push(['diagnostics', 'Диагностика', 'Интеграции и задачи', ShieldCheck]);
  return <Screen title="Ещё" subtitle="Все разделы работают внутри Mini App."><div className="grid grid-cols-2 gap-2">{items.map(([key, label, meta, Icon]) => <button key={String(key)} onClick={() => onOpen(String(key))} className="min-h-32 rounded-[22px] bg-white/[0.04] p-4 text-left ring-1 ring-inset ring-white/[0.07] transition-[background-color,transform] active:scale-[0.96]"><span className="grid h-10 w-10 place-items-center rounded-[14px] bg-primary/12 text-primary"><Icon className="h-5 w-5" /></span><b className="mt-4 block text-sm">{String(label)}</b><small className="mt-1 block leading-4 text-zinc-600">{String(meta)}</small></button>)}</div></Screen>;
};

const moduleNames: Record<string, [string, string]> = {
  cards: ['Карточки', 'Актуальность данных и ошибки подключений.'], content: ['Контент', 'Планы, новости, посты и готовые черновики.'], services: ['Услуги', 'Список, цены и предложения по улучшению.'],
  finance: ['Финансы', 'KPI, импорты и финансовые предупреждения.'], partnerships: ['Партнёрства', 'Лиды, черновики, ответы и контроль отправок.'], agents: ['ИИ-сотрудники', 'Состояние, история и результаты фоновой работы.'], settings: ['Настройки', 'Уведомления, подключения, тариф и доступ.'], diagnostics: ['Диагностика', 'Технические очереди и ошибки — только для суперадмина.'],
};

const ModuleScreen = ({ module, tasks, back }: { module: string; tasks: AttentionItem[]; back: () => void }) => { const content = moduleNames[module] || ['Раздел', 'Рабочая очередь LocalOS.']; return <Screen title={content[0]} subtitle={content[1]} action={<button onClick={back} className="grid h-11 w-11 place-items-center rounded-2xl bg-white/[0.05] ring-1 ring-inset ring-white/[0.07]"><ArrowLeft className="h-4 w-4" /></button>}><div className="rounded-[24px] bg-white/[0.04] p-5 ring-1 ring-inset ring-white/[0.07]"><div className="flex items-center gap-2 text-xs text-zinc-500"><Sparkles className="h-4 w-4 text-primary" />LocalOS проверил этот раздел</div><h3 className="mt-3 text-xl font-semibold">{tasks.length ? `${tasks.length} задач в общей очереди` : 'Новых задач нет'}</h3><p className="mt-2 text-sm leading-6 text-zinc-500">Опасные, массовые и внешние изменения появятся здесь с предпросмотром до подтверждения.</p></div></Screen>; };

const ScopePicker = ({ catalog, search, setSearch, choose }: { catalog?: Catalog; search: string; setSearch: (value: string) => void; choose: (kind: string, id?: string | null) => void }) => <Screen title="Где работаем?" subtitle="Выбор сохранится для следующего запуска."><label className="relative block"><Search className="absolute left-4 top-4 h-4 w-4 text-zinc-600" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Название, город или адрес" className="min-h-12 w-full rounded-2xl bg-white/[0.05] pl-11 pr-4 text-sm outline-none ring-1 ring-inset ring-white/[0.08] placeholder:text-zinc-700 focus:ring-primary/50" /></label><div className="mt-4 space-y-2">{catalog?.platform ? <ScopeRow icon={ShieldCheck} label="Вся платформа" meta="Операционная картина LocalOS" onClick={() => void choose('platform')} /> : null}{catalog?.networks?.map((item) => <ScopeRow key={item.id} icon={Network} label={item.name || 'Сеть'} meta={`${item.locations_count || 0} точек`} onClick={() => void choose('network', item.id)} />)}{catalog?.businesses?.map((item) => <ScopeRow key={item.id} icon={Building2} label={item.name || 'Бизнес'} meta={[item.network_name, item.address].filter(Boolean).join(' · ')} onClick={() => void choose('business', item.id)} />)}</div></Screen>;

const BottomNav = ({ current, setCurrent }: { current: Tab; setCurrent: (tab: Tab) => void }) => { const items: Array<[Tab, string, typeof Sparkles]> = [['today', 'Сегодня', Sparkles], ['tasks', 'Задачи', ClipboardCheck], ['reviews', 'Отзывы', MessageCircle], ['operator', 'Оператор', Bot], ['more', 'Ещё', CircleEllipsis]]; return <nav className="fixed inset-x-0 bottom-0 z-20 mx-auto max-w-xl border-t border-white/[0.07] bg-zinc-950/90 px-2 pb-[calc(8px+env(safe-area-inset-bottom))] pt-2 backdrop-blur-xl"> <div className="grid grid-cols-5">{items.map(([key, label, Icon]) => <button key={key} onClick={() => setCurrent(key)} className={`flex min-h-14 flex-col items-center justify-center gap-1 rounded-[16px] text-[10px] transition-[color,transform,background-color] active:scale-[0.96] ${current === key ? 'bg-primary/10 text-primary' : 'text-zinc-600'}`}><Icon className="h-5 w-5" /><span>{label}</span></button>)}</div></nav>; };

const Screen = ({ title, subtitle, children, action }: { title: string; subtitle: string; children: React.ReactNode; action?: React.ReactNode }) => <section className="px-4"><div className="mb-5 flex items-start gap-3"><div className="min-w-0 flex-1"><h1 className="text-balance text-2xl font-semibold tracking-[-0.04em]">{title}</h1><p className="mt-1 text-pretty text-sm leading-6 text-zinc-500">{subtitle}</p></div>{action}</div>{children}</section>;
const PrimaryButton = ({ children, onClick }: { children: React.ReactNode; onClick: () => void }) => <button onClick={onClick} className="mt-5 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 text-sm font-semibold text-white shadow-[0_12px_32px_rgba(255,92,51,0.24)] transition-[filter,transform] active:scale-[0.96]">{children}<ChevronRight className="h-4 w-4" /></button>;
const TaskRow = ({ item, onClick }: { item: AttentionItem; onClick: () => void }) => <button onClick={onClick} className="mt-2 flex min-h-16 w-full items-center gap-3 rounded-[20px] bg-white/[0.035] px-4 py-3 text-left ring-1 ring-inset ring-white/[0.06] active:scale-[0.98]"><span className={`h-2.5 w-2.5 rounded-full ${item.severity === 'high' ? 'bg-rose-400' : item.severity === 'medium' ? 'bg-amber-400' : 'bg-emerald-400'}`} /><span className="min-w-0 flex-1"><b className="block truncate text-sm">{item.title || 'Задача'}</b><small className="mt-1 block truncate text-zinc-600">{item.description}</small></span>{item.count ? <b className="tabular-nums text-zinc-400">{item.count}</b> : null}<ChevronRight className="h-4 w-4 text-zinc-700" /></button>;
const Segments = ({ value, setValue, options }: { value: string; setValue: (value: string) => void; options: string[][] }) => <div className="mb-4 flex gap-1 overflow-x-auto rounded-[18px] bg-white/[0.035] p-1 ring-1 ring-inset ring-white/[0.06]">{options.map(([key, label]) => <button key={key} onClick={() => setValue(key)} className={`min-h-11 flex-1 whitespace-nowrap rounded-[14px] px-3 text-xs font-semibold transition-[background-color,color,transform] active:scale-[0.96] ${value === key ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-600'}`}>{label}</button>)}</div>;
const ScopeRow = ({ icon: Icon, label, meta, onClick }: { icon: typeof Star; label: string; meta: string; onClick: () => void }) => <button onClick={onClick} className="flex min-h-16 w-full items-center gap-3 rounded-[20px] bg-white/[0.04] px-3 text-left ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]"><span className="grid h-10 w-10 place-items-center rounded-[14px] bg-primary/12 text-primary"><Icon className="h-5 w-5" /></span><span className="min-w-0 flex-1"><b className="block truncate text-sm">{label}</b><small className="block truncate text-zinc-600">{meta}</small></span><ChevronRight className="h-4 w-4 text-zinc-700" /></button>;
const Empty = ({ icon: Icon, title, text }: { icon: typeof Star; title: string; text: string }) => <div className="mt-4 rounded-[24px] bg-white/[0.025] px-6 py-10 text-center ring-1 ring-inset ring-white/[0.06]"><Icon className="mx-auto h-7 w-7 text-zinc-700" /><h3 className="mt-3 font-semibold">{title}</h3><p className="mx-auto mt-2 max-w-xs text-pretty text-sm leading-6 text-zinc-600">{text}</p></div>;
const ReviewSkeleton = () => <div className="space-y-3">{[1, 2, 3].map((item) => <div key={item} className="h-44 animate-pulse rounded-[24px] bg-white/[0.04] motion-reduce:animate-none" />)}</div>;
const LoadingScreen = ({ slow }: { slow: boolean }) => <main className="grid min-h-[100dvh] place-items-center bg-zinc-950 px-8 text-center text-white"><div><span className="relative mx-auto grid h-20 w-20 place-items-center rounded-[26px] bg-zinc-900 ring-1 ring-inset ring-white/[0.08]"><Sparkles className="h-7 w-7 text-primary" /></span><h1 className="mt-6 text-xl font-semibold tracking-[-0.03em]">Собираем ваш рабочий день</h1>{slow ? <p className="mt-3 text-sm text-zinc-500">Сверяем задачи и источники…</p> : null}</div></main>;
const TelegramGate = () => <main className="grid min-h-[100dvh] place-items-center bg-zinc-950 p-6 text-center text-white"><div className="max-w-sm"><span className="mx-auto grid h-20 w-20 place-items-center rounded-[26px] bg-primary/12 text-primary ring-1 ring-inset ring-primary/20"><Send className="h-7 w-7" /></span><h1 className="mt-6 text-balance text-2xl font-semibold tracking-[-0.04em]">Откройте LocalOS в Telegram</h1><p className="mt-3 text-pretty text-sm leading-6 text-zinc-500">Этот экран безопасно проверяет ваш аккаунт через Telegram. Вернитесь в бота и нажмите постоянную кнопку LocalOS.</p><a href="https://t.me/LocalOspro_bot" className="mt-6 flex min-h-12 items-center justify-center rounded-2xl bg-primary px-5 text-sm font-semibold text-white active:scale-[0.96]">Открыть бота</a></div></main>;

export default TelegramControlPage;
