import {
	humanizeMeta
} from './model';
import {
	userFacingAgentTechText
} from './normalization';
import type {
	AgentConnectionPlanItem,
	AgentProviderRoute
} from './types';

export const connectionActionTone = (action: string) => {
  if (action === 'ready' || action === 'native_ready') {
    return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  }
  if (action === 'choose_existing' || action === 'choose_route') {
    return 'bg-sky-50 text-sky-700 ring-sky-200';
  }
  if (action === 'planned_provider') {
    return 'bg-slate-50 text-slate-600 ring-slate-200';
  }
  return 'bg-amber-50 text-amber-700 ring-amber-200';
};

export const agentPolicyFacts = (item: AgentConnectionPlanItem) => {
  const rawFacts = [
    item.autonomy_level,
    item.execution_boundary,
    item.credential_state,
    item.approval_state,
    item.next_action_label,
  ];
  const facts: string[] = [];
  rawFacts.forEach((fact) => {
    const normalized = String(fact || '').trim();
    if (normalized && !facts.includes(normalized)) {
      facts.push(normalized);
    }
  });
  return facts.slice(0, 5);
};

export const providerRouteLabel = (state: string) => ({
  connected: 'подключено',
  available: 'доступно',
  manual: 'ручной режим',
  planned: 'позже',
  unavailable: 'недоступно',
}[state] || humanizeMeta(state || 'unknown'));

export const providerRouteTone = (state: string) => {
  if (state === 'connected' || state === 'available') {
    return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  }
  if (state === 'manual') {
    return 'bg-sky-50 text-sky-700 ring-sky-200';
  }
  if (state === 'planned') {
    return 'bg-slate-50 text-slate-600 ring-slate-200';
  }
  return 'bg-rose-50 text-rose-700 ring-rose-200';
};

export const providerActionLabel = (route?: AgentProviderRoute | null) => {
  const action = route?.provider_action;
  if (action?.label) {
    return userFacingAgentTechText(action.label);
  }
  return userFacingAgentTechText(route?.primary_cta || providerRouteLabel(route?.state || route?.status || ''));
};

export const providerActionDescription = (route?: AgentProviderRoute | null) => {
  const action = route?.provider_action;
  if (action?.description) {
    return userFacingAgentTechText(action.description);
  }
  if (route?.connect_mode === 'openclaw_policy_boundary') {
    return 'Этот способ работает внутри правил безопасности, ручных подтверждений, журнала и лимитов LocalOS.';
  }
  if (route?.connect_mode === 'external_account_key') {
    return 'Выберите сохранённый ключ доступа или добавьте его в интеграциях бизнеса.';
  }
  if (route?.connect_mode === 'planned_oauth_connector') {
    return 'Подключение через OAuth запланировано, но пока не позволяет включить агента.';
  }
  return '';
};
