import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Bot, CheckCircle2, Copy, KeyRound, RefreshCcw, ShieldCheck, Terminal, Activity } from 'lucide-react';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { useToast } from '../hooks/use-toast';
import { newAuth } from '../lib/auth_new';

interface AgentClient {
  id: string;
  organization_name: string;
  contact_email: string;
  status: string;
  allowed_scopes: string[];
  rate_limits?: Record<string, unknown>;
  metadata_json?: {
    telegram_bot_username?: string;
    telegram_bot_id?: string;
  };
  created_at?: string;
  updated_at?: string;
  last_seen_at?: string | null;
}

interface TelegramSender {
  username?: string;
  telegram_id?: string;
  sender_type?: string;
  chat_id?: string;
  message_id?: string;
}

interface LedgerItem {
  id: string;
  agent_client_id?: string;
  business_id?: string;
  action_type: string;
  capability?: string;
  required_scope?: string;
  risk_level: string;
  status: string;
  reason_code?: string;
  input_summary?: unknown;
  output_summary?: unknown;
  metadata_json?: {
    sender?: TelegramSender;
    agent_client_status?: string;
    transport_reason?: string;
  };
  created_at?: string;
}

interface DiscoveryItem {
  id: string;
  event_type: string;
  path: string;
  method: string;
  status_code?: number;
  agent_family: string;
  user_agent?: string;
  created_at?: string;
}

interface DiscoverySummary {
  docs_views?: number;
  machine_docs?: number;
  api_hits?: number;
}

interface SelfTestResult {
  ledger_id?: string;
  self_test?: {
    client?: {
      client_id?: string;
      organization_name?: string;
      status?: string;
      allowed_scopes?: string[];
    };
    available?: {
      read_scopes?: string[];
      draft_scopes?: string[];
      can_create_approval_request?: boolean;
      can_request_publish_approval?: boolean;
    };
    next_steps?: string[];
  };
}

const statusLabels: Record<string, string> = {
  sandbox: 'Sandbox',
  live: 'Live',
  suspended: 'Suspended',
};

const statusClassName = (status: string) => {
  if (status === 'live') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (status === 'suspended') return 'border-rose-200 bg-rose-50 text-rose-700';
  return 'border-amber-200 bg-amber-50 text-amber-700';
};

const formatDateTime = (value?: string | null) => {
  if (!value) return 'нет данных';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const normalizeScopesText = (scopes: string[]) => scopes.join('\n');

const extractTelegramSender = (item: LedgerItem): TelegramSender => {
  const metadataSender = item.metadata_json?.sender;
  if (metadataSender) return metadataSender;
  if (item.input_summary && typeof item.input_summary === 'object') {
    const input = Object(item.input_summary);
    if ('username' in input || 'telegram_id' in input) {
      return {
        username: typeof input.username === 'string' ? input.username : '',
        telegram_id: typeof input.telegram_id === 'string' ? input.telegram_id : '',
        sender_type: typeof input.sender_type === 'string' ? input.sender_type : '',
        chat_id: typeof input.chat_id === 'string' ? input.chat_id : '',
        message_id: typeof input.message_id === 'string' ? input.message_id : '',
      };
    }
  }
  return {};
};

export const AgentApiManagement = () => {
  const [clients, setClients] = useState<AgentClient[]>([]);
  const [ledger, setLedger] = useState<LedgerItem[]>([]);
  const [discovery, setDiscovery] = useState<DiscoveryItem[]>([]);
  const [summary, setSummary] = useState<DiscoverySummary>({});
  const [loading, setLoading] = useState(true);
  const [newKey, setNewKey] = useState('');
  const [form, setForm] = useState({
    organization_name: '',
    contact_email: '',
    telegram_bot_username: '',
    telegram_bot_id: '',
    allowed_scopes: 'audit:read\nservices:draft\nreviews:draft\ncontent:draft\nfinance:read\npartners:read\napprovals:create\npublish:request',
  });
  const [editingScopes, setEditingScopes] = useState<Record<string, string>>({});
  const [telegramBindings, setTelegramBindings] = useState<Record<string, { username: string; botId: string }>>({});
  const [promotionNotes, setPromotionNotes] = useState<Record<string, string>>({});
  const [selfTestKey, setSelfTestKey] = useState('');
  const [selfTestResult, setSelfTestResult] = useState<SelfTestResult | null>(null);
  const [ledgerFilter, setLedgerFilter] = useState<'all' | 'self_test'>('all');
  const { toast } = useToast();

  const metrics = useMemo(() => {
    const live = clients.filter((client) => client.status === 'live').length;
    const sandbox = clients.filter((client) => client.status === 'sandbox').length;
    const suspended = clients.filter((client) => client.status === 'suspended').length;
    const pending = ledger.filter((item) => item.status === 'pending_human').length;
    const denied = ledger.filter((item) => item.status === 'denied').length;
    const selfTests = ledger.filter((item) => item.action_type === 'agent_api_self_test').length;
    const promotionRequests = ledger.filter((item) => item.action_type === 'agent_client_promotion_request').length;
    return { live, sandbox, suspended, pending, denied, selfTests, promotionRequests };
  }, [clients, ledger]);

  const telegramEvents = useMemo(
    () => ledger.filter((item) => item.action_type === 'telegram_agent_transport_message'),
    [ledger],
  );

  const telegramMetrics = useMemo(() => {
    const unbound = telegramEvents.filter((item) => !item.agent_client_id).length;
    const blocked = telegramEvents.filter((item) => item.status === 'denied').length;
    const sandbox = telegramEvents.filter((item) => item.reason_code === 'TELEGRAM_AGENT_TRANSPORT_SANDBOX').length;
    return { total: telegramEvents.length, unbound, blocked, sandbox };
  }, [telegramEvents]);

  const visibleLedger = useMemo(() => {
    if (ledgerFilter === 'self_test') {
      return ledger.filter((item) => item.action_type === 'agent_api_self_test');
    }
    return ledger;
  }, [ledger, ledgerFilter]);

  const apiRequest = async (url: string, options?: RequestInit) => {
    const token = await newAuth.getToken();
    const headers = new Headers(options?.headers || {});
    headers.set('Authorization', `Bearer ${token}`);
    if (options?.body) {
      headers.set('Content-Type', 'application/json');
    }
    return fetch(url, { ...options, headers });
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const [clientsResponse, ledgerResponse, discoveryResponse] = await Promise.all([
        apiRequest('/api/agent-api/clients'),
        apiRequest('/api/agent-api/ledger?limit=80'),
        apiRequest('/api/agent-api/discovery?limit=80'),
      ]);
      const clientsData = await clientsResponse.json();
      const ledgerData = await ledgerResponse.json();
      const discoveryData = await discoveryResponse.json();
      setClients(clientsData.clients || []);
      setLedger(ledgerData.items || []);
      setDiscovery(discoveryData.items || []);
      setSummary(discoveryData.summary_24h || {});
      setEditingScopes((previous) => {
        const next: Record<string, string> = {};
        for (const client of clientsData.clients || []) {
          next[client.id] = previous[client.id] || normalizeScopesText(client.allowed_scopes || []);
        }
        return next;
      });
      setTelegramBindings((previous) => {
        const next: Record<string, { username: string; botId: string }> = {};
        for (const client of clientsData.clients || []) {
          const metadata = client.metadata_json || {};
          next[client.id] = previous[client.id] || {
            username: metadata.telegram_bot_username || '',
            botId: metadata.telegram_bot_id || '',
          };
        }
        return next;
      });
    } catch (error) {
      toast({
        title: 'Не удалось загрузить Agent API',
        description: 'Проверьте backend и миграцию agent security.',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const parseScopes = (value: string) =>
    value
      .split(/\n|,/)
      .map((item) => item.trim().toLowerCase())
      .filter(Boolean);

  const buildQuickstart = (agentKey = '$LOCALOS_AGENT_KEY') => `# LocalOS Agent API quickstart

curl -s "https://localos.pro/api/agent-api/security/policy"

curl -s -X POST "https://localos.pro/api/agent-api/self-test" \\
  -H "X-LocalOS-Agent-Key: ${agentKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"purpose":"sandbox onboarding","checks":["auth","scopes","ledger"]}'

curl -s -X POST "https://localos.pro/api/agent-api/approvals/request" \\
  -H "X-LocalOS-Agent-Key: ${agentKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"action_type":"test_publish_review_reply","capability":"reviews.reply.publish","risk_level":"high","requested_scope":"publish:request","input_summary":{"source":"sandbox quickstart"},"proposed_output":"Test approval request only."}'

curl -s -X POST "https://localos.pro/api/agent-api/clients/promotion/request" \\
  -H "X-LocalOS-Agent-Key: ${agentKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"requested_scopes":["audit:read","reviews:draft","approvals:create"],"use_case":"Read audits and draft review replies under human approval.","contact":"ops@example.com"}'
`;

  const copyQuickstart = async (agentKey = '') => {
    try {
      await navigator.clipboard.writeText(buildQuickstart(agentKey || '$LOCALOS_AGENT_KEY'));
      toast({ title: 'Quickstart скопирован', description: 'Вставьте agent_key перед отправкой внешнему агенту.' });
    } catch (error) {
      toast({
        title: 'Не удалось скопировать',
        description: error instanceof Error ? error.message : 'Скопируйте quickstart вручную',
        variant: 'destructive',
      });
    }
  };

  const runSelfTest = async () => {
    const key = selfTestKey.trim();
    if (!key) {
      toast({ title: 'Нужен agent_key', description: 'Вставьте ключ sandbox/live клиента.', variant: 'destructive' });
      return;
    }
    try {
      const response = await fetch('/api/agent-api/self-test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-LocalOS-Agent-Key': key,
        },
        body: JSON.stringify({
          purpose: 'admin sandbox onboarding self-test',
          checks: ['auth', 'scopes', 'ledger'],
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Self-test failed');
      }
      setSelfTestResult(data);
      toast({ title: 'Self-test прошёл', description: 'Событие записано в ledger.' });
      loadData();
    } catch (error) {
      toast({
        title: 'Self-test не прошёл',
        description: error instanceof Error ? error.message : 'Проверьте ключ и статус клиента',
        variant: 'destructive',
      });
    }
  };

  const createClient = async () => {
    try {
      const response = await apiRequest('/api/agent-api/clients', {
        method: 'POST',
        body: JSON.stringify({
          organization_name: form.organization_name,
          contact_email: form.contact_email,
          telegram_bot_username: form.telegram_bot_username,
          telegram_bot_id: form.telegram_bot_id,
          allowed_scopes: parseScopes(form.allowed_scopes),
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Не удалось создать клиента');
      }
      setNewKey(data.client?.agent_key || '');
      setForm((previous) => ({ ...previous, organization_name: '', contact_email: '', telegram_bot_username: '', telegram_bot_id: '' }));
      toast({ title: 'Agent client создан', description: 'Ключ показан один раз. Сохраните его сейчас.' });
      loadData();
    } catch (error) {
      toast({
        title: 'Ошибка создания',
        description: error instanceof Error ? error.message : 'Не удалось создать клиента',
        variant: 'destructive',
      });
    }
  };

  const updateClient = async (client: AgentClient, status?: string) => {
    try {
      const response = await apiRequest(`/api/agent-api/clients/${client.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          status: status || client.status,
          allowed_scopes: parseScopes(editingScopes[client.id] || ''),
          telegram_bot_username: telegramBindings[client.id]?.username || '',
          telegram_bot_id: telegramBindings[client.id]?.botId || '',
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Не удалось обновить клиента');
      }
      toast({ title: 'Agent client обновлён' });
      loadData();
    } catch (error) {
      toast({
        title: 'Ошибка обновления',
        description: error instanceof Error ? error.message : 'Не удалось обновить клиента',
        variant: 'destructive',
      });
    }
  };

  const rotateKey = async (client: AgentClient) => {
    try {
      const response = await apiRequest(`/api/agent-api/clients/${client.id}/rotate-key`, { method: 'POST' });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Не удалось перевыпустить ключ');
      }
      setNewKey(data.client?.agent_key || '');
      toast({ title: 'Ключ перевыпущен', description: 'Новый ключ показан один раз.' });
      loadData();
    } catch (error) {
      toast({
        title: 'Ошибка rotate key',
        description: error instanceof Error ? error.message : 'Не удалось перевыпустить ключ',
        variant: 'destructive',
      });
    }
  };

  const decidePromotion = async (client: AgentClient, decision: 'approve' | 'reject') => {
    try {
      const response = await apiRequest(`/api/agent-api/clients/${client.id}/promotion/decide`, {
        method: 'POST',
        body: JSON.stringify({
          decision,
          allowed_scopes: parseScopes(editingScopes[client.id] || ''),
          note: promotionNotes[client.id] || '',
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Не удалось принять решение');
      }
      toast({
        title: decision === 'approve' ? 'Live-доступ выдан' : 'Promotion отклонён',
        description: 'Решение записано в ledger и отправлено суперадмину в Telegram.',
      });
      setPromotionNotes((previous) => ({ ...previous, [client.id]: '' }));
      loadData();
    } catch (error) {
      toast({
        title: 'Ошибка promotion flow',
        description: error instanceof Error ? error.message : 'Не удалось принять решение',
        variant: 'destructive',
      });
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
            <ShieldCheck className="h-4 w-4" />
            Agent API control
          </div>
          <h2 className="mt-2 text-2xl font-semibold text-slate-950">Доступ ИИ-агентов</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">
            Клиенты API, scopes, последние действия и заходы в agent-документацию. Опасные действия остаются через human approval.
          </p>
        </div>
        <Button variant="outline" onClick={loadData} disabled={loading} className="rounded-2xl">
          <RefreshCcw className="mr-2 h-4 w-4" />
          Обновить
        </Button>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <Card className="rounded-2xl border-slate-200 shadow-none">
          <CardContent className="p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Клиенты</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{clients.length}</div>
            <div className="mt-1 text-xs text-slate-500">live {metrics.live} · sandbox {metrics.sandbox} · suspended {metrics.suspended}</div>
          </CardContent>
        </Card>
        <Card className="rounded-2xl border-slate-200 shadow-none">
          <CardContent className="p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Docs 24ч</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{summary.docs_views || 0}</div>
            <div className="mt-1 text-xs text-slate-500">agent-файлы {summary.machine_docs || 0}</div>
          </CardContent>
        </Card>
        <Card className="rounded-2xl border-slate-200 shadow-none">
          <CardContent className="p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">API 24ч</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{summary.api_hits || 0}</div>
            <div className="mt-1 text-xs text-slate-500">попытки обращения к Agent API</div>
          </CardContent>
        </Card>
        <Card className="rounded-2xl border-slate-200 shadow-none">
          <CardContent className="p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Approval</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{metrics.pending}</div>
            <div className="mt-1 text-xs text-slate-500">self-test {metrics.selfTests} · promotion {metrics.promotionRequests}</div>
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-2xl border-slate-200 shadow-none">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5" />
            Как подключить агента
          </CardTitle>
          <CardDescription>
            Минимальный безопасный flow: sandbox client → agent_key → self-test → test approval request → ledger.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 xl:grid-cols-[1fr_1fr]">
          <div className="grid gap-3 sm:grid-cols-5">
            {[
              'Создать sandbox client',
              'Сохранить agent_key',
              'Вызвать security policy',
              'Сделать test approval',
              'Проверить ledger',
            ].map((step, index) => (
              <div key={step} className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Шаг {index + 1}</div>
                <div className="mt-1 text-sm font-medium text-slate-900">{step}</div>
              </div>
            ))}
          </div>
          <div className="space-y-3 rounded-2xl border border-slate-200 p-4">
            <div className="grid gap-2 md:grid-cols-[1fr_auto_auto]">
              <Input
                value={selfTestKey}
                onChange={(event) => setSelfTestKey(event.target.value)}
                placeholder="Вставьте agent_key для self-test"
              />
              <Button variant="outline" onClick={() => copyQuickstart(selfTestKey)}>
                <Copy className="mr-2 h-4 w-4" />
                Quickstart
              </Button>
              <Button onClick={runSelfTest}>Проверить ключ</Button>
            </div>
            {selfTestResult ? (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-950">
                <div className="font-semibold">
                  {selfTestResult.self_test?.client?.organization_name || 'Agent'} · {selfTestResult.self_test?.client?.status || 'status'}
                </div>
                <div className="mt-1">
                  Scopes: {(selfTestResult.self_test?.client?.allowed_scopes || []).join(', ') || 'нет'}
                </div>
                <div className="mt-1 text-emerald-800">Ledger: {selfTestResult.ledger_id || 'записан'}</div>
              </div>
            ) : (
              <div className="text-sm text-slate-500">
                Self-test безопасен: он только проверяет ключ и пишет служебную запись в ledger.
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="rounded-2xl border-slate-200 shadow-none">
        <CardHeader>
          <CardTitle>Telegram transport</CardTitle>
          <CardDescription>
            Bot-to-bot события не идут в обычную автоматизацию: сначала binding, ledger и approval flow.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-2xl border border-slate-200 p-3">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">События</div>
              <div className="mt-1 text-xl font-semibold text-slate-950">{telegramMetrics.total}</div>
            </div>
            <div className="rounded-2xl border border-slate-200 p-3">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Без binding</div>
              <div className="mt-1 text-xl font-semibold text-slate-950">{telegramMetrics.unbound}</div>
            </div>
            <div className="rounded-2xl border border-slate-200 p-3">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Blocked</div>
              <div className="mt-1 text-xl font-semibold text-slate-950">{telegramMetrics.blocked}</div>
            </div>
            <div className="rounded-2xl border border-slate-200 p-3">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Sandbox</div>
              <div className="mt-1 text-xl font-semibold text-slate-950">{telegramMetrics.sandbox}</div>
            </div>
          </div>
          {telegramEvents.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 p-5 text-sm text-slate-500">
              Telegram-agent событий пока нет. Если внешний бот напишет в LocalOS, событие появится здесь и в ledger.
            </div>
          ) : (
            <div className="space-y-2">
              {telegramEvents.slice(0, 8).map((item) => {
                const sender = extractTelegramSender(item);
                const botLabel = sender.username || sender.telegram_id || 'unknown bot';
                return (
                  <div key={item.id} className="grid gap-3 rounded-2xl border border-slate-200 p-3 text-sm lg:grid-cols-[1.1fr_0.8fr_1fr_0.7fr]">
                    <div>
                      <div className="font-semibold text-slate-950">{botLabel}</div>
                      <div className="text-xs text-slate-500">
                        {item.agent_client_id ? `client ${item.agent_client_id.slice(0, 8)}` : 'не привязан к agent client'}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs uppercase tracking-[0.14em] text-slate-400">Причина</div>
                      <div className="font-medium text-slate-800">{item.reason_code || 'recorded'}</div>
                    </div>
                    <div>
                      <div className="text-xs uppercase tracking-[0.14em] text-slate-400">Что сделали</div>
                      <div className="text-slate-700">
                        {item.metadata_json?.transport_reason || 'Записано в ledger, прямой routing отключён.'}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs uppercase tracking-[0.14em] text-slate-400">Время</div>
                      <div className="font-medium text-slate-800">{formatDateTime(item.created_at)}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {newKey ? (
        <Card className="rounded-2xl border-amber-200 bg-amber-50 shadow-none">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <KeyRound className="mt-1 h-5 w-5 text-amber-700" />
              <div className="min-w-0 flex-1">
                <div className="font-semibold text-amber-950">Новый ключ показан один раз</div>
                <code className="mt-2 block overflow-x-auto rounded-xl bg-white p-3 text-xs text-slate-900">{newKey}</code>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card className="rounded-2xl border-slate-200 shadow-none">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            Новый sandbox client
          </CardTitle>
          <CardDescription>Создаёт ключ для интеграции. Live-доступ выдаётся только после ручной проверки.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-[1fr_1fr_1fr_1fr_1.4fr_auto] lg:items-end">
          <div className="space-y-2">
            <Label>Организация</Label>
            <Input
              value={form.organization_name}
              onChange={(event) => setForm((previous) => ({ ...previous, organization_name: event.target.value }))}
              placeholder="Например, OpenAI connector"
            />
          </div>
          <div className="space-y-2">
            <Label>Email контакта</Label>
            <Input
              value={form.contact_email}
              onChange={(event) => setForm((previous) => ({ ...previous, contact_email: event.target.value }))}
              placeholder="agent@example.com"
            />
          </div>
          <div className="space-y-2">
            <Label>Telegram bot username</Label>
            <Input
              value={form.telegram_bot_username}
              onChange={(event) => setForm((previous) => ({ ...previous, telegram_bot_username: event.target.value }))}
              placeholder="@PartnerAgentBot"
            />
          </div>
          <div className="space-y-2">
            <Label>Telegram bot ID</Label>
            <Input
              value={form.telegram_bot_id}
              onChange={(event) => setForm((previous) => ({ ...previous, telegram_bot_id: event.target.value }))}
              placeholder="опционально"
            />
          </div>
          <div className="space-y-2">
            <Label>Scopes</Label>
            <Textarea
              value={form.allowed_scopes}
              onChange={(event) => setForm((previous) => ({ ...previous, allowed_scopes: event.target.value }))}
              className="min-h-[86px]"
            />
          </div>
          <Button
            onClick={createClient}
            disabled={!form.organization_name.trim() || !form.contact_email.trim()}
            className="rounded-2xl"
          >
            Создать
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Card className="rounded-2xl border-slate-200 shadow-none">
          <CardHeader>
            <CardTitle>Agent clients</CardTitle>
            <CardDescription>Статус, scopes и ключевые действия по каждому подключению.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {clients.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
                Пока нет зарегистрированных agent clients.
              </div>
            ) : (
              clients.map((client) => (
                <div key={client.id} className="rounded-2xl border border-slate-200 p-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-semibold text-slate-950">{client.organization_name}</h3>
                        <Badge className={statusClassName(client.status)} variant="outline">
                          {statusLabels[client.status] || client.status}
                        </Badge>
                      </div>
                      <div className="mt-1 text-sm text-slate-500">{client.contact_email}</div>
                      <div className="mt-1 text-xs text-slate-400">Last seen: {formatDateTime(client.last_seen_at)}</div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" onClick={() => updateClient(client, 'sandbox')}>Sandbox</Button>
                      <Button size="sm" variant="outline" onClick={() => updateClient(client, 'suspended')}>Suspend</Button>
                      <Button size="sm" variant="outline" onClick={() => rotateKey(client)}>
                        <KeyRound className="mr-1 h-3.5 w-3.5" />
                        Rotate
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => copyQuickstart()}>
                        <Copy className="mr-1 h-3.5 w-3.5" />
                        Quickstart
                      </Button>
                    </div>
                  </div>
                  <div className="mt-4 space-y-2">
                    <Label>Telegram binding</Label>
                    <div className="grid gap-2 md:grid-cols-2">
                      <Input
                        value={telegramBindings[client.id]?.username || ''}
                        onChange={(event) => setTelegramBindings((previous) => ({
                          ...previous,
                          [client.id]: { ...(previous[client.id] || { username: '', botId: '' }), username: event.target.value },
                        }))}
                        placeholder="@PartnerAgentBot"
                      />
                      <Input
                        value={telegramBindings[client.id]?.botId || ''}
                        onChange={(event) => setTelegramBindings((previous) => ({
                          ...previous,
                          [client.id]: { ...(previous[client.id] || { username: '', botId: '' }), botId: event.target.value },
                        }))}
                        placeholder="Telegram bot ID"
                      />
                    </div>
                    <div className="text-xs text-slate-500">
                      Bot-to-bot события от этого username/ID будут писаться в ledger с этим client id.
                    </div>
                  </div>
                  <div className="mt-4 space-y-2">
                    <Label>Scopes</Label>
                    <Textarea
                      value={editingScopes[client.id] || ''}
                      onChange={(event) => setEditingScopes((previous) => ({ ...previous, [client.id]: event.target.value }))}
                      className="min-h-[92px] font-mono text-xs"
                    />
                    <Button size="sm" variant="secondary" onClick={() => updateClient(client)}>
                      Сохранить scopes
                    </Button>
                  </div>
                  <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    <Label>Promotion review</Label>
                    <Textarea
                      value={promotionNotes[client.id] || ''}
                      onChange={(event) => setPromotionNotes((previous) => ({ ...previous, [client.id]: event.target.value }))}
                      placeholder="Комментарий: кто проверил, почему можно дать live или почему отказали"
                      className="mt-2 min-h-[70px] bg-white text-sm"
                    />
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button size="sm" onClick={() => decidePromotion(client, 'approve')}>
                        Approve live
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => decidePromotion(client, 'reject')}>
                        Reject
                      </Button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-slate-200 shadow-none">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Discovery
            </CardTitle>
            <CardDescription>Кто смотрел docs, agent-файлы и Agent API.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {discovery.slice(0, 12).map((item) => (
              <div key={item.id} className="rounded-2xl border border-slate-200 p-3">
                <div className="flex items-center justify-between gap-2">
                  <Badge variant="outline">{item.agent_family}</Badge>
                  <span className="text-xs text-slate-400">{formatDateTime(item.created_at)}</span>
                </div>
                <div className="mt-2 truncate text-sm font-medium text-slate-900">{item.method} {item.path}</div>
                <div className="mt-1 truncate text-xs text-slate-500">{item.user_agent || 'user-agent не указан'}</div>
              </div>
            ))}
            {discovery.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
                Заходов в docs/API пока не видно.
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-2xl border-slate-200 shadow-none">
        <CardHeader>
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Terminal className="h-5 w-5" />
                Action ledger
              </CardTitle>
              <CardDescription>Последние approval requests, denied, self-test и служебные действия суперадмина.</CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant={ledgerFilter === 'all' ? 'default' : 'outline'} onClick={() => setLedgerFilter('all')}>
                Все события
              </Button>
              <Button size="sm" variant={ledgerFilter === 'self_test' ? 'default' : 'outline'} onClick={() => setLedgerFilter('self_test')}>
                Последние self-test
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {visibleLedger.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
              {ledgerFilter === 'self_test' ? 'Self-test событий пока нет.' : 'Ledger пока пуст.'}
            </div>
          ) : (
            visibleLedger.slice(0, 30).map((item) => (
              <div key={item.id} className="grid gap-3 rounded-2xl border border-slate-200 p-3 text-sm md:grid-cols-[1.2fr_0.8fr_0.8fr_0.8fr]">
                <div>
                  <div className="font-medium text-slate-950">{item.action_type}</div>
                  <div className="text-xs text-slate-500">{item.capability || 'capability не указана'}</div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-[0.14em] text-slate-400">Статус</div>
                  <div className="font-medium text-slate-800">{item.status}</div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-[0.14em] text-slate-400">Риск</div>
                  <div className="font-medium text-slate-800">{item.risk_level}</div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-[0.14em] text-slate-400">Время</div>
                  <div className="font-medium text-slate-800">{formatDateTime(item.created_at)}</div>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <div className="flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          API остаётся beta/internal. Перед продом нужна миграция БД; live scopes выдаём только после ручного review.
        </div>
      </div>
    </div>
  );
};
