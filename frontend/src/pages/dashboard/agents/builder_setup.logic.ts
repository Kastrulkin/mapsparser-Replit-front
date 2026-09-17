import { providerActionDescription } from './connections.logic';
import {
	humanizeMeta
} from './model';
import {
	connectorLabel,
	userFacingAgentTechText
} from './normalization';
import type {
	AgentBuilderPreview,
	AgentCompilerPolicyItem,
	AgentConnectionReadinessService
} from './types';

export const builderConnectionCardStatus = (action: string, selected: boolean) => {
  if (selected) {
    return 'способ выбран';
  }
  if (action === 'ready' || action === 'native_ready') {
    return 'готово';
  }
  if (action === 'choose_existing') {
    return 'выбрать доступ';
  }
  if (action === 'choose_route') {
    return 'выбрать способ';
  }
  if (action === 'connect_required') {
    return 'нужен способ';
  }
  if (action === 'planned_provider') {
    return 'позже';
  }
  if (action === 'forbidden' || action === 'unsupported') {
    return 'невозможно';
  }
  return humanizeMeta(action || 'проверить');
};

export const builderConnectionCardHint = (action: string, provider: string) => {
  if (action === 'ready' || action === 'native_ready') {
    return 'Этот доступ уже можно использовать в тесте без отправки.';
  }
  if (action === 'choose_existing') {
    return 'У бизнеса есть несколько подходящих подключений. Выберите одно для этого агента.';
  }
  if (action === 'choose_route') {
    return 'Выберите, как агенту безопасно доставлять результат или получать данные. Обычно подходит рекомендованный способ LocalOS.';
  }
  if (action === 'connect_required') {
    return `${connectorLabel(provider)} нужен агенту, но доступ ещё не выбран.`;
  }
  if (action === 'planned_provider') {
    return 'Этот способ подключения запланирован, но пока недоступен для включения агента.';
  }
  return 'LocalOS проверит этот доступ перед тестом без отправки.';
};

export const compilerPolicyItemLabel = (item?: AgentCompilerPolicyItem | null): string => {
  if (!item) {
    return '';
  }
  return String(
    item.title
    || item.message
    || item.reason
    || item.request
    || item.capability
    || item.provider
    || item.type
    || item.key
    || item.text
    || '',
  ).trim();
};

export const compilerPlanTriggerLabel = (trigger?: string) => {
  const value = String(trigger || '').trim();
  if (!value || value === 'manual.run') {
    return 'Запуск вручную';
  }
  if (value.includes('daily')) {
    const timeMatch = value.match(/at\(([^)]+)\)/);
    return `Каждый день${timeMatch?.[1] ? ` в ${timeMatch[1]}` : ''}`;
  }
  if (value.includes('schedule')) {
    return 'По расписанию';
  }
  if (value.includes('message') || value.includes('telegram')) {
    return 'Когда приходит сообщение';
  }
  return humanizeMeta(value);
};

export const compilerPlanStepCopy = (item: AgentCompilerPolicyItem, index: number) => {
  const capability = String(item.capability || item.key || item.type || '').trim();
  const provider = String(item.provider || '').trim();
  const rawLabel = compilerPolicyItemLabel(item);

  if (capability === 'google_sheets.read_rows' || provider === 'google_sheets') {
    return {
      title: 'Прочитать данные из Google Sheets',
      detail: 'Агент возьмёт строки из выбранной таблицы и вкладки. На этом шаге он только читает данные.',
    };
  }
  if (capability === 'communications.draft' || capability.includes('draft')) {
    return {
      title: 'Подготовить черновик сообщения',
      detail: 'LocalOS соберёт текст по заданному стилю. Это ещё не отправка наружу.',
    };
  }
  if (capability.includes('send') || capability.includes('publish')) {
    return {
      title: 'Попросить подтверждение перед отправкой',
      detail: 'Внешнее действие не выполняется автоматически: пользователь должен одобрить результат.',
    };
  }
  if (provider === 'telegram' || capability.includes('telegram')) {
    return {
      title: 'Передать результат в Telegram',
      detail: 'Сообщение будет доставлено через выбранный Telegram-канал после нужного подтверждения.',
    };
  }
  return {
    title: rawLabel || `Шаг ${index + 1}`,
    detail: item.reason || item.message || item.text || 'LocalOS выполнит этот шаг как часть проверяемого сценария.',
  };
};

export const builderPreviewDataText = (preview: AgentBuilderPreview | null, taskText: string) => {
  const labels: string[] = [];
  const seen = new Set<string>();
  const addLabel = (label: string) => {
    const cleanLabel = label.trim();
    const key = cleanLabel.toLowerCase();
    if (!cleanLabel || seen.has(key)) {
      return;
    }
    seen.add(key);
    labels.push(cleanLabel);
  };
  if (taskText.toLowerCase().includes('отзыв')) {
    addLabel('отзывы компании');
  }
  (preview?.data_sources || []).forEach((item) => addLabel(humanizeMeta(item)));
  return labels.join(', ') || 'ещё не выбрано';
};

export const builderConnectionStatusCopy = (service: AgentConnectionReadinessService) => {
  const action = String(service.action || service.status || '').trim();
  if (action === 'ready' || action === 'native_ready') {
    return 'Можно использовать';
  }
  if (action === 'choose_existing') {
    return 'Выберите доступ';
  }
  if (action === 'choose_route') {
    return 'Выберите способ';
  }
  if (action === 'planned_provider') {
    return 'Пока недоступно';
  }
  if (action === 'forbidden' || action === 'unsupported') {
    return 'Невозможно';
  }
  if (action === 'connect_required') {
    return 'Нужно подключить';
  }
  return service.action_label || humanizeMeta(action || 'проверить');
};

export const builderConnectionNextStepCopy = (service: AgentConnectionReadinessService, selected: boolean) => {
  if (selected) {
    return 'Этот способ будет сохранён в плане агента.';
  }
  const routeDescription = providerActionDescription(service.recommended_route || null);
  if (routeDescription) {
    return routeDescription;
  }
  if (service.connections?.length) {
    return 'Можно использовать уже сохранённое подключение бизнеса.';
  }
  if (service.provider_route_cta) {
	    return userFacingAgentTechText(service.provider_route_cta);
  }
	  return userFacingAgentTechText(service.route_summary || service.explanation || 'LocalOS проверит доступ перед тестом без отправки.');
};

export const serviceIntelligenceTone = (state: string) => {
  if (state === 'already_connected' || state === 'localos_native' || state === 'available_route') {
    return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  }
  if (state === 'multiple_routes') {
    return 'bg-sky-50 text-sky-700 ring-sky-200';
  }
  if (state === 'planned') {
    return 'bg-slate-50 text-slate-600 ring-slate-200';
  }
  if (state === 'impossible') {
    return 'bg-rose-50 text-rose-700 ring-rose-200';
  }
  return 'bg-amber-50 text-amber-700 ring-amber-200';
};

export const resolverStateTone = (state: string) => {
  if (state === 'ready' || state === 'native_ready') {
    return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  }
  if (state === 'available' || state === 'choose_existing') {
    return 'bg-sky-50 text-sky-700 ring-sky-200';
  }
  if (state === 'planned_provider') {
    return 'bg-slate-50 text-slate-600 ring-slate-200';
  }
  return 'bg-amber-50 text-amber-700 ring-amber-200';
};
