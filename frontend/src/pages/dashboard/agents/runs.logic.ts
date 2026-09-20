import {
	explainApproval,
	humanizeMeta
} from './model';
import type {
	AgentApproval,
	AgentJournalEntry,
	AgentReviewSection,
	AgentRunStep
} from './types';

export const buildJournalFromSections = (sections: AgentReviewSection[]) => sections.map((section) => ({
  kind: humanizeMeta(section.artifact_type || 'artifact'),
  title: section.title || 'Результат',
  status: section.status || 'completed',
  summary: section.summary || '',
  details: [],
  payload: section.payload || {},
}));

export const buildStepStatusMap = (steps: AgentRunStep[]) => {
  const statuses: Record<string, string> = {};
  steps.forEach((step) => {
    if (step.step_key && step.status) {
      statuses[step.step_key] = step.status;
    }
  });
  return statuses;
};

export const findJournalEntryForGenericStage = (journal: AgentJournalEntry[], kind: string) => {
  if (kind === 'approval') {
    return journal.find((entry) => entry.kind === 'approval');
  }
  return journal.find((entry) => entry.kind === kind);
};

export const getGenericStageStatus = (
  kind: string,
  entry: AgentJournalEntry | undefined,
  stepStatuses: Record<string, string>,
  pendingApproval: AgentApproval | null,
) => {
  if (kind === 'approval' && pendingApproval) {
    return 'waiting_approval';
  }
  if (entry?.status) {
    return entry.status;
  }
  if (kind === 'input') {
    return stepStatuses.collect_inputs || '';
  }
  if (kind === 'extraction') {
    return stepStatuses.extract_context || '';
  }
  if (kind === 'output') {
    return stepStatuses.prepare_output || '';
  }
  if (kind === 'approval') {
    return stepStatuses.approve_output || '';
  }
  return '';
};

export const getGenericStageDetail = (
  kind: string,
  entry: AgentJournalEntry | undefined,
  category: string,
  pendingApproval: AgentApproval | null,
) => {
  if (kind === 'input') {
    return findJournalDetailValue(entry, 'Подключено источников') || findJournalDetailValue(entry, 'Источники') || 'Данные агента подключены к запуску.';
  }
  if (kind === 'extraction') {
    return findJournalDetailValue(entry, 'Извлечено элементов') || findJournalDetailValue(entry, 'Что обработано') || entry?.summary || 'Агент разобрал источники.';
  }
  if (kind === 'output') {
    return getOutputStageDetail(entry, category);
  }
  if (kind === 'approval') {
    if (pendingApproval) {
      return explainApproval(pendingApproval);
    }
    return findJournalDetailValue(entry, 'Статус') || entry?.summary || 'Решения сохранены в журнале.';
  }
  return '';
};

export const getOutputStageDetail = (entry: AgentJournalEntry | undefined, category: string) => {
  if (!entry) {
    return 'Результат появится после запуска.';
  }
  if (category === 'documents') {
    return compactJoin([
      labelCount('Фактов', findJournalDetailValue(entry, 'Фактов')),
      labelCount('Рисков', findJournalDetailValue(entry, 'Рисков')),
      findJournalDetailValue(entry, 'Внешняя отправка'),
    ]);
  }
  if (category === 'email') {
    return compactJoin([
      findJournalDetailValue(entry, 'Тема письма'),
      labelCount('Пунктов чеклиста', findJournalDetailValue(entry, 'Чеклист')),
      findJournalDetailValue(entry, 'Внешняя отправка'),
    ]);
  }
  if (category === 'tables') {
    return compactJoin([
      labelCount('Исключений', findJournalDetailValue(entry, 'Исключений')),
      labelCount('Строк к проверке', findJournalDetailValue(entry, 'Строк к проверке')),
      findJournalDetailValue(entry, 'Внешняя отправка'),
    ]);
  }
  if (category === 'reviews') {
    return compactJoin([
      labelCount('Черновиков ответов', findJournalDetailValue(entry, 'Черновиков ответов')),
      labelCount('Причин ручной проверки', findJournalDetailValue(entry, 'Причин ручной проверки')),
      findJournalDetailValue(entry, 'Публикация'),
    ]);
  }
  return entry.summary || 'Агент подготовил результат.';
};

export const labelCount = (label: string, value: string) => (value ? `${label}: ${value}` : '');

export const compactJoin = (items: string[]) => items.filter((item) => item.trim()).join(' · ');

export const findJournalDetailValue = (entry: AgentJournalEntry | undefined, label: string) => {
  if (!entry || !Array.isArray(entry.details)) {
    return '';
  }
  const detail = entry.details.find((item) => item.label === label);
  return detail?.value || '';
};

export const toRecordOrNull = (value: unknown): Record<string, unknown> | null => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return Object.fromEntries(Object.entries(value));
};

export const hasCompleteDraftApprovalSnapshot = (approval: AgentApproval) => {
  const payload = approval.payload_json;
  return approval.approval_type === 'drafts'
    && payload?.snapshot_version === 1
    && Array.isArray(payload.items)
    && payload.items.length > 0
    && payload.items.every((item) => {
      const record = toRecordOrNull(item);
      return Boolean(record && typeof record.review_text === 'string' && record.review_text.trim().length > 0);
    });
};

export const formatPayloadItem = (value: unknown) => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const entries = Object.entries(value).filter(([, itemValue]) => itemValue !== '' && itemValue !== null && itemValue !== undefined);
    return entries.slice(0, 3).map(([key, itemValue]) => `${humanizeMeta(key)}: ${formatPayloadValue(itemValue)}`).join(' · ');
  }
  return formatPayloadValue(value);
};

export const formatPayloadValue = (value: unknown): string => {
  if (Array.isArray(value)) {
    return value.slice(0, 4).map((item) => formatPayloadValue(item)).join(', ');
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value).filter(([, itemValue]) => itemValue !== '' && itemValue !== null && itemValue !== undefined);
    return entries.slice(0, 3).map(([key, itemValue]) => `${humanizeMeta(key)}: ${formatPayloadValue(itemValue)}`).join('; ');
  }
  return String(value ?? '');
};

export const previewNextStepActionLabel = (nextStep: string, fallback: string) => {
  const labels: Record<string, string> = {
    connect_required_integrations: 'Открыть подключения',
    fix_preview_error: 'Открыть логику',
    review_approvals: 'Открыть решения',
    check_activation_gate: 'Проверить активацию',
    review_preview: 'Открыть запуск',
  };
  return labels[nextStep] || fallback || 'Открыть следующий шаг';
};

export const previewSimulationTone = (status: string) => {
  if (status === 'completed') {
    return 'bg-emerald-50 text-emerald-800 ring-emerald-100';
  }
  if (status === 'waiting_approval') {
    return 'bg-amber-50 text-amber-800 ring-amber-100';
  }
  if (status === 'blocked' || status === 'failed') {
    return 'bg-rose-50 text-rose-800 ring-rose-100';
  }
  return 'bg-slate-50 text-slate-600 ring-slate-200';
};

export const compactValue = (value: unknown) => {
  if (Array.isArray(value)) {
    return value.length ? value.join(', ') : 'any';
  }
  if (typeof value === 'number') {
    return String(value);
  }
  if (typeof value === 'string' && value.trim()) {
    return value.trim();
  }
  return 'any';
};
