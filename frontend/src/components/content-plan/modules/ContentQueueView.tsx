import { QueueHeader } from './QueueHeader';
import { QueueSummary } from './QueueSummary';
import { SocialFilterHeader } from './SocialFilterHeader';
import { SocialNextStepPanel } from './SocialNextStepPanel';
import { SocialStatusPanels } from './SocialStatusPanels';
import { SocialRecommendationPanel } from './SocialRecommendationPanel';
import { SelectedQueueActions } from './SelectedQueueActions';
import { QueueItems } from './QueueItems';
import { QueueEmpty } from './QueueEmpty';

export const ContentQueueView = ({ scope }) => {
  const { activeZone, currentPlan, loading, isRu } = scope;
  return (
    <div className={activeZone === 'queue' ? 'rounded-2xl border border-slate-200 bg-white p-5 shadow-sm' : 'hidden'}>
      <QueueHeader scope={scope} />
      {currentPlan?.items && currentPlan.items.length > 0 ? (
        <div className="mt-6 space-y-4">
          <QueueSummary scope={scope} />
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
            <SocialFilterHeader scope={scope} />
            <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3">
              <SocialNextStepPanel scope={scope} />
              <SocialStatusPanels scope={scope} />
              <SocialRecommendationPanel scope={scope} />
            </div>
            <SelectedQueueActions scope={scope} />
          </div>
          <QueueItems scope={scope} />
          <QueueEmpty scope={scope} />
        </div>
      ) : (
        <div className="mt-6 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 py-10 text-center text-sm text-slate-600">
          {loading
            ? (isRu ? 'Загружаем контекст и планы...' : 'Loading context and plans...')
            : (isRu ? 'Соберите первый контент-план, чтобы здесь появился календарь публикаций.' : 'Build your first content plan to see planned posts here.')}
        </div>
      )}
    </div>
  );
};
