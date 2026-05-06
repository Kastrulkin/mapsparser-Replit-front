import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Check, Clock, FileText, History, RefreshCcw, RotateCcw, Search, ShieldCheck, X } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent } from './ui/card';
import { newAuth } from '../lib/auth_new';
import { useToast } from '../hooks/use-toast';

type PatternTab = 'pending' | 'active' | 'revision' | 'impact';

type PatternProposal = {
  id: string;
  industry_key: string;
  pattern_type: string;
  proposed_pattern: string;
  confidence: number;
  risk_level: string;
  status: string;
  decision_comment?: string;
  created_at?: string;
  updated_at?: string;
};

type PatternHealth = {
  version_id: string;
  industry_key?: string;
  pattern_type?: string;
  applied_count?: number;
  result_count?: number;
  total_items?: number;
  good?: number;
  needs_review?: number;
  bad_rate?: number;
  recommendation?: string;
  business_effect_score?: number;
  business_effect_status?: string;
  seo_score_delta?: number;
  keyword_found_delta?: number;
  manual_edits?: number;
  accepted?: number;
};

type PatternVersion = {
  version_id: string;
  industry_key: string;
  pattern_type: string;
  pattern_text: string;
  version?: string;
  status: string;
  activated_by?: string;
  activated_at?: string;
  disabled_at?: string;
};

type PatternDetail = {
  version?: PatternVersion;
  health?: PatternHealth;
  recent_reasons?: string[];
  decisions?: Array<{ decision?: string; decided_by?: string; decision_comment?: string; created_at?: string }>;
  version_candidates?: PatternVersion[];
  bad_examples?: Array<{ sample_text?: string; result_status?: string; source?: string; reasons?: string[] }>;
  good_examples?: Array<{ sample_text?: string; result_status?: string; source?: string; reasons?: string[] }>;
};

type RollbackPreview = {
  current?: PatternVersion;
  target?: PatternVersion;
  current_health?: PatternHealth;
  target_health?: PatternHealth;
  text_diff?: {
    current_length?: number;
    target_length?: number;
    length_delta?: number;
    similarity?: number;
    added_terms?: string[];
    removed_terms?: string[];
  };
  warnings?: string[];
  can_confirm?: boolean;
  confirmation_token?: string;
};

type PatternSafety = {
  superadmin_only?: boolean;
  rollback_requires_preview?: boolean;
  destructive_actions_require_confirmation?: boolean;
  active_patterns?: number;
  pending_proposals?: number;
  needs_revision?: number;
  last_proposal_at?: string;
  last_admin_action_at?: string;
  destructive_actions?: number;
};

type PatternAdminEvent = {
  id: string;
  actor_id?: string;
  action: string;
  target_type?: string;
  target_id?: string;
  created_at?: string;
  metadata?: Record<string, unknown>;
};

type ConfirmAction = {
  title: string;
  description: string;
  confirmLabel: string;
  variant?: 'default' | 'destructive';
  onConfirm: () => void;
};

export type IndustryPatternsApiClient = {
  makeRequest: (endpoint: string, options?: RequestInit) => Promise<any>;
};

export type IndustryPatternsManagementProps = {
  apiClient?: IndustryPatternsApiClient;
};

const INDUSTRY_FILTERS = [
  { value: 'all', label: 'Все' },
  { value: 'beauty', label: 'Beauty' },
  { value: 'food', label: 'Food' },
  { value: 'medical', label: 'Medical' },
  { value: 'auto_service', label: 'Auto' },
];

const TYPE_FILTERS = [
  { value: 'all', label: 'Все типы' },
  { value: 'service', label: 'Услуги' },
  { value: 'news', label: 'Новости' },
  { value: 'review_reply', label: 'Отзывы' },
];

const ROLLBACK_REASONS = [
  'Ухудшает качество',
  'Много fallback',
  'Не та индустрия',
  'Слабые результаты',
  'Временный откат',
];

const PATTERN_TABS: Array<{ id: PatternTab; label: string }> = [
  { id: 'pending', label: 'Pending' },
  { id: 'active', label: 'Active' },
  { id: 'revision', label: 'На доработке' },
  { id: 'impact', label: 'Impact' },
];

const shortText = (value?: string, limit = 180) => {
  const text = String(value || '').trim();
  if (text.length <= limit) {
    return text || '-';
  }
  return `${text.slice(0, limit - 3).trim()}...`;
};

const typeLabel = (value?: string) => {
  if (value === 'service') return 'услуги';
  if (value === 'news') return 'новости';
  if (value === 'review_reply') return 'ответы';
  return value || '-';
};

const healthLine = (health?: PatternHealth) => {
  const item: PatternHealth = health || { version_id: '' };
  return `применений ${item.applied_count || 0}; OK ${item.good || 0}; needs_review ${item.needs_review || 0}; bad rate ${item.bad_rate || 0}; effect ${item.business_effect_score || 0}`;
};

const getErrorMessage = (error: unknown, fallback: string) => {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallback;
};

export const IndustryPatternsManagement: React.FC<IndustryPatternsManagementProps> = ({ apiClient = newAuth }) => {
  const [activeTab, setActiveTab] = useState<PatternTab>('pending');
  const [industry, setIndustry] = useState('all');
  const [patternType, setPatternType] = useState('all');
  const [query, setQuery] = useState('');
  const [summary, setSummary] = useState<any>(null);
  const [proposals, setProposals] = useState<PatternProposal[]>([]);
  const [versions, setVersions] = useState<PatternVersion[]>([]);
  const [health, setHealth] = useState<PatternHealth[]>([]);
  const [adminEvents, setAdminEvents] = useState<PatternAdminEvent[]>([]);
  const [detail, setDetail] = useState<PatternDetail | null>(null);
  const [rollbackPreview, setRollbackPreview] = useState<RollbackPreview | null>(null);
  const [rollbackReason, setRollbackReason] = useState(ROLLBACK_REASONS[0]);
  const [confirmAction, setConfirmAction] = useState<ConfirmAction | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const { toast } = useToast();

  const loadSummary = useCallback(async () => {
    const data = await apiClient.makeRequest('/admin/industry-patterns/summary');
    setSummary(data);
  }, [apiClient]);

  const loadAdminEvents = useCallback(async () => {
    const data = await apiClient.makeRequest('/admin/industry-patterns/admin-events?limit=8');
    setAdminEvents(data.events || []);
  }, [apiClient]);

  const loadProposals = useCallback(async () => {
    const status = activeTab === 'revision' ? 'needs_revision' : 'pending_review';
    const params = new URLSearchParams({ status, industry_key: industry, pattern_type: patternType, limit: '50' });
    const data = await apiClient.makeRequest(`/admin/industry-patterns/proposals?${params.toString()}`);
    setProposals(data.proposals || []);
  }, [activeTab, apiClient, industry, patternType]);

  const loadVersions = useCallback(async () => {
    const params = new URLSearchParams({ status: 'active', industry_key: industry, pattern_type: patternType, limit: '50' });
    const data = await apiClient.makeRequest(`/admin/industry-patterns/versions?${params.toString()}`);
    setVersions(data.versions || []);
    setHealth(data.health || []);
  }, [apiClient, industry, patternType]);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      await loadSummary();
      await loadAdminEvents();
      if (activeTab === 'active' || activeTab === 'impact') {
        await loadVersions();
      } else {
        await loadProposals();
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: getErrorMessage(error, 'Не удалось загрузить паттерны'),
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [activeTab, loadAdminEvents, loadProposals, loadSummary, loadVersions, toast]);

  useEffect(() => {
    reload();
  }, [reload]);

  const filteredProposals = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return proposals;
    return proposals.filter((item) => [
      item.industry_key,
      item.pattern_type,
      item.proposed_pattern,
      item.decision_comment || '',
    ].join(' ').toLowerCase().includes(normalized));
  }, [proposals, query]);

  const healthByVersion = useMemo(() => {
    const result: Record<string, PatternHealth> = {};
    health.forEach((item) => {
      if (item.version_id) {
        result[item.version_id] = item;
      }
    });
    return result;
  }, [health]);

  const filteredVersions = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    const source = activeTab === 'impact'
      ? versions.filter((item) => {
          const itemHealth = healthByVersion[item.version_id] || { version_id: item.version_id };
          return itemHealth.recommendation === 'disable_candidate' || itemHealth.recommendation === 'revise_candidate';
        })
      : versions;
    if (!normalized) return source;
    return source.filter((item) => [
      item.industry_key,
      item.pattern_type,
      item.pattern_text,
      item.version || '',
    ].join(' ').toLowerCase().includes(normalized));
  }, [activeTab, healthByVersion, query, versions]);

  const runAction = async (action: () => Promise<void>, success: string) => {
    setActionLoading(true);
    try {
      await action();
      toast({ title: 'Готово', description: success });
      await reload();
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: getErrorMessage(error, 'Действие не выполнено'),
        variant: 'destructive',
      });
    } finally {
      setActionLoading(false);
    }
  };

  const openDetail = async (versionId: string) => {
    setActionLoading(true);
    setRollbackPreview(null);
    try {
      const data = await apiClient.makeRequest(`/admin/industry-patterns/versions/${versionId}`);
      setDetail(data.detail || null);
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: getErrorMessage(error, 'Не удалось открыть карточку паттерна'),
        variant: 'destructive',
      });
    } finally {
      setActionLoading(false);
    }
  };

  const openRollbackPreview = async (currentVersionId: string, targetVersionId: string) => {
    setActionLoading(true);
    try {
      const data = await apiClient.makeRequest(
        `/admin/industry-patterns/versions/${currentVersionId}/rollback-preview/${targetVersionId}`,
      );
      setRollbackPreview(data.preview || null);
      setRollbackReason(ROLLBACK_REASONS[0]);
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: getErrorMessage(error, 'Не удалось подготовить rollback preview'),
        variant: 'destructive',
      });
    } finally {
      setActionLoading(false);
    }
  };

  const decideProposal = (proposalId: string, decision: string, comment: string) => runAction(
    () => apiClient.makeRequest(`/admin/industry-patterns/proposals/${proposalId}/decision`, {
      method: 'POST',
      body: JSON.stringify({ decision, comment }),
    }),
    'Решение сохранено',
  );

  const regenerateProposal = (proposalId: string) => runAction(
    () => apiClient.makeRequest(`/admin/industry-patterns/proposals/${proposalId}/regenerate`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),
    'Новая версия proposal создана',
  );

  const createVersionProposal = (versionId: string) => runAction(
    () => apiClient.makeRequest(`/admin/industry-patterns/versions/${versionId}/new-proposal`, {
      method: 'POST',
      body: JSON.stringify({ reason: 'Новая версия из web admin' }),
    }),
    'Pending proposal новой версии создан',
  );

  const markRevision = (versionId: string) => runAction(
    () => apiClient.makeRequest(`/admin/industry-patterns/versions/${versionId}/revision`, {
      method: 'POST',
      body: JSON.stringify({ reason: 'На доработку из web admin' }),
    }),
    'Паттерн отправлен на доработку',
  );

  const disableVersion = (versionId: string) => {
    setConfirmAction({
      title: 'Отключить active-паттерн',
      description: 'Паттерн перестанет попадать в оптимизатор без деплоя. Действие будет записано в audit timeline.',
      confirmLabel: 'Отключить',
      variant: 'destructive',
      onConfirm: () => {
        setConfirmAction(null);
        runAction(
          () => apiClient.makeRequest(`/admin/industry-patterns/versions/${versionId}/disable`, {
            method: 'POST',
            body: JSON.stringify({ reason: 'Отключено из web admin', confirm: true }),
          }),
          'Паттерн отключён',
        );
      },
    });
  };

  const confirmRollback = () => {
    const currentId = rollbackPreview?.current?.version_id || '';
    const targetId = rollbackPreview?.target?.version_id || '';
    if (!currentId || !targetId) return;
    runAction(
      () => apiClient.makeRequest(`/admin/industry-patterns/versions/${currentId}/rollback`, {
        method: 'POST',
        body: JSON.stringify({
          target_version_id: targetId,
          reason: rollbackReason,
          confirmation_token: rollbackPreview?.confirmation_token || '',
        }),
      }),
      'Rollback выполнен',
    ).then(() => {
      setRollbackPreview(null);
      setDetail(null);
    });
  };

  const runRecalibration = () => {
    setConfirmAction({
      title: 'Запустить калибровку',
      description: 'Система проанализирует данные и создаст только pending-предложения. Active-паттерны не меняются автоматически.',
      confirmLabel: 'Запустить',
      onConfirm: () => {
        setConfirmAction(null);
        runAction(
          () => apiClient.makeRequest('/admin/industry-patterns/recalibrate', {
            method: 'POST',
            body: JSON.stringify({ confirm: true }),
          }),
          'Калибровка запущена, pending-предложения обновлены',
        );
      },
    });
  };

  const renderProposal = (proposal: PatternProposal) => (
    <div key={proposal.id} className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">
            <span className="rounded-md bg-slate-100 px-2 py-1 text-slate-700">{proposal.industry_key}</span>
            <span className="rounded-md bg-blue-50 px-2 py-1 text-blue-700">{typeLabel(proposal.pattern_type)}</span>
            <span className="rounded-md bg-amber-50 px-2 py-1 text-amber-700">risk {proposal.risk_level || '-'}</span>
            <span className="rounded-md bg-emerald-50 px-2 py-1 text-emerald-700">confidence {proposal.confidence}</span>
          </div>
          <p className="whitespace-pre-wrap break-words text-sm leading-6 text-slate-900">{proposal.proposed_pattern}</p>
          {proposal.decision_comment ? (
            <p className="text-xs text-slate-500">Комментарий: {proposal.decision_comment}</p>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {proposal.status === 'pending_review' ? (
            <>
              <Button size="sm" className="rounded-md" onClick={() => decideProposal(proposal.id, 'accept', 'web admin')}>
                <Check className="mr-1.5 h-4 w-4" />
                Принять
              </Button>
              <Button size="sm" variant="outline" className="rounded-md" onClick={() => decideProposal(proposal.id, 'revise', 'На доработку из web admin')}>
                <History className="mr-1.5 h-4 w-4" />
                Доработать
              </Button>
              <Button size="sm" variant="destructive" className="rounded-md" onClick={() => decideProposal(proposal.id, 'reject', 'Отклонено из web admin')}>
                <X className="mr-1.5 h-4 w-4" />
                Отклонить
              </Button>
            </>
          ) : (
            <Button size="sm" variant="outline" className="rounded-md" onClick={() => regenerateProposal(proposal.id)}>
              <RefreshCcw className="mr-1.5 h-4 w-4" />
              Новая версия
            </Button>
          )}
        </div>
      </div>
    </div>
  );

  const renderVersion = (version: PatternVersion) => {
    const itemHealth = healthByVersion[version.version_id] || { version_id: version.version_id };
    return (
      <div key={version.version_id} className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">
              <span className="rounded-md bg-slate-100 px-2 py-1 text-slate-700">{version.industry_key}</span>
              <span className="rounded-md bg-blue-50 px-2 py-1 text-blue-700">{typeLabel(version.pattern_type)}</span>
              <span className="rounded-md bg-emerald-50 px-2 py-1 text-emerald-700">{version.status}</span>
              {itemHealth.recommendation ? (
                <span className="rounded-md bg-amber-50 px-2 py-1 text-amber-700">{itemHealth.recommendation}</span>
              ) : null}
            </div>
            <p className="whitespace-pre-wrap break-words text-sm leading-6 text-slate-900">{shortText(version.pattern_text, 320)}</p>
            <p className="text-xs text-slate-500">{healthLine(itemHealth)}</p>
            <p className="text-xs text-slate-500">
              business effect: {itemHealth.business_effect_status || 'no_data'} · SEO Δ {itemHealth.seo_score_delta || 0} · ключи Δ {itemHealth.keyword_found_delta || 0} · ручные правки {itemHealth.manual_edits || 0}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button size="sm" variant="outline" className="rounded-md" onClick={() => openDetail(version.version_id)}>
              <FileText className="mr-1.5 h-4 w-4" />
              Детали
            </Button>
            <Button size="sm" variant="outline" className="rounded-md" onClick={() => createVersionProposal(version.version_id)}>
              <Clock className="mr-1.5 h-4 w-4" />
              Новая версия
            </Button>
            <Button size="sm" variant="outline" className="rounded-md" onClick={() => markRevision(version.version_id)}>
              <History className="mr-1.5 h-4 w-4" />
              Доработать
            </Button>
            <Button size="sm" variant="destructive" className="rounded-md" onClick={() => disableVersion(version.version_id)}>
              <X className="mr-1.5 h-4 w-4" />
              Отключить
            </Button>
          </div>
        </div>
      </div>
    );
  };

  const currentCounts = summary?.proposal_counts || {};
  const versionCounts = summary?.version_counts || {};
  const impactTotals = summary?.impact?.totals || {};
  const effectTotals = {
    score: impactTotals.business_effect_score || 0,
    positive: impactTotals.business_effect_positive || 0,
    neutral: impactTotals.business_effect_neutral || 0,
    negative: impactTotals.business_effect_negative || 0,
    seoDelta: impactTotals.seo_score_delta || 0,
    keywordDelta: impactTotals.keyword_found_delta || 0,
    manualEdits: impactTotals.manual_edits || 0,
    accepted: impactTotals.accepted || 0,
  };
  const safety: PatternSafety = summary?.safety || {};

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Pending" value={currentCounts.pending_review || 0} />
        <Metric label="На доработке" value={currentCounts.needs_revision || 0} />
        <Metric label="Active" value={versionCounts.active || 0} />
        <Metric label="Needs review" value={impactTotals.needs_review || 0} />
      </div>

      <SafetyPanel safety={safety} events={adminEvents} />

      <BusinessEffectPanel totals={effectTotals} report={summary?.impact || {}} />

      <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-wrap gap-2">
          {PATTERN_TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`rounded-md px-3 py-2 text-sm font-semibold transition ${
                activeTab === tab.id ? 'bg-slate-950 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="flex flex-col gap-2 md:flex-row md:items-center">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="h-10 w-full rounded-md border border-slate-200 bg-white pl-9 pr-3 text-sm outline-none focus:border-slate-400 md:w-72"
              placeholder="Поиск по тексту"
            />
          </div>
          <select value={industry} onChange={(event) => setIndustry(event.target.value)} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm">
            {INDUSTRY_FILTERS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
          <select value={patternType} onChange={(event) => setPatternType(event.target.value)} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm">
            {TYPE_FILTERS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
          <Button variant="outline" className="h-10 rounded-md" onClick={reload} disabled={loading}>
            <RefreshCcw className="mr-1.5 h-4 w-4" />
            Обновить
          </Button>
          <Button className="h-10 rounded-md" onClick={runRecalibration} disabled={actionLoading}>
            <ShieldCheck className="mr-1.5 h-4 w-4" />
            Калибровка
          </Button>
        </div>
      </div>

      {activeTab === 'pending' || activeTab === 'revision' ? (
        <div className="space-y-3">
          {filteredProposals.length > 0 ? filteredProposals.map(renderProposal) : <Empty text="Предложений нет" />}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredVersions.length > 0 ? filteredVersions.map(renderVersion) : <Empty text="Active-паттернов нет" />}
        </div>
      )}

      {detail ? (
        <DetailPanel
          detail={detail}
          onClose={() => {
            setDetail(null);
            setRollbackPreview(null);
          }}
          onRollback={openRollbackPreview}
        />
      ) : null}

      {rollbackPreview ? (
        <RollbackPanel
          preview={rollbackPreview}
          reason={rollbackReason}
          setReason={setRollbackReason}
          onConfirm={confirmRollback}
          onCancel={() => setRollbackPreview(null)}
          disabled={actionLoading}
        />
      ) : null}

      {confirmAction ? (
        <ConfirmActionPanel
          action={confirmAction}
          disabled={actionLoading}
          onCancel={() => setConfirmAction(null)}
        />
      ) : null}
    </div>
  );
};

const Metric: React.FC<{ label: string; value: number | string }> = ({ label, value }) => (
  <div className="rounded-lg border border-slate-200 bg-white p-4">
    <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
    <div className="mt-2 text-2xl font-semibold text-slate-950">{value}</div>
  </div>
);

const Empty: React.FC<{ text: string }> = ({ text }) => (
  <Card className="border-dashed">
    <CardContent className="py-10 text-center text-sm text-slate-500">{text}</CardContent>
  </Card>
);

const BusinessEffectPanel: React.FC<{
  totals: {
    score: number | string;
    positive: number | string;
    neutral: number | string;
    negative: number | string;
    seoDelta: number | string;
    keywordDelta: number | string;
    manualEdits: number | string;
    accepted: number | string;
  };
  report: any;
}> = ({ totals, report }) => {
  const effective = report.effective || [];
  const questionable = report.questionable || [];
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-950">Business effect</div>
          <div className="text-xs text-slate-500">Эффект паттернов: SEO, ключи, принятие и ручные правки</div>
        </div>
        <div className="rounded-md bg-slate-950 px-3 py-2 text-sm font-semibold text-white">score {totals.score}</div>
      </div>
      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Positive / Neutral / Negative" value={`${totals.positive}/${totals.neutral}/${totals.negative}`} />
        <Metric label="SEO delta" value={totals.seoDelta} />
        <Metric label="Keyword delta" value={totals.keywordDelta} />
        <Metric label="Accepted / Manual edits" value={`${totals.accepted}/${totals.manualEdits}`} />
      </div>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <EffectList title="Эффективные" items={effective} empty="Пока нет уверенно эффективных паттернов" />
        <EffectList title="Сомнительные" items={questionable} empty="Сомнительных паттернов нет" />
      </div>
    </div>
  );
};

const EffectList: React.FC<{ title: string; items: PatternHealth[]; empty: string }> = ({ title, items, empty }) => (
  <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
    <div className="mb-2 text-sm font-semibold text-slate-950">{title}</div>
    <div className="space-y-2">
      {items.length > 0 ? items.slice(0, 3).map((item) => (
        <div key={item.version_id} className="rounded-md bg-white p-2 text-xs text-slate-600">
          <div className="font-semibold text-slate-900">{item.industry_key || '-'} / {typeLabel(item.pattern_type)}</div>
          <div>effect {item.business_effect_score || 0}; status {item.business_effect_status || 'no_data'}; applied {item.applied_count || 0}</div>
        </div>
      )) : (
        <div className="rounded-md border border-dashed border-slate-200 bg-white p-3 text-sm text-slate-500">{empty}</div>
      )}
    </div>
  </div>
);

const SafetyPanel: React.FC<{ safety: PatternSafety; events: PatternAdminEvent[] }> = ({ safety, events }) => (
  <div className="grid gap-3 lg:grid-cols-[1fr_1.2fr]">
    <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-emerald-900">
        <ShieldCheck className="h-4 w-4" />
        Safety status
      </div>
      <div className="grid gap-2 text-sm text-emerald-900 sm:grid-cols-2">
        <SafetyFlag label="Superadmin only" ok={Boolean(safety.superadmin_only)} />
        <SafetyFlag label="Rollback через preview" ok={Boolean(safety.rollback_requires_preview)} />
        <SafetyFlag label="Опасные действия с confirm" ok={Boolean(safety.destructive_actions_require_confirmation)} />
        <SafetyFlag label="Active" value={safety.active_patterns || 0} />
        <SafetyFlag label="Pending" value={safety.pending_proposals || 0} />
        <SafetyFlag label="На доработке" value={safety.needs_revision || 0} />
      </div>
      <div className="mt-3 text-xs text-emerald-800">
        Последний proposal: {safety.last_proposal_at || '-'} · последнее действие: {safety.last_admin_action_at || '-'}
      </div>
    </div>
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 text-sm font-semibold text-slate-950">Последние действия админки</div>
      <div className="space-y-2">
        {events.length > 0 ? events.map((event) => (
          <div key={event.id} className="flex flex-col gap-1 rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-600 sm:flex-row sm:items-center sm:justify-between">
            <span className="font-semibold text-slate-900">{event.action}</span>
            <span>{event.target_type || '-'} / {shortText(event.target_id, 28)}</span>
            <span>{event.created_at || '-'}</span>
          </div>
        )) : (
          <div className="rounded-md border border-dashed border-slate-200 p-3 text-sm text-slate-500">Действий пока нет</div>
        )}
      </div>
    </div>
  </div>
);

const SafetyFlag: React.FC<{ label: string; ok?: boolean; value?: number | string }> = ({ label, ok, value }) => (
  <div className="flex items-center justify-between gap-2 rounded-md bg-white/70 px-3 py-2">
    <span>{label}</span>
    <span className="font-semibold">{value !== undefined ? value : (ok ? 'OK' : 'нет')}</span>
  </div>
);

const DetailPanel: React.FC<{
  detail: PatternDetail;
  onClose: () => void;
  onRollback: (currentVersionId: string, targetVersionId: string) => void;
}> = ({ detail, onClose, onRollback }) => {
  const version = detail.version;
  const currentVersionId = version?.version_id || '';
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-h-[90vh] w-full max-w-5xl overflow-y-auto rounded-lg bg-white shadow-2xl">
        <div className="sticky top-0 flex items-start justify-between border-b border-slate-200 bg-white p-5">
          <div>
            <h3 className="text-lg font-semibold text-slate-950">Карточка паттерна</h3>
            <p className="text-sm text-slate-500">{version?.industry_key || '-'} / {typeLabel(version?.pattern_type)}</p>
          </div>
          <Button variant="ghost" size="sm" className="rounded-md" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="space-y-5 p-5">
          <div className="rounded-lg bg-slate-50 p-4">
            <p className="whitespace-pre-wrap break-words text-sm leading-6 text-slate-900">{version?.pattern_text || '-'}</p>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <Metric label="Impact" value={detail.health?.applied_count || 0} />
            <Metric label="OK" value={detail.health?.good || 0} />
            <Metric label="Bad rate" value={detail.health?.bad_rate || 0} />
          </div>
          <Section title="Последние причины" text={(detail.recent_reasons || []).join(', ') || '-'} />
          <Section title="Плохие примеры" text={(detail.bad_examples || []).map((item) => shortText(item.sample_text, 220)).join('\n\n') || '-'} />
          <Section title="Хорошие примеры" text={(detail.good_examples || []).map((item) => shortText(item.sample_text, 220)).join('\n\n') || '-'} />
          <div>
            <h4 className="mb-2 text-sm font-semibold text-slate-950">Rollback-кандидаты</h4>
            <div className="space-y-2">
              {(detail.version_candidates || []).length > 0 ? (detail.version_candidates || []).map((candidate, index) => (
                <div key={candidate.version_id || index} className="flex flex-col gap-3 rounded-lg border border-slate-200 p-3 md:flex-row md:items-center md:justify-between">
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-slate-500">{candidate.status} / {candidate.version || '-'}</div>
                    <div className="break-words text-sm text-slate-900">{shortText(candidate.pattern_text, 220)}</div>
                  </div>
                  <Button size="sm" variant="outline" className="shrink-0 rounded-md" onClick={() => onRollback(currentVersionId, candidate.version_id)}>
                    <RotateCcw className="mr-1.5 h-4 w-4" />
                    Сравнить
                  </Button>
                </div>
              )) : <div className="rounded-lg border border-dashed border-slate-200 p-4 text-sm text-slate-500">Других версий пока нет</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const Section: React.FC<{ title: string; text: string }> = ({ title, text }) => (
  <div>
    <h4 className="mb-2 text-sm font-semibold text-slate-950">{title}</h4>
    <div className="whitespace-pre-wrap rounded-lg border border-slate-200 bg-white p-3 text-sm leading-6 text-slate-700">{text}</div>
  </div>
);

const RollbackPanel: React.FC<{
  preview: RollbackPreview;
  reason: string;
  setReason: (value: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
  disabled: boolean;
}> = ({ preview, reason, setReason, onConfirm, onCancel, disabled }) => {
  const diff = preview.text_diff || {};
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4">
      <div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-lg bg-white shadow-2xl">
        <div className="border-b border-slate-200 p-5">
          <h3 className="text-lg font-semibold text-slate-950">Подтверждение rollback</h3>
          <p className="text-sm text-slate-500">Проверьте разницу и выберите причину перед применением.</p>
        </div>
        <div className="space-y-4 p-5">
          <div className="grid gap-3 md:grid-cols-2">
            <Section title="Сейчас active" text={preview.current?.pattern_text || '-'} />
            <Section title="Будет активирована" text={preview.target?.pattern_text || '-'} />
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <Section title="Impact текущей" text={healthLine(preview.current_health)} />
            <Section title="Impact rollback" text={healthLine(preview.target_health)} />
          </div>
          <Section
            title="Разница"
            text={[
              `длина: ${diff.current_length || 0} -> ${diff.target_length || 0} (${diff.length_delta || 0})`,
              `сходство: ${diff.similarity || 0}`,
              `добавится: ${(diff.added_terms || []).join(', ') || '-'}`,
              `уйдёт: ${(diff.removed_terms || []).join(', ') || '-'}`,
            ].join('\n')}
          />
          {(preview.warnings || []).length > 0 ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              <div className="mb-1 flex items-center gap-2 font-semibold">
                <AlertTriangle className="h-4 w-4" />
                Предупреждения
              </div>
              {(preview.warnings || []).join(', ')}
            </div>
          ) : null}
          <div>
            <label className="mb-2 block text-sm font-semibold text-slate-950">Причина</label>
            <select value={reason} onChange={(event) => setReason(event.target.value)} className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm md:w-80">
              {ROLLBACK_REASONS.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-2 border-t border-slate-100 pt-4 sm:flex-row sm:justify-end">
            <Button variant="outline" className="rounded-md" onClick={onCancel}>Отмена</Button>
            <Button className="rounded-md" onClick={onConfirm} disabled={disabled || !preview.can_confirm}>
              <RotateCcw className="mr-1.5 h-4 w-4" />
              Подтвердить rollback
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

const ConfirmActionPanel: React.FC<{
  action: ConfirmAction;
  disabled: boolean;
  onCancel: () => void;
}> = ({ action, disabled, onCancel }) => (
  <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4">
    <div className="w-full max-w-md rounded-lg bg-white shadow-2xl">
      <div className="border-b border-slate-200 p-5">
        <h3 className="text-lg font-semibold text-slate-950">{action.title}</h3>
        <p className="mt-2 text-sm leading-6 text-slate-600">{action.description}</p>
      </div>
      <div className="flex flex-col gap-2 p-5 sm:flex-row sm:justify-end">
        <Button variant="outline" className="rounded-md" onClick={onCancel} disabled={disabled}>Отмена</Button>
        <Button
          variant={action.variant === 'destructive' ? 'destructive' : 'default'}
          className="rounded-md"
          onClick={action.onConfirm}
          disabled={disabled}
        >
          {action.confirmLabel}
        </Button>
      </div>
    </div>
  </div>
);
