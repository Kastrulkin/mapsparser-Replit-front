import React, { useEffect, useMemo, useState } from 'react';
import { CalendarDays, CheckSquare, Globe, Lock, MapPinned, MoreHorizontal, Sparkles, Trash2, Wand2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useLanguage } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';
import type {
  ScopeOption, ContextPayload, PlanItem, PlanPayload, SocialPost, SocialPublishEvidence,
  SocialPublishRehearsal, SocialPublishRehearsalBulk, SocialOpenClawCapabilityStatus, SocialOpenClawReadiness, SocialSupervisedSafetyContract, SocialPostMetadata,
  SocialPostsSummary, SocialRecommendationPayload, SocialLearningReadiness, SocialRecommendationTopicInsight, SocialRecommendationChannelInsight, SocialRecommendationTextSuggestion,
  SocialQueueGroup, SocialDispatchPreview, SocialDispatchExecutionReport, SocialFirstCycleVerification, SocialLaunchRunbook, SocialMetricsLearningPacket,
  SocialTelegramPublishTargetProbe, SocialLaunchPreflight, SocialRuntimeStatus, SocialChannelReadiness, SocialChannelTargetSetup, SocialFirstApiProofDossier,
  SocialApiChannelPreflight, SocialChannelConnectionCheck, SocialPlanNextAction, SocialPlanNextStep, SocialGoalStage, SocialGoalProgress,
  SocialLaunchStage, SocialAttributionEventType, LearningMetricsPayload, ActionSummary, BulkNewsReview, BulkActionReview,
  SocialPreparePreview, SocialApprovalPreview, SocialApprovalPreviewSummary, SocialQueuePreview, SocialQueuePreviewSummary, NetworkOperatingSlice,
  OperatorInsight, ContentPlanTabProps, ContentMixKey, ContentMixState, ItemFilterKey, SignalFilterKey,
  ViewPresetKey, QuickActionKey, ContentPlanZone, ContentPlanMode, ContentLanguageKey
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
const CONTENT_LANGUAGE_OPTIONS: Array<{ value: ContentLanguageKey; label: string }> = [
  { value: 'ru', label: 'Русский' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Español' },
  { value: 'de', label: 'Deutsch' },
  { value: 'fr', label: 'Français' },
  { value: 'tr', label: 'Türkçe' },
  { value: 'it', label: 'Italiano' },
  { value: 'pt', label: 'Português' },
  { value: 'zh', label: '中文' },
];
const ITEM_FILTER_OPTIONS: ItemFilterKey[] = ['all', 'has_draft', 'urgent'];
const SIGNAL_FILTER_OPTIONS: SignalFilterKey[] = ['all', 'seo', 'services', 'sales', 'audit', 'seasonal'];
const CONTENT_PLAN_PREFERENCES_KEY = 'content_plan_preferences_v1';

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

export function _isSupervisedPlatform(platform: string): boolean {
  return platform === 'yandex_maps' || platform === 'two_gis';
}

export function _isSocialPostTextLocked(status: string): boolean {
  return ['queued', 'publishing', 'published'].includes(String(status || '').trim());
}

export function _socialSupervisedPayload(post: SocialPost) {
  return post.metadata_json?.supervised_publish || null;
}

export function _socialOpenClawReadinessDetails(
  readiness: SocialOpenClawReadiness | null,
  isRu: boolean,
): string[] {
  if (!readiness) return [];
  const diagnosticsSource = isRu ? readiness.diagnostics_ru : readiness.diagnostics_en;
  const diagnostics = Array.isArray(diagnosticsSource)
    ? diagnosticsSource.map(String).map((item) => item.trim()).filter(Boolean)
    : [];
  const delivery = readiness.delivery_readiness || {};
  const details = diagnostics.length > 0 ? diagnostics : [
    isRu
      ? 'Безопасная проверка: LocalOS ничего не публикует и только проверяет готовность OpenClaw.'
      : 'Safe check: LocalOS publishes nothing and only checks OpenClaw readiness.',
    readiness.ready
      ? (isRu ? 'Следующий шаг: подготовить контролируемое размещение и проверить предпросмотр.' : 'Next step: prepare supervised placement and review the preview.')
      : (isRu ? 'Следующий шаг: использовать ручной режим или проверить настройки OpenClaw.' : 'Next step: use manual fallback or check OpenClaw settings.'),
  ];
  if (readiness.browser_final_click_allowed === false || readiness.stop_before_final_publish) {
    details.push(
      isRu
        ? 'Финальная публикация остаётся за человеком.'
        : 'Final publishing stays human-controlled.',
    );
  }
  const forbidden = Array.isArray(readiness.forbidden_actions)
    ? readiness.forbidden_actions.map(String).filter(Boolean)
    : [];
  if (forbidden.includes('click_final_publish')) {
    details.push(
      isRu
        ? 'OpenClaw не нажимает финальную кнопку публикации.'
        : 'OpenClaw does not click the final publish button.',
    );
  }
  const suggestedCallback = String(delivery.suggested_callback_url || '').trim();
  const callbackEnvVar = String(delivery.callback_env_var || 'OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL').trim();
  const blockedCallbackReason = String(delivery.suggested_callback_blocked_reason || '').trim();
  if (suggestedCallback && !delivery.callback_configured) {
    details.push(
      isRu
        ? `Добавить env: ${callbackEnvVar}=${suggestedCallback}`
        : `Add env: ${callbackEnvVar}=${suggestedCallback}`,
    );
    details.push(
      isRu
        ? 'Стандартный адрес обратной связи OpenClaw: /m2m/localos/callbacks'
        : 'Standard OpenClaw receiver: /m2m/localos/callbacks',
    );
  }
  if (!suggestedCallback && blockedCallbackReason === 'sandbox_bridge_private_host') {
    details.push(
      isRu
        ? 'Текущий тестовый bridge не подходит для рабочего callback; нужен доступный адрес OpenClaw.'
        : 'The current sandbox bridge is not suitable for the production callback; use a reachable OpenClaw receiver.',
    );
  }
  if (delivery.outbox_available === true) {
    details.push(isRu ? 'Outbox для доставки task найден.' : 'Task delivery outbox is available.');
  }
  return Array.from(new Set(details)).slice(0, 6);
}

export function _socialLaunchStageStatusLabel(status: SocialLaunchStage['status'], isRu: boolean): string {
  if (status === 'done') return isRu ? 'готово' : 'done';
  if (status === 'current') return isRu ? 'сейчас' : 'now';
  if (status === 'attention') return isRu ? 'внимание' : 'attention';
  return isRu ? 'позже' : 'later';
}

export function _normalizeSocialGoalStage(stage: SocialGoalStage): SocialLaunchStage | null {
  const key = String(stage?.key || '').trim();
  const labelRu = String(stage?.labelRu || stage?.label_ru || '').trim();
  const labelEn = String(stage?.labelEn || stage?.label_en || '').trim();
  const detailRu = String(stage?.detailRu || stage?.detail_ru || '').trim();
  const detailEn = String(stage?.detailEn || stage?.detail_en || '').trim();
  const status = _normalizeSocialGoalStageStatus(stage?.status);
  if (!key || !labelRu || !labelEn) return null;
  return {
    key,
    labelRu,
    labelEn,
    status,
    detailRu,
    detailEn,
    count: Number(stage?.count || 0),
  };
}

export function _normalizeSocialGoalStageStatus(status: SocialGoalStage['status']): SocialLaunchStage['status'] {
  const normalized = String(status || '').trim();
  if (normalized === 'done' || normalized === 'current' || normalized === 'attention' || normalized === 'pending') {
    return normalized;
  }
  return 'pending';
}

export function _socialLaunchStageTone(status: SocialLaunchStage['status']): { dot: string; badge: string } {
  if (status === 'done') return { dot: 'bg-emerald-300', badge: 'bg-emerald-100 text-emerald-800' };
  if (status === 'current') return { dot: 'bg-sky-300', badge: 'bg-sky-100 text-sky-800' };
  if (status === 'attention') return { dot: 'bg-red-300', badge: 'bg-red-100 text-red-800' };
  return { dot: 'bg-slate-400', badge: 'bg-slate-100 text-slate-600' };
}

export function _socialOpenClawReadinessOperational(readiness: SocialOpenClawReadiness): boolean {
  if (typeof readiness.handoff_ready === 'boolean') return readiness.handoff_ready;
  if (readiness.delivery_readiness && typeof readiness.delivery_readiness.ready === 'boolean') {
    return Boolean(readiness.ready) && Boolean(readiness.delivery_readiness.ready);
  }
  return Boolean(readiness.ready);
}

export function _socialOpenClawReadinessTitle(readiness: SocialOpenClawReadiness, isRu: boolean): string {
  if (_socialOpenClawReadinessOperational(readiness)) {
    return isRu ? 'OpenClaw browser-use готов' : 'OpenClaw browser-use ready';
  }
  if (readiness.ready && readiness.delivery_readiness && !readiness.delivery_readiness.ready) {
    return isRu ? 'Доставка OpenClaw task не готова' : 'OpenClaw task delivery is not ready';
  }
  return isRu ? 'OpenClaw browser-use не подтверждён' : 'OpenClaw browser-use not confirmed';
}

export function _socialOpenClawOwnerCheckSummary(readiness: SocialOpenClawReadiness, isRu: boolean): string {
  const hasActionRef = Boolean(String(readiness.action_ref || '').trim());
  if (_socialOpenClawReadinessOperational(readiness)) {
    return hasActionRef
      ? (isRu
        ? 'Проверка OpenClaw пройдена: можно создать контролируемую задачу, финальная публикация остаётся за человеком.'
        : 'OpenClaw check passed: LocalOS can create a controlled task, and final publishing stays human-controlled.')
      : (isRu
        ? 'Проверка OpenClaw пройдена: можно готовить контролируемое размещение, финальная публикация остаётся за человеком.'
        : 'OpenClaw check passed: supervised placement can be prepared, and final publishing stays human-controlled.');
  }
  if (readiness.ready && readiness.delivery_readiness && !readiness.delivery_readiness.ready) {
    return isRu
      ? 'OpenClaw browser-use найден, но доставка задачи не готова: LocalOS сохранит ручной режим.'
      : 'OpenClaw browser-use is available, but callback/outbox delivery is not ready: LocalOS keeps manual fallback.';
  }
  if (readiness.provider_status === 'missing_catalog' || readiness.reason === 'openclaw_catalog_not_configured') {
    return isRu
      ? 'OpenClaw пока не подключён к этому экрану: LocalOS сохранит ручное размещение и не сорвёт план.'
      : 'OpenClaw is not connected to this screen yet: LocalOS keeps manual placement and will not block the plan.';
  }
  if (readiness.provider_status === 'error' || readiness.reason === 'openclaw_catalog_error') {
    return isRu
      ? 'LocalOS не смог проверить OpenClaw: используйте ручное размещение, пока доступ не восстановлен.'
      : 'LocalOS could not verify OpenClaw: use manual placement until access is restored.';
  }
  return isRu
    ? 'OpenClaw не подтверждён: для Яндекс/2ГИС будет показан ручной или контролируемый режим.'
    : 'OpenClaw is not confirmed: Yandex/2GIS will use manual or supervised fallback.';
}

export function _socialOpenClawCapabilityLine(
  status: string | SocialOpenClawCapabilityStatus | undefined,
  isRu: boolean,
): string {
  if (!status) return '';
  if (typeof status === 'string') {
    return status.trim() ? `OpenClaw browser-use: ${status.trim()}` : '';
  }
  const state = status.ready
    ? (isRu ? 'готов' : 'ready')
    : (isRu ? 'недоступен' : 'unavailable');
  const details = [
    status.status,
    status.source,
    status.reason,
    status.action_ref,
    status.error,
  ].map((item) => String(item || '').trim()).filter(Boolean);
  return `OpenClaw browser-use: ${state}${details.length ? ` · ${details.join(' · ')}` : ''}`;
}

export function _socialSupervisedHandoffStateLabel(state: string, isRu: boolean): string {
  const normalized = String(state || '').trim();
  if (normalized === 'ready_for_openclaw_handoff') {
    return isRu ? 'готово к OpenClaw' : 'ready for OpenClaw';
  }
  if (normalized === 'manual_fallback_required') {
    return isRu ? 'нужно вручную' : 'manual fallback';
  }
  return normalized;
}

export function _socialApiQueueWarnings(
  posts: SocialPost[],
  preflightByPlatform: Record<string, SocialApiChannelPreflight>,
  readinessByPlatform: Record<string, SocialChannelReadiness>,
  isRu: boolean,
): Array<{ postId: string; platform: string; label: string; status: string }> {
  const warnings: Array<{ postId: string; platform: string; label: string; status: string }> = [];
  for (const post of posts) {
    if (String(post.publish_mode || '').trim() !== 'api') continue;
    const platform = String(post.platform || '').trim();
    const preflight = preflightByPlatform[platform];
    const readiness = readinessByPlatform[platform];
    if (preflight && Boolean(preflight.ready)) continue;
    if (!preflight && (!readiness || Boolean(readiness.ready))) continue;
    warnings.push({
      postId: post.id,
      platform,
      label: String(preflight?.platform_label || readiness?.platform_label || post.platform_label || _socialPlatformLabel(platform, isRu)),
      status: String(preflight?.status || readiness?.status || (isRu ? 'нужно внимание' : 'needs attention')),
    });
  }
  return warnings;
}

export function _socialApprovalPostText(post: SocialPost): string {
  return String(post.platform_text || post.base_text || '').trim();
}

export function _socialApprovalSummary(
  posts: SocialPost[],
  preflightByPlatform: Record<string, SocialApiChannelPreflight>,
  readinessByPlatform: Record<string, SocialChannelReadiness>,
  isRu: boolean,
): SocialApprovalPreviewSummary {
  let api = 0;
  let supervised = 0;
  let emptyText = 0;
  const labels: string[] = [];
  const seenLabels = new Set<string>();
  for (const post of posts) {
    if (_isSupervisedPlatform(String(post.platform || ''))) {
      supervised += 1;
    } else {
      api += 1;
    }
    if (!_socialApprovalPostText(post)) {
      emptyText += 1;
    }
    const label = String(post.platform_label || _socialPlatformLabel(String(post.platform || ''), isRu));
    if (label && !seenLabels.has(label)) {
      seenLabels.add(label);
      labels.push(label);
    }
  }
  return {
    total: posts.length,
    api,
    supervised,
    emptyText,
    blockedApiWarnings: _socialApiQueueWarnings(posts, preflightByPlatform, readinessByPlatform, isRu),
    platformLabels: labels,
  };
}

export function _socialQueueSummary(
  posts: SocialPost[],
  preflightByPlatform: Record<string, SocialApiChannelPreflight>,
  readinessByPlatform: Record<string, SocialChannelReadiness>,
  isRu: boolean,
): SocialQueuePreviewSummary {
  let api = 0;
  let supervised = 0;
  let dueNow = 0;
  let firstScheduledFor = '';
  const labels: string[] = [];
  const seenLabels = new Set<string>();
  const nowMs = Date.now();
  for (const post of posts) {
    if (_isSupervisedPlatform(String(post.platform || ''))) {
      supervised += 1;
    } else {
      api += 1;
    }
    const scheduledFor = String(post.scheduled_for || '').trim();
    if (scheduledFor) {
      if (!firstScheduledFor || scheduledFor < firstScheduledFor) {
        firstScheduledFor = scheduledFor;
      }
      const scheduledMs = Date.parse(scheduledFor);
      if (Number.isFinite(scheduledMs) && scheduledMs <= nowMs) {
        dueNow += 1;
      }
    }
    const label = String(post.platform_label || _socialPlatformLabel(String(post.platform || ''), isRu));
    if (label && !seenLabels.has(label)) {
      seenLabels.add(label);
      labels.push(label);
    }
  }
  return {
    total: posts.length,
    api,
    supervised,
    dueNow,
    blockedApiWarnings: _socialApiQueueWarnings(posts, preflightByPlatform, readinessByPlatform, isRu),
    platformLabels: labels,
    firstScheduledFor,
  };
}

export function _socialSupervisedSafetySummary(
  contract: SocialSupervisedSafetyContract | undefined,
  isRu: boolean,
): { allowed: string[]; forbidden: string[]; fallback: string[] } {
  const allowedSource = Array.isArray(contract?.allowed_actions) && contract.allowed_actions.length
    ? contract.allowed_actions
    : ['open_platform', 'fill_text', 'attach_media', 'show_preview'];
  const forbiddenSource = Array.isArray(contract?.forbidden_actions) && contract.forbidden_actions.length
    ? contract.forbidden_actions
    : ['click_final_publish', 'publish_without_human_confirmation'];
  const fallbackSource = Array.isArray(contract?.manual_fallback_triggers) && contract.manual_fallback_triggers.length
    ? contract.manual_fallback_triggers
    : ['captcha', 'login_required', 'changed_ui'];
  return {
    allowed: allowedSource.map((item) => _socialSupervisedSafetyActionLabel(item, isRu)).filter(Boolean).slice(0, 4),
    forbidden: forbiddenSource.map((item) => _socialSupervisedSafetyActionLabel(item, isRu)).filter(Boolean).slice(0, 4),
    fallback: fallbackSource.map((item) => _socialSupervisedSafetyActionLabel(item, isRu)).filter(Boolean).slice(0, 4),
  };
}

export function _socialSupervisedSafetyActionLabel(action: string, isRu: boolean): string {
  const normalized = String(action || '').trim();
  if (normalized === 'open_platform') return isRu ? 'откроет площадку' : 'open the platform';
  if (normalized === 'fill_text') return isRu ? 'вставит текст' : 'fill the text';
  if (normalized === 'attach_media') return isRu ? 'добавит медиа' : 'attach media';
  if (normalized === 'show_preview') return isRu ? 'покажет предпросмотр' : 'show preview';
  if (normalized === 'return_task_status') return isRu ? 'вернёт статус задачи' : 'return task status';
  if (normalized === 'click_final_publish') return isRu ? 'не нажмёт финальную публикацию' : 'not click final publish';
  if (normalized === 'bypass_login') return isRu ? 'не обойдёт авторизацию' : 'not bypass login';
  if (normalized === 'solve_captcha_without_user') return isRu ? 'не решит капчу без вас' : 'not solve captcha without you';
  if (normalized === 'change_business_profile_data') return isRu ? 'не изменит карточку бизнеса' : 'not change business profile data';
  if (normalized === 'publish_without_human_confirmation') return isRu ? 'не опубликует без подтверждения' : 'not publish without confirmation';
  if (normalized === 'captcha') return isRu ? 'капча' : 'captcha';
  if (normalized === 'login_required') return isRu ? 'нужен вход' : 'login required';
  if (normalized === 'changed_ui') return isRu ? 'изменился интерфейс' : 'changed UI';
  if (normalized === 'missing_target_url') return isRu ? 'нет ссылки на профиль' : 'missing profile link';
  if (normalized === 'browser_capability_unavailable') return isRu ? 'browser-use недоступен' : 'browser-use unavailable';
  if (normalized === 'unexpected_external_prompt') return isRu ? 'внешний запрос подтверждения' : 'unexpected external prompt';
  return normalized.replace(/_/g, ' ');
}

export function _normalizeSocialChannelFilter(value: string): 'all' | 'social' | 'maps' {
  if (value === 'social') return 'social';
  if (value === 'maps') return 'maps';
  return 'all';
}

export function _socialChannelFilterLabel(value: string, isRu: boolean): string {
  if (value === 'social') return isRu ? 'Только соцсети' : 'Social only';
  if (value === 'maps') return isRu ? 'Только карты' : 'Maps only';
  return isRu ? 'Все каналы' : 'All channels';
}

export function _matchesChannelFilter(
  item: PlanItem,
  postsByItem: Record<string, SocialPost[]>,
  filterKey: 'all' | 'social' | 'maps',
): boolean {
  if (filterKey === 'all') return true;
  const posts = postsByItem[item.id] || [];
  if (!posts.length) return true;
  if (filterKey === 'maps') return posts.some((post) => _isSupervisedPlatform(post.platform) || post.platform === 'google_business');
  return posts.some((post) => !_isSupervisedPlatform(post.platform) && post.platform !== 'google_business');
}

export function _socialPlatformLabel(platform: string, isRu: boolean): string {
  const normalized = String(platform || '').trim();
  if (normalized === 'yandex_maps') return isRu ? 'Яндекс Карты' : 'Yandex Maps';
  if (normalized === 'two_gis') return '2ГИС';
  if (normalized === 'google_business') return 'Google Business';
  if (normalized === 'telegram') return 'Telegram';
  if (normalized === 'vk') return 'VK';
  if (normalized === 'instagram') return 'Instagram';
  if (normalized === 'facebook') return 'Facebook';
  return normalized || (isRu ? 'Канал' : 'Channel');
}

export function _socialMetricsSourceText(platform: string, isRu: boolean): string {
  const normalized = String(platform || '').trim();
  if (normalized === 'vk') {
    return isRu
      ? 'API-снимок: просмотры, лайки, комментарии и репосты; заявки/обращения можно отметить вручную.'
      : 'API snapshot: views, likes, comments, and shares; leads/inquiries can be marked manually.';
  }
  if (normalized === 'telegram') {
    return isRu
      ? 'Результат учитывается через ручные отметки заявок/обращений; Bot API не даёт полный срез реакций для обычного sendMessage.'
      : 'Results use manual lead/inquiry marking; Bot API does not expose a full reaction snapshot for ordinary sendMessage posts.';
  }
  if (normalized === 'yandex_maps' || normalized === 'two_gis') {
    return isRu
      ? 'После контролируемого или ручного размещения отметьте публикацию и заявки вручную; LocalOS не подставляет недоступные API-метрики.'
      : 'After supervised/manual placement, mark publishing and leads manually; LocalOS does not invent unavailable API metrics.';
  }
  if (normalized === 'google_business') {
    return isRu
      ? 'Метрики собираются через Google boundary там, где есть разрешения; иначе используйте ручные заявки/обращения.'
      : 'Metrics are collected through the Google boundary where permissions allow; otherwise use manual leads/inquiries.';
  }
  if (normalized === 'instagram' || normalized === 'facebook') {
    return isRu
      ? 'Meta-метрики появятся после permissions и business/page binding; до этого результат отмечается вручную.'
      : 'Meta metrics appear after permissions and business/page binding; until then, mark results manually.';
  }
  return isRu
    ? 'Результат учитывается по доступным API-метрикам и ручным отметкам заявок/обращений.'
    : 'Results use available API metrics and manual lead/inquiry marks.';
}

export function _socialSettingsPathForPlatform(platform: string): string {
  const normalized = String(platform || '').trim();
  if (normalized === 'telegram') return '/dashboard/settings?focus=telegram';
  if (normalized === 'vk') return '/dashboard/settings?focus=vk';
  if (normalized === 'google_business') return '/dashboard/settings?focus=google_business';
  if (normalized === 'instagram' || normalized === 'facebook') return `/dashboard/settings?focus=${normalized}`;
  if (normalized === 'yandex_maps' || normalized === 'two_gis') return '/dashboard/card?tab=news&mode=plan';
  return '/dashboard/settings?focus=integrations';
}

export function _socialChannelSetupSort(left: SocialChannelReadiness, right: SocialChannelReadiness): number {
  const priority = ['telegram', 'vk', 'google_business', 'instagram', 'facebook', 'yandex_maps', 'two_gis'];
  const leftPlatform = String(left.platform || '').trim();
  const rightPlatform = String(right.platform || '').trim();
  const leftIndex = priority.indexOf(leftPlatform);
  const rightIndex = priority.indexOf(rightPlatform);
  const leftRank = leftIndex >= 0 ? leftIndex : priority.length;
  const rightRank = rightIndex >= 0 ? rightIndex : priority.length;
  if (leftRank !== rightRank) return leftRank - rightRank;
  return String(left.platform_label || leftPlatform).localeCompare(String(right.platform_label || rightPlatform));
}

export function _socialChannelConnectionStateLabel(channel: SocialChannelReadiness, isRu: boolean): string {
  if (Boolean(channel.ready)) return isRu ? 'готово' : 'ready';
  const status = String(channel.status || '').trim();
  if (status.includes('permission') || status.includes('blocked')) return isRu ? 'нужны права' : 'permissions';
  if ((channel.missing_fields || []).length > 0) return isRu ? 'нужны ключи' : 'keys needed';
  return isRu ? 'нужно подключить' : 'setup needed';
}

export function _socialWorkerEnvLines(
  dispatchEnv: Record<string, string>,
  metricsEnv: Record<string, string>,
): string[] {
  const lines: string[] = [];
  for (const key of [
    'SOCIAL_POST_DISPATCH_ENABLED',
    'SOCIAL_POST_DISPATCH_INTERVAL_SEC',
    'SOCIAL_POST_DISPATCH_BATCH_SIZE',
    'SOCIAL_POST_DISPATCH_BUSINESS_ID',
  ]) {
    const value = String(dispatchEnv[key] || '').trim();
    if (value) lines.push(`${key}=${value}`);
  }
  for (const key of [
    'SOCIAL_POST_METRICS_ENABLED',
    'SOCIAL_POST_METRICS_INTERVAL_SEC',
    'SOCIAL_POST_METRICS_BATCH_SIZE',
    'SOCIAL_POST_METRICS_BUSINESS_ID',
  ]) {
    const value = String(metricsEnv[key] || '').trim();
    if (value) lines.push(`${key}=${value}`);
  }
  return lines;
}

export function _socialLaunchRunbookBlock(runbook: SocialLaunchRunbook | undefined, isRu: boolean) {
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

export function _socialLaunchRunbookClipboardLines(runbook: SocialLaunchRunbook | undefined, isRu: boolean): string[] {
  const steps = Array.isArray(isRu ? runbook?.steps_ru : runbook?.steps_en)
    ? (isRu ? runbook?.steps_ru : runbook?.steps_en) || []
    : [];
  const criteria = Array.isArray(isRu ? runbook?.success_criteria_ru : runbook?.success_criteria_en)
    ? (isRu ? runbook?.success_criteria_ru : runbook?.success_criteria_en) || []
    : [];
  const blockedReason = isRu ? String(runbook?.blocked_reason_ru || '') : String(runbook?.blocked_reason_en || '');
  const lines: string[] = [];
  if (steps.length || criteria.length || blockedReason) {
    lines.push('', isRu ? '# Runbook первого цикла dispatch' : '# First-cycle dispatch runbook');
  }
  if (blockedReason) lines.push(`${isRu ? 'Blocked' : 'Blocked'}: ${blockedReason}`);
  steps.forEach((step, index) => {
    lines.push(`${index + 1}. ${String(step)}`);
  });
  if (criteria.length) {
    lines.push(isRu ? 'Критерии успеха:' : 'Success criteria:');
    criteria.forEach((item) => {
      lines.push(`- ${String(item)}`);
    });
  }
  return lines;
}

export function _socialFirstCycleVerificationBlock(
  verification: SocialFirstCycleVerification | undefined,
  isRu: boolean,
) {
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

export async function copyTextToClipboard(value: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const textarea = document.createElement('textarea');
  textarea.value = value;
  textarea.setAttribute('readonly', 'true');
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand('copy');
  document.body.removeChild(textarea);
}

export function _socialPublishModeLabel(mode: string, isRu: boolean): string {
  const normalized = String(mode || '').trim();
  if (normalized === 'api') return isRu ? 'API после подтверждения' : 'API after approval';
  if (normalized === 'openclaw_browser') return isRu ? 'Контролируемый браузер OpenClaw' : 'Supervised OpenClaw browser-use';
  if (normalized === 'local_supervised_browser') return isRu ? 'Локальный контролируемый браузер' : 'Local supervised browser';
  if (normalized === 'manual') return isRu ? 'Ручное размещение' : 'Manual fallback';
  return isRu ? 'Режим не задан' : 'Mode not set';
}

export function _socialStatusLabel(status: string, isRu: boolean): string {
  const normalized = String(status || '').trim();
  if (normalized === 'draft') return isRu ? 'Черновик' : 'Draft';
  if (normalized === 'needs_review') return isRu ? 'Нужно проверить' : 'Needs review';
  if (normalized === 'approved') return isRu ? 'Подтверждено' : 'Approved';
  if (normalized === 'queued') return isRu ? 'В расписании' : 'Queued';
  if (normalized === 'publishing') return isRu ? 'Публикуется' : 'Publishing';
  if (normalized === 'published') return isRu ? 'Опубликовано' : 'Published';
  if (normalized === 'failed') return isRu ? 'Ошибка' : 'Failed';
  if (normalized === 'needs_manual_publish') return isRu ? 'Нужно вручную' : 'Manual needed';
  if (normalized === 'needs_supervised_publish') return isRu ? 'Контролируемое размещение' : 'Supervised placement';
  return isRu ? 'Статус неизвестен' : 'Unknown status';
}

export function _socialStatusClassName(status: string): string {
  const normalized = String(status || '').trim();
  const base = 'rounded-full px-3 py-1 text-xs font-medium';
  if (normalized === 'published') return `${base} bg-emerald-50 text-emerald-800`;
  if (normalized === 'failed') return `${base} bg-red-50 text-red-800`;
  if (normalized === 'needs_supervised_publish' || normalized === 'needs_manual_publish') return `${base} bg-amber-50 text-amber-800`;
  if (normalized === 'approved' || normalized === 'queued' || normalized === 'publishing') return `${base} bg-blue-50 text-blue-800`;
  return `${base} bg-slate-100 text-slate-700`;
}

export function _socialPublishEvidenceClassName(tone: string): string {
  const normalized = String(tone || '').trim();
  const base = 'mt-3 rounded-xl border px-3 py-2 text-xs leading-5';
  if (normalized === 'success') return `${base} border-emerald-200 bg-emerald-50 text-emerald-800`;
  if (normalized === 'danger') return `${base} border-red-200 bg-red-50 text-red-700`;
  if (normalized === 'warning') return `${base} border-amber-200 bg-amber-50 text-amber-800`;
  if (normalized === 'info') return `${base} border-blue-100 bg-blue-50 text-blue-800`;
  return `${base} border-slate-200 bg-slate-50 text-slate-700`;
}

export function _socialProofQualityLabel(value: string, isRu: boolean): string {
  const normalized = String(value || '').trim();
  if (normalized === 'url') return isRu ? 'ссылка' : 'URL';
  if (normalized === 'provider_id') return 'provider ID';
  if (normalized === 'published_without_provider_ref') return isRu ? 'без ссылки/ID' : 'no URL/ID';
  if (normalized === 'supervised_task') return isRu ? 'контролируемая задача' : 'supervised task';
  if (normalized === 'error') return isRu ? 'ошибка' : 'error';
  if (normalized === 'pending') return isRu ? 'ожидает результата' : 'pending';
  return normalized || (isRu ? 'неизвестно' : 'unknown');
}

export function _socialLearningReadinessClassName(confidence: string): string {
  const normalized = String(confidence || '').trim();
  const base = 'mt-3 rounded-lg border px-3 py-2';
  if (normalized === 'high') return `${base} border-emerald-100 bg-white text-emerald-900`;
  if (normalized === 'medium') return `${base} border-lime-100 bg-white text-lime-900`;
  if (normalized === 'low') return `${base} border-amber-100 bg-white text-amber-900`;
  return `${base} border-slate-200 bg-white text-slate-700`;
}

export function _socialLearningConfidenceLabel(confidence: string, isRu: boolean): string {
  const normalized = String(confidence || '').trim();
  if (normalized === 'high') return isRu ? 'доверие высокое' : 'high confidence';
  if (normalized === 'medium') return isRu ? 'среднее доверие' : 'medium confidence';
  if (normalized === 'low') return isRu ? 'данных мало' : 'low data';
  return isRu ? 'ждём факты' : 'waiting for facts';
}

export function _socialLearningChecklistStatusLabel(status: string, isRu: boolean): string {
  const normalized = String(status || '').trim();
  if (normalized === 'done') return isRu ? 'готово' : 'done';
  if (normalized === 'current') return isRu ? 'сейчас' : 'now';
  if (normalized === 'attention') return isRu ? 'внимание' : 'attention';
  return isRu ? 'позже' : 'later';
}

export function _socialNextActionLabel(action: string, isRu: boolean): string {
  const normalized = String(action || '').trim();
  if (normalized === 'review_required') return isRu ? 'следующий шаг: проверить текст' : 'next: review text';
  if (normalized === 'start_supervised_publish') return isRu ? 'следующий шаг: открыть контролируемое размещение' : 'next: open supervised placement';
  if (normalized === 'wait_for_api_publish') return isRu ? 'следующий шаг: поставить в расписание' : 'next: queue on schedule';
  if (normalized === 'wait_for_scheduled_publish') return isRu ? 'ждёт даты публикации' : 'waiting for scheduled publish';
  if (normalized === 'wait_for_scheduled_supervised_publish') return isRu ? 'ждёт даты контролируемого размещения' : 'waiting for scheduled supervised placement';
  if (normalized === 'open_supervised_publish') return isRu ? 'следующий шаг: завершить контролируемое размещение' : 'next: finish supervised placement';
  if (normalized === 'manual_publish') return isRu ? 'следующий шаг: разместить вручную' : 'next: publish manually';
  if (normalized === 'retry_or_manual') return isRu ? 'следующий шаг: повторить или вручную' : 'next: retry or manual';
  if (normalized === 'collect_metrics') return isRu ? 'следующий шаг: собрать реакции' : 'next: collect reactions';
  return isRu ? 'следующий шаг не требуется' : 'no next action';
}

export function _socialItemQueueSummary(posts: SocialPost[], isRu: boolean): {
  label: string;
  detail: string;
  totalLabel: string;
  className: string;
} {
  const counts = posts.reduce((acc, post) => {
    const status = String(post.status || '').trim();
    if (status === 'draft' || status === 'needs_review') acc.review += 1;
    else if (status === 'approved') acc.approved += 1;
    else if (status === 'queued' || status === 'publishing') acc.queued += 1;
    else if (status === 'needs_supervised_publish') acc.supervised += 1;
    else if (status === 'needs_manual_publish') acc.manual += 1;
    else if (status === 'failed') acc.failed += 1;
    else if (status === 'published') acc.published += 1;
    if (_isSupervisedPlatform(String(post.platform || ''))) acc.maps += 1;
    else acc.api += 1;
    return acc;
  }, {
    review: 0,
    approved: 0,
    queued: 0,
    supervised: 0,
    manual: 0,
    failed: 0,
    published: 0,
    api: 0,
    maps: 0,
  });
  const total = posts.length;
  const base = 'rounded-full px-2.5 py-1 text-[11px] font-semibold';
  let label = isRu ? 'Каналы готовы' : 'Channels ready';
  let className = `${base} bg-slate-100 text-slate-700`;

  if (counts.review > 0) {
    label = isRu ? `Проверить тексты: ${counts.review}` : `Review copy: ${counts.review}`;
    className = `${base} bg-sky-100 text-sky-800`;
  } else if (counts.approved > 0) {
    label = isRu ? `Можно в расписание: ${counts.approved}` : `Ready to queue: ${counts.approved}`;
    className = `${base} bg-blue-100 text-blue-800`;
  } else if (counts.failed > 0 || counts.manual > 0) {
    const attention = counts.failed + counts.manual;
    label = isRu ? `Нужно внимание: ${attention}` : `Needs attention: ${attention}`;
    className = `${base} bg-red-100 text-red-700`;
  } else if (counts.supervised > 0) {
    label = isRu ? `Контролируемое размещение: ${counts.supervised}` : `Supervised placement: ${counts.supervised}`;
    className = `${base} bg-amber-100 text-amber-800`;
  } else if (counts.queued > 0) {
    label = isRu ? `В расписании: ${counts.queued}` : `Queued: ${counts.queued}`;
    className = `${base} bg-blue-100 text-blue-800`;
  } else if (counts.published > 0) {
    label = isRu ? `Опубликовано: ${counts.published}` : `Published: ${counts.published}`;
    className = `${base} bg-emerald-100 text-emerald-800`;
  }

  const detailParts = [
    isRu ? `API ${counts.api}` : `API ${counts.api}`,
    isRu ? `карты ${counts.maps}` : `maps ${counts.maps}`,
  ];
  if (counts.review > 0) detailParts.push(isRu ? `проверка ${counts.review}` : `review ${counts.review}`);
  if (counts.approved > 0) detailParts.push(isRu ? `утверждено ${counts.approved}` : `approved ${counts.approved}`);
  if (counts.queued > 0) detailParts.push(isRu ? `расписание ${counts.queued}` : `queued ${counts.queued}`);
  if (counts.supervised > 0) detailParts.push(isRu ? `контролируемо ${counts.supervised}` : `supervised ${counts.supervised}`);
  if (counts.manual > 0) detailParts.push(isRu ? `вручную ${counts.manual}` : `manual ${counts.manual}`);
  if (counts.failed > 0) detailParts.push(isRu ? `ошибки ${counts.failed}` : `failed ${counts.failed}`);
  if (counts.published > 0) detailParts.push(isRu ? `вышло ${counts.published}` : `published ${counts.published}`);

  return {
    label,
    className,
    detail: detailParts.join(' · '),
    totalLabel: isRu ? `каналов: ${total}` : `channels: ${total}`,
  };
}

export function _socialDispatchActionLabel(action: string, isRu: boolean): string {
  const normalized = String(action || '').trim();
  if (normalized === 'publish_api') return isRu ? 'API-публикация' : 'API publish';
  if (normalized === 'create_supervised_task') return isRu ? 'контролируемое размещение' : 'supervised placement';
  if (normalized === 'manual_handoff') return isRu ? 'ручной шаг' : 'manual step';
  return isRu ? 'проверить' : 'check';
}

export function _socialDispatchReasonLabel(reason: string, isRu: boolean): string {
  const normalized = String(reason || '').trim();
  if (normalized === 'channel_ready') return isRu ? 'Канал готов: после подтверждения исполнитель сможет выполнить API-публикацию.' : 'Channel is ready; after approval the worker can publish via API.';
  if (normalized === 'openclaw_browser_ready') return isRu ? 'OpenClaw browser-use готов, финальная кнопка публикации не нажимается без подтверждения.' : 'OpenClaw browser-use is ready; final publish is not clicked without approval.';
  if (normalized === 'openclaw_browser_unavailable') return isRu ? 'Браузерное размещение недоступно, нужен ручной или контролируемый режим.' : 'Browser-use is unavailable, manual/supervised fallback is needed.';
  if (normalized === 'publish_mode_not_api') return isRu ? 'Для канала нет API-режима, нужен ручной шаг.' : 'This channel has no API mode, manual step is needed.';
  return normalized;
}

export function _socialInsightMetricLine(
  metrics: SocialRecommendationTopicInsight['metrics'] | undefined,
  isRu: boolean,
): string {
  const leads = Number(metrics?.leads || 0);
  const inquiries = Number(metrics?.inquiries || 0);
  const comments = Number(metrics?.comments || 0);
  const reach = Number(metrics?.reach || 0);
  return isRu
    ? `заявки ${leads}, обращения ${inquiries}, комментарии ${comments}, охват ${reach}`
    : `leads ${leads}, inquiries ${inquiries}, comments ${comments}, reach ${reach}`;
}

export function _socialAttributionFeedback(eventType: SocialAttributionEventType): { ru: string; en: string } {
  if (eventType === 'lead') {
    return {
      ru: 'Заявка привязана к публикации. Следующий план будет учитывать её выше охватов.',
      en: 'Lead recorded for this post. Next plan will rank it above reach.',
    };
  }
  if (eventType === 'inquiry') {
    return {
      ru: 'Обращение привязано к публикации. Следующий план будет учитывать его выше лайков и охватов.',
      en: 'Inquiry recorded for this post. Next plan will rank it above likes and reach.',
    };
  }
  if (eventType === 'comment') {
    return {
      ru: 'Комментарий привязан к публикации как ранний сигнал интереса.',
      en: 'Comment recorded as an early interest signal for this post.',
    };
  }
  if (eventType === 'share') {
    return {
      ru: 'Репост привязан к публикации. Это усилит оценку формата, но ниже заявок и обращений.',
      en: 'Share recorded for this post. It helps evaluate the format, below leads and inquiries.',
    };
  }
  if (eventType === 'like') {
    return {
      ru: 'Лайк привязан к публикации как ранний сигнал. Заявки и обращения всё равно важнее.',
      en: 'Like recorded as an early signal. Leads and inquiries still rank higher.',
    };
  }
  if (eventType === 'view') {
    return {
      ru: 'Просмотр привязан к публикации как ранний сигнал охвата.',
      en: 'View recorded as an early reach signal for this post.',
    };
  }
  return {
    ru: 'Клик привязан к публикации как ранний сигнал интереса.',
    en: 'Click recorded as an early interest signal for this post.',
  };
}

export function _socialQueueGroupLabel(group: SocialQueueGroup, isRu: boolean): string {
  const label = isRu ? group.label_ru : group.label_en;
  if (label) return label;
  const key = String(group.key || '').trim();
  if (key === 'needs_review') return isRu ? 'Нужно проверить' : 'Needs review';
  if (key === 'api_ready') return isRu ? 'Готово к API' : 'API ready';
  if (key === 'scheduled') return isRu ? 'Запланировано' : 'Scheduled';
  if (key === 'needs_supervised_publish') return isRu ? 'Нужно контролируемое размещение' : 'Needs supervised placement';
  if (key === 'needs_manual_publish') return isRu ? 'Нужно вручную / подключить канал' : 'Manual / connection needed';
  if (key === 'published') return isRu ? 'Опубликовано' : 'Published';
  if (key === 'failed') return isRu ? 'Ошибка' : 'Failed';
  return isRu ? 'Очередь' : 'Queue';
}

export function _socialQueueGroupNextAction(group: SocialQueueGroup, isRu: boolean): string {
  const text = isRu ? group.next_action_ru : group.next_action_en;
  if (text) return text;
  return isRu ? 'Следующее действие будет показано после подготовки каналов.' : 'Next action appears after channel preparation.';
}

export function _contentTypeLabel(contentType: string, isRu: boolean): string {
  const normalized = String(contentType || '').trim().toLowerCase();
  if (normalized === 'seo') return isRu ? 'SEO' : 'SEO';
  if (normalized === 'service') return isRu ? 'Услуга' : 'Service';
  if (normalized === 'sales') return isRu ? 'Продажи' : 'Sales';
  if (normalized === 'audit') return isRu ? 'Аудит' : 'Audit';
  if (normalized === 'seasonal') return isRu ? 'Сезонность' : 'Seasonal';
  return isRu ? 'Контент' : 'Content';
}

export function _scopeChipLabel(scopeType: string, isRu: boolean): string {
  const normalized = String(scopeType || '').trim().toLowerCase();
  if (normalized === 'network_parent') return isRu ? 'Сеть' : 'Network';
  if (normalized === 'network_location') return isRu ? 'Точка' : 'Location';
  return isRu ? 'Бизнес' : 'Business';
}

export function _locationScopeLabel(scopeType: string, isRu: boolean): string {
  const normalized = String(scopeType || '').trim().toLowerCase();
  if (normalized === 'network_parent') return isRu ? 'материнский план' : 'parent plan';
  if (normalized === 'network_location') return isRu ? 'локальный план' : 'local plan';
  return isRu ? 'текущий бизнес' : 'current business';
}

export function _planTargetLabel(plan: Pick<PlanPayload, 'scope_type' | 'scope_target_label' | 'scope_target_city' | 'scope_target_address'>, isRu: boolean): string {
  const label = String(plan.scope_target_label || '').trim();
  const city = String(plan.scope_target_city || '').trim();
  const address = String(plan.scope_target_address || '').trim();
  if (label && city) return `${label} · ${city}`;
  if (label && address) return `${label} · ${address}`;
  if (label) return label;
  return _scopeChipLabel(plan.scope_type, isRu);
}

export function _itemLocationLabel(item: Pick<PlanItem, 'location_label' | 'location_city' | 'location_address'>, isRu: boolean): string {
  const label = String(item.location_label || '').trim();
  const city = String(item.location_city || '').trim();
  const address = String(item.location_address || '').trim();
  if (label && city) return `${label} · ${city}`;
  if (label && address) return `${label} · ${address}`;
  if (label) return label;
  return isRu ? 'Точка сети' : 'Network location';
}

export function _locationLabelByKey(items: PlanItem[], locationKey: string, isRu: boolean): string {
  for (const item of items) {
    const currentKey = String(item.location_scope || item.business_id || '').trim();
    if (currentKey === locationKey) {
      return _itemLocationLabel(item, isRu);
    }
  }
  return isRu ? 'Точка сети' : 'Network location';
}

export function _bulkResultText(kind: 'drafts' | 'news', successCount: number, failedCount: number, isRu: boolean): string {
  if (kind === 'drafts') {
    if (failedCount > 0) {
      return isRu
        ? `сгенерировано черновиков ${successCount}, не получилось ${failedCount}`
        : `generated drafts ${successCount}, failed ${failedCount}`;
    }
    return isRu
      ? `сгенерировано черновиков ${successCount}`
      : `generated drafts ${successCount}`;
  }
  if (failedCount > 0) {
    return isRu
      ? `создано новостей ${successCount}, не получилось ${failedCount}`
      : `created news items ${successCount}, failed ${failedCount}`;
  }
  return isRu
    ? `создано новостей ${successCount}`
    : `created news items ${successCount}`;
}

export function _bulkResultDetails(failedThemes: string[], isRu: boolean): string[] {
  const cleanThemes = failedThemes
    .map((theme) => String(theme || '').trim())
    .filter(Boolean)
    .slice(0, 3);
  if (cleanThemes.length === 0) return [];
  const prefix = isRu ? 'Не обработано' : 'Not processed';
  return cleanThemes.map((theme) => `${prefix}: ${theme}`);
}

export function _learningCapabilityLabel(capability: string, isRu: boolean): string {
  const normalized = String(capability || '').trim().toLowerCase();
  if (normalized === 'content_plan.generate') return isRu ? 'Генерация плана' : 'Plan generation';
  if (normalized === 'content_plan.draft') return isRu ? 'Генерация черновика' : 'Draft generation';
  if (normalized === 'content_plan.item') return isRu ? 'Действия с элементами' : 'Item actions';
  if (normalized === 'content_plan.publish') return isRu ? 'Создание новостей' : 'News creation';
  return isRu ? 'Контент-план' : 'Content plan';
}

export function _networkQualityReasonLabel(reason: string, isRu: boolean): string {
  const normalized = String(reason || '').trim();
  if (normalized === 'many_edits') return isRu ? 'часто правят перед публикацией' : 'often edited before publishing';
  if (normalized === 'skipped_items') return isRu ? 'есть пропущенные темы' : 'has skipped topics';
  if (normalized === 'major_rewrites') return isRu ? 'есть смысловые переписывания' : 'has major rewrites';
  if (normalized === 'drafts_not_published') return isRu ? 'черновики не доходят до новостей' : 'drafts do not reach publishing';
  if (normalized === 'stable') return isRu ? 'работает стабильно' : 'stable';
  return isRu ? 'нужна проверка' : 'needs review';
}

export function _networkRiskLabel(riskScore: number, isRu: boolean): string {
  if (Number(riskScore || 0) >= 60) return isRu ? 'Высокий риск' : 'High risk';
  if (Number(riskScore || 0) >= 30) return isRu ? 'Средний риск' : 'Medium risk';
  return isRu ? 'Норма' : 'Stable';
}

export function _networkOperatingRecommendation(reasons: string[], isRu: boolean): string {
  const normalized = Array.isArray(reasons) ? reasons.map((item) => String(item || '').trim()) : [];
  if (normalized.includes('drafts_not_published')) {
    return isRu
      ? 'Сначала доведите готовые черновики до новостей: здесь уже есть заготовки, но они не превращаются в публикации.'
      : 'Start by turning ready drafts into news: this location has drafts that do not reach publishing.';
  }
  if (normalized.includes('skipped_items')) {
    return isRu
      ? 'Проверьте темы этой точки: часть идей пропускается, значит нужно упростить поводы и оставить только то, что реально выпустить.'
      : 'Review this location themes: skipped items mean the topics should be simpler and easier to publish.';
  }
  if (normalized.includes('major_rewrites')) {
    return isRu
      ? 'Генерируйте черновики точнее: конкретная услуга, понятная выгода, доказательство и одно действие для клиента.'
      : 'Generate tighter drafts: concrete service, clear benefit, proof point, and one customer action.';
  }
  if (normalized.includes('many_edits')) {
    return isRu
      ? 'Перед публикацией проверьте формулировки: по этой точке часто нужны ручные правки.'
      : 'Review wording before publishing: this location often needs manual edits.';
  }
  return isRu
    ? 'Работайте ближайшей неделей: закройте темы без текста, затем создайте новости из готовых черновиков.'
    : 'Work through the nearest week: fill missing drafts, then create news from ready drafts.';
}

export function _itemFilterLabel(filterKey: ItemFilterKey, isRu: boolean): string {
  if (filterKey === 'urgent') return isRu ? 'Срочное' : 'Urgent';
  if (filterKey === 'has_draft') return isRu ? 'Текст готов' : 'Draft ready';
  return isRu ? 'Все' : 'All';
}

export function _planItemStatus(item: Pick<PlanItem, 'draft_text' | 'usernews_id' | 'status'>, isRu: boolean): { label: string; className: string } {
  const normalizedStatus = String(item.status || '').trim();
  const hasDraft = Boolean(String(item.draft_text || '').trim());
  const hasNews = Boolean(String(item.usernews_id || '').trim());
  const baseClassName = 'rounded-full px-2.5 py-1 text-xs font-semibold';
  if (normalizedStatus === 'skipped') {
    return {
      label: isRu ? 'Пропущено' : 'Skipped',
      className: `${baseClassName} bg-slate-100 text-slate-500`,
    };
  }
  if (hasNews) {
    return {
      label: isRu ? 'Новость создана' : 'News created',
      className: `${baseClassName} bg-emerald-100 text-emerald-800`,
    };
  }
  if (hasDraft) {
    return {
      label: isRu ? 'Текст готов' : 'Draft ready',
      className: `${baseClassName} bg-sky-100 text-sky-800`,
    };
  }
  return {
    label: isRu ? 'Без текста' : 'No draft',
    className: `${baseClassName} bg-amber-100 text-amber-800`,
  };
}

export function _humanizePlanTitle(item: Pick<PlanItem, 'theme' | 'goal' | 'seo_keyword' | 'content_type'>, isRu: boolean): string {
  const rawTitle = String(item.theme || item.goal || item.seo_keyword || '').trim();
  const fallback = isRu ? 'Тема для публикации' : 'Publication topic';
  if (!rawTitle) return fallback;
  const noisyPrefixes = [
    'Закрыть слабую зону карточки:',
    'Недопокрытый поисковый сценарий:',
    'Ответить на спрос:',
    'Закрыть слабое место карточки:',
    'Аудит ·',
    'SEO ·',
    'Услуга ·',
    'Продажи ·',
  ];
  let title = rawTitle;
  for (const prefix of noisyPrefixes) {
    if (title.toLowerCase().startsWith(prefix.toLowerCase())) {
      title = title.slice(prefix.length).trim();
    }
  }
  title = title
    .replace(/\s+/g, ' ')
    .replace(/^["'«]+|["'»]+$/g, '')
    .trim();
  if (!title) return fallback;
  if (title.length <= 96) return title;
  return `${title.slice(0, 93).trim()}...`;
}

export function _humanizePlanGoal(item: Pick<PlanItem, 'goal' | 'theme' | 'source_kind' | 'source_ref' | 'seo_keyword'>, isRu: boolean): string {
  const rawGoal = String(item.goal || '').trim();
  const rawTheme = String(item.theme || '').trim();
  const sourceRef = String(item.source_ref || item.seo_keyword || '').trim();
  const combined = `${rawGoal} ${rawTheme} ${sourceRef}`.toLowerCase();
  if (!rawGoal && !rawTheme && !sourceRef) {
    return isRu ? 'Причина не указана.' : 'No reason provided.';
  }
  if (
    combined.includes('недопокрытый поисковый сценарий')
    || combined.includes('закрыть слабую зону карточки')
    || combined.includes('закрыть слабое место карточки')
  ) {
    const readableSource = _cleanTechnicalPlanText(sourceRef || rawTheme);
    if (readableSource && /цен|стоимост|прайс|пример|работ|фото/i.test(readableSource)) {
      return isRu
        ? 'Клиенту проще записаться, если в карточке видно цену, результат и понятный следующий шаг.'
        : 'Customers are more likely to book when the listing shows price, result, and the next step.';
    }
    if (readableSource) {
      return isRu
        ? `Карточке нужен понятный ответ на запрос клиента: ${readableSource}.`
        : `The listing needs a clear answer for this customer search: ${readableSource}.`;
    }
    return isRu
      ? 'Карточке нужен более понятный ответ на поисковый сценарий клиента.'
      : 'The listing needs a clearer answer for this customer search scenario.';
  }
  return rawGoal || rawTheme || (isRu ? 'Причина не указана.' : 'No reason provided.');
}

export function _cleanTechnicalPlanText(value: string): string {
  const prefixes = [
    'Закрыть слабую зону карточки:',
    'Закрыть слабое место карточки вокруг темы',
    'Закрыть слабое место карточки:',
    'Недопокрытый поисковый сценарий:',
    'Ответить на спрос:',
  ];
  let text = String(value || '').trim();
  let changed = true;
  while (changed) {
    changed = false;
    for (const prefix of prefixes) {
      if (text.toLowerCase().startsWith(prefix.toLowerCase())) {
        text = text.slice(prefix.length).trim();
        changed = true;
      }
    }
  }
  return text
    .replace(/^["'«]+|["'»]+$/g, '')
    .replace(/\s+и снизить сомнения перед звонком, визитом или записью\.?$/i, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function _matchesItemFilter(item: PlanItem, filterKey: ItemFilterKey): boolean {
  const status = String(item.status || '').trim();
  const hasNews = Boolean(String(item.usernews_id || '').trim());
  const hasDraft = Boolean(String(item.draft_text || '').trim());
  if (status === 'skipped') return filterKey === 'all';
  if (filterKey === 'urgent') return !hasNews;
  if (filterKey === 'has_draft') return hasDraft && !hasNews;
  return true;
}

export function _matchesDateRange(rawDate: string, fromDate: string, toDate: string): boolean {
  const itemDate = _inputDateValue(rawDate);
  const from = _inputDateValue(fromDate);
  const to = _inputDateValue(toDate);
  if (!itemDate) return !from && !to;
  if (from && itemDate < from) return false;
  if (to && itemDate > to) return false;
  return true;
}

export function _signalFilterLabel(filterKey: SignalFilterKey, isRu: boolean): string {
  if (filterKey === 'seo') return 'SEO';
  if (filterKey === 'services') return isRu ? 'Услуги' : 'Services';
  if (filterKey === 'sales') return isRu ? 'Продажи' : 'Sales';
  if (filterKey === 'audit') return isRu ? 'Аудит' : 'Audit';
  if (filterKey === 'seasonal') return isRu ? 'Сезонность' : 'Seasonal';
  return isRu ? 'Все сигналы' : 'All signals';
}

export function _sourceKindLabel(sourceKind: string, isRu: boolean): string {
  const normalized = String(sourceKind || '').trim().toLowerCase();
  if (normalized === 'seo_keyword') return isRu ? 'SEO-сигнал' : 'SEO signal';
  if (normalized === 'service') return isRu ? 'Основание: услуга' : 'Reason: service';
  if (normalized === 'transaction') return isRu ? 'Основание: продажи' : 'Reason: sales';
  if (normalized === 'audit_signal') return isRu ? 'Основание: аудит' : 'Reason: audit';
  if (normalized === 'seasonal') return isRu ? 'Основание: сезон' : 'Reason: season';
  if (normalized === 'fallback') return isRu ? 'Базовый сигнал' : 'Baseline signal';
  return isRu ? 'Сигнал' : 'Signal';
}

export function _seoViewsLabel(item: Pick<PlanItem, 'source_kind' | 'seo_views'>, isRu: boolean): string {
  if (String(item.source_kind || '').trim().toLowerCase() !== 'seo_keyword') return '';
  const views = Number(item.seo_views || 0);
  if (!Number.isFinite(views) || views <= 0) return '';
  const formatted = new Intl.NumberFormat(isRu ? 'ru-RU' : 'en-US').format(Math.round(views));
  return isRu ? `${formatted} показов` : `${formatted} searches`;
}

export function _matchesSignalFilter(item: PlanItem, filterKey: SignalFilterKey): boolean {
  if (filterKey === 'all') return true;
  const normalizedContentType = String(item.content_type || '').trim().toLowerCase();
  if (filterKey === 'services') return normalizedContentType === 'service';
  return normalizedContentType === filterKey;
}

export function _matchesItemLocationFilter(item: PlanItem, filterKey: string): boolean {
  if (filterKey === 'all') return true;
  const itemKey = String(item.location_scope || item.business_id || '').trim();
  return itemKey === filterKey;
}

export function _readStoredSortMode(): 'priority' | 'date' {
  if (typeof window === 'undefined') return 'priority';
  try {
    const raw = window.localStorage.getItem(CONTENT_PLAN_PREFERENCES_KEY);
    if (!raw) return 'priority';
    const parsed = JSON.parse(raw);
    const sortMode = parsed && typeof parsed.sortMode === 'string' ? parsed.sortMode : '';
    return sortMode === 'date' ? 'date' : 'priority';
  } catch {
    return 'priority';
  }
}

export function _readStoredPreferences(businessId: string): Record<string, string> | null {
  if (!businessId || typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(`${CONTENT_PLAN_PREFERENCES_KEY}:${businessId}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
}

export function _writeStoredPreferences(businessId: string, value: Record<string, string>): void {
  if (!businessId || typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(`${CONTENT_PLAN_PREFERENCES_KEY}:${businessId}`, JSON.stringify(value));
    window.localStorage.setItem(CONTENT_PLAN_PREFERENCES_KEY, JSON.stringify({ sortMode: value.sortMode || 'priority' }));
  } catch {
    // Ignore storage write failures to keep the UI operational.
  }
}

export function _isValidItemFilterKey(value: string): value is ItemFilterKey {
  return value === 'all'
    || value === 'urgent'
    || value === 'has_draft';
}

export function _isValidContentLanguageKey(value: string): value is ContentLanguageKey {
  return CONTENT_LANGUAGE_OPTIONS.some((item) => item.value === value);
}

export function _normalizeContentLanguage(value: string): ContentLanguageKey {
  const normalized = String(value || '').trim().toLowerCase();
  return _isValidContentLanguageKey(normalized) ? normalized : 'ru';
}

export function _isValidSignalFilterKey(value: string): value is SignalFilterKey {
  return value === 'all'
    || value === 'seo'
    || value === 'services'
    || value === 'sales'
    || value === 'audit'
    || value === 'seasonal';
}

export function _isValidViewPresetKey(value: string): value is ViewPresetKey {
  return value === 'overview'
    || value === 'urgent'
    || value === 'ready'
    || value === 'published'
    || value === 'focus'
    || value === 'custom';
}

export function _inferViewPresetKey(value: {
  selectedItemFilter: ItemFilterKey;
  selectedSignalFilter: SignalFilterKey;
  selectedPlanTargetKey: string;
  selectedItemLocationKey: string;
  selectedWeekKey: string;
  dateFromFilter: string;
  dateToFilter: string;
  sortMode: 'priority' | 'date';
}): ViewPresetKey {
  if (
    value.selectedSignalFilter !== 'all'
    || value.selectedPlanTargetKey !== 'all'
    || value.selectedItemLocationKey !== 'all'
    || value.selectedWeekKey !== 'all'
    || value.dateFromFilter
    || value.dateToFilter
  ) {
    return 'custom';
  }
  if (value.selectedItemFilter === 'all') {
    return 'overview';
  }
  if (value.selectedItemFilter === 'urgent') {
    return 'urgent';
  }
  if (value.selectedItemFilter === 'has_draft') {
    return 'ready';
  }
  return 'custom';
}

export function _shiftIsoDate(input: string, daysDelta: number): string {
  const normalized = _inputDateValue(input);
  if (!normalized) {
    return new Date(Date.now() + daysDelta * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  }
  const parsed = new Date(`${normalized}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return normalized;
  }
  parsed.setUTCDate(parsed.getUTCDate() + daysDelta);
  return parsed.toISOString().slice(0, 10);
}

export function _autoScheduledDate(index: number): string {
  return _shiftIsoDate('', Math.max(Number(index || 0), 0) * 3);
}

export function _inputDateValue(input: unknown): string {
  const rawValue = String(input || '').trim();
  if (!rawValue) return '';
  const isoMatch = rawValue.match(/\d{4}-\d{2}-\d{2}/);
  if (isoMatch) return isoMatch[0];
  const parsed = new Date(rawValue);
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toISOString().slice(0, 10);
}

export function _removeRecordKeys(source: Record<string, string>, keys: string[]): Record<string, string> {
  const blocked = new Set(keys.map((item) => String(item || '').trim()).filter(Boolean));
  const next: Record<string, string> = {};
  for (const [key, value] of Object.entries(source)) {
    if (!blocked.has(key)) {
      next[key] = value;
    }
  }
  return next;
}

export function _formatPlanItemDate(input: unknown, isRu: boolean): string {
  const normalized = _inputDateValue(input);
  if (!normalized) return isRu ? 'Дата не назначена' : 'No date set';
  const parsed = new Date(`${normalized}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return normalized;
  return new Intl.DateTimeFormat(isRu ? 'ru-RU' : 'en-US', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(parsed);
}

export function _itemPriorityRank(item: Pick<PlanItem, 'draft_text' | 'usernews_id'>): number {
  const hasNews = Boolean(String(item.usernews_id || '').trim());
  const hasDraft = Boolean(String(item.draft_text || '').trim());
  if (!hasDraft) return 0;
  if (hasDraft && !hasNews) return 1;
  return 2;
}

export function _weekBucketKey(dateValue: string): string {
  const value = _inputDateValue(dateValue);
  if (!value) return '';
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return '';
  const day = date.getUTCDay() || 7;
  const monday = new Date(date);
  monday.setUTCDate(date.getUTCDate() - day + 1);
  return monday.toISOString().slice(0, 10);
}

export function _weekBucketLabel(weekKey: string, isRu: boolean): string {
  const value = String(weekKey || '').trim();
  if (!value) return isRu ? 'Неделя' : 'Week';
  const monday = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(monday.getTime())) return value;
  const sunday = new Date(monday);
  sunday.setUTCDate(monday.getUTCDate() + 6);
  const formatter = new Intl.DateTimeFormat(isRu ? 'ru-RU' : 'en-US', {
    day: 'numeric',
    month: 'short',
  });
  return `${formatter.format(monday)} - ${formatter.format(sunday)}`;
}
