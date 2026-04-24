import { newAuth } from '@/lib/auth_new';

type PartnershipRequestInit = RequestInit;

type PartnershipLeadQuery = {
  businessId: string;
  stage: string;
  pilotCohort: string;
  query: string;
};

type GeoSearchParams = {
  businessId: string;
  provider: string;
  city: string;
  category: string;
  query: string;
  radiusKm: number;
  limit: number;
};

type ImportedLead = {
  name?: string;
  source_url?: string;
  city?: string;
  category?: string;
  address?: string;
  phone?: string;
  email?: string;
  website?: string;
  telegram_url?: string;
  whatsapp_url?: string;
  rating?: number;
  reviews_count?: number;
  source_kind?: string;
  source_provider?: string;
  lat?: number;
  lon?: number;
};

export const getStringIds = (value: unknown) => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item) => typeof item === 'string' && item.length > 0);
};

const request = <T = any>(path: string, init?: PartnershipRequestInit) => newAuth.makeRequest<T>(path, init);

export const loadPartnershipLeads = ({ businessId, stage, pilotCohort, query }: PartnershipLeadQuery) => {
  const params = new URLSearchParams();
  params.set('business_id', businessId);
  if (stage !== 'all') params.set('stage', stage);
  if (pilotCohort !== 'all') params.set('pilot_cohort', pilotCohort);
  if (query.trim()) params.set('q', query.trim());
  return request(`/partnership/leads?${params.toString()}`, { method: 'GET' });
};

export const loadPartnershipRalphLoop = (businessId: string, pilotCohort: string) => {
  const params = new URLSearchParams();
  params.set('business_id', businessId);
  params.set('window_days', '7');
  if (pilotCohort !== 'all') params.set('pilot_cohort', pilotCohort);
  return request(`/partnership/ralph-loop-summary?${params.toString()}`, { method: 'GET' });
};

export const loadPartnershipDrafts = (businessId: string) =>
  request(`/partnership/drafts?business_id=${encodeURIComponent(businessId)}`, { method: 'GET' });

export const loadPartnershipBatches = (businessId: string) =>
  request(`/partnership/send-batches?business_id=${encodeURIComponent(businessId)}`, { method: 'GET' });

export const loadPartnershipLearningMetrics = () =>
  request('/admin/ai/learning-metrics?intent=partnership_outreach', { method: 'GET' });

export const loadPartnershipHealth = (businessId: string) =>
  request(`/partnership/health?business_id=${encodeURIComponent(businessId)}`, { method: 'GET' });

export const loadPartnershipFunnel = (businessId: string) =>
  request(`/partnership/funnel?business_id=${encodeURIComponent(businessId)}&window_days=30`, { method: 'GET' });

export const loadPartnershipBlockers = (businessId: string) =>
  request(`/partnership/blockers-summary?business_id=${encodeURIComponent(businessId)}&window_days=30`, { method: 'GET' });

export const loadPartnershipOutcomes = (businessId: string) =>
  request(`/partnership/outcomes-summary?business_id=${encodeURIComponent(businessId)}&window_days=30`, { method: 'GET' });

export const loadPartnershipSourceQuality = (businessId: string) =>
  request(`/partnership/source-quality-summary?business_id=${encodeURIComponent(businessId)}&window_days=30`, {
    method: 'GET',
  });

export const importPartnershipLinks = (businessId: string, links: string[]) =>
  request('/partnership/leads/import-links', {
    method: 'POST',
    body: JSON.stringify({ business_id: businessId, links }),
  });

export const importPartnershipFile = (
  businessId: string,
  payload: {
    filename: string;
    format?: string;
    content: string;
  },
) =>
  request('/partnership/leads/import-file', {
    method: 'POST',
    body: JSON.stringify({
      business_id: businessId,
      ...payload,
    }),
  });

export const runPartnershipGeoSearch = ({
  businessId,
  provider,
  city,
  category,
  query,
  radiusKm,
  limit,
}: GeoSearchParams) =>
  request('/partnership/geo-search', {
    method: 'POST',
    body: JSON.stringify({
      business_id: businessId,
      provider,
      city,
      category,
      query,
      radius_km: Number.isFinite(radiusKm) ? radiusKm : 5,
      limit: Number.isFinite(limit) ? limit : 25,
    }),
  });

export const normalizePartnershipLeads = (
  businessId: string,
  params: {
    city: string;
    category: string;
    query: string;
    items: ImportedLead[];
  },
) =>
  request('/partnership/geo-search', {
    method: 'POST',
    body: JSON.stringify({
      business_id: businessId,
      provider: 'google',
      ...params,
    }),
  });

export const bulkUpdatePartnershipLeads = (
  businessId: string,
  leadIds: string[],
  payload: Record<string, unknown>,
) =>
  request<{ updated_count?: number }>('/partnership/leads/bulk-update', {
    method: 'POST',
    body: JSON.stringify({
      business_id: businessId,
      lead_ids: leadIds,
      ...payload,
    }),
  });

export const bulkDeletePartnershipLeads = (businessId: string, leadIds: string[]) =>
  request('/partnership/leads/bulk-delete', {
    method: 'POST',
    body: JSON.stringify({
      business_id: businessId,
      lead_ids: leadIds,
    }),
  });

export const bulkEnrichPartnershipContacts = (businessId: string, leadIds: string[]) =>
  request('/partnership/leads/bulk-enrich-contacts', {
    method: 'POST',
    body: JSON.stringify({
      business_id: businessId,
      lead_ids: leadIds,
    }),
  });

export const bulkMatchPartnershipLeads = (businessId: string, leadIds: string[]) =>
  request('/partnership/leads/bulk-match', {
    method: 'POST',
    body: JSON.stringify({
      business_id: businessId,
      lead_ids: leadIds,
    }),
  });

export const deletePartnershipLead = (businessId: string, leadId: string) =>
  request(`/partnership/leads/${leadId}?business_id=${encodeURIComponent(businessId)}`, { method: 'DELETE' });

export const patchPartnershipLead = (businessId: string, leadId: string, payload: Record<string, unknown>) =>
  request(`/partnership/leads/${leadId}`, {
    method: 'PATCH',
    body: JSON.stringify({
      business_id: businessId,
      ...payload,
    }),
  });

export const runPartnershipLeadAction = (
  businessId: string,
  leadId: string,
  action: 'audit' | 'parse' | 'match' | 'enrich-contacts' | 'draft-offer',
  payload?: Record<string, unknown>,
) =>
  request(`/partnership/leads/${leadId}/${action}`, {
    method: 'POST',
    body: JSON.stringify({
      business_id: businessId,
      ...payload,
    }),
  });

export const approvePartnershipDraft = (businessId: string, draftId: string, approvedText: string) =>
  request(`/partnership/drafts/${draftId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ business_id: businessId, approved_text: approvedText }),
  });

export const deletePartnershipDraft = (businessId: string, draftId: string) =>
  request(`/partnership/drafts/${draftId}?business_id=${encodeURIComponent(businessId)}`, { method: 'DELETE' });

export const createPartnershipBatch = (businessId: string, draftIds?: string[]) =>
  request('/partnership/send-batches', {
    method: 'POST',
    body: JSON.stringify({
      business_id: businessId,
      ...(draftIds ? { draft_ids: draftIds } : {}),
    }),
  });

export const approvePartnershipBatch = (businessId: string, batchId: string) =>
  request(`/partnership/send-batches/${batchId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ business_id: businessId }),
  });

export const updatePartnershipQueueDelivery = (businessId: string, queueId: string, deliveryStatus: string) =>
  request(`/partnership/send-queue/${queueId}/delivery`, {
    method: 'POST',
    body: JSON.stringify({ business_id: businessId, delivery_status: deliveryStatus }),
  });

export const deletePartnershipQueueItem = (businessId: string, queueId: string) =>
  request(`/partnership/send-queue/${queueId}?business_id=${encodeURIComponent(businessId)}`, { method: 'DELETE' });

export const recordPartnershipReaction = (businessId: string, queueId: string, outcome?: string) =>
  request(`/partnership/send-queue/${queueId}/reaction`, {
    method: 'POST',
    body: JSON.stringify({ business_id: businessId, outcome }),
  });

export const confirmPartnershipReaction = (businessId: string, reactionId: string, outcome: string) =>
  request(`/partnership/reactions/${reactionId}/confirm`, {
    method: 'POST',
    body: JSON.stringify({ business_id: businessId, outcome }),
  });

export const exportPartnershipData = (businessId: string, format: string) =>
  request(`/partnership/export?business_id=${encodeURIComponent(businessId)}&format=${format}&limit=50`, {
    method: 'GET',
  });
