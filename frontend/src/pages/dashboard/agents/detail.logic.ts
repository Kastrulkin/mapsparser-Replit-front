import type {
	AgentBillingBreakdownItem,
	AgentUnifiedBillingLedger
} from './types';

export const formatBillingEstimateSummary = (ledger?: AgentUnifiedBillingLedger) => {
  const summary = ledger?.summary || {};
  const credits = Number(summary.estimated_credits || 0);
  if (!credits) {
    return 'нет';
  }
  return `${credits} кр.`;
};

export const formatBillingActualSummary = (ledger?: AgentUnifiedBillingLedger) => {
  const summary = ledger?.summary || {};
  const credits = Number(summary.actual_credits || 0);
  if (!credits) {
    return 'нет списаний';
  }
  return `${credits} кр.`;
};

export const formatBillingEstimateValue = (item: AgentBillingBreakdownItem) => {
  const credits = Number(item.estimated_credits || 0);
  if (credits) {
    return `${credits} кр.`;
  }
  return '0 кр.';
};

export const formatBillingActualValue = (item: AgentBillingBreakdownItem) => {
  const credits = Number(item.actual_credits || item.charged_credits || 0);
  if (credits) {
    return `${credits} кр.`;
  }
  return '0 кр.';
};
