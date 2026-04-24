import { Star, Trash2, Trophy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { DashboardSection } from '@/components/dashboard/DashboardPrimitives';
import ReviewReplyAssistant from '@/components/ReviewReplyAssistant';
import NewsGenerator from '@/components/NewsGenerator';
import SEOKeywordsTab from '@/components/SEOKeywordsTab';

type ManualCompetitor = {
  id: string;
  name?: string;
  url: string;
  audit_status?: string;
  report_path?: string;
};

type Competitor = {
  name?: string;
  category?: string;
  rating?: string | number;
  reviews?: string | number;
  url?: string;
};

type CompetitorsTabProps = {
  manualCompetitorUrl: string;
  onManualCompetitorUrlChange: (value: string) => void;
  manualCompetitorName: string;
  onManualCompetitorNameChange: (value: string) => void;
  addingManualCompetitor: boolean;
  onAddManualCompetitor: () => void;
  manualCompetitors: ManualCompetitor[];
  competitors: Competitor[];
  requestingAuditId: string | null;
  deletingManualCompetitorId: string | null;
  onRequestAudit: (competitorId: string) => void;
  onDeleteManualCompetitor: (competitorId: string) => void;
};

export const CompetitorsTab = ({
  manualCompetitorUrl,
  onManualCompetitorUrlChange,
  manualCompetitorName,
  onManualCompetitorNameChange,
  addingManualCompetitor,
  onAddManualCompetitor,
  manualCompetitors,
  competitors,
  requestingAuditId,
  deletingManualCompetitorId,
  onRequestAudit,
  onDeleteManualCompetitor,
}: CompetitorsTabProps) => (
  <DashboardSection
    title="Конкуренты"
    description="Добавляйте важные карточки рядом, чтобы видеть их действия и запускать точечный аудит."
  >
    <div className="mb-6 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
      <p className="mb-3 text-sm text-blue-900">Добавьте конкурента, чтобы отслеживать его действия.</p>
      <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
        <input
          type="text"
          value={manualCompetitorUrl}
          onChange={(event) => onManualCompetitorUrlChange(event.target.value)}
          placeholder="Ссылка на конкурента (https://...)"
          className="w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm"
        />
        <input
          type="text"
          value={manualCompetitorName}
          onChange={(event) => onManualCompetitorNameChange(event.target.value)}
          placeholder="Название (необязательно)"
          className="w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm"
        />
        <Button onClick={onAddManualCompetitor} disabled={addingManualCompetitor} className="bg-blue-600 text-white hover:bg-blue-700">
          {addingManualCompetitor ? 'Добавляем...' : 'Добавить конкурента'}
        </Button>
      </div>
    </div>

    {manualCompetitors.length > 0 ? (
      <div className="mb-8">
        <h3 className="mb-3 text-lg font-semibold text-gray-900">Вручную добавленные конкуренты</h3>
        <div className="grid gap-4 md:grid-cols-2">
          {manualCompetitors.map((competitor) => (
            <div key={competitor.id} className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="mb-1 font-semibold text-gray-900">{competitor.name || 'Конкурент'}</div>
              <a href={competitor.url} target="_blank" rel="noreferrer" className="break-all text-sm text-blue-600 hover:underline">
                {competitor.url}
              </a>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="rounded bg-gray-100 px-2 py-1 text-xs text-gray-700">
                  Аудит: {competitor.audit_status === 'requested' ? 'запрошен' : competitor.audit_status === 'ready' ? 'готов' : 'не запрошен'}
                </span>
                {competitor.report_path ? (
                  <a href={competitor.report_path} target="_blank" rel="noreferrer" className="rounded bg-emerald-100 px-2 py-1 text-xs text-emerald-700 hover:bg-emerald-200">
                    Открыть отчёт
                  </a>
                ) : null}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button onClick={() => onRequestAudit(competitor.id)} disabled={requestingAuditId === competitor.id} variant="outline" className="border-amber-300 text-amber-700 hover:bg-amber-50">
                  {requestingAuditId === competitor.id ? 'Отправляем...' : 'Аудит'}
                </Button>
                <Button onClick={() => onDeleteManualCompetitor(competitor.id)} disabled={deletingManualCompetitorId === competitor.id} variant="outline" className="inline-flex items-center gap-2 border-red-300 text-red-700 hover:bg-red-50">
                  <Trash2 className="h-4 w-4" />
                  {deletingManualCompetitorId === competitor.id ? 'Удаляем...' : 'Удалить'}
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>
    ) : null}

    {competitors.length > 0 ? (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {competitors.map((competitor, index) => (
          <div key={`${competitor.name || 'competitor'}-${index}`} className="rounded-xl border border-gray-100 bg-white/50 p-4 transition-all hover:shadow-md">
            <div className="mb-1 text-lg font-semibold text-gray-900">{competitor.name || 'Без названия'}</div>
            <div className="mb-3 text-sm text-gray-500">{competitor.category}</div>
            <div className="flex items-center gap-4 text-sm">
              {competitor.rating ? (
                <div className="flex items-center gap-1 rounded-md bg-amber-50 px-2 py-1 text-amber-600">
                  <Star className="h-3 w-3 fill-amber-600" />
                  <span className="font-medium">{competitor.rating}</span>
                </div>
              ) : null}
              {competitor.reviews ? <div className="text-gray-500">{competitor.reviews}</div> : null}
            </div>
            {competitor.url ? (
              <a href={competitor.url} target="_blank" rel="noreferrer" className="mt-4 block w-full rounded-lg bg-blue-50 py-2 text-center text-sm font-medium text-blue-600 transition-colors hover:bg-blue-100">
                Посмотреть на карте
              </a>
            ) : null}
          </div>
        ))}
      </div>
    ) : (
      <div className="py-12 text-center text-gray-500">
        <Trophy className="mx-auto mb-3 h-12 w-12 text-gray-300" />
        <p>Конкуренты не найдены. Попробуйте обновить данные парсинга.</p>
      </div>
    )}
  </DashboardSection>
);

export const AutomationLockedNotice = ({ message }: { message: string }) => (
  <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
    {message}
  </div>
);

type ReviewsTabProps = {
  automationAllowed: boolean;
  automationLockedMessage: string;
  businessName?: string;
  selectedSource: string;
  aggregateScope: 'business' | 'network';
  onOpenLocation?: (businessId: string) => void;
  initialFilter?: 'all' | 'negative' | 'needs_reply';
};

export const ReviewsTab = ({
  automationAllowed,
  automationLockedMessage,
  businessName,
  selectedSource,
  aggregateScope,
  onOpenLocation,
  initialFilter,
}: ReviewsTabProps) => (
  automationAllowed ? (
    <ReviewReplyAssistant
      businessName={businessName}
      selectedSource={selectedSource}
      aggregateScope={aggregateScope}
      onOpenLocation={onOpenLocation}
      initialFilter={initialFilter}
    />
  ) : <AutomationLockedNotice message={automationLockedMessage} />
);

type NewsTabProps = {
  automationAllowed: boolean;
  automationLockedMessage: string;
  services: Array<{ id: string; name: string }>;
  businessId?: string;
  externalPosts: Array<{ source?: string }>;
  selectedSource: string;
};

export const NewsTab = ({
  automationAllowed,
  automationLockedMessage,
  services,
  businessId,
  externalPosts,
  selectedSource,
}: NewsTabProps) => (
  automationAllowed ? (
    <NewsGenerator
      services={services}
      businessId={businessId}
      externalPosts={externalPosts.filter((post) => selectedSource === 'all' || (post.source && post.source.toLowerCase().includes(selectedSource)))}
    />
  ) : <AutomationLockedNotice message={automationLockedMessage} />
);

export const KeywordsTab = ({ businessId }: { businessId?: string | null }) => (
  <SEOKeywordsTab businessId={businessId} />
);
