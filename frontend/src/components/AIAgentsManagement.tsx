import { useState, useEffect } from 'react';
import { useLanguage } from '@/i18n/LanguageContext';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { useToast } from '../hooks/use-toast';
import { newAuth } from '../lib/auth_new';
import { Plus, Edit, Trash2, Save, X, Bot, Send } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Tabs, TabsList, TabsTrigger, TabsContent } from './ui/tabs';
import { ScrollArea } from './ui/scroll-area';

interface WorkflowState {
  name: string;
  kind: string;
  process_name: string;
  init_state?: boolean;
  description: string;
  state_scenarios?: Array<{
    next_state: string;
    transition_name: string;
    description: string;
  }>;
  available_tools?: Record<string, string[]>;
}

interface AIAgent {
  id: string;
  name: string;
  type: string;
  description: string;
  personality?: string;
  workflow?: WorkflowState[];
  task?: string;
  identity?: string;
  speech_style?: string;
  restrictions: Record<string, any>;
  variables: Record<string, string>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export const AIAgentsManagement = () => {
  const { t } = useLanguage();
  const [agents, setAgents] = useState<AIAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingAgent, setEditingAgent] = useState<AIAgent | null>(null);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [sandboxMessages, setSandboxMessages] = useState<Array<{ sender: 'client' | 'agent', content: string }>>([]);
  const [sandboxInput, setSandboxInput] = useState('');
  const [sandboxLoading, setSandboxLoading] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    setLoading(true);
    try {
      const token = await newAuth.getToken();
      const response = await fetch('/api/admin/ai-agents', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        // Конвертируем старую структуру в новую, если нужно
        const convertedAgents = (data.agents || []).map((agent: any) => {
          // Если есть workflow_json, используем его, иначе конвертируем states_json
          if (agent.workflow) {
            return agent;
          }
          // Конвертация старой структуры (для обратной совместимости)
          if (agent.states) {
            const workflow: WorkflowState[] = Object.entries(agent.states).map(([key, state]: [string, any]) => ({
              name: key,
              kind: 'StateConfig',
              process_name: `${agent.name}Process`,
              init_state: key === 'greeting' || key === Object.keys(agent.states)[0],
              description: state.description || '',
              state_scenarios: (state.next_states || []).map((next: string) => ({
                next_state: next,
                transition_name: `${key}To${next}`,
                description: `Переход из ${key} в ${next}`
              })),
              available_tools: {
                'SingleStatefulOutboundAgent': ['ForwardSpeech']
              }
            }));
            return { ...agent, workflow };
          }
          return agent;
        });
        setAgents(convertedAgents || []);
      } else {
        setAgents([]);
        toast({
          title: 'Ошибка',
          description: 'Не удалось загрузить агентов',
          variant: 'destructive',
        });
      }
    } catch (error) {
      console.error('Ошибка загрузки агентов:', error);
      setAgents([]);
      toast({
        title: 'Ошибка',
        description: 'Ошибка при загрузке агентов',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  // Функция для конвертации workflow объекта в YAML формат
  const convertWorkflowToYAML = (workflow: any): string => {
    if (typeof workflow === 'string') {
      return workflow;
    }

    if (!Array.isArray(workflow)) {
      return '';
    }

    // Конвертируем массив стейтов в YAML формат
    return workflow.map((state: any) => {
      let yaml = `- name: ${state.name || ''}\n`;
      yaml += `  kind: ${state.kind || 'StateConfig'}\n`;
      yaml += `  process_name: ${state.process_name || ''}\n`;
      yaml += `  init_state: ${state.init_state || false}\n`;
      yaml += `  description: >\n    ${(state.description || '').replace(/\n/g, '\n    ')}\n`;

      if (state.state_scenarios && Array.isArray(state.state_scenarios) && state.state_scenarios.length > 0) {
        yaml += `  state_scenarios:\n`;
        state.state_scenarios.forEach((scenario: any) => {
          yaml += `    - next_state: ${scenario.next_state || ''}\n`;
          yaml += `      transition_name: ${scenario.transition_name || ''}\n`;
          yaml += `      description: ${scenario.description || ''}\n`;
        });
      }

      if (state.available_tools && typeof state.available_tools === 'object') {
        yaml += `  available_tools:\n`;
        Object.entries(state.available_tools).forEach(([key, tools]: [string, any]) => {
          yaml += `    ${key}:\n`;
          if (Array.isArray(tools)) {
            tools.forEach((tool: string) => {
              yaml += `      - ${tool}\n`;
            });
          }
        });
      }

      return yaml;
    }).join('\n');
  };

  const handleEdit = (agent: AIAgent) => {
    setEditingAgent({
      ...agent,
      workflow: agent.workflow || [],
      task: agent.task || '',
      identity: agent.identity || '',
      speech_style: agent.speech_style || ''
    });
    setShowEditDialog(true);
  };

  const handleCreate = () => {
    setEditingAgent({
      id: '',
      name: '',
      type: 'marketing',
      description: '',
      personality: '',
      workflow: [],
      task: '',
      identity: '',
      speech_style: '',
      restrictions: {},
      variables: {},
      is_active: true,
      created_at: '',
      updated_at: ''
    });
    setShowCreateDialog(true);
  };

  const handleSave = async () => {
    if (!editingAgent) return;

    try {
      const token = await newAuth.getToken();
      const isNew = !editingAgent.id;
      const url = isNew
        ? '/api/admin/ai-agents'
        : `/api/admin/ai-agents/${editingAgent.id}`;

      const method = isNew ? 'POST' : 'PUT';

      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: editingAgent.name,
          type: editingAgent.type,
          description: editingAgent.description,
          personality: editingAgent.personality || '',
          workflow: typeof editingAgent.workflow === 'string' ? editingAgent.workflow : (editingAgent.workflow || ''),
          task: editingAgent.task || '',
          identity: editingAgent.identity || '',
          speech_style: editingAgent.speech_style || '',
          restrictions: editingAgent.restrictions,
          variables: editingAgent.variables,
          is_active: editingAgent.is_active
        })
      });

      if (response.ok) {
        toast({
          title: 'Успешно',
          description: isNew ? 'Агент создан' : 'Агент обновлён',
        });
        setShowEditDialog(false);
        setShowCreateDialog(false);
        setEditingAgent(null);
        loadAgents();
      } else {
        const data = await response.json();
        toast({
          title: 'Ошибка',
          description: data.error || 'Не удалось сохранить агента',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Ошибка при сохранении агента',
        variant: 'destructive',
      });
    }
  };

  const handleSandboxSend = async () => {
    if (!editingAgent || !sandboxInput.trim() || sandboxLoading) return;

    const clientMessage = sandboxInput.trim();
    setSandboxInput('');
    setSandboxMessages(prev => [...prev, { sender: 'client', content: clientMessage }]);
    setSandboxLoading(true);

    try {
      const token = await newAuth.getToken();
      if (!token) {
        throw new Error('Требуется авторизация');
      }

      const response = await fetch(`/api/admin/ai-agents/${editingAgent.id}/test`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: clientMessage,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setSandboxMessages(prev => [...prev, { sender: 'agent', content: data.response }]);
        } else {
          throw new Error(data.error || 'Ошибка получения ответа');
        }
      } else {
        const data = await response.json();
        throw new Error(data.error || 'Ошибка запроса');
      }
    } catch (error: any) {
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось получить ответ от агента',
        variant: 'destructive',
      });
      setSandboxMessages(prev => [...prev, {
        sender: 'agent',
        content: `Ошибка: ${error.message || 'Не удалось получить ответ'}`
      }]);
    } finally {
      setSandboxLoading(false);
    }
  };

  const handleDelete = async (agentId: string) => {
    if (!confirm('Вы уверены, что хотите удалить этого агента?')) return;

    try {
      const token = await newAuth.getToken();
      const response = await fetch(`/api/admin/ai-agents/${agentId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        toast({
          title: 'Успешно',
          description: 'Агент удалён',
        });
        loadAgents();
      } else {
        const data = await response.json();
        toast({
          title: 'Ошибка',
          description: data.error || 'Не удалось удалить агента',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Ошибка при удалении агента',
        variant: 'destructive',
      });
    }
  };

  const updateState = (stateKey: string, field: string, value: any) => {
    if (!editingAgent) return;
    const newStates = { ...editingAgent.states };
    if (!newStates[stateKey]) {
      newStates[stateKey] = {};
    }
    newStates[stateKey][field] = value;
    setEditingAgent({ ...editingAgent, states: newStates });
  };

  // === Workflow helpers (новый формат стейтов) ===
  const addWorkflowState = () => {
    if (!editingAgent) return;

    const currentWorkflow = editingAgent.workflow || [];
    const isFirstState = currentWorkflow.length === 0;

    const newState: WorkflowState = {
      name: `State${currentWorkflow.length + 1}`,
      kind: 'StateConfig',
      process_name: `${editingAgent.name || 'Agent'}Process`,
      init_state: isFirstState,
      description: '',
      state_scenarios: [],
      available_tools: {
        SingleStatefulOutboundAgent: ['ForwardSpeech'],
      },
    };

    const newWorkflow = [...currentWorkflow, newState];
    setEditingAgent({ ...editingAgent, workflow: newWorkflow });
  };

  const removeWorkflowState = (index: number) => {
    if (!editingAgent) return;
    const currentWorkflow = editingAgent.workflow || [];
    if (index < 0 || index >= currentWorkflow.length) return;

    const confirmDelete = window.confirm('Удалить этот стейт workflow?');
    if (!confirmDelete) return;

    const newWorkflow = currentWorkflow.filter((_, i) => i !== index);

    // Если удалили стейт с init_state, переназначаем первый стейт как начальный
    if (!newWorkflow.some((s) => s.init_state) && newWorkflow.length > 0) {
      newWorkflow[0].init_state = true;
    }

    setEditingAgent({ ...editingAgent, workflow: newWorkflow });
  };

  const updateWorkflowState = (index: number, field: keyof WorkflowState, value: any) => {
    if (!editingAgent) return;
    const currentWorkflow = editingAgent.workflow || [];
    if (index < 0 || index >= currentWorkflow.length) return;

    const newWorkflow = [...currentWorkflow];
    // Копируем объект стейта, чтобы не мутировать напрямую
    const updatedState: WorkflowState = { ...newWorkflow[index], [field]: value } as WorkflowState;
    newWorkflow[index] = updatedState;

    setEditingAgent({ ...editingAgent, workflow: newWorkflow });
  };

  const addScenario = (stateIndex: number) => {
    if (!editingAgent) return;
    const currentWorkflow = editingAgent.workflow || [];
    if (stateIndex < 0 || stateIndex >= currentWorkflow.length) return;

    const newWorkflow = [...currentWorkflow];
    const scenarios = newWorkflow[stateIndex].state_scenarios || [];

    scenarios.push({
      next_state: '',
      transition_name: '',
      description: '',
    });

    newWorkflow[stateIndex] = {
      ...newWorkflow[stateIndex],
      state_scenarios: scenarios,
    };

    setEditingAgent({ ...editingAgent, workflow: newWorkflow });
  };

  const removeScenario = (stateIndex: number, scenarioIndex: number) => {
    if (!editingAgent) return;
    const currentWorkflow = editingAgent.workflow || [];
    if (stateIndex < 0 || stateIndex >= currentWorkflow.length) return;

    const newWorkflow = [...currentWorkflow];
    const scenarios = newWorkflow[stateIndex].state_scenarios || [];
    if (scenarioIndex < 0 || scenarioIndex >= scenarios.length) return;

    scenarios.splice(scenarioIndex, 1);
    newWorkflow[stateIndex] = {
      ...newWorkflow[stateIndex],
      state_scenarios: scenarios,
    };

    setEditingAgent({ ...editingAgent, workflow: newWorkflow });
  };

  const addState = () => {
    if (!editingAgent) return;
    const stateKey = prompt('Введите ключ стейта (например: greeting):');
    if (!stateKey) return;
    const newStates = { ...editingAgent.states };
    newStates[stateKey] = {
      name: '',
      description: '',
      prompt: '',
      next_states: []
    };
    setEditingAgent({ ...editingAgent, states: newStates });
  };

  const removeState = (stateKey: string) => {
    if (!editingAgent) return;
    if (!confirm(`Удалить стейт "${stateKey}"?`)) return;
    const newStates = { ...editingAgent.states };
    delete newStates[stateKey];
    setEditingAgent({ ...editingAgent, states: newStates });
  };

  const updateVariable = (key: string, value: string) => {
    if (!editingAgent) return;
    const newVariables = { ...editingAgent.variables };
    if (value) {
      newVariables[key] = value;
    } else {
      delete newVariables[key];
    }
    setEditingAgent({ ...editingAgent, variables: newVariables });
  };

  const addVariable = () => {
    if (!editingAgent) return;
    const key = prompt('Введите ключ переменной (например: salon_name):');
    if (!key) return;
    const value = prompt('Введите название переменной (например: Название салона):');
    if (!value) return;
    const newVariables = { ...editingAgent.variables };
    newVariables[key] = value;
    setEditingAgent({ ...editingAgent, variables: newVariables });
  };

  if (loading) {
    return <div className="text-center py-12">Загрузка...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Управление ИИ агентами</h2>
          <p className="text-gray-600 mt-1">{t.dashboard.settings.subtitle}</p>
        </div>
        <Button onClick={handleCreate}>
          <Plus className="h-4 w-4 mr-2" />
          Создать агента
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {agents && agents.length > 0 ? agents.map((agent) => (
          <Card key={agent.id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Bot className="h-5 w-5" />
                  <CardTitle>{agent.name}</CardTitle>
                </div>
                <Badge variant={agent.is_active ? 'default' : 'secondary'}>
                  {agent.is_active ? 'Активен' : 'Неактивен'}
                </Badge>
              </div>
              <CardDescription>
                Тип: {agent.type === 'marketing' ? 'Маркетинговый' : 'Для записи'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm text-gray-600">{agent.description || 'Нет описания'}</p>
              </div>
              <div>
                <p className="text-sm font-medium mb-1">Личность:</p>
                <p className="text-sm text-gray-600">{agent.personality || 'Не указана'}</p>
              </div>
              <div>
                <p className="text-sm font-medium mb-1">Стейты:</p>
                <div className="flex flex-wrap gap-2">
                  {agent.workflow && Array.isArray(agent.workflow) && agent.workflow.length > 0 ? (
                    agent.workflow.map((state) => (
                      <Badge key={state.name} variant="outline">
                        {state.name}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-sm text-gray-400">Нет стейтов</span>
                  )}
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleEdit(agent)}
                  className="flex-1"
                >
                  <Edit className="h-4 w-4 mr-2" />
                  Редактировать
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => handleDelete(agent.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )) : (
          <div className="col-span-2 text-center py-8 text-gray-500">
            Нет агентов. Создайте первого агента, нажав кнопку "Создать агента".
          </div>
        )}
      </div>

      {/* Диалог редактирования/создания */}
      {(showEditDialog || showCreateDialog) && editingAgent && (
        <Dialog open={showEditDialog || showCreateDialog} onOpenChange={(open) => {
          if (!open) {
            setShowEditDialog(false);
            setShowCreateDialog(false);
            setEditingAgent(null);
          }
        }}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                {showCreateDialog ? 'Создать агента' : 'Редактировать агента'}
              </DialogTitle>
              <DialogDescription>
                Настройте стейты, ограничения и личность агента
              </DialogDescription>
            </DialogHeader>

            <Tabs defaultValue="settings" className="w-full">
              <TabsList className={`grid w-full ${showCreateDialog ? 'grid-cols-1' : 'grid-cols-3'}`}>
                <TabsTrigger value="settings">Настройки</TabsTrigger>
                {!showCreateDialog && (
                  <>
                    <TabsTrigger value="tools">Tools</TabsTrigger>
                    <TabsTrigger value="sandbox">Песочница</TabsTrigger>
                  </>
                )}
              </TabsList>

              <TabsContent value="settings" className="space-y-6 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="agent-name">Название</Label>
                    <Input
                      id="agent-name"
                      value={editingAgent.name}
                      onChange={(e) => setEditingAgent({ ...editingAgent, name: e.target.value })}
                    />
                  </div>
                  <div>
                    <Label htmlFor="agent-type">Тип</Label>
                    <select
                      id="agent-type"
                      className="w-full px-3 py-2 border rounded-md"
                      value={editingAgent.type}
                      onChange={(e) => setEditingAgent({ ...editingAgent, type: e.target.value })}
                    >
                      <option value="marketing">Маркетинговый</option>
                      <option value="booking">Для записи</option>
                    </select>
                  </div>
                </div>

                <div>
                  <Label htmlFor="agent-description">Описание</Label>
                  <Textarea
                    id="agent-description"
                    value={editingAgent.description}
                    onChange={(e) => setEditingAgent({ ...editingAgent, description: e.target.value })}
                    rows={2}
                  />
                </div>

                <div>
                  <Label htmlFor="agent-identity">Identity (Личность агента)</Label>
                  <Textarea
                    id="agent-identity"
                    value={editingAgent.identity || ''}
                    onChange={(e) => setEditingAgent({ ...editingAgent, identity: e.target.value })}
                    placeholder="You are a multilingual digital airport transfer assistant, designed to communicate with passengers."
                    rows={3}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Определяет личность и роль агента
                  </p>
                </div>

                <div>
                  <Label htmlFor="agent-task">Task (Задачи агента)</Label>
                  <Textarea
                    id="agent-task"
                    value={editingAgent.task || ''}
                    onChange={(e) => setEditingAgent({ ...editingAgent, task: e.target.value })}
                    placeholder="##### **Initial Engagement:**&#10;- Greet the user at the beginning&#10;&#10;##### **Answering Questions:**&#10;- You represent..."
                    rows={8}
                    className="font-mono text-sm"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Задачи агента в формате Markdown. Используйте ##### для заголовков разделов.
                  </p>
                </div>

                <div>
                  <Label htmlFor="agent-speech-style">Speech Style (Стиль речи)</Label>
                  <Textarea
                    id="agent-speech-style"
                    value={editingAgent.speech_style || ''}
                    onChange={(e) => setEditingAgent({ ...editingAgent, speech_style: e.target.value })}
                    placeholder="You engage in conversation in a friendly and clear manner, using emojis..."
                    rows={4}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Стиль общения агента с клиентами
                  </p>
                </div>

                <div>
                  <Label htmlFor="agent-workflow">Workflow (Воркфлоу)</Label>
                  <Textarea
                    id="agent-workflow"
                    value={typeof editingAgent.workflow === 'string'
                      ? editingAgent.workflow
                      : (editingAgent.workflow
                        ? convertWorkflowToYAML(editingAgent.workflow)
                        : '')}
                    onChange={(e) => setEditingAgent({ ...editingAgent, workflow: e.target.value })}
                    placeholder={`- name: GreetingState
  kind: StateConfig
  process_name: MarketingEngagementProcess
  init_state: true
  description: >
    Warmly greet the client and introduce yourself as the marketing assistant for {salon_name}.
    Create a friendly first impression.
  state_scenarios:
    - next_state: PromotionState
      transition_name: GreetingComplete
      description: The client has been greeted and the conversation is ready to proceed.
  available_tools:
    SingleStatefulOutboundAgent:
      - ForwardSpeech
      - notify_operator
      - create_booking`}
                    rows={20}
                    className="font-mono text-sm"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Определите workflow агента в формате YAML или текста. Доступные tools: <strong>notify_operator</strong> (вызов оператора), <strong>create_booking</strong> (создание бронирования), <strong>send_message</strong> (отправка сообщения клиенту), <strong>get_client_info</strong> (получение информации о клиенте), <strong>get_services</strong> (получение списка услуг), <strong>check_availability</strong> (проверка доступного времени).
                  </p>
                </div>

                <div>
                  <Label htmlFor="agent-restrictions">Ограничения</Label>
                  <Textarea
                    id="agent-restrictions"
                    value={editingAgent.restrictions.text || ''}
                    onChange={(e) => setEditingAgent({
                      ...editingAgent,
                      restrictions: { text: e.target.value }
                    })}
                    placeholder="Например: Не предлагай скидки больше 50%"
                    rows={3}
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label>Переменные (названия для пользователя)</Label>
                    <Button variant="outline" size="sm" onClick={addVariable}>
                      <Plus className="h-4 w-4 mr-2" />
                      Добавить переменную
                    </Button>
                  </div>
                  <div className="space-y-2 border rounded-lg p-4">
                    {Object.entries(editingAgent.variables).map(([key, value]) => (
                      <div key={key} className="flex gap-2">
                        <Input
                          placeholder="Ключ"
                          value={key}
                          disabled
                          className="flex-1"
                        />
                        <Input
                          placeholder="Название"
                          value={value}
                          onChange={(e) => updateVariable(key, e.target.value)}
                          className="flex-1"
                        />
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => updateVariable(key, '')}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                    {Object.keys(editingAgent.variables).length === 0 && (
                      <p className="text-sm text-gray-500 text-center py-2">
                        Нет переменных. Нажмите "Добавить переменную" для создания.
                      </p>
                    )}
                  </div>
                </div>
              </TabsContent>

              {!showCreateDialog && (
                <TabsContent value="tools" className="py-4">
                  <div className="space-y-4">
                    <div className="text-sm text-gray-600 mb-4">
                      Доступные функции (Tools) для Function Calling в GigaChat. Эти функции автоматически доступны агенту при общении с клиентами.
                    </div>

                    <div className="space-y-4">
                      <Card>
                        <CardHeader>
                          <CardTitle className="text-lg">notify_operator</CardTitle>
                          <CardDescription>
                            Уведомить оператора/владельца бизнеса о необходимости его участия в диалоге
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-2">
                            <div>
                              <p className="text-sm font-medium mb-1">Параметры:</p>
                              <ul className="text-sm text-gray-600 list-disc list-inside space-y-1">
                                <li><code className="bg-gray-100 px-1 rounded">message</code> (string, обязательный) - Сообщение для оператора с описанием ситуации</li>
                              </ul>
                            </div>
                            <div>
                              <p className="text-sm font-medium mb-1">Использование:</p>
                              <p className="text-sm text-gray-600">
                                Используется когда клиент задает сложный вопрос, требует персонального внимания или когда нужно подтверждение заказа.
                              </p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      <Card>
                        <CardHeader>
                          <CardTitle className="text-lg">create_booking</CardTitle>
                          <CardDescription>
                            Создать бронирование/заказ на услугу
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-2">
                            <div>
                              <p className="text-sm font-medium mb-1">Параметры:</p>
                              <ul className="text-sm text-gray-600 list-disc list-inside space-y-1">
                                <li><code className="bg-gray-100 px-1 rounded">service_name</code> (string, обязательный) - Название услуги</li>
                                <li><code className="bg-gray-100 px-1 rounded">booking_date</code> (string, обязательный) - Дата в формате YYYY-MM-DD</li>
                                <li><code className="bg-gray-100 px-1 rounded">booking_time</code> (string, обязательный) - Время в формате HH:MM</li>
                                <li><code className="bg-gray-100 px-1 rounded">notes</code> (string, опционально) - Дополнительные заметки</li>
                              </ul>
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      <Card>
                        <CardHeader>
                          <CardTitle className="text-lg">send_message</CardTitle>
                          <CardDescription>
                            Отправить сообщение клиенту через WhatsApp или Telegram
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-2">
                            <div>
                              <p className="text-sm font-medium mb-1">Параметры:</p>
                              <ul className="text-sm text-gray-600 list-disc list-inside space-y-1">
                                <li><code className="bg-gray-100 px-1 rounded">message</code> (string, обязательный) - Текст сообщения</li>
                                <li><code className="bg-gray-100 px-1 rounded">channel</code> (string, обязательный) - Канал: "whatsapp" или "telegram"</li>
                              </ul>
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      <Card>
                        <CardHeader>
                          <CardTitle className="text-lg">get_client_info</CardTitle>
                          <CardDescription>
                            Получить информацию о клиенте: историю разговоров, бронирований и предпочтения
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-2">
                            <div>
                              <p className="text-sm font-medium mb-1">Параметры:</p>
                              <p className="text-sm text-gray-600">Нет параметров</p>
                            </div>
                            <div>
                              <p className="text-sm font-medium mb-1">Использование:</p>
                              <p className="text-sm text-gray-600">
                                Используется для персонализации общения с клиентом.
                              </p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      <Card>
                        <CardHeader>
                          <CardTitle className="text-lg">get_services</CardTitle>
                          <CardDescription>
                            Получить список доступных услуг бизнеса с ценами и описаниями
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-2">
                            <div>
                              <p className="text-sm font-medium mb-1">Параметры:</p>
                              <p className="text-sm text-gray-600">Нет параметров</p>
                            </div>
                            <div>
                              <p className="text-sm font-medium mb-1">Использование:</p>
                              <p className="text-sm text-gray-600">
                                Используется когда клиент спрашивает об услугах или ценах.
                              </p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      <Card>
                        <CardHeader>
                          <CardTitle className="text-lg">check_availability</CardTitle>
                          <CardDescription>
                            Проверить доступное время для записи на указанную дату
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-2">
                            <div>
                              <p className="text-sm font-medium mb-1">Параметры:</p>
                              <ul className="text-sm text-gray-600 list-disc list-inside space-y-1">
                                <li><code className="bg-gray-100 px-1 rounded">date</code> (string, обязательный) - Дата в формате YYYY-MM-DD</li>
                                <li><code className="bg-gray-100 px-1 rounded">service_duration</code> (integer, опционально) - Длительность услуги в минутах (по умолчанию 30)</li>
                              </ul>
                            </div>
                            <div>
                              <p className="text-sm font-medium mb-1">Использование:</p>
                              <p className="text-sm text-gray-600">
                                Используется при бронировании для предложения свободных слотов.
                              </p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                  </div>
                </TabsContent>
              )}

              {!showCreateDialog && (
                <TabsContent value="sandbox" className="py-4">
                  <div className="space-y-4">
                    <div className="text-sm text-gray-600 mb-4">
                      Протестируйте настройки агента. Вы пишете от лица клиента, агент отвечает в соответствии с настройками.
                    </div>

                    <ScrollArea className="h-96 border rounded-lg p-4 mb-4">
                      <div className="space-y-4">
                        {sandboxMessages.length === 0 ? (
                          <div className="text-center text-gray-500 py-8">
                            Начните диалог, отправив сообщение
                          </div>
                        ) : (
                          sandboxMessages.map((msg, idx) => (
                            <div
                              key={idx}
                              className={`flex ${msg.sender === 'client' ? 'justify-end' : 'justify-start'
                                }`}
                            >
                              <div
                                className={`max-w-[80%] rounded-lg p-3 ${msg.sender === 'client'
                                    ? 'bg-blue-100 text-blue-900'
                                    : 'bg-gray-100 text-gray-900'
                                  }`}
                              >
                                <div className="flex items-center gap-2 mb-1">
                                  {msg.sender === 'client' ? (
                                    <span className="text-xs font-medium">Вы (клиент)</span>
                                  ) : (
                                    <>
                                      <Bot className="w-4 h-4" />
                                      <span className="text-xs font-medium">{t.dashboard.chat.roles.agent}</span>
                                    </>
                                  )}
                                </div>
                                <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    </ScrollArea>

                    <div className="flex gap-2">
                      <Input
                        value={sandboxInput}
                        onChange={(e) => setSandboxInput(e.target.value)}
                        onKeyPress={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            handleSandboxSend();
                          }
                        }}
                        placeholder="Введите сообщение от лица клиента..."
                        disabled={sandboxLoading}
                      />
                      <Button
                        onClick={handleSandboxSend}
                        disabled={sandboxLoading || !sandboxInput.trim() || !editingAgent}
                      >
                        {sandboxLoading ? (
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                        ) : (
                          <Send className="w-4 h-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                </TabsContent>
              )}
            </Tabs>

            <DialogFooter>
              <Button variant="outline" onClick={() => {
                setShowEditDialog(false);
                setShowCreateDialog(false);
                setEditingAgent(null);
                setSandboxMessages([]);
                setSandboxInput('');
              }}>
                Отмена
              </Button>
              <Button onClick={handleSave}>
                <Save className="h-4 w-4 mr-2" />
                Сохранить
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};

