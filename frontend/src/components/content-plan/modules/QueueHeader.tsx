import React from 'react';
import { Button } from '@/components/ui/button';

export const QueueHeader = ({ scope }) => {
  const {
    isRu, plans, currentPlan, setActiveZone, setShowRecentPlans
  } = scope;
  return (
    <>
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
              {isRu ? 'Готовая очередь по плану' : 'Plan queue'}
            </div>
            <div className="mt-1 text-lg font-semibold text-slate-950">
              {currentPlan?.title || (isRu ? 'План ещё не собран' : 'No plan yet')}
            </div>
            <div className="mt-2 inline-flex rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 ring-1 ring-blue-100">
              {isRu
                ? 'Каналы: карты + соцсети, публикация только после подтверждения'
                : 'Channels: maps + social, publish only after approval'}
            </div>
            <div className="mt-1 text-sm leading-6 text-slate-600">
              {currentPlan?.items?.length
                ? (isRu
                  ? 'Здесь рабочий список тем из выбранного плана: найти тему, открыть текст, подготовить публикации.'
                  : 'This is the working list from the selected plan: find a topic, open a draft, prepare publications.')
                : (isRu
                  ? 'Очередь появится после создания первого плана.'
                  : 'The queue appears after the first plan is created.')}
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            <div className="rounded-full bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-700">
              {plans.length > 0 ? `${isRu ? 'Планов' : 'Plans'} · ${plans.length}` : `${isRu ? 'Планов' : 'Plans'} · 0`}
            </div>
            <button
              type="button"
              onClick={() => {
                setShowRecentPlans(true);
                setActiveZone('plan');
              }}
              className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
            >
              {isRu ? 'Управлять планами' : 'Manage plans'}
            </button>
          </div>
        </div>

        {!currentPlan?.items?.length ? (
          <div className="mt-6 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 py-8 text-sm leading-6 text-slate-600">
            <div className="text-base font-semibold text-slate-950">
              {isRu ? 'Очередь пока пустая' : 'The queue is empty'}
            </div>
            <div className="mt-1">
              {isRu
                ? 'Сначала создайте план во вкладке «План». После этого здесь появятся темы, тексты и действия для публикаций.'
                : 'Create a plan in the Plan tab first. Then topics, drafts, and publishing actions will appear here.'}
            </div>
            <div className="mt-4">
              <Button type="button" onClick={() => setActiveZone('plan')}>
                {isRu ? 'Перейти к созданию плана' : 'Go to plan creation'}
              </Button>
            </div>
          </div>
        ) : null}
    </>
  );
};
