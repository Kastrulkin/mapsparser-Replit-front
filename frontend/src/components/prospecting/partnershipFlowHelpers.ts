type PartnershipRequest = <T = unknown>(path: string, init?: RequestInit) => Promise<T>;

type SourceDescriptor = {
  source_kind?: string;
  source_provider?: string;
};

type PartnershipLeadLite = {
  id: string;
  name?: string;
  parse_status?: string;
  source_kind?: string;
  source_provider?: string;
  pilot_cohort?: string;
};

type PartnershipDraftLite = {
  id: string;
  lead_id: string;
  lead_name?: string;
  status?: string;
  approved_text?: string;
  edited_text?: string;
  generated_text?: string;
};

type PartnershipFlowCounts = {
  enrichedCount: number;
  auditedCount: number;
  matchedCount: number;
  draftedCount: number;
  skippedParseCount: number;
  errors: string[];
};

type PartnershipBatchPrepCounts = {
  approvedCount: number;
  queuedCount: number;
  batchId: string;
  errors: string[];
};

const normalize = (value: unknown) => String(value || '').trim().toLowerCase();

export function sourceMatchesDescriptor(
  item: SourceDescriptor,
  descriptor: SourceDescriptor | null | undefined,
) {
  if (!descriptor) {
    return false;
  }
  return (
    normalize(item.source_kind) === normalize(descriptor.source_kind) &&
    normalize(item.source_provider) === normalize(descriptor.source_provider)
  );
}

export function collectLeadIdsForSource(
  items: PartnershipLeadLite[],
  descriptor: SourceDescriptor | null | undefined,
  options?: { onlyOutsidePilot?: boolean },
) {
  return items
    .filter((item) => {
      if (!sourceMatchesDescriptor(item, descriptor)) {
        return false;
      }
      if (!options?.onlyOutsidePilot) {
        return true;
      }
      return normalize(item.pilot_cohort || 'backlog') !== 'pilot';
    })
    .map((item) => item.id);
}

export async function runPartnershipPilotFlow(
  request: PartnershipRequest,
  businessId: string,
  leads: PartnershipLeadLite[],
  options?: {
    channel?: string;
    tone?: string;
  },
) {
  const leadIds = leads.map((item) => item.id);
  const parseReadyLeads = leads.filter((item) => normalize(item.parse_status) === 'completed');
  const errors: string[] = [];
  let enrichedCount = 0;
  let auditedCount = 0;
  let matchedCount = 0;
  let draftedCount = 0;
  const skippedParseCount = Math.max(0, leads.length - parseReadyLeads.length);

  try {
    const enrichData = await request<{ updated_count?: number }>('/partnership/leads/bulk-enrich-contacts', {
      method: 'POST',
      body: JSON.stringify({
        business_id: businessId,
        lead_ids: leadIds,
      }),
    });
    enrichedCount = Number(enrichData?.updated_count || 0);
  } catch (error: unknown) {
    const message = error instanceof Error && error.message ? error.message : 'ошибка';
    errors.push(`enrich: ${message}`);
  }

  for (const lead of parseReadyLeads) {
    try {
      await request(`/partnership/leads/${lead.id}/audit`, {
        method: 'POST',
        body: JSON.stringify({ business_id: businessId }),
      });
      auditedCount += 1;
    } catch (error: unknown) {
      const message = error instanceof Error && error.message ? error.message : 'ошибка';
      errors.push(`${lead.name || lead.id}: audit — ${message}`);
      continue;
    }

    try {
      await request(`/partnership/leads/${lead.id}/match`, {
        method: 'POST',
        body: JSON.stringify({ business_id: businessId }),
      });
      matchedCount += 1;
    } catch (error: unknown) {
      const message = error instanceof Error && error.message ? error.message : 'ошибка';
      errors.push(`${lead.name || lead.id}: match — ${message}`);
      continue;
    }

    try {
      await request(`/partnership/leads/${lead.id}/draft-offer`, {
        method: 'POST',
        body: JSON.stringify({
          business_id: businessId,
          channel: options?.channel || 'telegram',
          tone: options?.tone || 'профессиональный',
        }),
      });
      draftedCount += 1;
    } catch (error: unknown) {
      const message = error instanceof Error && error.message ? error.message : 'ошибка';
      errors.push(`${lead.name || lead.id}: draft — ${message}`);
    }
  }

  const result: PartnershipFlowCounts = {
    enrichedCount,
    auditedCount,
    matchedCount,
    draftedCount,
    skippedParseCount,
    errors,
  };

  return result;
}

export async function preparePartnershipBatch(
  request: PartnershipRequest,
  businessId: string,
  drafts: PartnershipDraftLite[],
) {
  const draftIds: string[] = [];
  const errors: string[] = [];
  let approvedCount = 0;

  for (const draft of drafts) {
    try {
      if (normalize(draft.status) !== 'approved') {
        const approvedText = String(draft.approved_text || draft.edited_text || draft.generated_text || '');
        await request(`/partnership/drafts/${draft.id}/approve`, {
          method: 'POST',
          body: JSON.stringify({
            business_id: businessId,
            approved_text: approvedText || undefined,
          }),
        });
        approvedCount += 1;
      }
      draftIds.push(draft.id);
    } catch (error: unknown) {
      const message = error instanceof Error && error.message ? error.message : 'ошибка';
      errors.push(`${draft.lead_name || draft.id}: approve — ${message}`);
    }
  }

  if (draftIds.length === 0) {
    return {
      approvedCount,
      queuedCount: 0,
      batchId: '',
      errors,
    } satisfies PartnershipBatchPrepCounts;
  }

  const batchData = await request<{ queue_count?: number; batch_id?: string }>('/partnership/send-batches', {
    method: 'POST',
    body: JSON.stringify({
      business_id: businessId,
      draft_ids: draftIds,
    }),
  });

  return {
    approvedCount,
    queuedCount: Number(batchData?.queue_count || 0),
    batchId: String(batchData?.batch_id || ''),
    errors,
  } satisfies PartnershipBatchPrepCounts;
}
