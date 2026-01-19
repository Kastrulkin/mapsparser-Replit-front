import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Input } from './ui/input';
import { useToast } from '../hooks/use-toast';
import { newAuth } from '../lib/auth_new';
import { Save, Loader2 } from 'lucide-react';

interface Prompt {
  type: string;
  text: string;
  description: string;
  updated_at?: string;
  updated_by?: string;
}

const PROMPT_TYPES = {
  service_optimization: {
    label: 'Оптимизация услуг',
    description: 'Промпт для оптимизации услуг и прайс-листа'
  },
  review_reply: {
    label: t.dashboard.card.reviewReply.title,
    description: 'Промпт для генерации ответов на отзывы'
  },
  news_generation: {
    label: 'Генерация новостей',
    description: 'Промпт для генерации новостей'
  }
};

export const PromptsManagement: React.FC = () => {
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [editedPrompts, setEditedPrompts] = useState<Record<string, { text: string; description: string }>>({});
  const { toast } = useToast();

  useEffect(() => {
    loadPrompts();
  }, []);

  const loadPrompts = async () => {
    try {
      setLoading(true);
      const data = await newAuth.makeRequest('/admin/prompts', {
        method: 'GET'
      });
      
      setPrompts(data.prompts || []);
      
      // Инициализируем editedPrompts
      const initial: Record<string, { text: string; description: string }> = {};
      data.prompts?.forEach((p: Prompt) => {
        initial[p.type] = { text: p.text, description: p.description || '' };
      });
      setEditedPrompts(initial);
    } catch (error: any) {
      console.error('Ошибка загрузки промптов:', error);
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось загрузить промпты',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (promptType: string) => {
    try {
      setSaving(promptType);
      const edited = editedPrompts[promptType];
      
      if (!edited) {
        throw new Error('Нет изменений для сохранения');
      }

      await newAuth.makeRequest(`/admin/prompts/${promptType}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          text: edited.text,
          description: edited.description
        })
      });

      toast({
        title: 'Успешно',
        description: 'Промпт сохранён'
      });
      await loadPrompts(); // Перезагружаем для получения обновлённых данных
    } catch (error: any) {
      console.error('Ошибка сохранения промпта:', error);
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось сохранить промпт',
        variant: 'destructive'
      });
    } finally {
      setSaving(null);
    }
  };

  const handleTextChange = (promptType: string, field: 'text' | 'description', value: string) => {
    setEditedPrompts(prev => ({
      ...prev,
      [promptType]: {
        ...prev[promptType],
        [field]: value
      }
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
        <span className="ml-2">Загрузка промптов...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Промпты анализа</h2>
        <p className="text-gray-600 mt-1">Редактируйте промпты для AI-генерации контента</p>
      </div>

      {Object.entries(PROMPT_TYPES).map(([type, info]) => {
        const prompt = prompts.find(p => p.type === type);
        const edited = editedPrompts[type];
        const hasChanges = prompt && edited && (
          prompt.text !== edited.text || 
          (prompt.description || '') !== edited.description
        );

        return (
          <div key={type} className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="mb-4">
              <h3 className="text-lg font-semibold text-gray-900">{info.label}</h3>
              <p className="text-sm text-gray-600 mt-1">{info.description}</p>
              {prompt?.updated_at && (
                <p className="text-xs text-gray-500 mt-1">
                  Обновлено: {new Date(prompt.updated_at).toLocaleString('ru-RU')}
                </p>
              )}
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Описание промпта
                </label>
                <Input
                  value={edited?.description || ''}
                  onChange={(e) => handleTextChange(type, 'description', e.target.value)}
                  placeholder="Краткое описание назначения промпта"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Текст промпта
                </label>
                <Textarea
                  value={edited?.text || ''}
                  onChange={(e) => handleTextChange(type, 'text', e.target.value)}
                  placeholder="Введите текст промпта..."
                  rows={15}
                  className="font-mono text-sm"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Используйте {'{'}переменные{'}'} для подстановки значений (например: {'{'}language_name{'}'}, {'{'}tone{'}'})
                </p>
              </div>

              <div className="flex justify-end">
                <Button
                  onClick={() => handleSave(type)}
                  disabled={!hasChanges || saving === type}
                  variant={hasChanges ? 'default' : 'outline'}
                >
                  {saving === type ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Сохранение...
                    </>
                  ) : (
                    <>
                      <Save className="w-4 h-4 mr-2" />
                      Сохранить
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

