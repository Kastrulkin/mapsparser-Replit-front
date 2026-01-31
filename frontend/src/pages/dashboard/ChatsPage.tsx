import React, { useState, useEffect, useRef } from 'react';
import { useOutletContext } from 'react-router-dom';
import { newAuth } from '@/lib/auth_new';
import { useToast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { MessageSquare, Bot, User as UserIcon, Send, Pause, Play, X, FlaskConical } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useLanguage } from '@/i18n/LanguageContext';

interface Conversation {
  id: string;
  client_phone: string;
  client_name: string | null;
  current_state: string;
  last_message_at: string;
  is_agent_paused: number;
  unread_count?: number;
}

interface Message {
  id: string;
  content: string;
  sender: 'client' | 'agent' | 'operator';
  message_type: string;
  created_at: string;
}

interface AgentInfo {
  id: string;
  name: string;
  type: 'marketing' | 'booking';
  description: string | null;
}

export const ChatsPage: React.FC = () => {
  const { currentBusinessId } = useOutletContext<{ currentBusinessId: string }>();
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [sandboxMessages, setSandboxMessages] = useState<Array<{ role: 'user' | 'assistant', content: string }>>([]);
  const [sandboxInput, setSandboxInput] = useState('');
  const [sandboxLoading, setSandboxLoading] = useState(false);
  const { toast } = useToast();
  const { t } = useLanguage();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (currentBusinessId) {
      loadAgents();
    }
  }, [currentBusinessId]);

  useEffect(() => {
    if (selectedAgentId && currentBusinessId) {
      loadConversations();
      // Очищаем песочницу при смене агента
      if (isSandbox) {
        setSandboxMessages([]);
      }
    }
  }, [selectedAgentId, currentBusinessId]);

  useEffect(() => {
    // Не загружаем сообщения для песочницы
    if (selectedConversationId && selectedConversationId !== 'sandbox') {
      loadMessages();
      // Автообновление сообщений каждые 3 секунды
      const interval = setInterval(loadMessages, 3000);
      return () => clearInterval(interval);
    }
  }, [selectedConversationId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadAgents = async () => {
    try {
      const token = await newAuth.getToken();
      if (!token) return;

      const response = await fetch(`/api/business/${currentBusinessId}/ai-agents`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.agents) {
          setAgents(data.agents);
          if (data.agents.length > 0 && !selectedAgentId) {
            setSelectedAgentId(data.agents[0].id);
          }
        }
      }
    } catch (error) {
      console.error('Ошибка загрузки агентов:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadConversations = async () => {
    try {
      const token = await newAuth.getToken();
      if (!token || !selectedAgentId) return;

      const response = await fetch(
        `/api/business/${currentBusinessId}/conversations?agent_id=${selectedAgentId}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setConversations(data.conversations || []);
        }
      }
    } catch (error) {
      console.error('Ошибка загрузки чатов:', error);
    }
  };

  const loadMessages = async () => {
    try {
      const token = await newAuth.getToken();
      if (!token || !selectedConversationId) return;

      const response = await fetch(
        `/api/conversations/${selectedConversationId}/messages`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setMessages(data.messages || []);
        }
      }
    } catch (error) {
      console.error('Ошибка загрузки сообщений:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim() || !selectedConversationId || sending) return;

    try {
      setSending(true);
      const token = await newAuth.getToken();
      if (!token) return;

      const response = await fetch(
        `/api/conversations/${selectedConversationId}/send-message`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            message: newMessage,
            sender: 'operator',
          }),
        }
      );

      if (response.ok) {
        setNewMessage('');
        await loadMessages();
        toast({
          title: t.success,
          description: t.dashboard.chats.messages.sent,
        });
      } else {
        throw new Error('Ошибка отправки сообщения');
      }
    } catch (error: any) {
      toast({
        title: t.error,
        description: error.message || t.dashboard.chats.messages.error,
        variant: 'destructive',
      });
    } finally {
      setSending(false);
    }
  };

  const handleToggleAgent = async (conversationId: string, pause: boolean) => {
    try {
      const token = await newAuth.getToken();
      if (!token) return;

      const response = await fetch(
        `/api/conversations/${conversationId}/toggle-agent`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ pause }),
        }
      );

      if (response.ok) {
        await loadConversations();
        if (conversationId === selectedConversationId) {
          await loadMessages();
        }
        toast({
          title: t.success,
          description: pause ? t.dashboard.chats.messages.agentPaused : t.dashboard.chats.messages.agentResumed,
        });
      }
    } catch (error: any) {
      toast({
        title: t.error,
        description: t.dashboard.chats.messages.statusError,
        variant: 'destructive',
      });
    }
  };

  const selectedConversation = conversations.find(c => c.id === selectedConversationId);
  const selectedAgent = agents.find(a => a.id === selectedAgentId);
  const isSandbox = selectedConversationId === 'sandbox';

  const handleSandboxSend = async () => {
    if (!sandboxInput.trim() || !selectedAgentId || sandboxLoading) return;

    try {
      setSandboxLoading(true);
      const token = await newAuth.getToken();
      if (!token) return;

      // Добавляем сообщение пользователя в историю
      const userMessage = { role: 'user' as const, content: sandboxInput };
      const updatedHistory = [...sandboxMessages, userMessage];
      setSandboxMessages(updatedHistory);
      setSandboxInput('');

      // Формируем историю для отправки
      const conversationHistory = updatedHistory.slice(0, -1).map(msg => ({
        role: msg.role === 'user' ? 'client' : 'agent',
        content: msg.content
      }));

      const response = await fetch(
        `/api/business/${currentBusinessId}/ai-agents/${selectedAgentId}/test`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            message: sandboxInput,
            conversation_history: conversationHistory,
          }),
        }
      );

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          // Добавляем ответ агента в историю
          setSandboxMessages([...updatedHistory, { role: 'assistant', content: data.response }]);
        } else {
          throw new Error(data.error || t.dashboard.chats.messages.error);
        }
      } else {
        const errorData = await response.json();
        throw new Error(errorData.error || t.dashboard.chats.messages.error);
      }
    } catch (error: any) {
      toast({
        title: t.error,
        description: error.message || t.dashboard.chats.messages.error,
        variant: 'destructive',
      });
      // Удаляем последнее сообщение пользователя при ошибке
      setSandboxMessages(sandboxMessages);
    } finally {
      setSandboxLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="h-full flex gap-4">
      {/* Левая панель: Агенты */}
      <div className="w-64 bg-white rounded-lg border border-gray-200 p-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">{t.dashboard.chats.agents.title}</h2>
        <div className="space-y-2">
          {agents.map((agent) => (
            <button
              key={agent.id}
              onClick={() => {
                setSelectedAgentId(agent.id);
                setSelectedConversationId(null);
              }}
              className={`w-full text-left p-3 rounded-lg border transition-colors ${selectedAgentId === agent.id
                  ? 'bg-blue-50 border-blue-200 text-blue-700'
                  : 'bg-gray-50 border-gray-200 text-gray-700 hover:bg-gray-100'
                }`}
            >
              <div className="flex items-center gap-2">
                <Bot className="w-4 h-4" />
                <div className="flex-1">
                  <div className="font-medium">{agent.name}</div>
                  <div className="text-xs text-gray-500">
                    {agent.type === 'marketing' ? t.dashboard.chats.agents.marketing : t.dashboard.chats.agents.booking}
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Средняя панель: Список чатов */}
      <div className="w-80 bg-white rounded-lg border border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            {selectedAgent ? `${t.dashboard.chats.list.title}: ${selectedAgent.name}` : t.dashboard.chats.list.title}
          </h2>
        </div>
        <ScrollArea className="flex-1">
          <div className="p-2">
            {/* Песочница - всегда первый элемент */}
            {selectedAgentId && (
              <button
                onClick={() => {
                  setSelectedConversationId('sandbox');
                  setSandboxMessages([]);
                }}
                className={`w-full text-left p-3 rounded-lg border mb-2 transition-colors ${isSandbox
                    ? 'bg-blue-50 border-blue-200'
                    : 'bg-gray-50 border-gray-200 hover:bg-gray-100'
                  }`}
              >
                <div className="flex items-center gap-2">
                  <FlaskConical className="w-4 h-4 text-purple-500" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-900">{t.dashboard.chats.sandbox.title}</div>
                    <div className="text-xs text-gray-500">{t.dashboard.chats.sandbox.subtitle}</div>
                  </div>
                </div>
              </button>
            )}

            {conversations.length === 0 ? (
              <div className="text-center text-gray-500 py-8">
                {t.dashboard.chats.list.empty}
              </div>
            ) : (
              conversations.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => setSelectedConversationId(conv.id)}
                  className={`w-full text-left p-3 rounded-lg border mb-2 transition-colors ${selectedConversationId === conv.id
                      ? 'bg-blue-50 border-blue-200'
                      : 'bg-gray-50 border-gray-200 hover:bg-gray-100'
                    }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-900 truncate">
                        {conv.client_name || conv.client_phone}
                      </div>
                      <div className="text-xs text-gray-500">
                        {new Date(conv.last_message_at).toLocaleString('ru-RU')}
                      </div>
                    </div>
                    {conv.is_agent_paused === 1 && (
                      <Pause className="w-4 h-4 text-orange-500" />
                    )}
                  </div>
                </button>
              ))
            )}
          </div>
        </ScrollArea>
      </div>

      {/* Правая панель: Детали чата */}
      <div className="flex-1 bg-white rounded-lg border border-gray-200 flex flex-col">
        {isSandbox ? (
          <>
            <div className="p-4 border-b border-gray-200 flex items-center gap-2">
              <FlaskConical className="w-5 h-5 text-purple-500" />
              <div>
                <h3 className="text-lg font-semibold text-gray-900">{t.dashboard.chats.sandbox.title}</h3>
                <div className="text-sm text-gray-500">
                  {t.dashboard.chats.sandbox.subtitle}: {selectedAgent?.name || t.dashboard.chats.sandbox.noAgent}
                </div>
              </div>
            </div>

            <ScrollArea className="flex-1 p-4">
              <div className="space-y-4">
                {sandboxMessages.length === 0 ? (
                  <div className="text-center text-gray-500 py-8">
                    {t.dashboard.chats.sandbox.empty}
                  </div>
                ) : (
                  sandboxMessages.map((msg, idx) => (
                    <div
                      key={idx}
                      className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'
                        }`}
                    >
                      <div
                        className={`max-w-[70%] rounded-lg p-3 ${msg.role === 'user'
                            ? 'bg-blue-100 text-blue-900'
                            : 'bg-green-100 text-green-900'
                          }`}
                      >
                        <div className="flex items-center gap-2 mb-1">
                          {msg.role === 'user' ? (
                            <UserIcon className="w-4 h-4" />
                          ) : (
                            <Bot className="w-4 h-4" />
                          )}
                          <span className="text-xs font-medium">
                            {msg.role === 'user' ? t.dashboard.chats.sandbox.user : t.dashboard.chats.sandbox.agent}
                          </span>
                        </div>
                        <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                      </div>
                    </div>
                  ))
                )}
                {sandboxLoading && (
                  <div className="flex justify-start">
                    <div className="bg-gray-100 rounded-lg p-3">
                      <div className="flex items-center gap-2">
                        <Bot className="w-4 h-4" />
                        <span className="text-xs font-medium">{t.dashboard.chats.sandbox.agentTyping}</span>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>

            <div className="p-4 border-t border-gray-200">
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
                  placeholder={t.dashboard.chats.sandbox.placeholder}
                  disabled={sandboxLoading || !selectedAgentId}
                />
                <Button
                  onClick={handleSandboxSend}
                  disabled={sandboxLoading || !sandboxInput.trim() || !selectedAgentId}
                >
                  <Send className="w-4 h-4" />
                </Button>
              </div>
              {!selectedAgentId && (
                <div className="text-xs text-orange-600 mt-2">
                  {t.dashboard.chats.sandbox.noAgent}
                </div>
              )}
            </div>
          </>
        ) : selectedConversation ? (
          <>
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  {selectedConversation.client_name || selectedConversation.client_phone}
                </h3>
                <div className="text-sm text-gray-500">
                  {selectedConversation.client_phone}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {selectedConversation.is_agent_paused === 1 ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleToggleAgent(selectedConversation.id, false)}
                  >
                    <Play className="w-4 h-4 mr-2" />
                    {t.dashboard.chats.controls.resume}
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleToggleAgent(selectedConversation.id, true)}
                  >
                    <Pause className="w-4 h-4 mr-2" />
                    {t.dashboard.chats.controls.pause}
                  </Button>
                )}
              </div>
            </div>

            <ScrollArea className="flex-1 p-4">
              <div className="space-y-4">
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.sender === 'client' ? 'justify-start' : 'justify-end'
                      }`}
                  >
                    <div
                      className={`max-w-[70%] rounded-lg p-3 ${msg.sender === 'client'
                          ? 'bg-gray-100 text-gray-900'
                          : msg.sender === 'operator'
                            ? 'bg-blue-100 text-blue-900'
                            : 'bg-green-100 text-green-900'
                        }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        {msg.sender === 'client' ? (
                          <UserIcon className="w-4 h-4" />
                        ) : msg.sender === 'operator' ? (
                          <UserIcon className="w-4 h-4" />
                        ) : (
                          <Bot className="w-4 h-4" />
                        )}
                        <span className="text-xs font-medium">
                          {msg.sender === 'client'
                            ? t.dashboard.chats.roles.client
                            : msg.sender === 'operator'
                              ? t.dashboard.chats.roles.operator
                              : t.dashboard.chats.roles.agent}
                        </span>
                      </div>
                      <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                      <div className="text-xs text-gray-500 mt-1">
                        {new Date(msg.created_at).toLocaleString('ru-RU')}
                      </div>
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>

            <div className="p-4 border-t border-gray-200">
              <div className="flex gap-2">
                <Input
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  placeholder={t.dashboard.chats.input.placeholder}
                  disabled={sending || selectedConversation.is_agent_paused !== 1}
                />
                <Button
                  onClick={handleSendMessage}
                  disabled={sending || !newMessage.trim() || selectedConversation.is_agent_paused !== 1}
                >
                  <Send className="w-4 h-4" />
                </Button>
              </div>
              {selectedConversation.is_agent_paused === 1 && (
                <div className="text-xs text-orange-600 mt-2">
                  {t.dashboard.chats.input.agentPaused}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            {selectedAgentId ? t.dashboard.chats.messages.selectChat : t.dashboard.chats.messages.selectAgent}
          </div>
        )}
      </div>
    </div>
  );
};

