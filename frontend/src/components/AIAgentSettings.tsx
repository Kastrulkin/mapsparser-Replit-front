import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useToast } from '@/hooks/use-toast';
import { Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { useLanguage } from '@/i18n/LanguageContext';

interface AIAgentSettingsProps {
  businessId: string | null;
  business: any;
}

const TONE_OPTIONS = [
  { value: 'professional', label: 'Профессиональный' },
  { value: 'friendly', label: 'Дружелюбный' },
  { value: 'casual', label: 'Неформальный' },
  { value: 'formal', label: 'Официальный' },
];

const AGENT_TYPES = [
  { value: 'marketing', label: 'Маркетинговый агент' },
  { value: 'booking', label: 'Агент для записи' },
];

const LANGUAGE_OPTIONS = [
  { value: 'ru', label: 'Русский' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Español' },
  { value: 'de', label: 'Deutsch' },
  { value: 'fr', label: 'Français' },
  { value: 'it', label: 'Italiano' },
  { value: 'pt', label: 'Português' },
  { value: 'zh', label: '中文' },
];

// Специальное значение для "дефолтного" агента, Radix Select запрещает пустую строку
const DEFAULT_AGENT_VALUE = '__default__';

export const AIAgentSettings = ({ businessId, business }: AIAgentSettingsProps) => {
  const { language: interfaceLanguage } = useLanguage();
  const [enabled, setEnabled] = useState(false);
  const [agentType, setAgentType] = useState('booking');
  const [tone, setTone] = useState('professional');
  const [agentLanguage, setAgentLanguage] = useState<string>(interfaceLanguage);
  const [variables, setVariables] = useState<Record<string, string>>({});
  // Значения переменных для конкретного бизнеса (что именно будет подставляться в промпты)
  const [variableValues, setVariableValues] = useState<Record<string, string>>({});
  const [availableAgents, setAvailableAgents] = useState<any[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [isSettingsCollapsed, setIsSettingsCollapsed] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    if (business) {
      const newEnabled = business.ai_agent_enabled === 1;
      // Если агент только что включен, разворачиваем настройки
      if (!enabled && newEnabled) {
        setIsSettingsCollapsed(false);
      }
      setEnabled(newEnabled);
      setAgentType(business.ai_agent_type || 'booking');
      setTone(business.ai_agent_tone || 'professional');
      setSelectedAgentId(business.ai_agent_id || '');
      // Язык агента: из бизнеса или язык интерфейса по умолчанию
      setAgentLanguage(business.ai_agent_language || interfaceLanguage);
      
       // Инициализируем значения переменных из ограничений бизнеса (ai_agent_restrictions)
      if (business.ai_agent_restrictions) {
        try {
          const parsed =
            typeof business.ai_agent_restrictions === 'string'
              ? JSON.parse(business.ai_agent_restrictions)
              : business.ai_agent_restrictions;
          if (parsed && typeof parsed === 'object') {
            setVariableValues(parsed as Record<string, string>);
          } else {
            setVariableValues({});
          }
        } catch {
          setVariableValues({});
        }
      } else {
        setVariableValues({});
      }
      
      // Загружаем переменные из выбранного агента
      if (business.ai_agent_id) {
        loadAgentVariables(business.ai_agent_id);
      }
    } else {
      // Если бизнес не загружен, используем язык интерфейса
      setAgentLanguage(interfaceLanguage);
    }
    loadAvailableAgents();
  }, [business, interfaceLanguage]);

  const loadAvailableAgents = async () => {
    try {
      const { newAuth } = await import('@/lib/auth_new');
      const token = await newAuth.getToken();
      if (!token) return;
      
      const response = await fetch('/api/admin/ai-agents', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setAvailableAgents(Array.isArray(data.agents) ? data.agents : []);
      } else {
        setAvailableAgents([]);
      }
    } catch (error) {
      console.error('Ошибка загрузки агентов:', error);
      setAvailableAgents([]);
    }
  };

  const loadAgentVariables = async (agentId: string) => {
    try {
      const { newAuth } = await import('@/lib/auth_new');
      const token = await newAuth.getToken();
      if (!token) return;
      
      const response = await fetch(`/api/admin/ai-agents/${agentId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setVariables(data.variables && typeof data.variables === 'object' ? data.variables : {});
      } else {
        setVariables({});
      }
    } catch (error) {
      console.error('Ошибка загрузки переменных агента:', error);
      setVariables({});
    }
  };

  const handleAgentTypeChange = (newType: string) => {
    setAgentType(newType);
    // При смене типа разворачиваем настройки, чтобы пользователь видел изменения
    setIsSettingsCollapsed(false);
    // При смене типа сбрасываем выбор агента на дефолтный
    setSelectedAgentId('');
    // Загружаем переменные дефолтного агента для нового типа, если он есть
    if (Array.isArray(availableAgents) && availableAgents.length > 0) {
      const defaultAgent = availableAgents.find(a => a && a.type === newType && a.is_active);
      if (defaultAgent) {
        loadAgentVariables(defaultAgent.id);
      } else {
        setVariables({});
        setVariableValues({});
      }
    } else {
      setVariables({});
      setVariableValues({});
    }
  };

  const handleAgentSelect = (value: string) => {
    // Значение по умолчанию — используем дефолтного агента для типа
    if (value === DEFAULT_AGENT_VALUE) {
      setSelectedAgentId('');
      // При возврате к дефолтному агенту оставляем текущие значения переменных пользователя
      return;
    }

    setSelectedAgentId(value);
    // При выборе агента разворачиваем настройки
    setIsSettingsCollapsed(false);
    if (value) {
      loadAgentVariables(value);
    } else {
      setVariables({});
    }
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
        toast({
          title: 'Ошибка',
          description: 'Требуется авторизация',
          variant: 'destructive',
        });
        return;
      }
      
      const response = await fetch('/api/business/profile', {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          business_id: businessId,
          ai_agent_enabled: enabled ? 1 : 0,
          ai_agent_type: agentType,
          ai_agent_id: selectedAgentId || null,
          ai_agent_tone: tone,
          ai_agent_language: agentLanguage,
          // Сохраняем значения переменных как JSON
          ai_agent_restrictions: JSON.stringify(variableValues || {})
        })
      });

      const data = await response.json();

      if (response.ok) {
        toast({
          title: 'Успешно',
          description: 'Настройки ИИ агента сохранены',
        });
        // Сворачиваем настройки после сохранения
        setIsSettingsCollapsed(true);
        // Обновляем локальное состояние бизнеса через пропсы
        // Компонент получит обновленные данные через useEffect при следующем рендере
      } else {
        toast({
          title: 'Ошибка',
          description: data.error || 'Не удалось сохранить настройки',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Ошибка при сохранении настроек',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900">Настройки ИИ агента</h2>
        <p className="text-sm text-gray-600 mt-1">
          Настройте ИИ агента для автоматического консультирования клиентов
        </p>
      </div>
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label htmlFor="ai-agent-enabled">Включить ИИ агента</Label>
            <p className="text-sm text-gray-500">
              Агент будет автоматически отвечать на сообщения клиентов
            </p>
          </div>
          <Switch
            id="ai-agent-enabled"
            checked={enabled}
            onCheckedChange={(checked) => {
              setEnabled(checked);
              // При включении агента разворачиваем настройки
              if (checked) {
                setIsSettingsCollapsed(false);
              }
            }}
          />
        </div>

        {enabled && (
          <>
            {/* Заголовок секции настроек с кнопкой сворачивания */}
            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  Настройки {AGENT_TYPES.find(t => t.value === agentType)?.label || 'агента'}
                </h3>
                {selectedAgentId && (
                  <p className="text-sm text-gray-500 mt-1">
                    {availableAgents.find(a => a.id === selectedAgentId)?.name || 'Дефолтный агент'}
                  </p>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsSettingsCollapsed(!isSettingsCollapsed)}
                className="flex items-center gap-2"
              >
                {isSettingsCollapsed ? (
                  <>
                    <ChevronDown className="h-4 w-4" />
                    Развернуть
                  </>
                ) : (
                  <>
                    <ChevronUp className="h-4 w-4" />
                    Свернуть
                  </>
                )}
              </Button>
            </div>

            {!isSettingsCollapsed && (
              <>
            <div className="space-y-2">
              <Label htmlFor="ai-agent-type">Тип агента</Label>
              <Select value={agentType} onValueChange={handleAgentTypeChange}>
                <SelectTrigger id="ai-agent-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {AGENT_TYPES.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-gray-500">
                Выберите тип агента: маркетинговый для акций или для записи на услуги
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="ai-agent-select">Выберите агента</Label>
              <Select
                value={selectedAgentId || DEFAULT_AGENT_VALUE}
                onValueChange={handleAgentSelect}
              >
                <SelectTrigger id="ai-agent-select">
                  <SelectValue placeholder="Выберите агента (опционально)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={DEFAULT_AGENT_VALUE}>
                    Использовать дефолтного агента
                  </SelectItem>
                  {availableAgents
                    .filter(a => a && a.type === agentType && a.is_active)
                    .map((agent) => (
                      <SelectItem key={agent.id} value={agent.id}>
                        {agent.name}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-gray-500">
                Выберите конкретного агента для типа "{agentType === 'marketing' ? 'маркетинговый' : 'запись'}" или используйте дефолтного
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="ai-agent-tone">Тон общения</Label>
              <Select value={tone} onValueChange={setTone}>
                <SelectTrigger id="ai-agent-tone">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TONE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-gray-500">
                Выберите стиль общения ИИ агента с клиентами
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="ai-agent-language">Язык агента</Label>
              <Select value={agentLanguage} onValueChange={setAgentLanguage}>
                <SelectTrigger id="ai-agent-language">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LANGUAGE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-gray-500">
                Язык, на котором ИИ агент будет писать свои мысли и действия. По умолчанию используется язык интерфейса ({LANGUAGE_OPTIONS.find(l => l.value === interfaceLanguage)?.label || interfaceLanguage})
              </p>
            </div>

            {variables && typeof variables === 'object' && Object.keys(variables).length > 0 && (
              <div className="space-y-2">
                <Label>Переменные агента</Label>
                <div className="border rounded-lg p-4 space-y-4">
                  {Object.entries({
                    ...variables,
                    // Добавляем поле «Предложение», если его нет в конфигурации агента
                    offer: variables.offer || 'Предложение',
                  }).map(([key, label]) => (
                    <div key={key} className="space-y-1">
                      <Label className="text-sm">{label}</Label>
                      <Input
                        value={variableValues[key] || ''}
                        onChange={(e) =>
                          setVariableValues((prev) => ({
                            ...prev,
                            [key]: e.target.value,
                          }))
                        }
                        placeholder="Введите значение"
                      />
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-500">
                  Эти значения будут использоваться ИИ агентом в сообщениях (например, для описания акции и скидки).
                </p>
              </div>
            )}

            <Alert>
              <AlertDescription>
                <strong>Настройка агента:</strong> пожалуйста, выберите тон общения, добавьте название акции, размер скидки и описание.
              </AlertDescription>
            </Alert>
              </>
            )}
          </>
        )}

        <div className="flex justify-start">
          <Button
            onClick={handleSave}
            disabled={saving || loading}
            size="sm"
          >
            {saving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
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

