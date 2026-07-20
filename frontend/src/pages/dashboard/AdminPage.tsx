import React, { Suspense, lazy, useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { ChevronDown, ChevronRight, Building2, Network, MapPin, User, Plus, Trash2, Ban, AlertTriangle, Bot, Settings, BarChart3, FileText, X, Search, ShieldCheck, KeyRound, CreditCard, CalendarDays, Radar, BookOpen, Download, Loader2 } from 'lucide-react';
import { newAuth } from '../../lib/auth_new';
import { useToast } from '../../hooks/use-toast';
import { CreateBusinessModal } from '../../components/CreateBusinessModal';
import { AdminExternalCabinetSettings } from '../../components/AdminExternalCabinetSettings';
import { AdminLeadRegistry } from '../../components/prospecting/AdminLeadRegistry';
import { TelegramOpportunityRadar } from '../../components/TelegramOpportunityRadar';
import {
  DashboardCompactMetricsRow,
  DashboardEmptyState,
  DashboardPageHeader,
  DashboardSection,
} from '../../components/dashboard/DashboardPrimitives';

const AgentApiManagement = lazy(() =>
  import('../../components/AgentApiManagement').then((module) => ({ default: module.AgentApiManagement })),
);
const TokenUsageStats = lazy(() =>
  import('../../components/TokenUsageStats').then((module) => ({ default: module.TokenUsageStats })),
);
const PromptsManagement = lazy(() =>
  import('../../components/PromptsManagement').then((module) => ({ default: module.PromptsManagement })),
);
const ProxyManagement = lazy(() =>
  import('../../components/ProxyManagement').then((module) => ({ default: module.ProxyManagement })),
);
const ParsingManagement = lazy(() =>
  import('../../components/ParsingManagement').then((module) => ({ default: module.ParsingManagement })),
);
const IndustryPatternsManagement = lazy(() =>
  import('../../components/IndustryPatternsManagement').then((module) => ({ default: module.IndustryPatternsManagement })),
);
const KnowledgeMarketOverview = lazy(() =>
  import('../../components/KnowledgeMarketOverview').then((module) => ({ default: module.KnowledgeMarketOverview })),
);

type AdminTabId = 'businesses' | 'subscriptions' | 'agents' | 'agentApi' | 'tokens' | 'prompts' | 'patterns' | 'proxies' | 'parsing' | 'prospecting' | 'telegramRadar' | 'knowledge';
interface Business {
  id: string;
  name: string;
  description?: string;
  address?: string;
  industry?: string;
  created_at?: string;
  is_active?: number;
  subscription_tier?: string;
  subscription_status?: string;
  subscription_ends_at?: string;
  moderation_status?: string;
  is_lead_business?: boolean;
  entity_group?: 'lead' | 'company';
}

interface Network {
  id: string;
  name: string;
  description?: string;
  businesses: Business[];
  created_at?: string;
}

interface UserWithBusinesses {
  id: string;
  email: string;
  name?: string;
  phone?: string;
  is_superadmin?: boolean;
  is_active?: number;
  password_setup_required?: boolean;
  has_password_setup_token?: boolean;
  direct_businesses: Business[];
  networks: Network[];
}

interface BusinessListItem {
  id: string;
  name: string;
  type: 'direct' | 'network';
  networkId?: string;
  networkName?: string;
  business: Business;
}

interface PaymentDialogState {
  isOpen: boolean;
  scope: 'business' | 'network';
  targetId: string;
  targetName: string;
  isPaid: boolean;
  paidCount: number;
  totalCount: number;
  endsAt: string;
}

interface AdminAgentBlueprint {
  id: string;
  business_id: string;
  business_name: string;
  owner_email: string;
  creator_email: string;
  name: string;
  category: string;
  description: string;
  status: string;
  latest_goal: string;
  latest_version_number?: number;
  runs_count: number;
  pending_approvals_count: number;
  sources_count: number;
  integration_count: number;
  integration_providers: string;
  created_at?: string;
  updated_at?: string;
  risk_level: 'low' | 'medium' | 'high';
  risk_reasons: string[];
}

interface AdminAgentBlueprintSummary {
  total: number;
  draft: number;
  active: number;
  archived: number;
  high_risk: number;
  medium_risk: number;
  low_risk: number;
}

interface AdminAgentRuntimeIssue {
  run_id: string;
  blueprint_id: string;
  business_id: string;
  agent_name: string;
  business_name: string;
  status: string;
  attempt_count: number;
  error: string;
  updated_at?: string;
}

interface AdminAgentSchedulerEvent {
  event_id: string;
  blueprint_id: string;
  run_id: string;
  business_id: string;
  agent_name: string;
  business_name: string;
  event_type: string;
  status: string;
  run_status: string;
  reason_code: string;
  schedule_date: string;
  schedule_time: string;
  timezone: string;
  created_at?: string;
}

interface AdminAgentSchedulerCanary {
  blueprint_id: string;
  business_id: string;
  agent_name: string;
  business_name: string;
  active_version_id: string;
  schedule_time: string;
  timezone: string;
  target_days: number;
  successful_days: number;
  successful_dates: string[];
  last_success_date?: string;
  failed_events: number;
  deferred_events: number;
  old_version_runs: number;
  duplicate_runs: number;
  status: 'observing' | 'attention' | 'passed';
  last_event_at?: string;
}

interface AdminAgentRuntimeOverview {
  flags: {
    async_runs_enabled: boolean;
    schedule_dispatch_enabled: boolean;
    beta_businesses_count: number;
    queue_interval_seconds: number;
  };
  runs: {
    queued: number;
    running: number;
    retry_wait: number;
    waiting_approval: number;
    stale_running: number;
    failed_24h: number;
    completed_24h: number;
    billing_bound_runs: number;
    last_run_at?: string;
  };
  scheduler: {
    total_events: number;
    events_24h: number;
    failed_24h: number;
    deferred_24h: number;
    last_event_at?: string;
    recent_events: AdminAgentSchedulerEvent[];
    canaries: AdminAgentSchedulerCanary[];
  };
  consistency: {
    archived_unfinished_runs: number;
    archived_pending_approvals: number;
    waiting_without_pending_approval: number;
  };
  integrations: {
    active: number;
    inactive: number;
  };
  billing: {
    active_reservations: number;
    reserved_credits: number;
    charged_credits: number;
    released_credits: number;
  };
  recent_issues: AdminAgentRuntimeIssue[];
}

interface AdminAgentBlueprintOverview {
  summary: AdminAgentBlueprintSummary;
  runtime: AdminAgentRuntimeOverview;
  agents: AdminAgentBlueprint[];
}

interface AdminSubscriptionSummary {
  subscriptions_total: number;
  active_subscriptions: number;
  blocked_subscriptions: number;
  canceled_subscriptions: number;
  autopay_enabled: number;
  missing_payment_method: number;
  due_soon_7d: number;
  overdue: number;
  new_users_30d: number;
  inactive_users_total: number;
  churned_or_blocked_30d: number;
  users_total: number;
  monthly_recurring_revenue: number;
  currency: string;
}

interface AdminSubscriptionRow {
  id: string;
  user_id: string;
  business_id?: string;
  tariff_id: string;
  pending_tariff_id?: string;
  status: string;
  period_start?: string;
  next_billing_date?: string;
  payment_method_linked?: boolean;
  last_payment_id?: string;
  retry_count?: number;
  next_retry_at?: string;
  created_at?: string;
  updated_at?: string;
  user_email?: string;
  user_name?: string;
  user_is_active?: boolean | number;
  credits_balance?: number;
  business_name?: string;
  business_subscription_tier?: string;
  business_subscription_status?: string;
  business_subscription_ends_at?: string;
  latest_attempt_status?: string;
  latest_attempt_type?: string;
  latest_attempt_payment_id?: string;
  latest_attempt_error?: string;
  latest_attempt_at?: string;
}

interface AdminBillingAttemptRow {
  id: string;
  subscription_id: string;
  attempt_type?: string;
  attempt_no?: number;
  status?: string;
  payment_id?: string;
  amount_value?: string | number;
  currency?: string;
  error_message?: string;
  created_at?: string;
  updated_at?: string;
  user_email?: string;
  business_name?: string;
}

interface AdminCreditLedgerRow {
  id: string;
  user_id: string;
  subscription_id?: string;
  delta: number;
  reason: string;
  period_start?: string;
  period_end?: string;
  external_id?: string;
  created_at?: string;
  user_email?: string;
  business_name?: string;
}

interface AdminSubscriptionsOverview {
  summary: AdminSubscriptionSummary;
  subscriptions: AdminSubscriptionRow[];
  recent_attempts: AdminBillingAttemptRow[];
  credit_ledger: AdminCreditLedgerRow[];
}

type AdminTabConfig = {
  id: AdminTabId;
  label: string;
  icon: typeof User;
};

const LOCALOS_RADAR_BUSINESS_ID = '__localos__';

const adminTabs: AdminTabConfig[] = [
  { id: 'businesses', label: 'Пользователи и бизнесы', icon: User },
  { id: 'subscriptions', label: 'Подписки', icon: CreditCard },
  { id: 'agents', label: 'Агенты пользователей', icon: Bot },
  { id: 'agentApi', label: 'Agent API', icon: KeyRound },
  { id: 'prospecting', label: 'Лиды', icon: Search },
  { id: 'knowledge', label: 'Знания рынка', icon: BookOpen },
  { id: 'telegramRadar', label: 'Telegram-радар', icon: Radar },
  { id: 'tokens', label: 'Статистика кредитов', icon: BarChart3 },
  { id: 'prompts', label: 'Промпты анализа', icon: FileText },
  { id: 'patterns', label: 'Паттерны', icon: ShieldCheck },
  { id: 'proxies', label: 'Прокси', icon: Network },
  { id: 'parsing', label: 'Парсинг', icon: MapPin },
];

const primaryAdminTabs: AdminTabConfig[] = [
  { id: 'businesses', label: 'Пользователи', icon: User },
  { id: 'subscriptions', label: 'Подписки', icon: CreditCard },
  { id: 'agents', label: 'Агенты', icon: Bot },
  { id: 'agentApi', label: 'Agent API', icon: KeyRound },
  { id: 'prospecting', label: 'Лиды', icon: Search },
  { id: 'knowledge', label: 'Знания рынка', icon: BookOpen },
  { id: 'telegramRadar', label: 'Telegram-радар', icon: Radar },
];

const toolsAdminTabs: AdminTabConfig[] = [
  { id: 'parsing', label: 'Парсинг', icon: MapPin },
  { id: 'proxies', label: 'Прокси', icon: Network },
  { id: 'prompts', label: 'Промпты анализа', icon: FileText },
  { id: 'patterns', label: 'Паттерны', icon: ShieldCheck },
  { id: 'tokens', label: 'Статистика кредитов', icon: BarChart3 },
];

const isAdminTabId = (value: string | null): value is AdminTabId => (
  value !== null && adminTabs.some((tab) => tab.id === value)
);

const LEAD_OUTREACH_STATUS = 'lead_outreach';
const PAID_TIERS = new Set(['starter', 'professional', 'concierge', 'elite', 'promo', 'basic', 'pro', 'enterprise']);
const ACTIVE_SUBSCRIPTION_STATUSES = new Set(['active', 'trialing']);
const PAYMENT_PERIODS = [
  { label: '1 месяц', months: 1 },
  { label: '3 месяца', months: 3 },
  { label: '6 месяцев', months: 6 },
  { label: '12 месяцев', months: 12 },
];

const getErrorMessage = (error: unknown, fallback: string) => {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallback;
};

const isLeadBusiness = (business?: Business | null) =>
  business?.is_lead_business === true ||
  String(business?.entity_group || '').trim().toLowerCase() === 'lead' ||
  String(business?.moderation_status || '').trim().toLowerCase() === LEAD_OUTREACH_STATUS;

const filterUsersBySearch = (users: UserWithBusinesses[], normalizedSearchQuery: string) =>
  users.filter((user) => {
    const directBusinesses = user.direct_businesses || [];
    const networkBusinesses = (user.networks || []).flatMap((network) => network.businesses || []);
    const allBusinesses = [...directBusinesses, ...networkBusinesses];

    if (!normalizedSearchQuery) {
      return true;
    }

    const userHaystack = [
      user.email || '',
      user.name || '',
      user.phone || '',
    ].join(' ').toLowerCase();

    if (userHaystack.includes(normalizedSearchQuery)) {
      return true;
    }

    return allBusinesses.some((business) =>
      [
        business.name || '',
        business.address || '',
        business.description || '',
        business.id || '',
      ].join(' ').toLowerCase().includes(normalizedSearchQuery)
    );
  });

const addMonthsForInput = (months: number) => {
  const date = new Date();
  date.setMonth(date.getMonth() + months);
  return date.toISOString().slice(0, 10);
};

const toDateInputValue = (value?: string) => {
  if (!value) {
    return addMonthsForInput(1);
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return addMonthsForInput(1);
  }
  return date.toISOString().slice(0, 10);
};

const isPastDate = (value?: string) => {
  if (!value) {
    return false;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return false;
  }
  return date.getTime() < Date.now();
};

const isBusinessSubscriptionPaid = (business?: Business | null) => {
  const tier = String(business?.subscription_tier || '').trim().toLowerCase();
  const status = String(business?.subscription_status || '').trim().toLowerCase();
  return PAID_TIERS.has(tier) && ACTIVE_SUBSCRIPTION_STATUSES.has(status) && !isPastDate(business?.subscription_ends_at);
};

const getSubscriptionEndLabel = (value?: string) => {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return date.toLocaleDateString('ru-RU');
};

const getNetworkPaymentState = (businesses: Business[]) => {
  const totalCount = businesses.length;
  const paidBusinesses = businesses.filter(isBusinessSubscriptionPaid);
  return {
    allPaid: totalCount > 0 && paidBusinesses.length === totalCount,
    paidCount: paidBusinesses.length,
    totalCount,
  };
};

const formatAdminDateTime = (value?: string) => {
  if (!value) {
    return 'Дата не указана';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Дата не указана';
  }
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
};

const formatAdminMoney = (value?: number, currency = 'RUB') =>
  new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value || 0));

const getSubscriptionStatusLabel = (status?: string) => {
  if (status === 'active') return 'Активна';
  if (status === 'blocked') return 'Проблема оплаты';
  if (status === 'canceled') return 'Отменена';
  return 'Неизвестно';
};

const getSubscriptionStatusClassName = (status?: string) => {
  if (status === 'active') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (status === 'blocked') return 'border-amber-200 bg-amber-50 text-amber-800';
  if (status === 'canceled') return 'border-slate-200 bg-slate-100 text-slate-600';
  return 'border-slate-200 bg-white text-slate-600';
};

const getBillingAttemptLabel = (status?: string) => {
  if (status === 'succeeded') return 'Успешно';
  if (status === 'pending') return 'Ожидает';
  if (status === 'canceled') return 'Отменён';
  if (status === 'failed') return 'Ошибка';
  if (status === 'scheduled') return 'Запланирован';
  return status || 'Нет попыток';
};

const getBillingAttemptClassName = (status?: string) => {
  if (status === 'succeeded') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (status === 'pending' || status === 'scheduled') return 'border-sky-200 bg-sky-50 text-sky-700';
  if (status === 'failed' || status === 'canceled') return 'border-rose-200 bg-rose-50 text-rose-700';
  return 'border-slate-200 bg-slate-50 text-slate-600';
};

const buildSubscriptionAttention = (subscription: AdminSubscriptionRow) => {
  const status = String(subscription.status || '');
  if (status === 'blocked') {
    return 'Нужна проверка оплаты';
  }
  if (status === 'active' && !subscription.payment_method_linked) {
    return 'Нет карты для автосписания';
  }
  if (subscription.latest_attempt_status === 'failed' || subscription.latest_attempt_status === 'canceled') {
    return 'Последнее списание не прошло';
  }
  return 'В порядке';
};

const closeConfirmDialog = (
  setConfirmDialog: React.Dispatch<React.SetStateAction<{
    isOpen: boolean;
    title: string;
    message: string;
    confirmText: string;
    cancelText: string;
    onConfirm: () => void;
    variant?: 'delete' | 'block';
  }>>,
) => {
  setConfirmDialog((previous) => ({ ...previous, isOpen: false }));
};

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText: string;
  cancelText: string;
  onConfirm: () => void;
  onCancel: () => void;
  variant?: 'delete' | 'block';
}

const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  message,
  confirmText,
  cancelText,
  onConfirm,
  onCancel,
  variant = 'delete'
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-in fade-in duration-200">
      <Card className="max-w-md w-full mx-4 shadow-2xl border-0 animate-in zoom-in-95 duration-200">
        <CardContent className="p-6">
          <div className="flex items-start space-x-4 mb-6">
            <div className={`p-3 rounded-xl ${variant === 'delete' ? 'bg-red-50' : 'bg-primary/10'}`}>
              <AlertTriangle className={`w-6 h-6 ${variant === 'delete' ? 'text-red-600' : 'text-primary'}`} />
            </div>
            <div className="flex-1">
              <h3 className="text-xl font-semibold text-foreground mb-2">{title}</h3>
              <p className="text-muted-foreground leading-relaxed">{message}</p>
            </div>
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={onCancel} className="min-w-[100px]">
              {cancelText}
            </Button>
            <Button
              variant={variant === 'delete' ? 'destructive' : 'default'}
              onClick={onConfirm}
              className="min-w-[100px]"
            >
              {confirmText}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

const AdminTabFallback = () => (
  <Card className="border-dashed">
    <CardContent className="flex items-center justify-center py-12 text-sm text-muted-foreground">
      Загрузка раздела...
    </CardContent>
  </Card>
);

export const AdminPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab = searchParams.get('tab');
  const [activeTab, setActiveTab] = useState<AdminTabId>(() => (
    isAdminTabId(requestedTab) ? requestedTab : 'businesses'
  ));
  const [users, setUsers] = useState<UserWithBusinesses[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [agentBlueprintOverview, setAgentBlueprintOverview] = useState<AdminAgentBlueprintOverview | null>(null);
  const [agentBlueprintLoading, setAgentBlueprintLoading] = useState(false);
  const [downloadingAgentRunId, setDownloadingAgentRunId] = useState('');
  const [subscriptionsOverview, setSubscriptionsOverview] = useState<AdminSubscriptionsOverview | null>(null);
  const [subscriptionsLoading, setSubscriptionsLoading] = useState(false);
  const [selectedRadarBusinessId, setSelectedRadarBusinessId] = useState('');
  const [expandedNetworks, setExpandedNetworks] = useState<Set<string>>(new Set());
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [settingsModal, setSettingsModal] = useState<{
    isOpen: boolean;
    businessId: string | null;
    businessName: string;
  }>({
    isOpen: false,
    businessId: null,
    businessName: '',
  });
  const [paymentDialog, setPaymentDialog] = useState<PaymentDialogState>({
    isOpen: false,
    scope: 'business',
    targetId: '',
    targetName: '',
    isPaid: false,
    paidCount: 0,
    totalCount: 0,
    endsAt: addMonthsForInput(1),
  });

  useEffect(() => {
    if (isAdminTabId(requestedTab) && requestedTab !== activeTab) {
      setActiveTab(requestedTab);
    }
  }, [activeTab, requestedTab]);

  const selectAdminTab = useCallback((tabId: AdminTabId) => {
    setActiveTab(tabId);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set('tab', tabId);
    setSearchParams(nextParams, { replace: true });
  }, [searchParams, setSearchParams]);
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    confirmText: string;
    cancelText: string;
    onConfirm: () => void;
    variant?: 'delete' | 'block';
  }>({
    isOpen: false,
    title: '',
    message: '',
    confirmText: '',
    cancelText: '',
    onConfirm: () => { },
  });
  const navigate = useNavigate();
  const { toast } = useToast();

  const loadUsers = useCallback(async () => {
    try {
      setLoading(true);
      const data = await newAuth.makeRequest('/admin/users-with-businesses');

      if (data.success) {
        setUsers(data.users || []);
      }
    } catch (error: unknown) {
      console.error('Ошибка загрузки пользователей:', error);
      const message = getErrorMessage(error, 'Не удалось загрузить данные');
      if (message.includes('401') || message.includes('403')) {
        toast({
          title: 'Ошибка доступа',
          description: 'Недостаточно прав для просмотра этой страницы',
          variant: 'destructive',
        });
        navigate('/dashboard');
        return;
      }
      toast({
        title: 'Ошибка',
        description: message,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [navigate, toast]);

  const loadAgentBlueprintOverview = useCallback(async () => {
    try {
      setAgentBlueprintLoading(true);
      const data = await newAuth.makeRequest('/admin/agent-blueprints/overview');
      if (data.success) {
        setAgentBlueprintOverview({
          summary: data.summary,
          runtime: data.runtime,
          agents: data.agents || [],
        });
      }
    } catch (error: unknown) {
      toast({
        title: 'Ошибка',
        description: getErrorMessage(error, 'Не удалось загрузить обзор агентов'),
        variant: 'destructive',
      });
    } finally {
      setAgentBlueprintLoading(false);
    }
  }, [toast]);

  const loadSubscriptionsOverview = useCallback(async () => {
    try {
      setSubscriptionsLoading(true);
      const data = await newAuth.makeRequest('/admin/subscriptions/overview');
      if (data.success) {
        setSubscriptionsOverview({
          summary: data.summary,
          subscriptions: data.subscriptions || [],
          recent_attempts: data.recent_attempts || [],
          credit_ledger: data.credit_ledger || [],
        });
      }
    } catch (error: unknown) {
      toast({
        title: 'Ошибка',
        description: getErrorMessage(error, 'Не удалось загрузить подписки'),
        variant: 'destructive',
      });
    } finally {
      setSubscriptionsLoading(false);
    }
  }, [toast]);

  const downloadAgentSupportExport = async (runId: string) => {
    setDownloadingAgentRunId(runId);
    try {
      const data = await newAuth.makeRequest(`/agent-runs/${runId}/support-export?format=json`);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `agent-run-${runId}-support.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error: unknown) {
      toast({
        title: 'Не удалось выгрузить диагностику',
        description: getErrorMessage(error, 'Повторите попытку позже'),
        variant: 'destructive',
      });
    } finally {
      setDownloadingAgentRunId('');
    }
  };

  const runReloadingMutation = useCallback(async (
    request: () => Promise<unknown>,
    successDescription: string,
    fallbackError: string,
    options?: { closeDialog?: boolean },
  ) => {
    try {
      const response = await request();
      const payload = typeof response === 'object' && response !== null ? response : null;
      const isSuccess = payload !== null && 'success' in payload && payload.success === true;

      if (isSuccess) {
        toast({
          title: 'Успешно',
          description: successDescription,
        });
        await loadUsers();
      }
    } catch (error: unknown) {
      toast({
        title: 'Ошибка',
        description: getErrorMessage(error, fallbackError),
        variant: 'destructive',
      });
    } finally {
      if (options?.closeDialog) {
        closeConfirmDialog(setConfirmDialog);
      }
    }
  }, [loadUsers, toast]);

  useEffect(() => {
    const checkAccess = async () => {
      try {
        const currentUser = await newAuth.getCurrentUser();
        if (!currentUser) {
          toast({
            title: 'Требуется авторизация',
            description: 'Пожалуйста, войдите в систему',
            variant: 'destructive',
          });
          navigate('/login');
          return;
        }
        if (!currentUser.is_superadmin) {
          toast({
            title: 'Доступ запрещён',
            description: 'Эта страница доступна только супер-администраторам',
            variant: 'destructive',
          });
          navigate('/dashboard');
          return;
        }
        loadUsers();
      } catch (error: unknown) {
        console.error('Ошибка проверки доступа:', error);
        toast({
          title: 'Ошибка',
          description: getErrorMessage(error, 'Не удалось проверить доступ'),
          variant: 'destructive',
        });
      }
    };
    checkAccess();
  }, [loadUsers, navigate, toast]);

  useEffect(() => {
    if (activeTab === 'agents') {
      loadAgentBlueprintOverview();
    }
  }, [activeTab, loadAgentBlueprintOverview]);

  useEffect(() => {
    if (activeTab === 'subscriptions') {
      loadSubscriptionsOverview();
    }
  }, [activeTab, loadSubscriptionsOverview]);

  const toggleNetwork = (networkId: string) => {
    const newExpanded = new Set(expandedNetworks);
    if (newExpanded.has(networkId)) {
      newExpanded.delete(networkId);
    } else {
      newExpanded.add(networkId);
    }
    setExpandedNetworks(newExpanded);
  };

  const handleBusinessClick = async (businessId: string) => {
    localStorage.setItem('admin_selected_business_id', businessId);
    navigate('/dashboard/profile');
    window.location.reload();
  };

  const handleDelete = (businessId: string, businessName: string) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Подтверждение удаления',
      message: `Вы уверены, что хотите удалить бизнес "${businessName}"? Это действие нельзя отменить.`,
      confirmText: 'Удалить',
      cancelText: 'Отмена',
      variant: 'delete',
      onConfirm: async () => {
        await runReloadingMutation(
          () => newAuth.makeRequest(`/superadmin/businesses/${businessId}`, {
            method: 'DELETE',
          }),
          'Бизнес удалён',
          'Не удалось удалить бизнес',
          { closeDialog: true },
        );
      },
    });
  };

  const handleBlock = (businessId: string, businessName: string, isBlocked: boolean) => {
    setConfirmDialog({
      isOpen: true,
      title: isBlocked ? 'Подтверждение блокировки' : 'Подтверждение разблокировки',
      message: isBlocked
        ? `Вы уверены, что хотите заблокировать бизнес "${businessName}"?`
        : `Вы уверены, что хотите разблокировать бизнес "${businessName}"?`,
      confirmText: isBlocked ? 'Заблокировать' : 'Разблокировать',
      cancelText: 'Отмена',
      variant: 'block',
      onConfirm: async () => {
        await runReloadingMutation(
          () => newAuth.makeRequest(`/admin/businesses/${businessId}/block`, {
            method: 'POST',
            body: JSON.stringify({ is_blocked: isBlocked }),
          }),
          isBlocked ? 'Бизнес заблокирован' : 'Бизнес разблокирован',
          'Не удалось изменить статус бизнеса',
          { closeDialog: true },
        );
      },
    });
  };

  const handlePauseUser = (userId: string, userEmail: string, isPaused: boolean) => {
    setConfirmDialog({
      isOpen: true,
      title: isPaused ? 'Подтверждение приостановки' : 'Подтверждение возобновления',
      message: isPaused
        ? `Вы уверены, что хотите приостановить пользователя "${userEmail}"? Все его бизнесы также будут приостановлены.`
        : `Вы уверены, что хотите возобновить пользователя "${userEmail}"? Все его бизнесы также будут возобновлены.`,
      confirmText: isPaused ? 'Приостановить' : 'Возобновить',
      cancelText: 'Отмена',
      variant: 'block',
      onConfirm: async () => {
        const endpoint = isPaused ? `/superadmin/users/${userId}/pause` : `/superadmin/users/${userId}/unpause`;
        await runReloadingMutation(
          () => newAuth.makeRequest(endpoint, {
            method: 'POST',
          }),
          isPaused ? 'Пользователь приостановлен' : 'Пользователь возобновлен',
          'Не удалось изменить статус пользователя',
          { closeDialog: true },
        );
      },
    });
  };

  const handleDeleteUser = (userId: string, userEmail: string) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Подтверждение удаления',
      message: `Вы уверены, что хотите удалить пользователя "${userEmail}"? Это действие нельзя отменить. Все его бизнесы и данные будут удалены.`,
      confirmText: 'Удалить',
      cancelText: 'Отмена',
      variant: 'delete',
      onConfirm: async () => {
        closeConfirmDialog(setConfirmDialog);
        await runReloadingMutation(
          () => newAuth.makeRequest(`/superadmin/users/${userId}`, {
            method: 'DELETE',
          }),
          'Пользователь удалён',
          'Не удалось удалить пользователя',
        );
      },
    });
  };

  const handleSendPasswordSetup = async (userId: string, userEmail: string) => {
    try {
      const response = await newAuth.makeRequest(`/superadmin/users/${userId}/send-password-setup`, {
        method: 'POST',
      });
      const setupUrl = typeof response?.setup_url === 'string' ? response.setup_url : '';
      if (setupUrl && navigator.clipboard) {
        await navigator.clipboard.writeText(setupUrl);
      }
      toast({
        title: response?.email_sent ? 'Письмо отправлено' : 'Ссылка создана',
        description: response?.email_sent
          ? `Ссылка установки пароля отправлена на ${userEmail}`
          : 'Письмо не отправилось, но ссылка скопирована в буфер обмена',
      });
      await loadUsers();
    } catch (error: unknown) {
      toast({
        title: 'Ошибка',
        description: getErrorMessage(error, 'Не удалось отправить ссылку установки пароля'),
        variant: 'destructive',
      });
    }
  };

  const openBusinessPaymentDialog = (business: Business) => {
    setPaymentDialog({
      isOpen: true,
      scope: 'business',
      targetId: business.id,
      targetName: business.name,
      isPaid: isBusinessSubscriptionPaid(business),
      paidCount: isBusinessSubscriptionPaid(business) ? 1 : 0,
      totalCount: 1,
      endsAt: toDateInputValue(business.subscription_ends_at),
    });
  };

  const openNetworkPaymentDialog = (networkId: string, networkName: string, businesses: Business[]) => {
    const paymentState = getNetworkPaymentState(businesses);
    const firstPaidBusiness = businesses.find(isBusinessSubscriptionPaid);
    setPaymentDialog({
      isOpen: true,
      scope: 'network',
      targetId: networkId,
      targetName: networkName,
      isPaid: paymentState.allPaid,
      paidCount: paymentState.paidCount,
      totalCount: paymentState.totalCount,
      endsAt: toDateInputValue(firstPaidBusiness?.subscription_ends_at),
    });
  };

  const closePaymentDialog = () => {
    setPaymentDialog((previous) => ({ ...previous, isOpen: false }));
  };

  const applyPaymentPeriod = (months: number) => {
    setPaymentDialog((previous) => ({ ...previous, endsAt: addMonthsForInput(months) }));
  };

  const updatePaymentEndDate = (endsAt: string) => {
    setPaymentDialog((previous) => ({ ...previous, endsAt }));
  };

  const submitPaymentDialog = async (isPaid: boolean) => {
    const endpoint = paymentDialog.scope === 'network'
      ? `/admin/networks/${paymentDialog.targetId}/promo`
      : `/admin/businesses/${paymentDialog.targetId}/promo`;
    const subscriptionEndsAt = paymentDialog.endsAt ? `${paymentDialog.endsAt}T23:59:59` : null;
    const successDescription = isPaid
      ? `Оплата отмечена для ${paymentDialog.scope === 'network' ? 'сети' : 'точки'} "${paymentDialog.targetName}"`
      : `Оплата отключена для ${paymentDialog.scope === 'network' ? 'сети' : 'точки'} "${paymentDialog.targetName}"`;

    await runReloadingMutation(
      () => newAuth.makeRequest(endpoint, {
        method: 'POST',
        body: JSON.stringify({
          is_promo: isPaid,
          tier: 'promo',
          subscription_ends_at: subscriptionEndsAt,
        }),
      }),
      successDescription,
      'Не удалось изменить оплату',
    );
    closePaymentDialog();
  };

  const handleCreateSuccess = () => {
    loadUsers();
  };

  const normalizedSearchQuery = searchQuery.trim().toLowerCase();
  const pinnedBusinessId = localStorage.getItem('selectedBusinessId') || localStorage.getItem('admin_selected_business_id') || '';
  const filteredUsers = useMemo(
    () => filterUsersBySearch(users, normalizedSearchQuery),
    [users, normalizedSearchQuery],
  );
  const radarBusinessOptions = useMemo(() => {
    const options: Array<{ id: string; name: string; owner: string }> = [];
    users.forEach((user) => {
      const owner = user.email || user.name || 'Владелец не указан';
      (user.direct_businesses || []).forEach((business) => {
        if (!isLeadBusiness(business)) {
          options.push({ id: business.id, name: business.name, owner });
        }
      });
      (user.networks || []).forEach((network) => {
        (network.businesses || []).forEach((business) => {
          if (!isLeadBusiness(business)) {
            options.push({ id: business.id, name: `${business.name} · ${network.name}`, owner });
          }
        });
      });
    });
    return options.sort((a, b) => a.name.localeCompare(b.name, 'ru'));
  }, [users]);

  useEffect(() => {
    if (
      selectedRadarBusinessId === LOCALOS_RADAR_BUSINESS_ID ||
      (selectedRadarBusinessId && radarBusinessOptions.some((item) => item.id === selectedRadarBusinessId))
    ) {
      return;
    }
    const savedBusinessId = localStorage.getItem('selectedBusinessId') || localStorage.getItem('admin_selected_business_id') || '';
    const nextBusinessId = radarBusinessOptions.find((item) => item.id === savedBusinessId)?.id || LOCALOS_RADAR_BUSINESS_ID;
    setSelectedRadarBusinessId(nextBusinessId);
  }, [radarBusinessOptions, selectedRadarBusinessId]);
  const adminStats = useMemo(() => {
    let businessCount = 0;
    let networkCount = 0;
    let pausedUserCount = 0;
    let leadBusinessCount = 0;

    users.forEach((user) => {
      if (user.is_active === 0) {
        pausedUserCount += 1;
      }

      const directBusinesses = user.direct_businesses || [];
      businessCount += directBusinesses.length;
      leadBusinessCount += directBusinesses.filter((business) => isLeadBusiness(business)).length;

      const networks = user.networks || [];
      networkCount += networks.length;
      networks.forEach((network) => {
        const businesses = network.businesses || [];
        businessCount += businesses.length;
        leadBusinessCount += businesses.filter((business) => isLeadBusiness(business)).length;
      });
    });

    return {
      businessCount,
      leadBusinessCount,
      networkCount,
      pausedUserCount,
    };
  }, [users]);
  const activeTabConfig = adminTabs.find((tab) => tab.id === activeTab) || adminTabs[0];
  const agentSummary = agentBlueprintOverview?.summary;
  const agentMetrics = [
    { label: 'Всего агентов', value: String(agentSummary?.total || 0), tone: 'default' },
    { label: 'Высокий риск', value: String(agentSummary?.high_risk || 0), tone: 'warning' },
    { label: 'Средний риск', value: String(agentSummary?.medium_risk || 0), tone: 'warning' },
    { label: 'Активные', value: String(agentSummary?.active || 0), tone: 'positive' },
  ];
  const agentRuntime = agentBlueprintOverview?.runtime;
  const agentRuntimeIssues = Number(agentRuntime?.runs.stale_running || 0)
    + Number(agentRuntime?.runs.failed_24h || 0)
    + Number(agentRuntime?.scheduler.failed_24h || 0)
    + Number(agentRuntime?.consistency.archived_unfinished_runs || 0)
    + Number(agentRuntime?.consistency.waiting_without_pending_approval || 0);
  const agentRuntimeMetrics = [
    {
      label: 'В очереди и работе',
      value: String(Number(agentRuntime?.runs.queued || 0) + Number(agentRuntime?.runs.running || 0)),
      hint: `${agentRuntime?.runs.retry_wait || 0} ожидают повтора`,
      tone: agentRuntime?.runs.stale_running ? 'warning' : 'default',
    },
    {
      label: 'Завершено за сутки',
      value: String(agentRuntime?.runs.completed_24h || 0),
      hint: `${agentRuntime?.runs.failed_24h || 0} ошибок за сутки`,
      tone: agentRuntime?.runs.failed_24h ? 'warning' : 'positive',
    },
    {
      label: 'Запуски расписания',
      value: String(agentRuntime?.scheduler.total_events || 0),
      hint: agentRuntime?.scheduler.last_event_at
        ? `${agentRuntime.scheduler.failed_24h || 0} ошибок · ${agentRuntime.scheduler.deferred_24h || 0} отложено`
        : 'Canary ещё не зафиксирован',
      tone: agentRuntime?.scheduler.failed_24h ? 'warning' : agentRuntime?.scheduler.total_events ? 'positive' : 'warning',
    },
    {
      label: 'Списано кредитов',
      value: String(agentRuntime?.billing.charged_credits || 0),
      hint: `${agentRuntime?.billing.active_reservations || 0} активных резервов`,
      tone: agentRuntime?.billing.active_reservations ? 'warning' : 'positive',
    },
  ];
  const subscriptionSummary = subscriptionsOverview?.summary;
  const subscriptionMetrics = [
    {
      label: 'Активные подписки',
      value: <span className="tabular-nums">{subscriptionSummary?.active_subscriptions || 0}</span>,
      hint: `${subscriptionSummary?.autopay_enabled || 0} с автоплатежом`,
      tone: 'positive',
    },
    {
      label: 'Списания скоро',
      value: <span className="tabular-nums">{subscriptionSummary?.due_soon_7d || 0}</span>,
      hint: `${subscriptionSummary?.overdue || 0} уже просрочены`,
      tone: subscriptionSummary?.overdue ? 'warning' : 'default',
    },
    {
      label: 'Новые пользователи',
      value: <span className="tabular-nums">{subscriptionSummary?.new_users_30d || 0}</span>,
      hint: 'За последние 30 дней',
    },
    {
      label: 'MRR',
      value: <span className="tabular-nums">{formatAdminMoney(subscriptionSummary?.monthly_recurring_revenue, subscriptionSummary?.currency || 'RUB')}</span>,
      hint: `${subscriptionSummary?.churned_or_blocked_30d || 0} отвалились или заблокированы за 30 дней`,
      tone: subscriptionSummary?.churned_or_blocked_30d ? 'warning' : 'default',
    },
  ];
  const formatAdminDate = (value?: string) => {
    if (!value) return 'Дата не указана';
    return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(value));
  };
  const riskLabel = (level: AdminAgentBlueprint['risk_level']) => {
    if (level === 'high') return 'Высокий риск';
    if (level === 'medium') return 'Средний риск';
    return 'Низкий риск';
  };
  const riskClassName = (level: AdminAgentBlueprint['risk_level']) => {
    if (level === 'high') return 'border-red-200 bg-red-50 text-red-700';
    if (level === 'medium') return 'border-amber-200 bg-amber-50 text-amber-800';
    return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  };
  const agentStatusLabel = (status: string) => {
    if (status === 'active') return 'Активен';
    if (status === 'archived') return 'Убран из списка';
    if (status === 'paused') return 'На паузе';
    return 'Черновик';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-4">
          <div className="relative">
            <div className="animate-spin rounded-full h-16 w-16 border-4 border-primary/20 border-t-primary mx-auto"></div>
            <div className="absolute inset-0 rounded-full border-4 border-transparent border-r-primary/40 animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }}></div>
          </div>
          <p className="text-muted-foreground font-medium">Загрузка данных...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50/60">
      <div className="mx-auto flex w-full max-w-[1680px] flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <DashboardPageHeader
          eyebrow="Bazich admin"
          title="Панель администратора"
          description="Единое место для контроля пользователей, бизнесов, агентов, парсинга и операционных настроек."
          icon={Settings}
          actions={(
            <Button
              onClick={() => setShowCreateModal(true)}
              className="rounded-2xl bg-slate-950 px-5 text-white shadow-sm hover:bg-slate-800"
            >
              <Plus className="mr-2 h-4 w-4" />
              Создать аккаунт
            </Button>
          )}
        />

        <DashboardCompactMetricsRow
          items={[
            {
              label: 'Пользователи',
              value: users.length,
              hint: filteredUsers.length === users.length ? 'Всего в панели' : `Показано ${filteredUsers.length}`,
            },
            {
              label: 'Бизнесы',
              value: adminStats.businessCount,
              hint: adminStats.leadBusinessCount > 0 ? `Лид-бизнесы скрыты: ${adminStats.leadBusinessCount}` : 'Рабочие аккаунты',
              tone: 'positive',
            },
            {
              label: 'Сети',
              value: adminStats.networkCount,
              hint: 'Сетевые аккаунты и точки',
            },
            {
              label: 'Требуют внимания',
              value: adminStats.pausedUserCount,
              hint: 'Приостановленные пользователи',
              tone: adminStats.pausedUserCount > 0 ? 'warning' : 'default',
            },
          ]}
        />

        <div className="rounded-[2rem] border border-slate-200/80 bg-white/95 p-2.5 shadow-sm">
          <div className="flex flex-col gap-2">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
              {primaryAdminTabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                const isProspecting = tab.id === 'prospecting';
                const isTelegramRadar = tab.id === 'telegramRadar';
                return (
                  <button
                    key={tab.id}
                    onClick={() => selectAdminTab(tab.id)}
                    className={`flex items-center justify-center gap-2 rounded-[1.4rem] px-4 py-3 text-sm font-semibold transition ${
                      isActive
                        ? isProspecting
                          ? 'bg-orange-500 text-white shadow-sm shadow-orange-200'
                          : isTelegramRadar
                            ? 'bg-sky-600 text-white shadow-sm shadow-sky-200'
                          : 'bg-slate-950 text-white shadow-sm'
                        : isProspecting
                          ? 'bg-orange-50 text-orange-700 hover:bg-orange-100'
                          : isTelegramRadar
                            ? 'bg-sky-50 text-sky-700 hover:bg-sky-100'
                          : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>

            <div className="grid grid-cols-1 gap-2 border-t border-slate-100 pt-2 sm:grid-cols-2 lg:grid-cols-6">
              {toolsAdminTabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => selectAdminTab(tab.id)}
                    className={`flex items-center justify-center gap-2 rounded-[1.2rem] px-3 py-2.5 text-xs font-semibold transition ${
                      isActive
                        ? 'bg-slate-900 text-white shadow-sm'
                        : 'bg-slate-50 text-slate-500 hover:bg-slate-100 hover:text-slate-950'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <Suspense fallback={<AdminTabFallback />}>
        {activeTab === 'subscriptions' ? (
          <DashboardSection
            title="Подписки"
            description="Кто платит, когда следующее списание, есть ли карта для автоплатежа и сколько кредитов осталось у пользователей."
            actions={(
              <Button type="button" variant="outline" onClick={loadSubscriptionsOverview} disabled={subscriptionsLoading}>
                Обновить
              </Button>
            )}
            contentClassName="space-y-6"
          >
            <DashboardCompactMetricsRow items={subscriptionMetrics} />

            <div className="grid gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.55fr)]">
              <div className="rounded-3xl border border-slate-200 bg-white shadow-sm">
                <div className="flex flex-col gap-2 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h3 className="text-base font-semibold text-slate-950">Клиенты и подписки</h3>
                    <p className="text-sm leading-6 text-slate-500">Срок, автоплатёж, остаток кредитов и последний платёжный статус.</p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-semibold text-slate-600 tabular-nums">
                    {subscriptionsOverview?.subscriptions.length || 0} всего
                  </span>
                </div>

                {subscriptionsLoading ? (
                  <div className="px-5 py-10 text-center text-sm text-slate-500">Загружаем подписки...</div>
                ) : !subscriptionsOverview || subscriptionsOverview.subscriptions.length === 0 ? (
                  <div className="px-5 py-6">
                    <DashboardEmptyState
                      title="Подписок пока нет"
                      description="После первой оплаты здесь появятся клиенты, даты списаний, автоплатёж и баланс кредитов."
                    />
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <div className="min-w-[980px]">
                      <div className="grid grid-cols-[minmax(220px,1.2fr)_minmax(170px,0.8fr)_minmax(150px,0.65fr)_minmax(150px,0.65fr)_minmax(130px,0.55fr)_minmax(180px,0.8fr)] gap-3 border-b border-slate-100 bg-slate-50 px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        <div>Клиент</div>
                        <div>Тариф</div>
                        <div>Статус</div>
                        <div>Следующее списание</div>
                        <div>Кредиты</div>
                        <div>Что проверить</div>
                      </div>
                      <div className="divide-y divide-slate-100">
                        {subscriptionsOverview.subscriptions.map((subscription) => (
                          <div
                            key={subscription.id}
                            className="grid grid-cols-[minmax(220px,1.2fr)_minmax(170px,0.8fr)_minmax(150px,0.65fr)_minmax(150px,0.65fr)_minmax(130px,0.55fr)_minmax(180px,0.8fr)] gap-3 px-5 py-4 text-sm"
                          >
                            <div className="min-w-0">
                              <div className="truncate font-semibold text-slate-950">
                                {subscription.business_name || subscription.user_name || subscription.user_email || 'Клиент без названия'}
                              </div>
                              <div className="mt-1 truncate text-xs text-slate-500">{subscription.user_email || 'email не указан'}</div>
                              <div className="mt-2 truncate text-xs text-slate-400">{subscription.id}</div>
                            </div>

                            <div className="min-w-0">
                              <div className="font-semibold text-slate-900">{subscription.tariff_id || 'тариф не указан'}</div>
                              <div className="mt-1 text-xs text-slate-500">
                                {subscription.payment_method_linked ? 'Автоплатёж включён' : 'Карта не привязана'}
                              </div>
                            </div>

                            <div>
                              <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${getSubscriptionStatusClassName(subscription.status)}`}>
                                {getSubscriptionStatusLabel(subscription.status)}
                              </span>
                              {subscription.latest_attempt_status ? (
                                <div className={`mt-2 inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${getBillingAttemptClassName(subscription.latest_attempt_status)}`}>
                                  {getBillingAttemptLabel(subscription.latest_attempt_status)}
                                </div>
                              ) : null}
                            </div>

                            <div className="leading-6 text-slate-700">
                              <div className="font-medium tabular-nums">{formatAdminDateTime(subscription.next_billing_date)}</div>
                              {subscription.next_retry_at ? (
                                <div className="text-xs text-amber-700">retry: {formatAdminDateTime(subscription.next_retry_at)}</div>
                              ) : null}
                            </div>

                            <div className="text-xl font-semibold tracking-tight text-slate-950 tabular-nums">
                              {Number(subscription.credits_balance || 0)}
                            </div>

                            <div className="text-sm leading-6 text-slate-600">
                              <div>{buildSubscriptionAttention(subscription)}</div>
                              {subscription.latest_attempt_error ? (
                                <div className="mt-1 line-clamp-2 text-xs text-rose-600">{subscription.latest_attempt_error}</div>
                              ) : null}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                  <h3 className="text-base font-semibold text-slate-950">Что требует внимания</h3>
                  <div className="mt-4 space-y-3">
                    <div className="flex items-center justify-between rounded-2xl bg-amber-50 px-4 py-3 text-sm">
                      <span className="font-medium text-amber-900">Без карты</span>
                      <span className="font-semibold text-amber-900 tabular-nums">{subscriptionSummary?.missing_payment_method || 0}</span>
                    </div>
                    <div className="flex items-center justify-between rounded-2xl bg-rose-50 px-4 py-3 text-sm">
                      <span className="font-medium text-rose-900">Проблема оплаты</span>
                      <span className="font-semibold text-rose-900 tabular-nums">{subscriptionSummary?.blocked_subscriptions || 0}</span>
                    </div>
                    <div className="flex items-center justify-between rounded-2xl bg-slate-50 px-4 py-3 text-sm">
                      <span className="font-medium text-slate-700">Пользователи всего</span>
                      <span className="font-semibold text-slate-950 tabular-nums">{subscriptionSummary?.users_total || 0}</span>
                    </div>
                  </div>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                  <h3 className="text-base font-semibold text-slate-950">Последние списания</h3>
                  <div className="mt-4 space-y-3">
                    {(subscriptionsOverview?.recent_attempts || []).slice(0, 5).map((attempt) => (
                      <div key={attempt.id} className="rounded-2xl bg-slate-50 px-4 py-3">
                        <div className="flex items-center justify-between gap-3">
                          <span className="truncate text-sm font-semibold text-slate-900">{attempt.business_name || attempt.user_email || 'Клиент'}</span>
                          <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold ${getBillingAttemptClassName(attempt.status)}`}>
                            {getBillingAttemptLabel(attempt.status)}
                          </span>
                        </div>
                        <div className="mt-1 text-xs leading-5 text-slate-500">
                          {attempt.attempt_type || 'payment'} · {formatAdminDateTime(attempt.created_at)}
                        </div>
                        {attempt.error_message ? (
                          <div className="mt-1 line-clamp-2 text-xs text-rose-600">{attempt.error_message}</div>
                        ) : null}
                      </div>
                    ))}
                    {(subscriptionsOverview?.recent_attempts || []).length === 0 ? (
                      <div className="rounded-2xl bg-slate-50 px-4 py-5 text-sm text-slate-500">Попыток списания пока нет.</div>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white shadow-sm">
              <div className="border-b border-slate-100 px-5 py-4">
                <h3 className="text-base font-semibold text-slate-950">Движение кредитов</h3>
                <p className="text-sm leading-6 text-slate-500">Последние начисления и списания, чтобы быстро понять остатки и причины изменения баланса.</p>
              </div>
              <div className="overflow-x-auto">
                <div className="min-w-[860px] divide-y divide-slate-100">
                  {(subscriptionsOverview?.credit_ledger || []).map((entry) => (
                    <div key={entry.id} className="grid grid-cols-[minmax(220px,1fr)_120px_minmax(180px,0.8fr)_minmax(220px,1fr)] gap-3 px-5 py-3 text-sm">
                      <div className="min-w-0">
                        <div className="truncate font-semibold text-slate-950">{entry.business_name || entry.user_email || 'Пользователь'}</div>
                        <div className="truncate text-xs text-slate-500">{entry.user_email || entry.user_id}</div>
                      </div>
                      <div className={`font-semibold tabular-nums ${Number(entry.delta || 0) < 0 ? 'text-rose-700' : 'text-emerald-700'}`}>
                        {Number(entry.delta || 0) > 0 ? '+' : ''}{Number(entry.delta || 0)}
                      </div>
                      <div className="text-slate-700">{entry.reason || 'Причина не указана'}</div>
                      <div className="text-slate-500 tabular-nums">{formatAdminDateTime(entry.created_at)}</div>
                    </div>
                  ))}
                  {(subscriptionsOverview?.credit_ledger || []).length === 0 ? (
                    <div className="px-5 py-8 text-center text-sm text-slate-500">Движения кредитов пока нет.</div>
                  ) : null}
                </div>
              </div>
            </div>
          </DashboardSection>
        ) : activeTab === 'agents' ? (
          <DashboardSection
            title={activeTabConfig.label}
            description="Только просмотр: задача, бизнес, внешние действия, запуски и риск для модерации пользовательских агентов."
            actions={(
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="outline" onClick={loadAgentBlueprintOverview} disabled={agentBlueprintLoading}>
                  Обновить
                </Button>
                <Button type="button" onClick={() => navigate('/dashboard/agents')}>
                  Открыть Мои агенты
                </Button>
              </div>
            )}
            contentClassName="space-y-5"
          >
            <DashboardCompactMetricsRow items={agentMetrics} />

            <div className="border-y border-slate-200 py-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h3 className="text-base font-semibold text-slate-950">Работа агентов</h3>
                  <p className="mt-1 text-sm leading-6 text-slate-600">
                    Очередь, расписание, ошибки и списания. Здесь видно, выполняются ли задачи на самом деле.
                  </p>
                </div>
                <div className={`inline-flex w-fit rounded-full border px-3 py-1 text-xs font-semibold ${agentRuntimeIssues ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>
                  {agentRuntimeIssues ? `Требуют внимания: ${agentRuntimeIssues}` : 'Состояние штатное'}
                </div>
              </div>

              <DashboardCompactMetricsRow items={agentRuntimeMetrics} className="mt-4" />

              <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm text-slate-600">
                <span>Фоновая очередь: <strong className="text-slate-900">{agentRuntime?.flags.async_runs_enabled ? 'включена' : 'выключена'}</strong></span>
                <span>Расписание: <strong className="text-slate-900">{agentRuntime?.flags.schedule_dispatch_enabled ? 'включено' : 'выключено'}</strong></span>
                <span>Beta-бизнесов: <strong className="tabular-nums text-slate-900">{agentRuntime?.flags.beta_businesses_count || 0}</strong></span>
                <span>Активных подключений: <strong className="tabular-nums text-slate-900">{agentRuntime?.integrations.active || 0}</strong></span>
              </div>

              {(agentRuntime?.scheduler.canaries || []).length > 0 ? (
                <div className="mt-4 border-t border-slate-200 pt-4">
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                    <h4 className="text-sm font-semibold text-slate-900">Проверка работы по расписанию</h4>
                    <span className="text-xs text-slate-500">Нужно 7 последовательных дней без пропусков и дублей</span>
                  </div>
                  <div className="mt-2 divide-y divide-slate-100">
                    {(agentRuntime?.scheduler.canaries || []).map((canary) => {
                      const hasIssues = canary.status === 'attention';
                      const passed = canary.status === 'passed';
                      const issueParts = [
                        canary.failed_events ? `${canary.failed_events} ошибок` : '',
                        canary.deferred_events ? `${canary.deferred_events} отложено` : '',
                        canary.duplicate_runs ? `${canary.duplicate_runs} дублей` : '',
                        canary.old_version_runs ? `${canary.old_version_runs} запусков старой версии` : '',
                      ].filter(Boolean);
                      return (
                        <div key={canary.blueprint_id} className="grid gap-2 py-3 text-sm md:grid-cols-[minmax(220px,1fr)_minmax(180px,0.7fr)_minmax(210px,0.9fr)] md:items-center">
                          <div className="min-w-0">
                            <div className="truncate font-semibold text-slate-900">{canary.agent_name}</div>
                            <button type="button" onClick={() => handleBusinessClick(canary.business_id)} className="truncate text-xs text-slate-500 underline-offset-4 hover:underline">
                              {canary.business_name}
                            </button>
                          </div>
                          <div className="text-slate-600 tabular-nums">
                            {canary.schedule_time || 'Время не записано'}
                            <div className="text-xs text-slate-500">{canary.timezone || 'Часовой пояс не записан'}</div>
                          </div>
                          <div>
                            <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${passed ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : hasIssues ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-sky-200 bg-sky-50 text-sky-700'}`}>
                              {passed ? 'Проверка пройдена' : `${canary.successful_days} из ${canary.target_days} дней`}
                            </span>
                            <div className={`mt-1 text-xs ${hasIssues ? 'text-amber-800' : 'text-slate-500'}`}>
                              {passed && canary.last_success_date
                                ? `Последний результат: ${canary.last_success_date}`
                                : issueParts.length > 0
                                  ? issueParts.join(' · ')
                                  : canary.last_success_date
                                    ? `Последний результат: ${canary.last_success_date}`
                                    : 'Ожидаем первый запуск'}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              {(agentRuntime?.consistency.archived_unfinished_runs || agentRuntime?.consistency.waiting_without_pending_approval) ? (
                <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
                  Несогласованные состояния: {agentRuntime.consistency.archived_unfinished_runs} незавершённых запусков архивных агентов и {agentRuntime.consistency.waiting_without_pending_approval} запусков без актуального решения.
                </div>
              ) : null}

              {(agentRuntime?.scheduler.recent_events || []).length > 0 ? (
                <details className="mt-4 border-t border-slate-200 pt-4">
                  <summary className="cursor-pointer text-sm font-semibold text-slate-900">Последние запуски по расписанию</summary>
                  <div className="mt-3 divide-y divide-slate-100">
                    {(agentRuntime?.scheduler.recent_events || []).map((event) => (
                      <div key={event.event_id} className="grid gap-2 py-3 text-sm md:grid-cols-[minmax(180px,0.9fr)_minmax(190px,0.9fr)_minmax(170px,0.75fr)_minmax(220px,1fr)_auto] md:items-center">
                        <div className="min-w-0">
                          <div className="truncate font-semibold text-slate-900">{event.agent_name}</div>
                          <button type="button" onClick={() => handleBusinessClick(event.business_id)} className="truncate text-xs text-slate-500 underline-offset-4 hover:underline">
                            {event.business_name}
                          </button>
                        </div>
                        <div className="text-slate-600 tabular-nums">
                          {event.schedule_date || 'Дата не записана'} {event.schedule_time || ''}
                          <div className="text-xs text-slate-500">{event.timezone || 'Часовой пояс не записан'}</div>
                        </div>
                        <div>
                          <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${event.status === 'run_started' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : event.status === 'deferred' ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-red-200 bg-red-50 text-red-700'}`}>
                            {event.status === 'run_started' ? 'Запущен' : event.status === 'deferred' ? 'Будет повторён' : 'Ошибка'}
                          </span>
                          {event.run_status ? <div className="mt-1 text-xs text-slate-500">Задача: {event.run_status}</div> : null}
                        </div>
                        <div className="break-words text-slate-600">
                          {event.reason_code || (event.run_status === 'completed' ? 'Результат сохранён' : 'Событие принято')}
                          <div className="text-xs text-slate-500 tabular-nums">{formatAdminDateTime(event.created_at)}</div>
                        </div>
                        {event.run_id ? (
                          <Button type="button" size="sm" variant="outline" onClick={() => downloadAgentSupportExport(event.run_id)} disabled={downloadingAgentRunId === event.run_id}>
                            {downloadingAgentRunId === event.run_id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                            Диагностика
                          </Button>
                        ) : <span className="text-xs text-slate-400">Запуск не создан</span>}
                      </div>
                    ))}
                  </div>
                </details>
              ) : null}

              {(agentRuntime?.recent_issues || []).length > 0 ? (
                <details className="mt-4 border-t border-slate-200 pt-4">
                  <summary className="cursor-pointer text-sm font-semibold text-slate-900">Последние ошибки и повторы</summary>
                  <div className="mt-3 divide-y divide-slate-100">
                    {(agentRuntime?.recent_issues || []).map((issue) => (
                      <div key={issue.run_id} className="grid gap-2 py-3 text-sm md:grid-cols-[minmax(180px,0.8fr)_minmax(180px,0.8fr)_minmax(240px,1.3fr)_160px_auto] md:items-center">
                        <div className="min-w-0">
                          <div className="truncate font-semibold text-slate-900">{issue.agent_name}</div>
                          <button type="button" onClick={() => handleBusinessClick(issue.business_id)} className="truncate text-xs text-slate-500 underline-offset-4 hover:underline">
                            {issue.business_name}
                          </button>
                        </div>
                        <div className="text-slate-600">{issue.status} · попыток {issue.attempt_count}</div>
                        <div className="break-words text-slate-700">{issue.error}</div>
                        <div className="tabular-nums text-slate-500">{formatAdminDateTime(issue.updated_at)}</div>
                        <Button type="button" size="sm" variant="outline" onClick={() => downloadAgentSupportExport(issue.run_id)} disabled={downloadingAgentRunId === issue.run_id}>
                          {downloadingAgentRunId === issue.run_id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                          Диагностика
                        </Button>
                      </div>
                    ))}
                  </div>
                </details>
              ) : null}
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700">
              Этот экран нужен LocalOS для модерации и развития продукта: видеть, какие задачи автоматизируют клиенты, где есть внешние отправки или потенциально чувствительные действия, и какие сценарии стоит превращать в готовые шаблоны.
            </div>

            {agentBlueprintLoading ? (
              <div className="rounded-2xl border border-slate-200 bg-white px-5 py-8 text-center text-sm text-slate-500">
                Загружаем агентов...
              </div>
            ) : (agentBlueprintOverview?.agents || []).length === 0 ? (
              <DashboardEmptyState
                title="Пользовательские агенты пока не созданы"
                description="Когда пользователи начнут создавать кастомных агентов, здесь появятся их задачи, бизнесы, интеграции и оценка риска."
              />
            ) : (
              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                <div className="grid grid-cols-[minmax(260px,1.4fr)_minmax(190px,0.9fr)_minmax(170px,0.8fr)_minmax(220px,1fr)_minmax(150px,0.6fr)] gap-3 border-b border-slate-100 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                  <div>Агент</div>
                  <div>Бизнес</div>
                  <div>Риск</div>
                  <div>Данные и действия</div>
                  <div>Активность</div>
                </div>
                <div className="divide-y divide-slate-100">
                  {(agentBlueprintOverview?.agents || []).map((agent) => (
                    <div key={agent.id} className="grid grid-cols-[minmax(260px,1.4fr)_minmax(190px,0.9fr)_minmax(170px,0.8fr)_minmax(220px,1fr)_minmax(150px,0.6fr)] gap-3 px-4 py-4 text-sm">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="truncate font-semibold text-slate-950">{agent.name}</div>
                          <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-semibold text-slate-600">
                            {agentStatusLabel(agent.status)}
                          </span>
                        </div>
                        <div className="mt-1 line-clamp-2 text-slate-600">
                          {agent.latest_goal || agent.description || 'Описание не заполнено'}
                        </div>
                        <div className="mt-2 text-xs text-slate-400">
                          v{agent.latest_version_number || 1} · создан {formatAdminDate(agent.created_at)}
                        </div>
                      </div>

                      <div className="min-w-0">
                        <button
                          type="button"
                          onClick={() => handleBusinessClick(agent.business_id)}
                          className="truncate text-left font-semibold text-slate-900 underline-offset-4 hover:underline"
                        >
                          {agent.business_name}
                        </button>
                        <div className="mt-1 truncate text-xs text-slate-500">{agent.owner_email || agent.creator_email || 'Владелец не указан'}</div>
                      </div>

                      <div>
                        <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${riskClassName(agent.risk_level)}`}>
                          {riskLabel(agent.risk_level)}
                        </span>
                        <div className="mt-2 space-y-1 text-xs leading-5 text-slate-500">
                          {agent.risk_reasons.slice(0, 2).map((reason) => (
                            <div key={reason}>{reason}</div>
                          ))}
                        </div>
                      </div>

                      <div className="text-sm leading-6 text-slate-600">
                        <div>{agent.sources_count} источн. · {agent.integration_count} интегр.</div>
                        <div className="truncate text-xs text-slate-500">
                          {agent.integration_providers || 'Внешние интеграции не найдены'}
                        </div>
                      </div>

                      <div className="text-sm leading-6 text-slate-600">
                        <div>{agent.runs_count} запусков</div>
                        <div className="text-xs text-slate-500">{agent.pending_approvals_count} ожидают согласования</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </DashboardSection>
        ) : activeTab === 'agentApi' ? (
          <DashboardSection
            title={activeTabConfig.label}
            description="Внешние ИИ-подключения: ключи, scopes, ledger и заходы в agent-документацию."
            contentClassName="p-0"
          >
            <AgentApiManagement />
          </DashboardSection>
        ) : activeTab === 'tokens' ? (
          <DashboardSection
            title={activeTabConfig.label}
            description="Расход кредитов, аномалии и контроль нагрузки в одном рабочем блоке."
            contentClassName="p-0"
          >
            <TokenUsageStats />
          </DashboardSection>
        ) : activeTab === 'prompts' ? (
          <DashboardSection
            title={activeTabConfig.label}
            description="Управление промптами анализа и рабочими версиями генерации."
            contentClassName="p-0"
          >
            <PromptsManagement />
          </DashboardSection>
        ) : activeTab === 'patterns' ? (
          <DashboardSection
            title={activeTabConfig.label}
            description="Web-контур HITL для active-паттернов: pending, impact, версии и rollback без деплоя."
            contentClassName="p-0"
          >
            <IndustryPatternsManagement />
          </DashboardSection>
        ) : activeTab === 'proxies' ? (
          <DashboardSection
            title={activeTabConfig.label}
            description="Прокси и технические настройки парсинга в отдельном контуре."
            contentClassName="p-0"
          >
            <ProxyManagement />
          </DashboardSection>
        ) : activeTab === 'parsing' ? (
          <DashboardSection
            title={activeTabConfig.label}
            description="Очереди, источники и статусы сбора данных по картам."
            contentClassName="p-0"
          >
            <ParsingManagement />
          </DashboardSection>
        ) : activeTab === 'prospecting' ? (
          <DashboardSection
            title={activeTabConfig.label}
            description="Один список компаний: продажи LocalOS и партнёры клиентов с раздельными сообщениями, комнатами и результатами."
            contentClassName="p-0"
          >
            <AdminLeadRegistry businessOptions={radarBusinessOptions} senderBusinessLabel="LocalOS" />
          </DashboardSection>
        ) : activeTab === 'knowledge' ? (
          <DashboardSection
            title={activeTabConfig.label}
            description="Проверенные рыночные сигналы, источники и ограничения их использования."
            contentClassName="p-0"
          >
            <KnowledgeMarketOverview />
          </DashboardSection>
        ) : activeTab === 'telegramRadar' ? (
          <DashboardSection
            title={activeTabConfig.label}
            description="Суперадминский доступ к inbox радара: выберите ЛокалОС или клиентский бизнес, проверьте найденные сообщения и статусы."
            actions={(
              <div className="flex w-full flex-col gap-2 sm:w-[420px]">
                <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                  Бизнес
                </label>
                <select
                  value={selectedRadarBusinessId}
                  onChange={(event) => setSelectedRadarBusinessId(event.target.value)}
                  className="h-11 rounded-2xl border border-slate-200 bg-white px-4 text-sm font-medium text-slate-900 outline-none transition focus:border-sky-300 focus:ring-4 focus:ring-sky-100"
                >
                  <option value={LOCALOS_RADAR_BUSINESS_ID}>ЛокалОС</option>
                  {radarBusinessOptions.length === 0 ? (
                    <option value="">Нет доступных бизнесов</option>
                  ) : radarBusinessOptions.map((business) => (
                    <option key={business.id} value={business.id}>
                      {business.name} · {business.owner}
                    </option>
                  ))}
                </select>
              </div>
            )}
            contentClassName="p-0"
          >
            <TelegramOpportunityRadar businessId={selectedRadarBusinessId || null} mode="work" />
          </DashboardSection>
        ) : (
          <>
            {(() => {
              return (
                <>
            <DashboardSection
              title="Пользователи и бизнесы"
              description="Сначала найдите аккаунт, затем откройте бизнес или управляйте доступом прямо из строки."
              actions={(
                <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-center">
                  <div className="relative w-full sm:w-[360px]">
                    <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <input
                      value={searchQuery}
                      onChange={(event) => setSearchQuery(event.target.value)}
                      placeholder="Поиск по бизнесу, адресу или email"
                      className="h-11 w-full rounded-2xl border border-slate-200 bg-white pl-11 pr-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:ring-4 focus:ring-slate-100"
                    />
                  </div>
                  <Button
                    onClick={() => setShowCreateModal(true)}
                    variant="outline"
                    className="h-11 rounded-2xl border-slate-200 bg-white px-4 text-slate-800 shadow-sm hover:bg-slate-50"
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    Новый аккаунт
                  </Button>
                </div>
              )}
              contentClassName="space-y-5"
            >
              {filteredUsers.length === 0 ? (
                <DashboardEmptyState
                  title="Пользователи не найдены"
                  description={normalizedSearchQuery ? 'Попробуйте изменить запрос или очистить поиск.' : 'Создайте первый аккаунт, чтобы добавить бизнес и подключить рабочие кабинеты.'}
                  action={(
                    <Button
                      onClick={() => setShowCreateModal(true)}
                      variant="outline"
                      className="rounded-2xl"
                    >
                      <Plus className="mr-2 h-4 w-4" />
                      Создать аккаунт
                    </Button>
                  )}
                />
              ) : (
                filteredUsers.map((user) => {
                  const allBusinesses: BusinessListItem[] = [];

                  // Добавляем прямые бизнесы (включая заблокированные)
                  const directBusinesses = user.direct_businesses || [];
                  directBusinesses.forEach(business => {
                    allBusinesses.push({
                      id: business.id,
                      name: business.name,
                      type: 'direct',
                      business
                    });
                  });

                  // Добавляем сети (каждая сеть - одна строка, бизнесы внутри раскрываются)
                  user.networks.forEach(network => {
                    const networkBusinesses = network.businesses || [];
                    // Добавляем сеть как отдельный элемент (показываем первый бизнес или название сети)
                    if (networkBusinesses.length > 0) {
                      allBusinesses.push({
                        id: network.id,
                        name: network.name,
                        type: 'network',
                        networkId: network.id,
                        networkName: network.name,
                        business: networkBusinesses[0] // Используем первый бизнес для отображения в строке
                      });
                    }
                  });

                  const regularBusinesses = allBusinesses.filter((item) => !isLeadBusiness(item.business));
                  const matchedBusinesses = regularBusinesses.filter((item) => {
                    if (!normalizedSearchQuery) {
                      return true;
                    }
                    const haystack = [
                      item.name || '',
                      item.networkName || '',
                      item.business.address || '',
                      item.business.description || '',
                      item.business.id || '',
                    ].join(' ').toLowerCase();
                    return haystack.includes(normalizedSearchQuery);
                  });
                  const visibleBusinesses = [...matchedBusinesses].sort((left, right) => {
                    const leftPinned = left.business.id === pinnedBusinessId ? 1 : 0;
                    const rightPinned = right.business.id === pinnedBusinessId ? 1 : 0;
                    return rightPinned - leftPinned;
                  });
                  if (visibleBusinesses.length === 0) {
                    return null;
                  }

                  const renderBusinessItems = (items: BusinessListItem[]) => items.map((item, index) => (
                    <div
                      key={`${item.id}-${index}`}
                      className="group relative"
                    >
                      {item.type === 'network' ? (
                        <div className="space-y-3">
                          {(() => {
                            const networkId = item.networkId || '';
                            const networkName = item.networkName || item.name;
                            const networkBusinesses = user.networks.find((network) => network.id === networkId)?.businesses || [];
                            const networkPaymentState = getNetworkPaymentState(networkBusinesses);
                            return (
                              <div
                                className="flex cursor-pointer flex-col gap-4 rounded-3xl border border-slate-200 bg-slate-50/70 p-4 transition hover:border-slate-300 hover:bg-white sm:flex-row sm:items-center sm:justify-between"
                                onClick={() => toggleNetwork(networkId)}
                              >
                                <div className="flex min-w-0 items-center gap-3">
                                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-slate-900 text-white">
                                    <Network className="h-4 w-4" />
                                  </div>
                                  <div className="min-w-0">
                                    <div className="flex flex-wrap items-center gap-2">
                                      <h4 className="break-words font-semibold text-slate-950">{networkName}</h4>
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={(event) => {
                                          event.stopPropagation();
                                          openNetworkPaymentDialog(networkId, networkName, networkBusinesses);
                                        }}
                                        className={`h-7 rounded-full px-2.5 text-xs ${networkPaymentState.allPaid ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100' : 'bg-white text-slate-500 hover:bg-slate-100'}`}
                                        title="Управлять оплатой сети"
                                      >
                                        <CreditCard className="mr-1.5 h-3.5 w-3.5" />
                                        {networkPaymentState.allPaid
                                          ? 'Оплачено сеть'
                                          : networkPaymentState.paidCount > 0
                                            ? `Оплачено ${networkPaymentState.paidCount}/${networkPaymentState.totalCount}`
                                            : 'Отметить оплату'}
                                      </Button>
                                    </div>
                                    <p className="text-xs font-medium text-slate-500">
                                      {networkBusinesses.length} точек сети
                                    </p>
                                  </div>
                                </div>
                                <div className="flex items-center gap-1.5" onClick={(event) => event.stopPropagation()}>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-9 w-9 rounded-full p-0 text-slate-500 hover:bg-white hover:text-slate-950"
                                    onClick={() => toggleNetwork(networkId)}
                                  >
                                    {expandedNetworks.has(networkId) ? (
                                      <ChevronDown className="h-4 w-4" />
                                    ) : (
                                      <ChevronRight className="h-4 w-4" />
                                    )}
                                  </Button>
                                </div>
                              </div>
                            );
                          })()}
                          {expandedNetworks.has(item.networkId || '') && (
                            <div className="space-y-2 border-l border-slate-200 pl-4 sm:ml-5">
                              {user.networks.find((network) => network.id === item.networkId)?.businesses.map((business) => (
                                <BusinessCard
                                  key={business.id}
                                  business={business}
                                  isPinned={business.id === pinnedBusinessId}
                                  onSettingsClick={() => setSettingsModal({
                                    isOpen: true,
                                    businessId: business.id,
                                    businessName: business.name,
                                  })}
                                  onPaymentClick={() => openBusinessPaymentDialog(business)}
                                  onBlockClick={() => handleBlock(business.id, business.name, business.is_active === 1)}
                                  onDeleteClick={() => handleDelete(business.id, business.name)}
                                  onClick={() => handleBusinessClick(business.id)}
                                />
                              ))}
                            </div>
                          )}
                        </div>
                      ) : (
                        <BusinessCard
                          business={item.business}
                          isPinned={item.business.id === pinnedBusinessId}
                          onSettingsClick={() => setSettingsModal({
                            isOpen: true,
                            businessId: item.business.id,
                            businessName: item.name,
                          })}
                          onPaymentClick={() => openBusinessPaymentDialog(item.business)}
                          onBlockClick={() => handleBlock(item.business.id, item.name, item.business.is_active === 1)}
                          onDeleteClick={() => handleDelete(item.business.id, item.name)}
                          onClick={() => handleBusinessClick(item.business.id)}
                        />
                      )}
                    </div>
                  ));

                  return (
                    <Card
                      key={user.id}
                      className="overflow-hidden rounded-3xl border-slate-200/80 bg-white shadow-sm transition hover:border-slate-300 hover:shadow-md"
                    >
                      <CardHeader className="border-b border-slate-100 px-5 py-4">
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                          <div className="flex min-w-0 items-center gap-3">
                            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-slate-100 text-slate-700">
                              <User className="h-5 w-5" />
                            </div>
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <h3 className={`break-words text-lg font-semibold ${user.is_active === 0 ? 'text-slate-400 line-through' : 'text-slate-950'}`}>
                                  {user.name || user.email}
                                </h3>
                                {user.is_superadmin && (
                                  <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-semibold text-indigo-700">
                                    Админ
                                  </span>
                                )}
                                {user.is_active === 0 && (
                                  <span className="rounded-full bg-rose-50 px-2 py-0.5 text-xs font-semibold text-rose-700">
                                    Приостановлен
                                  </span>
                                )}
                                {user.password_setup_required && user.is_active !== 0 && (
                                  <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700">
                                    Нужен пароль
                                  </span>
                                )}
                              </div>
                              <p className="mt-0.5 truncate text-sm text-slate-500">{user.email}</p>
                            </div>
                          </div>
                          <div className="flex flex-wrap items-center gap-2 lg:justify-end">
                            <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                              {visibleBusinesses.length} {visibleBusinesses.length === 1 ? 'бизнес' : 'бизнесов'}
                            </div>
                            <div className="flex items-center gap-1 rounded-full border border-slate-200 bg-white p-1">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 rounded-full p-0 text-slate-500 hover:bg-slate-100 hover:text-slate-950"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handlePauseUser(user.id, user.email, user.is_active !== 0);
                                }}
                                title={user.is_active === 0 ? "Возобновить пользователя" : "Приостановить пользователя"}
                              >
                                {user.is_active === 0 ? (
                                  <User className="h-4 w-4" />
                                ) : (
                                  <Ban className="h-4 w-4" />
                                )}
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 rounded-full p-0 text-amber-600 hover:bg-amber-50 hover:text-amber-700 disabled:cursor-not-allowed disabled:opacity-40"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleSendPasswordSetup(user.id, user.email);
                                }}
                                disabled={!user.password_setup_required || user.is_active === 0}
                                title={user.password_setup_required ? "Отправить ссылку установки пароля" : "Пароль уже установлен"}
                              >
                                <KeyRound className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 rounded-full p-0 text-rose-500 hover:bg-rose-50 hover:text-rose-700"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteUser(user.id, user.email);
                                }}
                                title="Удалить пользователя"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="px-5 py-5">
                        <div className="space-y-4">
                          {renderBusinessItems(visibleBusinesses)}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })
              )}
            </DashboardSection>
                </>
              );
            })()}
          </>
        )}
        </Suspense>
      </div>

      <CreateBusinessModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSuccess={handleCreateSuccess}
      />

      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        title={confirmDialog.title}
        message={confirmDialog.message}
        confirmText={confirmDialog.confirmText}
        cancelText={confirmDialog.cancelText}
        onConfirm={confirmDialog.onConfirm}
        onCancel={() => setConfirmDialog({ ...confirmDialog, isOpen: false })}
        variant={confirmDialog.variant}
      />

      {paymentDialog.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm animate-in fade-in duration-200">
          <Card className="w-full max-w-lg border-0 shadow-2xl animate-in zoom-in-95 duration-200">
            <CardHeader className="border-b border-slate-100">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <CardTitle className="text-xl">
                    {paymentDialog.scope === 'network' ? 'Оплата сети' : 'Оплата точки'}
                  </CardTitle>
                  <p className="mt-1 text-sm text-slate-500">{paymentDialog.targetName}</p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={closePaymentDialog}
                  className="rounded-full"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-5 p-6">
              {paymentDialog.scope === 'network' && (
                <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
                  Сейчас оплачено {paymentDialog.paidCount} из {paymentDialog.totalCount} точек сети.
                </div>
              )}

              <div className="space-y-3">
                <label className="text-sm font-semibold text-slate-700">Период оплаты</label>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {PAYMENT_PERIODS.map((period) => (
                    <Button
                      key={period.months}
                      type="button"
                      variant="outline"
                      className="h-10 rounded-xl"
                      onClick={() => applyPaymentPeriod(period.months)}
                    >
                      {period.label}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700" htmlFor="subscription-end-date">
                  Действует до
                </label>
                <div className="relative">
                  <CalendarDays className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input
                    id="subscription-end-date"
                    type="date"
                    value={paymentDialog.endsAt}
                    onChange={(event) => updatePaymentEndDate(event.target.value)}
                    className="h-11 w-full rounded-xl border border-slate-200 bg-white pl-10 pr-3 text-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                  />
                </div>
              </div>

              <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
                <Button
                  variant="outline"
                  onClick={() => submitPaymentDialog(false)}
                  className="rounded-xl text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                >
                  Отключить оплату
                </Button>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={closePaymentDialog} className="rounded-xl">
                    Отмена
                  </Button>
                  <Button onClick={() => submitPaymentDialog(true)} className="rounded-xl">
                    Отметить оплату
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Модальное окно настроек внешних кабинетов */}
      {settingsModal.isOpen && settingsModal.businessId && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
          <Card className="max-w-4xl w-full max-h-[90vh] overflow-hidden shadow-2xl border-0 animate-in zoom-in-95 duration-200">
            <CardHeader className="border-b border-border/50 bg-gradient-to-r from-card to-card/50">
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle className="text-2xl">Настройки внешних кабинетов</CardTitle>
                  <p className="text-sm text-muted-foreground mt-1">{settingsModal.businessName}</p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setSettingsModal({ isOpen: false, businessId: null, businessName: '' })}
                  className="rounded-full"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="overflow-y-auto max-h-[calc(90vh-120px)] p-6">
              {settingsModal.businessId && (
                <AdminExternalCabinetSettings
                  businessId={settingsModal.businessId}
                  businessName={settingsModal.businessName}
                />
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

// Business Card Component
interface BusinessCardProps {
  business: Business;
  isPinned?: boolean;
  onSettingsClick: () => void;
  onPaymentClick: () => void;
  onBlockClick: () => void;
  onDeleteClick: () => void;
  onClick: () => void;
}

const BusinessCard: React.FC<BusinessCardProps> = ({
  business,
  isPinned = false,
  onSettingsClick,
  onPaymentClick,
  onBlockClick,
  onDeleteClick,
  onClick,
}) => {
  const isBlocked = business.is_active === 0;
  const isPaid = isBusinessSubscriptionPaid(business);
  const subscriptionEndLabel = getSubscriptionEndLabel(business.subscription_ends_at);

  return (
    <div
      className="group relative cursor-pointer rounded-3xl border border-slate-200 bg-white p-4 transition hover:border-slate-300 hover:bg-slate-50/60"
      onClick={onClick}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
              <Building2 className="h-4 w-4" />
            </div>
            <h4 className={`break-words font-semibold ${isBlocked ? 'text-slate-400 line-through' : 'text-slate-950'}`}>
              {business.name}
            </h4>
            {isBlocked && (
              <span className="rounded-full bg-rose-50 px-2 py-0.5 text-xs font-semibold text-rose-700">
                Заблокирован
              </span>
            )}
            {isPaid && (
              <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">
                {subscriptionEndLabel ? `Оплачено до ${subscriptionEndLabel}` : 'Оплачено'}
              </span>
            )}
            {isPinned && (
              <span className="rounded-full bg-sky-50 px-2 py-0.5 text-xs font-semibold text-sky-700">
                Выбран сейчас
              </span>
            )}
          </div>
          {business.address && (
            <div className="ml-10 flex items-center gap-1.5 text-sm text-slate-500">
              <MapPin className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{business.address}</span>
            </div>
          )}
        </div>
        <div
          className="flex w-full items-center justify-end gap-1 rounded-2xl border border-slate-200 bg-slate-50 p-1 lg:w-auto"
          onClick={(event) => event.stopPropagation()}
        >
          <Button
            variant="ghost"
            size="sm"
            onClick={onSettingsClick}
            className="h-8 w-8 rounded-xl p-0 text-slate-500 hover:bg-white hover:text-slate-950"
            title="Настройки"
          >
            <Settings className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onPaymentClick}
            className={`h-8 w-8 rounded-xl p-0 ${isPaid ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-100' : 'text-slate-500 hover:bg-white hover:text-slate-950'}`}
            title="Управлять оплатой"
          >
            <CreditCard className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onBlockClick}
            className={`h-8 w-8 rounded-xl p-0 ${!isBlocked ? 'text-slate-500 hover:bg-rose-50 hover:text-rose-700' : 'text-emerald-600 hover:bg-white hover:text-emerald-700'}`}
            title={isBlocked ? 'Разблокировать' : 'Заблокировать'}
          >
            <Ban className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onDeleteClick}
            className="h-8 w-8 rounded-xl p-0 text-rose-500 hover:bg-rose-50 hover:text-rose-700"
            title="Удалить"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};
