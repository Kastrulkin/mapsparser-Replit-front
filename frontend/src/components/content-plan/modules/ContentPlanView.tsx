import React from 'react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Globe, Lock, Sparkles, Trash2, Wand2 } from 'lucide-react';
import { _contentTypeLabel, _scopeChipLabel, _planTargetLabel, _learningCapabilityLabel, _networkQualityReasonLabel, _sourceKindLabel, _normalizeContentLanguage, _formatPlanItemDate } from './helpers';
import { PERIOD_OPTIONS, DENSITY_OPTIONS, CONTENT_MIX_OPTIONS, CONTENT_LANGUAGE_OPTIONS } from './constants';

export const ContentPlanView = ({ scope }) => {
  const {
    navigate, language, isRu, context, plans, currentPlan, loading, generating,
    metricsLoading, error, learningMetrics, selectedScopeKey, setSelectedScopeKey, selectedPeriod, setSelectedPeriod, selectedDensity,
    setSelectedDensity, contentMix, knowledgeFoundations, selectedKnowledgeType, setSelectedKnowledgeType,
    selectedKnowledgeAssertionId, setSelectedKnowledgeAssertionId, selectedPlanTargetKey, setSelectedPlanTargetKey,
    showPlanSetupDetails, setShowPlanSetupDetails, showLearningDetails, setShowLearningDetails,
    showContextDetails, setShowContextDetails, activeZone, setActiveZone, contentLanguage, setContentLanguage, showRecentPlans, setShowRecentPlans,
    allowedHorizons, scopeOptions, isNetworkContext, selectedScopeDescription, selectedScopeLabel, readiness, missingInputs, mapLinksCount,
    servicesCount, seoKeywordsCount, networkLocationsCount, networkHasSearchPlanFoundation, selectedScopeOption, availablePlanTargets, visiblePlans, planOperationalSummary,
    operatorQualityInsights, loadPlans, openPlan, deletePlan, loadContext, toggleMix, generatePlan
  } = scope;
  return (
    <>
      <div className={activeZone === 'plan' ? 'space-y-6' : 'hidden'}>
      {selectedScopeDescription ? (
        <div className="rounded-2xl border border-indigo-100 bg-indigo-50/70 px-5 py-4 text-sm text-indigo-950">
          <div className="font-semibold">
            {selectedScopeLabel || (isRu ? 'Выбранный сценарий' : 'Selected scope')}
          </div>
          <div className="mt-1 leading-6 text-indigo-900/90">
            {selectedScopeDescription}
          </div>
        </div>
      ) : null}

      {readiness && !readiness.is_grounded_for_search ? (
        <div
          className={[
            'rounded-2xl border px-5 py-4 text-sm',
            networkHasSearchPlanFoundation
              ? 'border-emerald-200 bg-emerald-50 text-emerald-950'
              : 'border-amber-200 bg-amber-50 text-amber-950',
          ].join(' ')}
        >
          <div className="font-semibold">
            {networkHasSearchPlanFoundation
              ? (isRu ? 'Сеть готова для поискового контент-плана' : 'The network is ready for a search-driven content plan')
              : (isRu ? 'План пока строится не на полном наборе данных' : 'The plan is not yet using the full data set')}
          </div>
          <div
            className={[
              'mt-1 leading-6',
              networkHasSearchPlanFoundation ? 'text-emerald-900/90' : 'text-amber-900/90',
            ].join(' ')}
          >
            {networkHasSearchPlanFoundation
              ? (isRu
                ? `Есть ${mapLinksCount} ссылок на карты и ${seoKeywordsCount} SEO-ключей. Можно строить план по спросу; меню, товары или услуги добавят темам коммерческую конкретику.`
                : `There are ${mapLinksCount} map listings and ${seoKeywordsCount} SEO keywords. You can build demand-driven posts now; menu items, products, or services will make topics more commercial.`)
              : (isRu
                ? 'Сейчас контент-план опирается в основном на аудит и сезонные поводы. Чтобы получить темы по реальному спросу, добавьте карту и услуги.'
                : 'Right now the plan relies mostly on audit signals and seasonal prompts. Add a map listing and services to ground it in real demand.')}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {missingInputs.includes('map_links') ? (
              <span className="rounded-full border border-amber-300 bg-white/80 px-3 py-1 text-xs font-medium text-amber-800">
                {isRu ? 'Нет ссылки на карту' : 'No map listing yet'}
              </span>
            ) : null}
            {missingInputs.includes('services') ? (
              <span
                className={[
                  'rounded-full border bg-white/80 px-3 py-1 text-xs font-medium',
                  networkHasSearchPlanFoundation
                    ? 'border-emerald-300 text-emerald-800'
                    : 'border-amber-300 text-amber-800',
                ].join(' ')}
              >
                {isNetworkContext
                  ? (isRu ? 'Нет меню, товаров или услуг' : 'No menu, products, or services yet')
                  : (isRu ? 'Нет услуг в карточке' : 'No services yet')}
              </span>
            ) : null}
            {missingInputs.includes('seo_keywords') ? (
              <span className="rounded-full border border-amber-300 bg-white/80 px-3 py-1 text-xs font-medium text-amber-800">
                {isRu ? 'Нет SEO-ключей по реальному спросу' : 'No grounded SEO keywords yet'}
              </span>
            ) : null}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {missingInputs.includes('map_links') ? (
              <Button
                type="button"
                variant="outline"
                className="border-amber-300 bg-white text-amber-900 hover:bg-amber-100"
                onClick={() => navigate('/dashboard/profile')}
              >
                {isRu ? 'Добавить ссылку на карту' : 'Add map link'}
              </Button>
            ) : null}
            {missingInputs.includes('services') ? (
              <Button
                type="button"
                variant="outline"
                className={[
                  'bg-white',
                  networkHasSearchPlanFoundation
                    ? 'border-emerald-300 text-emerald-900 hover:bg-emerald-100'
                    : 'border-amber-300 text-amber-900 hover:bg-amber-100',
                ].join(' ')}
                onClick={() => navigate('/dashboard/card?tab=services')}
              >
                {isNetworkContext
                  ? (isRu ? 'Добавить меню/услуги' : 'Add menu/services')
                  : (isRu ? 'Добавить услуги' : 'Add services')}
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}

      {currentPlan?.items?.length ? (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-sm text-emerald-950">
          <div className="font-semibold">
            {isRu ? 'План уже создан' : 'A plan already exists'}
          </div>
          <div className="mt-1 leading-6 text-emerald-900/90">
            {isRu
              ? `Сейчас активен план «${currentPlan.title || 'Контент-план'}»: ${planOperationalSummary.total} тем, ${planOperationalSummary.readyToPublish} текстов готово, ${planOperationalSummary.needsDraft} без текста. Работать с ним нужно во вкладке «Готовая очередь по плану».`
              : `The active plan is "${currentPlan.title || 'Content plan'}": ${planOperationalSummary.total} topics, ${planOperationalSummary.readyToPublish} drafts ready, ${planOperationalSummary.needsDraft} without text. Work with it in the Plan queue tab.`}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button type="button" size="sm" onClick={() => setActiveZone('queue')}>
              {isRu ? 'Перейти в готовую очередь' : 'Open plan queue'}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="bg-white/80"
              onClick={() => {
                setShowRecentPlans(true);
              }}
            >
              {isRu ? `Показать старые планы · ${plans.length}` : `Show old plans · ${plans.length}`}
            </Button>
          </div>
        </div>
      ) : null}

      {showRecentPlans && plans.length > 0 ? (
        <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
            {isRu
              ? 'Здесь можно открыть любой старый план, сравнить его с текущим по счётчикам, отредактировать темы или удалить лишнее. Детали открытого плана появятся во вкладке «Готовая очередь по плану».'
              : 'Here you can open any old plan, compare it by counters, edit topics, or delete what is not needed. The selected plan details appear in the Plan queue tab.'}
          </div>
          <div className="flex flex-wrap gap-2">
            {availablePlanTargets.map((target) => (
              <button
                key={target.key}
                type="button"
                onClick={() => setSelectedPlanTargetKey(target.key)}
                className={[
                  'rounded-full border px-3 py-1.5 text-sm transition-colors',
                  selectedPlanTargetKey === target.key
                    ? 'border-indigo-300 bg-indigo-50 text-indigo-800'
                    : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                ].join(' ')}
              >
                {target.label}
              </button>
            ))}
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            {visiblePlans.map((plan, index) => {
              const isActivePlan = currentPlan?.id === plan.id;
              const planTitle = plan.title || `${_scopeChipLabel(plan.scope_type, isRu)} · ${_planTargetLabel(plan, isRu)} · ${plan.period_days} ${isRu ? 'дней' : 'days'}`;
              return (
                <div
                  key={plan.id}
                  className={[
                    'rounded-2xl border bg-white px-4 py-4 shadow-sm',
                    isActivePlan ? 'border-indigo-300 ring-2 ring-indigo-100' : 'border-slate-200',
                  ].join(' ')}
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <button type="button" className="min-w-0 text-left" onClick={() => { void openPlan(plan.id); }}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
                          {index === 0 ? (isRu ? 'Последний' : 'Latest') : `${isRu ? 'План' : 'Plan'} ${plans.length - index}`}
                        </span>
                        {isActivePlan ? (
                          <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-800">
                            {isRu ? 'Открыт сейчас' : 'Open now'}
                          </span>
                        ) : null}
                      </div>
                      <div className="mt-2 text-sm font-semibold leading-5 text-slate-950">
                        {planTitle}
                      </div>
                      <div className="mt-1 text-xs leading-5 text-slate-500">
                        {_planTargetLabel(plan, isRu)} · {_formatPlanItemDate(plan.period_start || plan.created_at, isRu)}
                        {plan.period_end ? ` - ${_formatPlanItemDate(plan.period_end, isRu)}` : ''}
                      </div>
                    </button>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant={isActivePlan ? 'default' : 'outline'}
                        onClick={() => { void openPlan(plan.id); }}
                      >
                        {isRu ? 'Открыть' : 'Open'}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="border-red-200 text-red-700 hover:bg-red-50"
                        onClick={() => { void deletePlan(plan.id); }}
                      >
                        <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                        {isRu ? 'Удалить' : 'Delete'}
                      </Button>
                    </div>
                  </div>
                  <div className="mt-4 grid grid-cols-5 gap-2 text-center text-xs text-slate-500">
                    <div className="rounded-xl bg-slate-50 px-2 py-2">
                      <div className="text-sm font-semibold text-slate-950">{Number(plan.items_count || 0)}</div>
                      <div>{isRu ? 'тем' : 'topics'}</div>
                    </div>
                    <div className="rounded-xl bg-amber-50 px-2 py-2">
                      <div className="text-sm font-semibold text-amber-900">{Number(plan.needs_draft_count || 0)}</div>
                      <div>{isRu ? 'без текста' : 'no draft'}</div>
                    </div>
                    <div className="rounded-xl bg-emerald-50 px-2 py-2">
                      <div className="text-sm font-semibold text-emerald-900">{Number(plan.ready_count || 0)}</div>
                      <div>{isRu ? 'готово' : 'ready'}</div>
                    </div>
                    <div className="rounded-xl bg-blue-50 px-2 py-2">
                      <div className="text-sm font-semibold text-blue-900">{Number(plan.news_count || 0)}</div>
                      <div>{isRu ? 'новостей' : 'news'}</div>
                    </div>
                    <div className="rounded-xl bg-slate-50 px-2 py-2">
                      <div className="text-sm font-semibold text-slate-950">{Number(plan.skipped_count || 0)}</div>
                      <div>{isRu ? 'пропущено' : 'skipped'}</div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4">
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
              {isRu ? 'Что сделать сейчас' : 'What to do now'}
            </div>
            <div className="mt-1 text-lg font-semibold text-slate-950">
              {currentPlan?.items?.length
                ? (isRu ? 'У вас уже есть рабочий план' : 'You already have a working plan')
                : (isRu ? 'Соберите первый план публикаций' : 'Build the first publication plan')}
            </div>
            <div className="mt-1 text-sm leading-6 text-slate-600">
              {isRu
                ? (currentPlan?.items?.length
                  ? 'Новый план создавать не нужно, если вы просто хотите найти тему, дописать текст или создать публикацию. Для этого откройте очередь.'
                  : 'Создайте один план. Источники, плотность и тонкие настройки спрятаны, чтобы экран не начинался с перегруза.')
                : (currentPlan?.items?.length
                  ? 'You do not need a new plan if you only want to find a topic, edit a draft, or create a publication. Open the queue instead.'
                  : 'Create one plan. Sources, density, and detailed controls are tucked away to reduce first-screen noise.')}
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <div className="text-sm font-semibold text-slate-700">{isRu ? 'Куда строить план' : 'Scope'}</div>
              <Select value={selectedScopeKey} onValueChange={setSelectedScopeKey}>
                <SelectTrigger className="rounded-xl border-slate-200">
                  <SelectValue placeholder={isRu ? 'Выберите точку или сеть' : 'Select scope'} />
                </SelectTrigger>
                <SelectContent>
                  {scopeOptions.map((item) => {
                    const key = `${item.scope_type}:${item.scope_target_id}`;
                    const labelPrefix = item.is_parent
                      ? (isRu ? 'Материнская точка' : 'Parent network')
                      : item.scope_type === 'network_location'
                        ? (isRu ? 'Точка сети' : 'Network location')
                        : (isRu ? 'Текущий бизнес' : 'Current business');
                    return (
                      <SelectItem key={key} value={key}>
                        {labelPrefix}: {item.label}
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <div className="text-sm font-semibold text-slate-700">{isRu ? 'Горизонт планирования' : 'Planning horizon'}</div>
              <div className="grid grid-cols-3 gap-2">
                {PERIOD_OPTIONS.map((period) => {
                  const allowed = allowedHorizons.includes(period);
                  return (
                    <button
                      key={period}
                      type="button"
                      disabled={!allowed}
                      onClick={() => allowed && setSelectedPeriod(String(period))}
                      className={[
                        'rounded-xl border px-3 py-2 text-sm font-medium transition-colors',
                        selectedPeriod === String(period) && allowed
                          ? 'border-indigo-300 bg-indigo-50 text-indigo-800'
                          : 'border-slate-200 bg-white text-slate-700',
                        !allowed ? 'cursor-not-allowed opacity-60' : 'hover:bg-slate-50',
                      ].join(' ')}
                    >
                      <div className="flex items-center justify-center gap-1">
                        {!allowed ? <Lock className="h-3.5 w-3.5" /> : null}
                        {period}
                      </div>
                    </button>
                  );
                })}
              </div>
              {!allowedHorizons.includes(60) || !allowedHorizons.includes(90) ? (
                <div className="text-xs text-amber-700">
                  {isRu
                    ? 'Планы на 60 и 90 дней доступны на тарифах 25k и Elite.'
                    : '60 and 90 day plans are available on 25k and Elite tiers.'}
                </div>
              ) : null}
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                <Globe className="h-4 w-4 text-slate-500" />
                {isRu ? 'Язык публикаций' : 'Publication language'}
              </div>
              <Select value={contentLanguage} onValueChange={(value) => setContentLanguage(_normalizeContentLanguage(value))}>
                <SelectTrigger className="rounded-xl border-slate-200">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CONTENT_LANGUAGE_OPTIONS.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="text-xs text-slate-500">
                {isRu
                  ? 'Новые черновики из плана будут генерироваться на этом языке.'
                  : 'New drafts from the plan will use this language.'}
              </div>
            </div>

            {showPlanSetupDetails ? (
              <>
                <div className="space-y-2">
                  <div className="text-sm font-semibold text-slate-700">{isRu ? 'Плотность' : 'Density'}</div>
                  <Select value={selectedDensity} onValueChange={setSelectedDensity}>
                    <SelectTrigger className="rounded-xl border-slate-200">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {DENSITY_OPTIONS.map((item) => (
                        <SelectItem key={item.value} value={item.value}>
                          {isRu ? item.labelRu : item.labelEn}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <div className="text-sm font-semibold text-slate-700">{isRu ? 'Что использовать' : 'Use signals from'}</div>
                  <div className="flex flex-wrap gap-2">
                    {CONTENT_MIX_OPTIONS.map((item) => (
                      <button
                        key={item.key}
                        type="button"
                        onClick={() => toggleMix(item.key)}
                        className={[
                          'rounded-full border px-3 py-1.5 text-sm transition-colors',
                          contentMix[item.key]
                            ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
                            : 'border-slate-200 bg-white text-slate-600',
                        ].join(' ')}
                      >
                        {isRu ? item.labelRu : item.labelEn}
                      </button>
                    ))}
                  </div>
                </div>

                {knowledgeFoundations.length > 0 ? (
                  <div className="space-y-3 md:col-span-2">
                    <div>
                      <div className="text-sm font-semibold text-slate-700">
                        {isRu ? 'Основание из знаний рынка' : 'Market knowledge foundation'}
                      </div>
                      <div className="mt-1 text-xs leading-5 text-slate-500">
                        {isRu
                          ? 'Выберите проверенный тезис. LocalOS использует смысл и источник, но не копирует чужой пост.'
                          : 'Choose a sourced idea. LocalOS uses the meaning and evidence without copying the original post.'}
                      </div>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-3">
                      {knowledgeFoundations.map((foundation) => {
                        const available = foundation.items.length > 0;
                        const selected = selectedKnowledgeType === foundation.type;
                        return (
                          <button
                            key={foundation.type}
                            type="button"
                            disabled={!available}
                            onClick={() => {
                              setSelectedKnowledgeType(foundation.type);
                              setSelectedKnowledgeAssertionId(foundation.items[0]?.assertion_id || '');
                            }}
                            className={[
                              'min-h-20 rounded-lg px-3 py-3 text-left shadow-[0_0_0_1px_rgba(148,163,184,0.28)] transition-colors active:scale-[0.96]',
                              selected ? 'bg-sky-50 text-sky-950 shadow-[0_0_0_2px_rgba(14,165,233,0.38)]' : 'bg-white text-slate-700 hover:bg-slate-50',
                              !available ? 'cursor-not-allowed opacity-50' : '',
                            ].join(' ')}
                          >
                            <span className="block text-sm font-semibold">{foundation.label}</span>
                            <span className="mt-1 block text-xs leading-5 text-slate-500">
                              {available ? `${foundation.items.length} ${isRu ? 'варианта' : 'options'}` : (isRu ? 'Пока нет данных' : 'No data yet')}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                    {selectedKnowledgeType ? (
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                        <select
                          value={selectedKnowledgeAssertionId}
                          onChange={(event) => setSelectedKnowledgeAssertionId(event.target.value)}
                          className="h-11 min-w-0 flex-1 rounded-lg bg-white px-3 text-sm text-slate-800 shadow-[0_0_0_1px_rgba(148,163,184,0.35)] outline-none focus:shadow-[0_0_0_3px_rgba(14,165,233,0.16)]"
                        >
                          {(knowledgeFoundations.find((foundation) => foundation.type === selectedKnowledgeType)?.items || []).map((item) => (
                            <option key={item.assertion_id} value={item.assertion_id}>
                              {item.label} · {item.source_title || (isRu ? 'источник' : 'source')}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedKnowledgeType('');
                            setSelectedKnowledgeAssertionId('');
                          }}
                          className="min-h-10 rounded-md px-3 text-sm font-semibold text-slate-600 hover:bg-slate-100 active:scale-[0.96]"
                        >
                          {isRu ? 'Не использовать' : 'Do not use'}
                        </button>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </>
            ) : null}
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Button onClick={() => { void generatePlan(); }} disabled={generating || loading || !selectedScopeOption}>
              <Sparkles className="mr-2 h-4 w-4" />
              {generating
                ? (isRu ? 'Собираем план...' : 'Building plan...')
                : currentPlan?.items?.length
                  ? (isRu ? 'Создать новый план' : 'Create new plan')
                  : (isRu ? 'Собрать план' : 'Build plan')}
            </Button>
            <Button variant="outline" onClick={() => { void loadContext(); void loadPlans(); }} disabled={loading}>
              <Wand2 className="mr-2 h-4 w-4" />
              {isRu ? 'Обновить контекст' : 'Refresh context'}
            </Button>
            <button
              type="button"
              onClick={() => setShowPlanSetupDetails((prev) => !prev)}
              className="rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
            >
              {showPlanSetupDetails
                ? (isRu ? 'Скрыть настройки' : 'Hide settings')
                : (isRu ? 'Настроить источники' : 'Tune sources')}
            </button>
          </div>

          {error ? (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          ) : null}
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
                {isRu ? 'Качество данных' : 'Data quality'}
              </div>
              <div className="mt-1 text-lg font-semibold text-slate-950">
                {readiness?.is_grounded_for_search || networkHasSearchPlanFoundation
                  ? (isRu ? 'Данных достаточно для плана' : 'Enough data for planning')
                  : (isRu ? 'Плану не хватает источников' : 'The plan needs more inputs')}
              </div>
              {networkHasSearchPlanFoundation ? (
                <div className="mt-1 text-sm leading-6 text-slate-600">
                  {isRu
                    ? 'Для сети уже есть поисковый фундамент. Услуги и товары нужны как следующий слой конкретики.'
                    : 'The network already has a search foundation. Services and products are the next layer of specificity.'}
                </div>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => setShowContextDetails((prev) => !prev)}
              className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
            >
              {showContextDetails ? (isRu ? 'Скрыть' : 'Hide') : (isRu ? 'Подробнее' : 'Details')}
            </button>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2 text-sm text-slate-700">
            <div className="rounded-2xl bg-slate-50 px-3 py-3">
              <div className="text-lg font-semibold text-slate-950">{mapLinksCount}</div>
              <div className="text-xs text-slate-500">{isNetworkContext ? (isRu ? 'ссылок на карты' : 'map links') : (isRu ? 'карты' : 'maps')}</div>
            </div>
            <div className="rounded-2xl bg-slate-50 px-3 py-3">
              <div className="text-lg font-semibold text-slate-950">{servicesCount}</div>
              <div className="text-xs text-slate-500">{isNetworkContext ? (isRu ? 'меню/услуг' : 'menu/services') : (isRu ? 'услуг' : 'services')}</div>
            </div>
            <div className="rounded-2xl bg-slate-50 px-3 py-3">
              <div className="text-lg font-semibold text-slate-950">{seoKeywordsCount}</div>
              <div className="text-xs text-slate-500">{isRu ? 'SEO' : 'SEO'}</div>
            </div>
          </div>
          {showContextDetails ? (
          <div className="mt-4 space-y-3 text-sm text-slate-700">
            {isNetworkContext ? (
              <div>
                <div className="font-semibold text-slate-900">{isRu ? 'Режим сети' : 'Network mode'}</div>
                <div>
                  {context?.scope?.network?.has_parent_scope
                    ? `${isRu ? 'Точек в сети' : 'Locations in network'}: ${networkLocationsCount}`
                    : (isRu ? 'План строится по текущему бизнесу.' : 'Planning uses the current business.')}
                </div>
              </div>
            ) : null}
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'Ссылки на карты' : 'Map listings'}</div>
              <div>{mapLinksCount}</div>
            </div>
            <div>
              <div className="font-semibold text-slate-900">{isNetworkContext ? (isRu ? 'Меню, товары или услуги' : 'Menu, products, or services') : (isRu ? 'Услуги' : 'Services')}</div>
              <div>{servicesCount}</div>
            </div>
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'SEO-ключи' : 'SEO keywords'}</div>
              <div>{seoKeywordsCount}</div>
            </div>
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'Продажи' : 'Sales signals'}</div>
              <div>{context?.sales_signals?.length || 0}</div>
            </div>
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'Сигналы аудита' : 'Audit signals'}</div>
              <div>{context?.audit_signals?.length || 0}</div>
            </div>
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'Последние новости' : 'Recent news'}</div>
              <div>{context?.recent_news?.length || 0}</div>
            </div>
          </div>
          ) : null}
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
              {isRu ? 'Качество плана' : 'Plan quality'}
            </div>
            <div className="mt-1 text-lg font-semibold text-slate-950">
              {isRu ? 'Что система уже поняла по работе с темами' : 'What the system learned from topic work'}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowLearningDetails((prev) => !prev)}
            className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
          >
            {metricsLoading
              ? (isRu ? 'Обновляем...' : 'Refreshing...')
              : showLearningDetails
                ? (isRu ? 'Скрыть метрики' : 'Hide metrics')
                : `${isRu ? 'Показать метрики' : 'Show metrics'} · ${learningMetrics?.window_days || 30} ${isRu ? 'дней' : 'days'}`}
          </button>
        </div>
        {operatorQualityInsights.length > 0 ? (
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {operatorQualityInsights.map((item) => (
              <div
                key={item.key}
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700"
              >
                {isRu ? item.textRu : item.textEn}
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-600">
            {isRu
              ? 'Пока мало истории, чтобы делать выводы. После публикаций и правок здесь появятся подсказки по качеству тем.'
              : 'There is not enough history yet. After edits and publications, quality guidance will appear here.'}
          </div>
        )}
        {showLearningDetails ? (
          <>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Сгенерировано' : 'Generated'}</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{learningMetrics?.summary?.generated_total || 0}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Принято' : 'Accepted'}</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{learningMetrics?.summary?.accepted_total || 0}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Правили перед публикацией' : 'Edited before accept'}</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{learningMetrics?.summary?.accepted_edited_total || 0}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Пропущено' : 'Skipped'}</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{learningMetrics?.summary?.skipped_total || 0}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Правки до принятия' : 'Edited before accept'}</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{Number(learningMetrics?.summary?.edited_before_accept_pct || 0).toFixed(0)}%</div>
          </div>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Небольшие правки' : 'Minor edits'}</div>
            <div className="mt-2 text-xl font-semibold text-slate-950">{learningMetrics?.summary?.minor_edit_total || 0}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Смысловые переписывания' : 'Major rewrites'}</div>
            <div className="mt-2 text-xl font-semibold text-slate-950">{learningMetrics?.summary?.major_rewrite_total || 0}</div>
          </div>
        </div>
        {learningMetrics?.quality_insights && learningMetrics.quality_insights.length > 0 ? (
          <div className="mt-4 space-y-2">
            {learningMetrics.quality_insights.map((item) => (
              <div
                key={`${item.kind}:${item.text_ru || item.text_en}`}
                className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700"
              >
                {isRu ? item.text_ru : item.text_en}
              </div>
            ))}
          </div>
        ) : null}
        {learningMetrics?.items && learningMetrics.items.length > 0 ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {learningMetrics.items.map((item) => (
              <div
                key={item.capability}
                className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700"
              >
                {_learningCapabilityLabel(item.capability, isRu)} · {isRu ? 'принято' : 'accepted'} {item.accepted_total} · {isRu ? 'сгенерировано' : 'generated'} {item.generated_total}
              </div>
            ))}
          </div>
        ) : null}
        {(learningMetrics?.source_kind_breakdown && learningMetrics.source_kind_breakdown.length > 0)
          || (learningMetrics?.content_type_breakdown && learningMetrics.content_type_breakdown.length > 0)
          || (learningMetrics?.location_breakdown && learningMetrics.location_breakdown.length > 0) ? (
          <div className="mt-4 grid gap-4 xl:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                {isRu ? 'Чаще правят по сигналу' : 'Most edited by signal'}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {(learningMetrics?.source_kind_breakdown || []).slice(0, 5).map((item) => (
                  <div
                    key={item.key}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700"
                  >
                    {_sourceKindLabel(item.key, isRu)} · {Number(item.edited_before_accept_pct || 0).toFixed(0)}%
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                {isRu ? 'Чаще правят по типу темы' : 'Most edited by content type'}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {(learningMetrics?.content_type_breakdown || []).slice(0, 5).map((item) => (
                  <div
                    key={item.key}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700"
                  >
                    {_contentTypeLabel(item.key, isRu)} · {Number(item.edited_before_accept_pct || 0).toFixed(0)}%
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                {isRu ? 'Чаще правят по точке' : 'Most edited by location'}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {(learningMetrics?.location_breakdown || []).slice(0, 5).map((item) => (
                  <div
                    key={item.key}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700"
                  >
                    {String(item.label || item.key || (isRu ? 'Точка' : 'Location'))} · {Number(item.edited_before_accept_pct || 0).toFixed(0)}%
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : null}
        {learningMetrics?.network_quality && learningMetrics.network_quality.length > 0 ? (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-4">
            <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                  {isRu ? 'Качество по точкам' : 'Quality by location'}
                </div>
                <div className="mt-1 text-sm text-slate-600">
                  {isRu
                    ? 'Показывает, где контент-план чаще требует вмешательства: правки, пропуски, черновики без публикации.'
                    : 'Shows where the content plan needs more operator attention: edits, skips, drafts without publishing.'}
                </div>
              </div>
            </div>
            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              {learningMetrics.network_quality.slice(0, 3).map((item) => (
                <div key={item.key} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-slate-950">
                        {String(item.label || item.key || (isRu ? 'Точка' : 'Location'))}
                      </div>
                      <div className="mt-1 text-xs text-slate-500">
                        {isRu ? 'Индекс риска' : 'Risk score'} · {Number(item.risk_score || 0).toFixed(0)}
                      </div>
                    </div>
                    <span className={[
                      'rounded-full px-2.5 py-1 text-xs font-medium',
                      Number(item.risk_score || 0) >= 60
                        ? 'bg-red-100 text-red-700'
                        : Number(item.risk_score || 0) >= 30
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-emerald-100 text-emerald-800',
                    ].join(' ')}
                    >
                      {Number(item.risk_score || 0) >= 60
                        ? (isRu ? 'Высокий' : 'High')
                        : Number(item.risk_score || 0) >= 30
                          ? (isRu ? 'Средний' : 'Medium')
                          : (isRu ? 'Норма' : 'Stable')}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <span className="rounded-full bg-white px-2.5 py-1 text-slate-700">
                      {isRu ? 'Опубликовано' : 'Published'} · {item.accepted_total}
                    </span>
                    <span className="rounded-full bg-white px-2.5 py-1 text-slate-700">
                      {isRu ? 'Правки' : 'Edits'} · {Number(item.edited_before_accept_pct || 0).toFixed(0)}%
                    </span>
                    <span className="rounded-full bg-white px-2.5 py-1 text-slate-700">
                      {isRu ? 'Пропуски' : 'Skipped'} · {item.skipped_total}
                    </span>
                    <span className="rounded-full bg-white px-2.5 py-1 text-slate-700">
                      {isRu ? 'Переписывания' : 'Rewrites'} · {item.major_rewrite_total}
                    </span>
                  </div>
                  {item.reasons && item.reasons.length > 0 ? (
                    <div className="mt-3 text-xs leading-5 text-slate-500">
                      {item.reasons.slice(0, 2).map((reason) => _networkQualityReasonLabel(reason, isRu)).join(' · ')}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        ) : null}
          </>
        ) : null}
      </div>

      </div>
    </>
  );
};
