import { _socialLaunchStageStatusLabel, _socialLaunchStageTone } from './helpers.logic';

import type {
	ContentMixKey,
	ItemFilterKey, SignalFilterKey,
	SocialFirstCycleVerification, SocialLaunchRunbook,
	SocialLaunchStage,
	SocialPlanNextAction
} from './types';

const PERIOD_OPTIONS = [30, 60, 90];

const DENSITY_OPTIONS = [
  { value: 'light', labelRu: 'Спокойно', labelEn: 'Light' },
  { value: 'standard', labelRu: 'Стандартно', labelEn: 'Standard' },
  { value: 'active', labelRu: 'Активно', labelEn: 'Active' },
];

const CONTENT_MIX_OPTIONS: Array<{ key: ContentMixKey; labelRu: string; labelEn: string }> = [
  { key: 'services', labelRu: 'Услуги', labelEn: 'Services' },
  { key: 'seo', labelRu: 'SEO', labelEn: 'SEO' },
  { key: 'sales', labelRu: 'Продажи', labelEn: 'Sales' },
  { key: 'audit', labelRu: 'Аудит', labelEn: 'Audit' },
  { key: 'seasonal', labelRu: 'Сезонность', labelEn: 'Seasonal' },
];
const ITEM_FILTER_OPTIONS: ItemFilterKey[] = ['all', 'has_draft', 'urgent'];
const SIGNAL_FILTER_OPTIONS: SignalFilterKey[] = ['all', 'seo', 'services', 'sales', 'audit', 'seasonal'];

export function SocialLaunchChecklist({
  stages,
  summary,
  isRu,
  compact = false,
}: {
  stages: SocialLaunchStage[];
  summary: {
    done: number;
    total: number;
    attention: number;
    current?: SocialLaunchStage;
  };
  isRu: boolean;
  compact?: boolean;
}) {
  if (!stages.length) return null;
  const current = summary.current;
  return (
    <div
      data-testid={compact ? 'social-launch-checklist-compact' : 'social-launch-checklist'}
      className="mt-3 rounded-xl bg-white/10 px-3 py-3 text-xs leading-5 text-slate-200"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="font-semibold text-white">
            {isRu ? 'До рабочего запуска' : 'Before launch'}
          </div>
          <div className="mt-1 text-slate-300">
            {isRu
              ? `Готово ${summary.done} из ${summary.total}. ${summary.attention > 0 ? 'Есть блокер, его нужно снять перед исполнением.' : 'Следующий шаг ниже.'}`
              : `${summary.done} of ${summary.total} ready. ${summary.attention > 0 ? 'A blocker needs attention before execution.' : 'Next step is below.'}`}
          </div>
        </div>
        {current ? (
          <div className="rounded-lg bg-white/10 px-2 py-1.5 text-slate-200 sm:max-w-[260px]">
            <span className="font-semibold text-white">
              {isRu ? 'Сейчас: ' : 'Now: '}
            </span>
            {isRu ? current.labelRu : current.labelEn}
          </div>
        ) : null}
      </div>
      <div className={compact ? 'mt-3 grid gap-1' : 'mt-3 grid gap-1 sm:grid-cols-2'}>
        {stages.map((stage) => {
          const tone = _socialLaunchStageTone(stage.status);
          return (
            <div
              key={`launch-checklist-${compact ? 'compact' : 'full'}-${stage.key}`}
              className="flex items-start gap-2 rounded-lg bg-white/10 px-2 py-2"
            >
              <span className={['mt-1 h-2 w-2 shrink-0 rounded-full', tone.dot].join(' ')} />
              <span className="min-w-0 flex-1">
                <span className="font-semibold text-white">
                  {isRu ? stage.labelRu : stage.labelEn}
                </span>
                {!compact ? (
                  <span className="block text-slate-300">
                    {isRu ? stage.detailRu : stage.detailEn}
                  </span>
                ) : null}
              </span>
              <span className={['shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold', tone.badge].join(' ')}>
                {_socialLaunchStageStatusLabel(stage.status, isRu)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function SocialOwnerLaunchPath({
  isRu,
  currentAction,
}: {
  isRu: boolean;
  currentAction: SocialPlanNextAction;
}) {
  const normalized = String(currentAction || 'none').trim() as SocialPlanNextAction;
  const steps: Array<{
    key: string;
    ru: string;
    en: string;
    actions: SocialPlanNextAction[];
  }> = [
    {
      key: 'prepare',
      ru: 'Подготовить',
      en: 'Prepare',
      actions: ['prepare'],
    },
    {
      key: 'review',
      ru: 'Проверить',
      en: 'Review',
      actions: ['review'],
    },
    {
      key: 'launch',
      ru: 'Расписание',
      en: 'Queue',
      actions: ['queue', 'wait', 'supervised', 'manual'],
    },
    {
      key: 'learn',
      ru: 'Результат',
      en: 'Results',
      actions: ['collect', 'recommend'],
    },
  ];
  const currentIndex = steps.findIndex((step) => step.actions.includes(normalized));
  const activeIndex = currentIndex >= 0 ? currentIndex : 0;

  return (
    <div
      data-testid="social-owner-launch-path"
      className="mt-3 grid gap-1.5 text-xs sm:grid-cols-4"
    >
      {steps.map((step, index) => {
        const isCurrent = index === activeIndex;
        const isDone = normalized !== 'none' && index < activeIndex;
        return (
          <div
            key={`owner-launch-path-${step.key}`}
            className={[
              'flex items-center gap-2 rounded-lg px-2 py-1.5',
              isCurrent
                ? 'bg-white text-slate-950'
                : isDone
                  ? 'bg-emerald-300/15 text-emerald-50'
                  : 'bg-white/10 text-slate-300',
            ].join(' ')}
          >
            <span
              className={[
                'flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold',
                isCurrent
                  ? 'bg-slate-950 text-white'
                  : isDone
                    ? 'bg-emerald-200 text-emerald-900'
                    : 'bg-white/10 text-slate-300',
              ].join(' ')}
            >
              {index + 1}
            </span>
            <span className="min-w-0 truncate font-medium">
              {isRu ? step.ru : step.en}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function SocialLaunchRunbookBlock({ runbook, isRu }: { runbook: SocialLaunchRunbook | undefined; isRu: boolean }) {
  const steps = Array.isArray(isRu ? runbook?.steps_ru : runbook?.steps_en)
    ? (isRu ? runbook?.steps_ru : runbook?.steps_en) || []
    : [];
  const criteria = Array.isArray(isRu ? runbook?.success_criteria_ru : runbook?.success_criteria_en)
    ? (isRu ? runbook?.success_criteria_ru : runbook?.success_criteria_en) || []
    : [];
  const title = isRu ? String(runbook?.title_ru || '') : String(runbook?.title_en || '');
  const summary = isRu ? String(runbook?.summary_ru || '') : String(runbook?.summary_en || '');
  const blockedReason = isRu ? String(runbook?.blocked_reason_ru || '') : String(runbook?.blocked_reason_en || '');
  if (!title && !summary && !steps.length && !criteria.length && !blockedReason) return null;
  return (
    <div className="mt-2 rounded-lg border border-emerald-300/20 bg-emerald-400/10 px-2 py-2 text-[11px] leading-5 text-emerald-50">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-white">
          {title || (isRu ? 'Runbook первого цикла' : 'First-cycle runbook')}
        </span>
        <span className={runbook?.ready ? 'rounded-full bg-emerald-300/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-50' : 'rounded-full bg-amber-300/20 px-2 py-0.5 text-[10px] font-semibold text-amber-50'}>
          {runbook?.ready ? (isRu ? 'готов' : 'ready') : (isRu ? 'не готов' : 'not ready')}
        </span>
      </div>
      {summary ? (
        <div className="mt-1 text-emerald-100">{summary}</div>
      ) : null}
      {blockedReason ? (
        <div className="mt-1 rounded-md bg-amber-400/10 px-2 py-1 text-amber-100">
          {blockedReason}
        </div>
      ) : null}
      {steps.length > 0 ? (
        <div className="mt-2 space-y-1">
          <div className="font-semibold text-white">{isRu ? 'Шаги' : 'Steps'}</div>
          {steps.slice(0, 6).map((step, index) => (
            <div key={`${index}-${String(step)}`} className="flex gap-1.5 rounded-md bg-white/10 px-2 py-1">
              <span className="shrink-0 font-semibold text-white">{index + 1}.</span>
              <span>{String(step)}</span>
            </div>
          ))}
        </div>
      ) : null}
      {criteria.length > 0 ? (
        <div className="mt-2 space-y-1">
          <div className="font-semibold text-white">{isRu ? 'Успех первого цикла' : 'First-cycle success'}</div>
          {criteria.slice(0, 5).map((item) => (
            <div key={String(item)} className="rounded-md bg-white/10 px-2 py-1">
              {String(item)}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function SocialFirstCycleVerificationBlock({ verification, isRu }: {
  verification: SocialFirstCycleVerification | undefined;
  isRu: boolean;
}) {
  const expected = Array.isArray(verification?.expected_statuses)
    ? verification.expected_statuses.filter(Boolean)
    : [];
  const checks = Array.isArray(isRu ? verification?.checks_ru : verification?.checks_en)
    ? (isRu ? verification?.checks_ru : verification?.checks_en) || []
    : [];
  const logFilter = String(verification?.log_filter || '').trim();
  if (!expected.length && !checks.length && !logFilter) return null;
  return (
    <div className="mt-2 rounded-lg border border-violet-300/20 bg-violet-400/10 px-2 py-2 text-[11px] leading-5 text-violet-50">
      <div className="font-semibold text-white">
        {isRu ? 'Проверка после первого цикла' : 'First-cycle verification'}
      </div>
      {logFilter ? (
        <div className="mt-1 font-mono text-[10px] text-violet-100">
          logs: {logFilter}
        </div>
      ) : null}
      {expected.length > 0 ? (
        <div className="mt-1 space-y-1">
          {expected.slice(0, 4).map((item) => (
            <div key={String(item.key || item.label_ru || item.label_en)} className="rounded-md bg-white/10 px-2 py-1">
              <span className="font-medium text-white">
                {isRu ? String(item.label_ru || '') : String(item.label_en || '')}
              </span>
              <span className="text-violet-100">
                {' '}
                - {isRu ? String(item.expected_ru || '') : String(item.expected_en || '')}
              </span>
            </div>
          ))}
        </div>
      ) : null}
      {checks.length > 0 ? (
        <div className="mt-1 space-y-0.5 text-violet-100">
          {checks.slice(0, 4).map((check) => (
            <div key={String(check)}>{String(check)}</div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
