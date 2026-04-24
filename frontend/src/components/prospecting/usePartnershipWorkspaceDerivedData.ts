import { useMemo } from 'react';

export type PartnershipDerivedLead = {
  id: string;
  phone?: string;
  email?: string;
  website?: string;
  telegram_url?: string;
  whatsapp_url?: string;
  source_kind?: string;
  source_provider?: string;
  partnership_stage?: string;
  pilot_cohort?: string;
  parse_status?: string;
  deferred_until?: string;
  search_payload_json?: Record<string, any> | null;
  enrich_payload_json?: {
    provider?: string;
    found_fields?: string[];
  } | null;
  next_best_action?: {
    code?: string;
  };
};

export type PartnershipDerivedDraft = {
  id: string;
  lead_id: string;
  status?: string;
};

export type PartnershipDerivedBatch = {
  id: string;
  status: string;
  items?: Array<{
    id: string;
    lead_id?: string;
    delivery_status?: string;
    latest_outcome?: string | null;
    latest_human_outcome?: string | null;
    [key: string]: any;
  }>;
};

export type PartnershipDerivedReaction = {
  lead_id: string;
  classified_outcome?: string | null;
  human_confirmed_outcome?: string | null;
  [key: string]: any;
};

type SourceDescriptor = {
  source_kind?: string;
  source_provider?: string;
};

type PartnershipDerivedArgs<TLead extends PartnershipDerivedLead> = {
  items: TLead[];
  selectedLeadId: string | null;
  auditData: any;
  leadView: string;
  leadBucket: 'active' | 'deferred';
  preferredSourceFilter: SourceDescriptor | null;
  lastGeoSearchLeadIds: string[];
  ralphLoop: any;
  batches: PartnershipDerivedBatch[];
  drafts: PartnershipDerivedDraft[];
  reactions: PartnershipDerivedReaction[];
  draftView: string;
  queueView: string;
  reactionView: string;
  outcomes: any;
};

const ACTIVE_PIPELINE_STAGES = [
  'audited',
  'matched',
  'proposal_draft_ready',
  'selected_for_outreach',
  'channel_selected',
  'approved_for_send',
  'sent',
];

const AUDITED_FLOW_STAGES = ['audited', 'matched', 'proposal_draft_ready', 'proposal_approved', 'queued_for_send', 'sent'];
const MATCHED_FLOW_STAGES = ['matched', 'proposal_draft_ready', 'proposal_approved', 'queued_for_send', 'sent'];
const DRAFT_READY_FLOW_STAGES = ['proposal_draft_ready', 'proposal_approved', 'queued_for_send', 'sent'];

const hasAnyContact = (item: PartnershipDerivedLead) =>
  Boolean(item.phone || item.email || item.telegram_url || item.whatsapp_url || item.website);

const sameSource = (left?: SourceDescriptor | null, right?: SourceDescriptor | null) => {
  if (!left || !right) return false;
  return (
    String(left.source_kind || '').toLowerCase() === String(right.source_kind || '').toLowerCase() &&
    String(left.source_provider || '').toLowerCase() === String(right.source_provider || '').toLowerCase()
  );
};

const sourceLeadsForIds = (items: PartnershipDerivedLead[], ids: string[]) =>
  items.filter((item) => ids.includes(item.id));

export function usePartnershipWorkspaceDerivedData<TLead extends PartnershipDerivedLead>({
  items,
  selectedLeadId,
  auditData,
  leadView,
  leadBucket,
  preferredSourceFilter,
  lastGeoSearchLeadIds,
  ralphLoop,
  batches,
  drafts,
  reactions,
  draftView,
  queueView,
  reactionView,
  outcomes,
}: PartnershipDerivedArgs<TLead>) {
  const selectedLead = useMemo(
    () => items.find((item) => item.id === selectedLeadId) || null,
    [items, selectedLeadId]
  );

  const selectedLeadLogo = useMemo(() => {
    if (auditData?.preview_meta?.logo_url) return String(auditData.preview_meta.logo_url);
    if (selectedLead?.search_payload_json?.logo_url) return String(selectedLead.search_payload_json.logo_url);
    return '';
  }, [auditData, selectedLead]);

  const selectedLeadPhotos = useMemo(() => {
    const fromAudit = auditData?.preview_meta?.photo_urls;
    if (Array.isArray(fromAudit) && fromAudit.length > 0) {
      return fromAudit.map((item: unknown) => String(item || '').trim()).filter(Boolean).slice(0, 8);
    }
    const fromLead = selectedLead?.search_payload_json?.photos;
    if (Array.isArray(fromLead) && fromLead.length > 0) {
      return fromLead.map((item: unknown) => String(item || '').trim()).filter(Boolean).slice(0, 8);
    }
    return [];
  }, [auditData, selectedLead]);

  const visibleLeads = useMemo(() => {
    const todayIso = new Date().toISOString().slice(0, 10);
    return items.filter((item) => {
      const parseStatus = String(item.parse_status || '').toLowerCase();
      const partnershipStage = String(item.partnership_stage || '').toLowerCase();
      const nextCode = String(item.next_best_action?.code || '').toLowerCase();
      const deferredUntil = String(item.deferred_until || '').slice(0, 10);
      const isOverdueReturn = partnershipStage === 'deferred' && Boolean(deferredUntil) && deferredUntil <= todayIso;
      if (leadBucket === 'deferred' && partnershipStage !== 'deferred') return false;
      if (leadBucket === 'active' && partnershipStage === 'deferred') return false;
      if (leadView === 'deferred') return partnershipStage === 'deferred';
      if (leadView === 'overdue_return') return isOverdueReturn;
      if (leadView === 'requires_action') {
        return ['captcha', 'error'].includes(parseStatus) || ['parse_captcha', 'parse_error', 'fill_contacts'].includes(nextCode);
      }
      if (leadView === 'no_parse') return !parseStatus || ['pending', 'queued', 'imported'].includes(parseStatus);
      if (leadView === 'ready_for_letter') return ['draft', 'approve_draft'].includes(nextCode);
      if (leadView === 'errors') return ['error', 'failed'].includes(parseStatus);
      if (leadView === 'last_geo_search') return lastGeoSearchLeadIds.includes(item.id);
      if (leadView === 'ready_next_step') {
        return ['parse', 'match', 'draft', 'approve_draft', 'queue', 'approve_batch', 'confirm_outcome'].includes(nextCode);
      }
      if (leadView === 'parsed') return parseStatus === 'completed';
      if (leadView === 'with_contacts') return hasAnyContact(item);
      if (leadView === 'best_source') return sameSource(item, preferredSourceFilter);
      return true;
    });
  }, [items, leadView, leadBucket, preferredSourceFilter, lastGeoSearchLeadIds]);

  const bestSourceThisWeek = useMemo(() => {
    if (!Array.isArray(ralphLoop?.source_performance) || ralphLoop.source_performance.length === 0) return null;
    return ralphLoop.source_performance[0] || null;
  }, [ralphLoop]);

  const lastGeoSearchSourceSummary = useMemo(() => {
    const sourceLeads = sourceLeadsForIds(items, lastGeoSearchLeadIds);
    if (sourceLeads.length === 0) return null;
    const counts = new Map<string, { source_kind?: string; source_provider?: string; count: number }>();
    sourceLeads.forEach((item) => {
      const sourceKind = String(item.source_kind || '').trim() || undefined;
      const sourceProvider = String(item.source_provider || '').trim() || undefined;
      const key = `${sourceKind || 'unknown'}::${sourceProvider || 'unknown'}`;
      const current = counts.get(key) || { source_kind: sourceKind, source_provider: sourceProvider, count: 0 };
      current.count += 1;
      counts.set(key, current);
    });
    return Array.from(counts.values()).sort((a, b) => b.count - a.count)[0] || null;
  }, [items, lastGeoSearchLeadIds]);

  const lastGeoSearchMatchesBestSource = useMemo(
    () => sameSource(bestSourceThisWeek, lastGeoSearchSourceSummary),
    [bestSourceThisWeek, lastGeoSearchSourceSummary]
  );

  const lastGeoSearchStats = useMemo(() => {
    const sourceLeads = sourceLeadsForIds(items, lastGeoSearchLeadIds);
    if (sourceLeads.length === 0) return null;
    return {
      total: sourceLeads.length,
      parsedCompleted: sourceLeads.filter((item) => String(item.parse_status || '').toLowerCase() === 'completed').length,
      withContacts: sourceLeads.filter(hasAnyContact).length,
      enriched: sourceLeads.filter((item) => {
        const payload = item.enrich_payload_json;
        return Boolean(payload?.provider || (Array.isArray(payload?.found_fields) && payload.found_fields.length > 0));
      }).length,
      readyForDraft: sourceLeads.filter((item) => String(item.next_best_action?.code || '').toLowerCase() === 'draft').length,
    };
  }, [items, lastGeoSearchLeadIds]);

  const allQueueItems = useMemo(
    () => batches.flatMap((batch) => (batch.items || []).map((item) => ({ ...item, batch_status: batch.status, batch_id: batch.id }))),
    [batches]
  );

  const lastGeoSearchFlowSummary = useMemo(() => {
    const sourceLeads = sourceLeadsForIds(items, lastGeoSearchLeadIds);
    if (sourceLeads.length === 0) return null;
    const leadIds = new Set(sourceLeads.map((item) => item.id));
    const sourceDrafts = drafts.filter((draft) => leadIds.has(String(draft.lead_id || '')));
    const sourceQueueItems = allQueueItems.filter((item) => leadIds.has(String(item.lead_id || '')));
    const sourceReactions = reactions.filter((item) => leadIds.has(String(item.lead_id || '')));
    return {
      total: sourceLeads.length,
      audited: sourceLeads.filter((item) => AUDITED_FLOW_STAGES.includes(String(item.partnership_stage || '').toLowerCase())).length,
      matched: sourceLeads.filter((item) => MATCHED_FLOW_STAGES.includes(String(item.partnership_stage || '').toLowerCase())).length,
      draftReady: sourceLeads.filter((item) => DRAFT_READY_FLOW_STAGES.includes(String(item.partnership_stage || '').toLowerCase())).length,
      draftsApproved: sourceDrafts.filter((draft) => String(draft.status || '').toLowerCase() === 'approved').length,
      queued: sourceQueueItems.filter((item) => ['queued', 'sending', 'retry', 'sent', 'delivered', 'failed'].includes(String(item.delivery_status || '').toLowerCase())).length,
      sent: sourceQueueItems.filter((item) => ['sent', 'delivered'].includes(String(item.delivery_status || '').toLowerCase())).length,
      positive: sourceReactions.filter((item) => String(item.human_confirmed_outcome || item.classified_outcome || '').toLowerCase() === 'positive').length,
    };
  }, [items, lastGeoSearchLeadIds, drafts, allQueueItems, reactions]);

  const selectedLeadFlowStatus = useMemo(() => {
    if (!selectedLead) return null;
    const leadId = String(selectedLead.id || '');
    const leadDrafts = drafts.filter((draft) => String(draft.lead_id || '') === leadId);
    const leadQueueItems = allQueueItems.filter((item) => String(item.lead_id || '') === leadId);
    const leadReactions = reactions.filter((item) => String(item.lead_id || '') === leadId);
    return {
      draftsTotal: leadDrafts.length,
      draftsApproved: leadDrafts.filter((draft) => String(draft.status || '').toLowerCase() === 'approved').length,
      queueTotal: leadQueueItems.length,
      sentTotal: leadQueueItems.filter((item) => ['sent', 'delivered'].includes(String(item.delivery_status || '').toLowerCase())).length,
      outcomeFinal: leadReactions[0]?.human_confirmed_outcome || leadReactions[0]?.classified_outcome || null,
    };
  }, [selectedLead, drafts, allQueueItems, reactions]);

  const visibleDrafts = useMemo(() => drafts.filter((draft) => {
    const status = String(draft.status || '').toLowerCase();
    if (draftView === 'needs_approval') return !status || status === 'generated' || status === 'draft';
    if (draftView === 'approved') return status === 'approved';
    return true;
  }), [drafts, draftView]);

  const visibleBatches = useMemo(() => batches
    .map((batch) => {
      const items = (batch.items || []).filter((item) => {
        const delivery = String(item.delivery_status || '').toLowerCase();
        const outcome = String(item.latest_human_outcome || item.latest_outcome || '').toLowerCase();
        if (queueView === 'needs_approval') return String(batch.status || '').toLowerCase() === 'draft';
        if (queueView === 'waiting_delivery') return ['queued', 'pending', 'created', 'draft', ''].includes(delivery);
        if (queueView === 'waiting_outcome') return delivery === 'sent' && !outcome;
        if (queueView === 'failed') return delivery === 'failed';
        return true;
      });
      return { ...batch, items };
    })
    .filter((batch) => queueView === 'needs_approval' ? String(batch.status || '').toLowerCase() === 'draft' : (batch.items || []).length > 0),
    [batches, queueView]
  );

  const visibleReactions = useMemo(() => reactions.filter((reaction) => {
    const finalOutcome = String(reaction.human_confirmed_outcome || reaction.classified_outcome || '').toLowerCase();
    if (reactionView === 'needs_confirmation') return !reaction.human_confirmed_outcome;
    if (reactionView !== 'all') return finalOutcome === reactionView;
    return true;
  }), [reactions, reactionView]);

  const pilotSummary = useMemo(() => ({
    total: items.length,
    parsed: items.filter((item) => String(item.parse_status || '').toLowerCase() === 'completed').length,
    readyForDraft: items.filter((item) => String(item.next_best_action?.code || '') === 'draft').length,
    waitingApproval: drafts.filter((draft) => {
      const status = String(draft.status || '').toLowerCase();
      return !status || status === 'generated' || status === 'draft';
    }).length,
    waitingOutcome: allQueueItems.filter((item) => {
      const delivery = String(item.delivery_status || '').toLowerCase();
      return delivery === 'sent' && !(item.latest_human_outcome || item.latest_outcome);
    }).length,
    acceptance: Number(outcomes?.summary?.positive_rate_pct || 0),
  }), [items, drafts, allQueueItems, outcomes]);

  const deferredLeadsCount = useMemo(
    () => items.filter((item) => String(item.partnership_stage || '').toLowerCase() === 'deferred').length,
    [items]
  );

  const overdueDeferredLeadsCount = useMemo(() => {
    const todayIso = new Date().toISOString().slice(0, 10);
    return items.filter((item) => {
      const stageValue = String(item.partnership_stage || '').toLowerCase();
      const deferredUntil = String(item.deferred_until || '').slice(0, 10);
      return stageValue === 'deferred' && Boolean(deferredUntil) && deferredUntil <= todayIso;
    }).length;
  }, [items]);

  const activeLeadsCount = useMemo(
    () => items.filter((item) => String(item.partnership_stage || '').toLowerCase() !== 'deferred').length,
    [items]
  );

  const rawLeads = visibleLeads;
  const rawLeadCount = rawLeads.length;
  const pipelineLeads = useMemo(() => visibleLeads.filter((item) => {
    const stageValue = String(item.partnership_stage || '').toLowerCase();
    return stageValue && stageValue !== 'imported';
  }), [visibleLeads]);
  const pipelineLeadCount = pipelineLeads.length;
  const lastGeoSearchLeadCount = lastGeoSearchLeadIds.length;

  const pipelineSummary = useMemo(() => ({
    raw: rawLeadCount,
    withAudit: items.filter((item) => ACTIVE_PIPELINE_STAGES.includes(String(item.partnership_stage || '').toLowerCase())).length,
    readyToContact: items.filter((item) => ['proposal_draft_ready', 'selected_for_outreach', 'channel_selected'].includes(String(item.partnership_stage || '').toLowerCase())).length,
    deferred: deferredLeadsCount,
  }), [items, rawLeadCount, deferredLeadsCount]);

  const rawLeadStatusSummary = useMemo(() => {
    const imported = rawLeads.filter((item) => {
      const stageValue = String(item.partnership_stage || '').toLowerCase();
      return !stageValue || stageValue === 'imported';
    }).length;
    const inPipeline = rawLeads.filter((item) => ACTIVE_PIPELINE_STAGES.includes(String(item.partnership_stage || '').toLowerCase())).length;
    const deferred = rawLeads.filter((item) => String(item.partnership_stage || '').toLowerCase() === 'deferred').length;
    const rejected = rawLeads.filter((item) => ['rejected', 'shortlist_rejected'].includes(String(item.partnership_stage || '').toLowerCase())).length;
    return { imported, inPipeline, deferred, rejected };
  }, [rawLeads]);

  return {
    selectedLead,
    selectedLeadLogo,
    selectedLeadPhotos,
    visibleLeads,
    bestSourceThisWeek,
    lastGeoSearchSourceSummary,
    lastGeoSearchMatchesBestSource,
    lastGeoSearchStats,
    allQueueItems,
    lastGeoSearchFlowSummary,
    selectedLeadFlowStatus,
    visibleDrafts,
    visibleBatches,
    visibleReactions,
    pilotSummary,
    deferredLeadsCount,
    overdueDeferredLeadsCount,
    activeLeadsCount,
    rawLeads,
    rawLeadCount,
    pipelineLeads,
    pipelineLeadCount,
    lastGeoSearchLeadCount,
    pipelineSummary,
    rawLeadStatusSummary,
  };
}
