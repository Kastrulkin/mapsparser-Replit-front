import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Check, Clock3, ExternalLink, MapPinned } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useLanguage, type Language } from '@/i18n/LanguageContext.logic';
import { newAuth } from '@/lib/auth_new';
import { cn } from '@/lib/utils';
import {
  managedActionCopy,
  managedCardDateLocale,
  managedCardGrowthCopyForLanguage,
  managedDecision,
  managedDisclaimer,
  managedEvidence,
  managedFactLabel,
  managedGateLabel,
  managedGoalLabel,
  managedBenchmarkLabel,
  managedProviderLabel,
  managedStateLabel,
} from './managedCardGrowthCopy';

type FactState = 'observed' | 'missing' | 'unknown' | 'not_applicable' | 'blocked';

type CardFact = {
  value?: unknown;
  state: FactState;
  source?: string;
  observed_at?: string | null;
  confidence?: number;
  evidence?: string;
  evidence_code?: string | null;
};

type ProviderState = {
  provider: string;
  provider_label?: string;
  source_state: 'observed' | 'unknown' | 'blocked';
  observed_at?: string | null;
  facts: Record<string, CardFact>;
  benchmark?: {
    status?: string;
    sample_size?: number;
    period_days?: number;
    scope?: string;
      metrics?: Record<string, { median?: number | null; p75?: number | null }>;
      disclaimer_code?: string | null;
      disclaimer?: string;
  };
};

type LocationState = {
  business_id: string;
  business_name: string;
  goal?: string;
  goal_status?: 'recommended' | 'confirmed';
  providers: ProviderState[];
  critical?: boolean;
};

export type ManagedCardGrowth = {
  policy_version?: string;
  goal?: {
    value?: string | null;
    label?: string;
    status?: 'recommended' | 'confirmed';
    options?: Array<{ value: string; label: string }>;
  };
  card_state?: {
    scope_kind?: string;
    status?: 'healthy' | 'needs_attention';
    locations?: LocationState[];
    critical_locations?: string[];
  };
  baseline?: {
    status?: string;
    period?: { start?: string; end?: string; days?: number };
    providers?: Record<string, {
      views?: number;
      clicks?: number;
      actions?: number;
      details?: Record<string, number>;
    }>;
    disclaimer?: string;
    disclaimer_code?: string | null;
  };
  measurement?: {
    status?: string;
    checkpoints?: Array<{ days: number; due_at: string; status: string }>;
    decision?: string | null;
    decision_reason?: string | null;
    decision_reason_code?: string | null;
    result?: {
      checkpoint_days?: number;
      deltas?: Record<string, { goal_metric?: string; goal_before?: number; goal_after?: number; goal_delta?: number }>;
      disclaimer?: string;
      disclaimer_code?: string | null;
    } | null;
  };
  next_actions?: Array<{
    id?: string;
    title: string;
    reason?: string;
    business_name?: string;
    gate_label?: string;
    provider?: string | null;
    provider_label?: string | null;
    fact?: string;
    gate?: number;
    copy_code?: string | null;
    copy_params?: { goal?: string; benchmark_median?: number };
  }>;
};

const STATE_CLASS: Record<FactState, string> = {
  observed: 'bg-emerald-50 text-emerald-800',
  missing: 'bg-amber-50 text-amber-900',
  unknown: 'bg-slate-100 text-slate-600',
  not_applicable: 'bg-slate-100 text-slate-500',
  blocked: 'bg-rose-50 text-rose-800',
};

const stateClass = (state: string) => Object.entries(STATE_CLASS).find(([key]) => key === state)?.[1] || STATE_CLASS.unknown;

const formatDate = (value: string | null | undefined, language: Language) => {
  const copy = managedCardGrowthCopyForLanguage(language);
  if (!value) return copy.dateUnknown;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return copy.dateUnknown;
  return new Intl.DateTimeFormat(managedCardDateLocale[language], { day: 'numeric', month: 'long', year: 'numeric' }).format(date);
};

const formatNumber = (value: number | undefined, language: Language) => new Intl.NumberFormat(managedCardDateLocale[language]).format(value || 0);

export function ManagedCardGrowthPanel({
  businessId,
  growth,
  onUpdated,
}: {
  businessId: string;
  growth: ManagedCardGrowth;
  onUpdated: () => void;
}) {
  const { language } = useLanguage();
  const copy = managedCardGrowthCopyForLanguage(language);
  const options = growth.goal?.options || [];
  const firstOption = options[0]?.value;
  const [goal, setGoal] = useState(growth.goal?.value || firstOption || 'inquiries');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const locations = growth.card_state?.locations || [];
  const singleLocation = locations.length === 1;

  useEffect(() => {
    setGoal(growth.goal?.value || firstOption || 'inquiries');
  }, [growth.goal?.value, firstOption]);

  const nextCheckpoint = useMemo(
    () => growth.measurement?.checkpoints?.find((checkpoint) => checkpoint.status === 'waiting' || checkpoint.status === 'due'),
    [growth.measurement?.checkpoints],
  );

  const confirmGoal = async () => {
    setSaving(true);
    setError('');
    try {
      await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/growth-goal`, {
        method: 'PUT',
        body: JSON.stringify({ goal }),
      });
      onUpdated();
    } catch (requestError) {
      setError(language === 'ru' && requestError instanceof Error ? requestError.message : copy.saveError);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm" aria-labelledby="managed-growth-title">
      <div className="grid gap-5 border-b border-slate-200 p-5 lg:grid-cols-[minmax(0,1fr)_minmax(300px,0.55fr)] lg:p-6">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-orange-700">
            <MapPinned className="h-4 w-4" />
            {copy.eyebrow}
          </div>
          <h2 id="managed-growth-title" className="mt-2 text-xl font-semibold text-slate-950">{copy.title}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            {copy.description}
          </p>
        </div>

        <div className="border-t border-slate-200 pt-5 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
          <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500" htmlFor="card-growth-goal">{copy.goal}</label>
          <Select value={goal} onValueChange={setGoal} disabled={!singleLocation || saving}>
            <SelectTrigger id="card-growth-goal" className="mt-2 min-h-11 w-full">
              <SelectValue placeholder={copy.chooseGoal} />
            </SelectTrigger>
            <SelectContent>
              {options.map((option) => <SelectItem key={option.value} value={option.value}>{managedGoalLabel(language, option.value, option.label)}</SelectItem>)}
            </SelectContent>
          </Select>
          {singleLocation && growth.goal?.status !== 'confirmed' ? (
            <Button type="button" className="mt-3 min-h-11 w-full bg-orange-600 text-white hover:bg-orange-700" onClick={confirmGoal} disabled={saving}>
              <Check className="mr-2 h-4 w-4" />
              {saving ? copy.saving : copy.confirmGoal}
            </Button>
          ) : (
            <p className="mt-3 text-sm text-slate-600">
              {singleLocation ? copy.goalConfirmed : copy.networkGoal}
            </p>
          )}
          {error ? <p className="mt-2 text-sm text-rose-700" role="alert">{error}</p> : null}
        </div>
      </div>

      {growth.measurement?.status === 'waiting_for_measurement' && nextCheckpoint ? (
        <div className="flex items-start gap-3 border-b border-slate-200 bg-sky-50 px-5 py-4 text-sm text-sky-950 lg:px-6">
          <Clock3 className="mt-0.5 h-5 w-5 shrink-0" />
          <div>
            <div className="font-semibold">{copy.waitingUntil(formatDate(nextCheckpoint.due_at, language))}</div>
            <p className="mt-1 leading-6">{copy.waitingDescription}</p>
          </div>
        </div>
      ) : null}

      {growth.baseline?.status === 'observed' && growth.baseline.providers ? (
        <div className="border-b border-slate-200 px-5 py-4 lg:px-6">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="font-semibold text-slate-950">{copy.baseline}</h3>
            <span className="text-xs text-slate-500">
              {formatDate(growth.baseline.period?.start, language)} — {formatDate(growth.baseline.period?.end, language)}
            </span>
          </div>
          <div className="mt-3 divide-y divide-slate-200 border-y border-slate-200">
            {Object.entries(growth.baseline.providers).map(([provider, metrics]) => (
              <div key={provider} className="grid gap-2 py-3 text-sm sm:grid-cols-[minmax(100px,1fr)_repeat(3,minmax(90px,auto))] sm:items-center">
                <span className="font-medium text-slate-900">{managedProviderLabel(provider)}</span>
                <span className="text-slate-600">{copy.views}: <strong className="text-slate-900">{formatNumber(metrics.views, language)}</strong></span>
                <span className="text-slate-600">{copy.clicks}: <strong className="text-slate-900">{formatNumber(metrics.clicks, language)}</strong></span>
                <span className="text-slate-600">{copy.actions}: <strong className="text-slate-900">{formatNumber(metrics.actions, language)}</strong></span>
              </div>
            ))}
          </div>
          <p className="mt-2 text-xs leading-5 text-slate-500">{managedDisclaimer(language, growth.baseline.disclaimer_code, growth.baseline.disclaimer)}</p>
        </div>
      ) : null}

      {growth.measurement?.result?.deltas ? (
        <div className="border-b border-slate-200 px-5 py-4 lg:px-6">
          <h3 className="font-semibold text-slate-950">{copy.result}</h3>
          {growth.measurement.decision_reason ? <p className="mt-1 text-sm leading-6 text-slate-600">{managedDecision(language, growth.measurement.decision_reason_code || growth.measurement.decision || undefined, growth.measurement.decision_reason)}</p> : null}
          <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
            {Object.entries(growth.measurement.result.deltas).map(([provider, delta]) => (
              <span key={provider} className="text-slate-600">
                {managedProviderLabel(provider)}: <strong className={cn('tabular-nums', (delta.goal_delta || 0) > 0 ? 'text-emerald-700' : (delta.goal_delta || 0) < 0 ? 'text-rose-700' : 'text-slate-900')}>
                  {(delta.goal_delta || 0) > 0 ? '+' : ''}{formatNumber(delta.goal_delta, language)}
                </strong>
              </span>
            ))}
          </div>
          <p className="mt-2 text-xs leading-5 text-slate-500">{managedDisclaimer(language, growth.measurement.result.disclaimer_code || undefined, growth.measurement.result.disclaimer)}</p>
        </div>
      ) : null}

      {locations.length ? locations.map((location) => (
        <div key={location.business_id} className="border-b border-slate-200 p-5 last:border-b-0 lg:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold text-slate-950">{location.business_name}</h3>
              <p className="mt-1 text-sm text-slate-600">{location.critical ? copy.critical : copy.noCritical}</p>
            </div>
            {location.critical ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-900">
                <AlertTriangle className="h-3.5 w-3.5" /> {copy.needsAttention}
              </span>
            ) : null}
          </div>

          {location.providers.length ? (
            <div className="mt-4 divide-y divide-slate-200 border-y border-slate-200">
              {location.providers.map((provider) => (
                <details key={provider.provider} className="group py-4">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500">
                    <div>
                      <span className="font-semibold text-slate-950">{managedProviderLabel(provider.provider, provider.provider_label)}</span>
                      <span className="ml-2 text-sm text-slate-500">{copy.snapshot(formatDate(provider.observed_at, language))}</span>
                    </div>
                    <span className={cn('rounded-full px-3 py-1 text-xs font-semibold', provider.source_state === 'observed' ? 'bg-emerald-50 text-emerald-800' : provider.source_state === 'blocked' ? 'bg-rose-50 text-rose-800' : 'bg-slate-100 text-slate-600')}>
                      {provider.source_state === 'observed' ? copy.sourceObserved : provider.source_state === 'blocked' ? copy.sourceBlocked : copy.sourceUnknown}
                    </span>
                  </summary>
                  <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                    {Object.entries(provider.facts).map(([key, fact]) => (
                      <div key={key} className="flex min-h-12 items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2">
                        <span className="text-sm text-slate-700">{managedFactLabel(language, key)}</span>
                        <span className={cn('shrink-0 rounded-full px-2 py-1 text-xs font-semibold', stateClass(fact.state))}>{managedStateLabel(language, fact.state)}</span>
                      </div>
                    ))}
                  </div>
                  {provider.benchmark?.sample_size ? (
                    <div className="mt-3 text-xs leading-5 text-slate-500">
                      <p>
                        {copy.benchmark(provider.benchmark.sample_size, provider.benchmark.period_days || 90)}
                        {provider.benchmark.status === 'small_sample' ? copy.smallSample : ''}
                      </p>
                      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
                        {Object.entries(provider.benchmark.metrics || {}).filter(([, metric]) => metric.median != null || metric.p75 != null).map(([metricName, metric]) => (
                          <span key={metricName}>{managedBenchmarkLabel(language, metricName)}: {copy.median} {metric.median == null ? '—' : formatNumber(metric.median, language)}, {copy.upperQuartile} {metric.p75 == null ? '—' : formatNumber(metric.p75, language)}</span>
                        ))}
                      </div>
                      <p className="mt-1">{managedDisclaimer(language, provider.benchmark.disclaimer_code, provider.benchmark.disclaimer)}</p>
                    </div>
                  ) : null}
                </details>
              ))}
            </div>
          ) : (
            <div className="mt-4 rounded-lg bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950">
              {copy.noProviders}
            </div>
          )}
        </div>
      )) : (
        <div className="p-5 text-sm text-slate-600 lg:p-6">{copy.noCardState}</div>
      )}

      {growth.next_actions?.length ? (
        <div className="border-t border-slate-200 px-5 py-5 lg:px-6">
          <h3 className="font-semibold text-slate-950">{copy.nextSteps}</h3>
          <p className="mt-1 text-sm text-slate-600">{copy.nextStepsDescription}</p>
          <ol className="mt-4 divide-y divide-slate-200 border-y border-slate-200">
            {growth.next_actions.slice(0, 3).map((action, index) => (
              <li key={action.id || action.title} className="flex gap-3 py-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-950 text-xs font-semibold text-white">{index + 1}</span>
                <div className="min-w-0">
                  <div className="font-medium text-slate-900">{managedActionCopy(language, action.copy_code || undefined, managedProviderLabel(action.provider, action.provider_label), action.copy_params?.goal, action.copy_params?.benchmark_median, { title: action.title }).title}</div>
                  <div className="mt-0.5 text-sm text-slate-500">{[action.business_name, managedGateLabel(language, action.gate, action.gate_label)].filter(Boolean).join(' · ')}</div>
                </div>
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 px-5 py-3 text-xs text-slate-500 lg:px-6">
        <span>{copy.policyVersion}: {growth.policy_version || copy.policyUnknown}</span>
        <a className="inline-flex min-h-10 items-center gap-1.5 font-semibold text-slate-700 underline-offset-4 hover:underline" href="/dashboard/progress?section=maps&audit=open">
          {copy.openEvidence} <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </div>
    </section>
  );
}
