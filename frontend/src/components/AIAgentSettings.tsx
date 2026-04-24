import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { Loader2, ChevronDown, ChevronUp, Bot, Zap, Circle } from 'lucide-react';
import { useLanguage } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';
import { cn } from '@/lib/utils';
import { getAutomationAccessForBusiness } from '@/lib/subscriptionAccess';
import { AIAgentsManagement } from './AIAgentsManagement';

interface AIAgentSettingsProps {
  businessId: string | null;
  business: any;
}

interface AgentConfig {
  enabled: boolean;
  agent_id: string | null;
  tone: string;
  language: string;
  variables: Record<string, string>;
}

const DEFAULT_AGENT_VALUE = '__default__';
const EMPTY_AGENT_FORM = {
  id: '',
  name: '',
  type: 'booking',
  description: '',
  personality: '',
  workflow: '',
  task: '',
  identity: '',
  speech_style: '',
  is_active: true,
};

export const AIAgentSettings = ({ businessId, business }: AIAgentSettingsProps) => {
  const { language: interfaceLanguage, t } = useLanguage();
  const automationAccess = getAutomationAccessForBusiness(business);
  const [agentsConfig, setAgentsConfig] = useState<Record<string, AgentConfig>>({});
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());
  const [availableAgents, setAvailableAgents] = useState<any[]>([]);
  const [editingAgentForm, setEditingAgentForm] = useState<any | null>(null);
  const [showAgentForm, setShowAgentForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savingAgentForm, setSavingAgentForm] = useState(false);
  const { toast } = useToast();

  // ... (rest of constants)
  const TONE_OPTIONS = [
    { value: 'professional', label: t.dashboard.settings.ai.tones.professional },
    { value: 'friendly', label: t.dashboard.settings.ai.tones.friendly },
    { value: 'casual', label: t.dashboard.settings.ai.tones.casual },
    { value: 'formal', label: t.dashboard.settings.ai.tones.formal },
  ];

  const AGENT_TYPES = [
    {
      key: 'booking_agent',
      label: t.dashboard.settings.ai.types.booking,
      icon: Bot,
      description: t.dashboard.settings.ai.types.bookingDesc,
      gradient: 'from-blue-500 to-indigo-600',
      bgGradient: 'from-blue-50 to-indigo-50',
    },
    {
      key: 'marketing_agent',
      label: t.dashboard.settings.ai.types.marketing,
      icon: Zap,
      description: t.dashboard.settings.ai.types.marketingDesc,
      gradient: 'from-orange-500 to-pink-600',
      bgGradient: 'from-orange-50 to-pink-50',
    },
  ];

  const LANGUAGE_OPTIONS = [
    { value: 'ru', label: 'Русский' },
    { value: 'en', label: 'English' },
    { value: 'es', label: 'Español' },
    { value: 'de', label: 'Deutsch' },
    { value: 'fr', label: 'Français' },
    { value: 'tr', label: 'Türkçe' },
  ];

  useEffect(() => {
    loadAvailableAgents();
    if (business) {
      loadAgentConfigs(business);
    }
  }, [business, interfaceLanguage]);

  const loadAgentConfigs = (businessData: any) => {
    const newConfigs: Record<string, AgentConfig> = {};

    // Try loading from new ai_agents_config field
    if (businessData.ai_agents_config) {
      try {
        const parsed = typeof businessData.ai_agents_config === 'string'
          ? JSON.parse(businessData.ai_agents_config)
          : businessData.ai_agents_config;
        Object.assign(newConfigs, parsed);
      } catch (e) {
        console.error('Error parsing ai_agents_config:', e);
      }
    }

    // Fallback to old schema for backwards compatibility
    if (Object.keys(newConfigs).length === 0 && businessData.ai_agent_enabled) {
      const agentType = businessData.ai_agent_type || 'booking';
      const restrictions = businessData.ai_agent_restrictions;
      let variables = {};
      try {
        variables = restrictions ? JSON.parse(restrictions) : {};
      } catch { }

      newConfigs[`${agentType}_agent`] = {
        enabled: true,
        agent_id: businessData.ai_agent_id || null,
        tone: businessData.ai_agent_tone || 'professional',
        language: businessData.ai_agent_language || interfaceLanguage,
        variables,
      };
    }

    // Initialize missing agents with defaults
    AGENT_TYPES.forEach(({ key }) => {
      if (!newConfigs[key]) {
        newConfigs[key] = {
          enabled: false,
          agent_id: null,
          tone: 'professional',
          language: interfaceLanguage,
          variables: {},
        };
      }
    });

    setAgentsConfig(newConfigs);

    // Auto-expand enabled agents
    const enabled = new Set(
      Object.entries(newConfigs)
        .filter(([_, config]) => config.enabled)
        .map(([key]) => key)
    );
    setExpandedAgents(enabled);
  };

  const loadAvailableAgents = async () => {
    try {
      const token = await newAuth.getToken();
      if (!token) return;

      const url = businessId
        ? `/api/business/${businessId}/ai-agents/manage`
        : '/api/admin/ai-agents';
      const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (response.ok) {
        const data = await response.json();
        setAvailableAgents(Array.isArray(data.agents) ? data.agents : []);
      }
    } catch (error) {
      console.error('Error loading agents:', error);
    }
  };

  const resetAgentForm = () => {
    setEditingAgentForm({ ...EMPTY_AGENT_FORM });
  };

  const openCreateAgentForm = () => {
    resetAgentForm();
    setShowAgentForm(true);
  };

  const openEditAgentForm = (agent: any) => {
    setEditingAgentForm({
      id: agent.id,
      name: agent.name || '',
      type: agent.type || 'booking',
      description: agent.description || '',
      personality: agent.personality || '',
      workflow: agent.workflow || '',
      task: agent.task || '',
      identity: agent.identity || '',
      speech_style: agent.speech_style || '',
      is_active: agent.is_active !== false,
    });
    setShowAgentForm(true);
  };

  const saveAgentForm = async () => {
    if (!businessId) {
      toast({ title: t.common.error, description: t.dashboard.settings.telegram.selectBusiness, variant: 'destructive' });
      return;
    }
    if (!editingAgentForm?.name?.trim() || !editingAgentForm?.type?.trim()) {
      toast({ title: t.common.error, description: 'Название и тип агента обязательны', variant: 'destructive' });
      return;
    }
    setSavingAgentForm(true);
    try {
      const token = await newAuth.getToken();
      if (!token) throw new Error('Требуется авторизация');
      const isEdit = Boolean(editingAgentForm.id);
      const url = isEdit
        ? `/api/business/${businessId}/ai-agents/manage/${editingAgentForm.id}`
        : `/api/business/${businessId}/ai-agents/manage`;
      const response = await fetch(url, {
        method: isEdit ? 'PUT' : 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(editingAgentForm),
      });
      const data = await response.json();
      if (!response.ok || data?.success === false) {
        throw new Error(data?.error || 'Не удалось сохранить агента');
      }
      toast({ title: t.common.success, description: isEdit ? 'Агент обновлён' : 'Агент создан' });
      setShowAgentForm(false);
      resetAgentForm();
      await loadAvailableAgents();
    } catch (e: any) {
      toast({ title: t.common.error, description: e?.message || 'Не удалось сохранить агента', variant: 'destructive' });
    } finally {
      setSavingAgentForm(false);
    }
  };

  const deleteOwnAgent = async (agentId: string) => {
    if (!businessId) return;
    const ok = window.confirm('Удалить этого агента?');
    if (!ok) return;
    try {
      const token = await newAuth.getToken();
      if (!token) throw new Error('Требуется авторизация');
      const response = await fetch(`/api/business/${businessId}/ai-agents/manage/${agentId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await response.json();
      if (!response.ok || data?.success === false) {
        throw new Error(data?.error || 'Не удалось удалить агента');
      }
      toast({ title: t.common.success, description: 'Агент удалён' });
      await loadAvailableAgents();
    } catch (e: any) {
      toast({ title: t.common.error, description: e?.message || 'Не удалось удалить агента', variant: 'destructive' });
    }
  };

  const toggleAgent = (agentKey: string) => {
    setAgentsConfig(prev => ({
      ...prev,
      [agentKey]: {
        ...prev[agentKey],
        enabled: !prev[agentKey]?.enabled,
      },
    }));

    // Auto-expand when enabling
    if (!agentsConfig[agentKey]?.enabled) {
      setExpandedAgents(prev => new Set(prev).add(agentKey));
    }
  };

  const toggleExpand = (agentKey: string) => {
    setExpandedAgents(prev => {
      const next = new Set(prev);
      if (next.has(agentKey)) {
        next.delete(agentKey);
      } else {
        next.add(agentKey);
      }
      return next;
    });
  };

  const updateAgentConfig = (agentKey: string, updates: Partial<AgentConfig>) => {
    setAgentsConfig(prev => ({
      ...prev,
      [agentKey]: {
        ...prev[agentKey],
        ...updates,
      },
    }));
  };

  const handleSave = async () => {
    if (!businessId) {
      toast({
        title: t.common.error,
        description: t.dashboard.settings.telegram.selectBusiness,
        variant: 'destructive',
      });
      return;
    }

    setSaving(true);
    try {
      const token = await newAuth.getToken();
      if (!token) {
        toast({ title: t.common.error, description: t.common.error, variant: 'destructive' });
        return;
      }

      const response = await fetch('/api/business/profile', {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          business_id: businessId,
          ai_agents_config: JSON.stringify(agentsConfig),
        }),
      });

      const data = await response.json();

      if (response.ok) {
        toast({ title: t.common.success, description: t.dashboard.settings.ai.saved });
      } else {
        toast({ title: t.common.error, description: data.error || t.common.error, variant: 'destructive' });
      }
    } catch (error) {
      toast({ title: t.common.error, description: t.common.error, variant: 'destructive' });
    } finally {
      setSaving(false);
    }
  };

  const activeCount = Object.values(agentsConfig).filter(c => c.enabled).length;

  if (!automationAccess.automationAllowed) {
    return (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-900">
        {automationAccess.message || 'Автоматизация доступна только после оплаты тарифа.'}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className={cn(
        "rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
      )}>
        <div>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-slate-950">
                {t.dashboard.settings.ai.title}
              </h2>
              <p className="mt-1 text-sm leading-6 text-slate-600">
                {t.dashboard.settings.ai.subtitle}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-right">
              <div className="text-2xl font-semibold text-slate-950">{activeCount}/{AGENT_TYPES.length}</div>
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{t.dashboard.settings.ai.active}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Agent Cards Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {AGENT_TYPES.map(({ key, label, icon: Icon, description }) => {
          const config: AgentConfig = agentsConfig[key] || {
            enabled: false,
            agent_id: null,
            tone: 'professional',
            language: interfaceLanguage,
            variables: {},
          };
          const isExpanded = expandedAgents.has(key);
          const agentTypeKey = key.replace('_agent', '');

          return (
            <div
              key={key}
              className={`group relative overflow-hidden rounded-xl border transition-all duration-300 ${config.enabled
                ? 'border-emerald-200 bg-emerald-50/40 shadow-sm'
                : 'border-slate-200 bg-white shadow-sm hover:border-slate-300'
                }`}
            >
              {config.enabled && (
                <div className="absolute inset-0 bg-emerald-50/60"></div>
              )}

              <div className="relative z-10 bg-white/85 p-6">
                {/* Card Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-4">
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-slate-700">
                      <Icon className="w-6 h-6" />
                    </div>
                    <div>
                      <h3 className="text-xl font-bold text-gray-900 mb-1">{label}</h3>
                      <p className="text-sm text-gray-600">{description}</p>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <Switch
                      checked={config.enabled}
                      onCheckedChange={() => toggleAgent(key)}
                      className="data-[state=checked]:bg-gradient-to-r data-[state=checked]:from-green-500 data-[state=checked]:to-emerald-600"
                    />
                    <div className="flex items-center gap-2">
                      <Circle className={`w-2 h-2 ${config.enabled ? 'fill-green-500 text-green-500' : 'fill-gray-300 text-gray-300'}`} />
                      <span className={`text-xs font-semibold uppercase tracking-wide ${config.enabled ? 'text-green-700' : 'text-gray-500'}`}>
                        {config.enabled ? t.dashboard.settings.ai.status.active : t.dashboard.settings.ai.status.disabled}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Expandable Configuration */}
                {config.enabled && (
                  <>
                    <button
                      onClick={() => toggleExpand(key)}
                      className="w-full flex items-center justify-between py-3 px-4 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors mb-4"
                    >
                      <span className="font-semibold text-gray-700">{t.dashboard.settings.ai.agentSettings}</span>
                      {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                    </button>

                    {isExpanded && (
                      <div className="space-y-4 animate-in slide-in-from-top duration-300">
                        {/* Tone Selection */}
                        <div className="space-y-2">
                          <Label className="text-sm font-semibold text-gray-700">{t.dashboard.settings.ai.tone}</Label>
                          <Select
                            value={config.tone}
                            onValueChange={(value) => updateAgentConfig(key, { tone: value })}
                          >
                            <SelectTrigger className="bg-white border-gray-300">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {TONE_OPTIONS.map(opt => (
                                <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>

                        {/* Language Selection */}
                        <div className="space-y-2">
                          <Label className="text-sm font-semibold text-gray-700">{t.dashboard.settings.ai.language}</Label>
                          <Select
                            value={config.language}
                            onValueChange={(value) => updateAgentConfig(key, { language: value })}
                          >
                            <SelectTrigger className="bg-white border-gray-300">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {LANGUAGE_OPTIONS.map(opt => (
                                <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>

                        {/* Agent Selection */}
                        <div className="space-y-2">
                          <Label className="text-sm font-semibold text-gray-700">{t.dashboard.settings.ai.selectAgent}</Label>
                          <Select
                            value={config.agent_id || DEFAULT_AGENT_VALUE}
                            onValueChange={(value) =>
                              updateAgentConfig(key, { agent_id: value === DEFAULT_AGENT_VALUE ? null : value })
                            }
                          >
                            <SelectTrigger className="bg-white border-gray-300">
                              <SelectValue placeholder={t.dashboard.settings.ai.defaultAgent} />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value={DEFAULT_AGENT_VALUE}>{t.dashboard.settings.ai.defaultAgent}</SelectItem>
                              {availableAgents
                                .filter(a => a && a.type === agentTypeKey && a.is_active)
                                .map(agent => (
                                  <SelectItem key={agent.id} value={agent.id}>
                                    {agent.name}
                                  </SelectItem>
                                ))}
                            </SelectContent>
                          </Select>
                        </div>

                        {/* Variables (Future Enhancement) */}
                        {Object.keys(config.variables || {}).length > 0 && (
                          <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                            <Label className="text-sm font-semibold text-amber-900 mb-2 block">{t.dashboard.settings.ai.variables}</Label>
                            <div className="space-y-2">
                              {Object.entries(config.variables).map(([varKey, varValue]) => (
                                <div key={varKey} className="flex items-center gap-2">
                                  <Label className="text-xs text-amber-800 flex-1">{varKey}:</Label>
                                  <Input
                                    value={String(varValue || '')}
                                    onChange={(e) =>
                                      updateAgentConfig(key, {
                                        variables: { ...config.variables, [varKey]: e.target.value },
                                      })
                                    }
                                    className="flex-[2] text-sm"
                                  />
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button
          onClick={handleSave}
          disabled={saving}
          size="lg"
          className="bg-slate-900 px-8 font-semibold text-white shadow-sm hover:bg-slate-800"
        >
          {saving ? (
            <>
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              {t.dashboard.settings.ai.saving}
            </>
          ) : (
            t.dashboard.settings.ai.save
          )}
        </Button>
      </div>

      <AIAgentsManagement mode="business" businessId={businessId} />
    </div>
  );
};
