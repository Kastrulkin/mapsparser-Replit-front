import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { Loader2, ChevronDown, ChevronUp, Bot, Zap, Circle } from 'lucide-react';
import { useLanguage } from '@/i18n/LanguageContext';

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

const TONE_OPTIONS = [
  { value: 'professional', label: 'Профессиональный' },
  { value: 'friendly', label: 'Дружелюбный' },
  { value: 'casual', label: 'Неформальный' },
  { value: 'formal', label: 'Официальный' },
];

const LANGUAGE_OPTIONS = [
  { value: 'ru', label: 'Русский' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Español' },
  { value: 'de', label: 'Deutsch' },
  { value: 'fr', label: 'Français' },
];

const AGENT_TYPES = [
  {
    key: 'booking_agent',
    label: 'Агент для записи',
    icon: Bot,
    description: 'Автоматическая запись клиентов на услуги',
    gradient: 'from-blue-500 to-indigo-600',
    bgGradient: 'from-blue-50 to-indigo-50',
  },
  {
    key: 'marketing_agent',
    label: 'Маркетинговый агент',
    icon: Zap,
    description: 'Отправка акций и специальных предложений',
    gradient: 'from-orange-500 to-pink-600',
    bgGradient: 'from-orange-50 to-pink-50',
  },
];

const DEFAULT_AGENT_VALUE = '__default__';

export const AIAgentSettings = ({ businessId, business }: AIAgentSettingsProps) => {
  const { language: interfaceLanguage } = useLanguage();
  const [agentsConfig, setAgentsConfig] = useState<Record<string, AgentConfig>>({});
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());
  const [availableAgents, setAvailableAgents] = useState<any[]>([]);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

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
      const { newAuth } = await import('@/lib/auth_new');
      const token = await newAuth.getToken();
      if (!token) return;

      const response = await fetch('/api/admin/ai-agents', {
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
        title: 'Ошибка',
        description: 'Бизнес не выбран',
        variant: 'destructive',
      });
      return;
    }

    setSaving(true);
    try {
      const { newAuth } = await import('@/lib/auth_new');
      const token = await newAuth.getToken();
      if (!token) {
        toast({ title: 'Ошибка', description: 'Требуется авторизация', variant: 'destructive' });
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
        toast({ title: 'Успешно', description: 'Настройки ИИ агентов сохранены' });
      } else {
        toast({ title: 'Ошибка', description: data.error || 'Не удалось сохранить', variant: 'destructive' });
      }
    } catch (error) {
      toast({ title: 'Ошибка', description: 'Ошибка при сохранении', variant: 'destructive' });
    } finally {
      setSaving(false);
    }
  };

  const activeCount = Object.values(agentsConfig).filter(c => c.enabled).length;

  return (
    <div className="space-y-6">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-8 shadow-2xl">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjAzKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] opacity-40"></div>
        <div className="relative z-10">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-3xl font-bold text-white mb-2 tracking-tight">
                Управление ИИ Агентами
              </h2>
              <p className="text-purple-200 text-lg">
                Настройте автоматизированных помощников для вашего бизнеса
              </p>
            </div>
            <div className="text-right">
              <div className="text-5xl font-black text-white mb-1">{activeCount}/{AGENT_TYPES.length}</div>
              <div className="text-purple-300 text-sm uppercase tracking-wider font-semibold">Активно</div>
            </div>
          </div>
        </div>
      </div>

      {/* Agent Cards Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {AGENT_TYPES.map(({ key, label, icon: Icon, description, gradient, bgGradient }) => {
          const config = agentsConfig[key] || {};
          const isExpanded = expandedAgents.has(key);
          const agentTypeKey = key.replace('_agent', '');

          return (
            <div
              key={key}
              className={`group relative overflow-hidden rounded-2xl border-2 transition-all duration-500 ${config.enabled
                  ? 'border-transparent shadow-xl scale-[1.02]'
                  : 'border-gray-200 hover:border-gray-300 shadow-md hover:shadow-lg'
                }`}
            >
              {/* Gradient Background (visible when enabled) */}
              {config.enabled && (
                <div className={`absolute inset-0 bg-gradient-to-br ${bgGradient} opacity-60`}></div>
              )}

              <div className="relative z-10 p-6 bg-white/80 backdrop-blur-sm">
                {/* Card Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-4">
                    <div className={`p-3 rounded-xl bg-gradient-to-br ${gradient} shadow-lg group-hover:scale-110 transition-transform duration-300`}>
                      <Icon className="w-7 h-7 text-white" />
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
                        {config.enabled ? 'Активен' : 'Выключен'}
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
                      <span className="font-semibold text-gray-700">Настройки агента</span>
                      {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                    </button>

                    {isExpanded && (
                      <div className="space-y-4 animate-in slide-in-from-top duration-300">
                        {/* Tone Selection */}
                        <div className="space-y-2">
                          <Label className="text-sm font-semibold text-gray-700">Тон общения</Label>
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
                          <Label className="text-sm font-semibold text-gray-700">Язык агента</Label>
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
                          <Label className="text-sm font-semibold text-gray-700">Выберите агента</Label>
                          <Select
                            value={config.agent_id || DEFAULT_AGENT_VALUE}
                            onValueChange={(value) =>
                              updateAgentConfig(key, { agent_id: value === DEFAULT_AGENT_VALUE ? null : value })
                            }
                          >
                            <SelectTrigger className="bg-white border-gray-300">
                              <SelectValue placeholder="Дефолтный агент" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value={DEFAULT_AGENT_VALUE}>Использовать дефолтного</SelectItem>
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
                            <Label className="text-sm font-semibold text-amber-900 mb-2 block">Переменные агента</Label>
                            <div className="space-y-2">
                              {Object.entries(config.variables).map(([varKey, varValue]) => (
                                <div key={varKey} className="flex items-center gap-2">
                                  <Label className="text-xs text-amber-800 flex-1">{varKey}:</Label>
                                  <Input
                                    value={varValue}
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
          className="bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-semibold px-8 shadow-lg hover:shadow-xl transition-all duration-300"
        >
          {saving ? (
            <>
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Сохранение...
            </>
          ) : (
            'Сохранить настройки'
          )}
        </Button>
      </div>
    </div>
  );
};
