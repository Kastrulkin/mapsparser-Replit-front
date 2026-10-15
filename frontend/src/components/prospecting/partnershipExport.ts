type OperatorSnapshotPayload = {
  generated_at: string;
  business_id?: string;
  pilot_summary?: {
    total?: number;
    parsed?: number;
    readyForDraft?: number;
    waitingApproval?: number;
    waitingOutcome?: number;
    acceptance?: number;
  };
  ralph_loop?: any;
  blockers?: any;
  funnel?: any;
  outcomes?: any;
  health?: any;
  source_quality?: any;
};

type OperatorSnapshotInput = Omit<OperatorSnapshotPayload, 'generated_at'>;

export const downloadTextFile = (filename: string, content: string, mime = 'text/plain;charset=utf-8') => {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};

export const buildOperatorSnapshotPayload = (input: OperatorSnapshotInput): OperatorSnapshotPayload => ({
  generated_at: new Date().toISOString(),
  ...input,
});

export const buildOperatorSnapshotMarkdown = (snapshot: OperatorSnapshotPayload) => {
  const lines: string[] = [
    '# Partnership Operator Snapshot',
    '',
    `- business_id: \`${snapshot.business_id || '-'}\``,
    `- generated_at: \`${snapshot.generated_at}\``,
    '',
    '## Pilot Summary',
    `- leads_total: ${snapshot.pilot_summary?.total ?? 0}`,
    `- parsed_completed: ${snapshot.pilot_summary?.parsed ?? 0}`,
    `- ready_for_draft: ${snapshot.pilot_summary?.readyForDraft ?? 0}`,
    `- waiting_approval: ${snapshot.pilot_summary?.waitingApproval ?? 0}`,
    `- waiting_outcome: ${snapshot.pilot_summary?.waitingOutcome ?? 0}`,
    `- positive_rate_pct: ${snapshot.pilot_summary?.acceptance ?? 0}`,
    '',
    '## Ralph Loop (7 days)',
    `- sent_total: ${snapshot.ralph_loop?.summary?.sent_total ?? 0}`,
    `- positive_count: ${snapshot.ralph_loop?.summary?.positive_count ?? 0}`,
    `- positive_rate_pct: ${snapshot.ralph_loop?.summary?.positive_rate_pct ?? 0}`,
    `- baseline_sent_total: ${snapshot.ralph_loop?.baseline?.sent_total ?? 0}`,
    `- baseline_positive_rate_pct: ${snapshot.ralph_loop?.baseline?.positive_rate_pct ?? 0}`,
    '',
    '### Recommendations',
  ];

  const recommendations = Array.isArray(snapshot.ralph_loop?.recommendations) ? snapshot.ralph_loop?.recommendations || [] : [];
  if (recommendations.length > 0) {
    recommendations.forEach((item: string) => lines.push(`- ${item}`));
  } else {
    lines.push('- none');
  }

  lines.push('', '### Prompt Versions');
  const promptPerf = Array.isArray(snapshot.ralph_loop?.prompt_performance) ? snapshot.ralph_loop?.prompt_performance || [] : [];
  if (promptPerf.length > 0) {
    promptPerf.slice(0, 10).forEach((item: any) => {
      lines.push(
        `- ${item.prompt_key || 'unknown'} / v${item.prompt_version || 'unknown'} | approved=${item.approved_total ?? 0} | edited=${item.edited_before_accept_pct ?? 0}% | sent=${item.sent_total ?? 0} | positive=${item.positive_rate_pct ?? 0}%`
      );
    });
  } else {
    lines.push('- none');
  }

  lines.push('', '### Blockers');
  const blockerItems = Array.isArray(snapshot.ralph_loop?.blockers) ? snapshot.ralph_loop?.blockers || [] : [];
  if (blockerItems.length > 0) {
    blockerItems.forEach((item: string) => lines.push(`- ${item}`));
  } else {
    lines.push('- none');
  }

  lines.push('', '### Outcome Summary');
  lines.push(`- positive: ${snapshot.outcomes?.summary?.positive_count ?? 0}`);
  lines.push(`- question: ${snapshot.outcomes?.summary?.question_count ?? 0}`);
  lines.push(`- no_response: ${snapshot.outcomes?.summary?.no_response_count ?? 0}`);
  lines.push(`- hard_no: ${snapshot.outcomes?.summary?.hard_no_count ?? 0}`);

  lines.push('', '### Funnel');
  const funnelItems = Array.isArray(snapshot.funnel?.funnel) ? snapshot.funnel?.funnel || [] : [];
  if (funnelItems.length > 0) {
    funnelItems.forEach((item: any) => {
      lines.push(`- ${item.label}: ${item.count ?? 0} (conv ${item.conversion_from_prev_pct ?? 0}%)`);
    });
  } else {
    lines.push('- none');
  }

  lines.push('', '### Source Quality');
  const sourceItems = Array.isArray(snapshot.source_quality?.items) ? snapshot.source_quality?.items || [] : [];
  if (sourceItems.length > 0) {
    sourceItems.slice(0, 10).forEach((item: any) => {
      lines.push(
        `- ${item.source_kind || 'unknown'} / ${item.source_provider || 'unknown'} | leads=${item.leads_total ?? 0} | draft=${item.draft_rate_pct ?? 0}% | sent=${item.sent_rate_pct ?? 0}% | lead_to_positive=${item.lead_to_positive_pct ?? 0}%`
      );
    });
  } else {
    lines.push('- none');
  }

  return lines.join('\n');
};

export const buildPartnershipCsvTemplate = () => {
  const header = [
    'name',
    'source_url',
    'city',
    'category',
    'phone',
    'email',
    'website',
    'telegram_url',
    'whatsapp_url',
    'rating',
    'reviews_count',
  ].join(',');
  const example = [
    'Салон Ромашка',
    'https://yandex.ru/maps/org/1234567890/',
    'Санкт-Петербург',
    'Салон красоты',
    '+7 921 000-00-00',
    'owner@example.com',
    'https://romashka.example',
    'https://t.me/romashka',
    'https://wa.me/79210000000',
    '4.8',
    '152',
  ].join(',');
  return `${header}\n${example}\n`;
};
