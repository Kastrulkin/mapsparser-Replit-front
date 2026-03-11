import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Input } from './ui/input';
import { useToast } from '../hooks/use-toast';
import { newAuth } from '../lib/auth_new';
import { Save, Loader2, History, RefreshCcw, Copy } from 'lucide-react';
import { useLanguage } from '@/i18n/LanguageContext';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from './ui/dialog';

interface Prompt {
  type: string;
  text: string;
  description: string;
  updated_at?: string;
  updated_by?: string;
  current_version?: number;
}

interface PromptVersion {
  version: number;
  prompt_text: string;
  description?: string;
  created_at?: string;
  created_by?: string;
}

interface DiffPreviewState {
  promptType: string;
  version: PromptVersion;
}

interface DiffLine {
  index: number;
  current: string;
  selected: string;
  changed: boolean;
}


export const PromptsManagement: React.FC = () => {
  const { t } = useLanguage();

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
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [publishingVersion, setPublishingVersion] = useState<string | null>(null);
  const [loadingVersions, setLoadingVersions] = useState<Record<string, boolean>>({});
  const [versionsOpen, setVersionsOpen] = useState<Record<string, boolean>>({});
  const [promptVersions, setPromptVersions] = useState<Record<string, PromptVersion[]>>({});
  const [diffPreview, setDiffPreview] = useState<DiffPreviewState | null>(null);
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

  const loadPromptVersions = async (promptType: string) => {
    try {
      setLoadingVersions(prev => ({ ...prev, [promptType]: true }));
      const data = await newAuth.makeRequest(`/admin/prompts/${promptType}`, {
        method: 'GET'
      });
      setPromptVersions(prev => ({
        ...prev,
        [promptType]: data.versions || []
      }));
    } catch (error: any) {
      console.error('Ошибка загрузки истории версий:', error);
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось загрузить историю версий',
        variant: 'destructive'
      });
    } finally {
      setLoadingVersions(prev => ({ ...prev, [promptType]: false }));
    }
  };

  const togglePromptVersions = async (promptType: string) => {
    const nextIsOpen = !versionsOpen[promptType];
    setVersionsOpen(prev => ({ ...prev, [promptType]: nextIsOpen }));
    if (nextIsOpen && !promptVersions[promptType]) {
      await loadPromptVersions(promptType);
    }
  };

  const applyVersionToEditor = (promptType: string, version: PromptVersion) => {
    setEditedPrompts(prev => ({
      ...prev,
      [promptType]: {
        text: version.prompt_text || '',
        description: version.description || ''
      }
    }));
    toast({
      title: 'Версия загружена',
      description: `Версия v${version.version} загружена в редактор`
    });
  };

  const publishVersionAsCurrent = async (promptType: string, version: PromptVersion) => {
    try {
      setPublishingVersion(`${promptType}:${version.version}`);
      await newAuth.makeRequest(`/admin/prompts/${promptType}/version`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          text: version.prompt_text,
          description: version.description || ''
        })
      });
      toast({
        title: 'Успешно',
        description: `Версия v${version.version} применена как текущая`
      });
      await loadPrompts();
      await loadPromptVersions(promptType);
    } catch (error: any) {
      console.error('Ошибка применения версии:', error);
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось применить версию',
        variant: 'destructive'
      });
    } finally {
      setPublishingVersion(null);
    }
  };

  const buildLineDiff = (currentText: string, selectedText: string): DiffLine[] => {
    const currentLines = (currentText || '').split('\n');
    const selectedLines = (selectedText || '').split('\n');
    const maxLen = Math.max(currentLines.length, selectedLines.length);
    const lines: DiffLine[] = [];
    for (let i = 0; i < maxLen; i += 1) {
      const current = currentLines[i] ?? '';
      const selected = selectedLines[i] ?? '';
      lines.push({
        index: i + 1,
        current,
        selected,
        changed: current !== selected
      });
    }
    return lines;
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
              <p className="text-xs text-gray-500 mt-1">
                Текущая версия: v{prompt?.current_version || 1}
              </p>
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

              <div className="border-t border-gray-100 pt-4">
                <div className="flex items-center justify-between gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => togglePromptVersions(type)}
                  >
                    <History className="w-4 h-4 mr-2" />
                    {versionsOpen[type] ? 'Скрыть историю версий' : 'Показать историю версий'}
                  </Button>
                  {versionsOpen[type] && (
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => loadPromptVersions(type)}
                      disabled={!!loadingVersions[type]}
                    >
                      {loadingVersions[type] ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Обновление...
                        </>
                      ) : (
                        <>
                          <RefreshCcw className="w-4 h-4 mr-2" />
                          Обновить
                        </>
                      )}
                    </Button>
                  )}
                </div>

                {versionsOpen[type] && (
                  <div className="mt-3 space-y-2">
                    {loadingVersions[type] ? (
                      <div className="text-sm text-gray-500">Загрузка истории...</div>
                    ) : (promptVersions[type] || []).length === 0 ? (
                      <div className="text-sm text-gray-500">Версии пока не найдены</div>
                    ) : (
                      promptVersions[type].map((version) => {
                        const isCurrent = version.version === (prompt?.current_version || 1);
                        const opKey = `${type}:${version.version}`;
                        return (
                          <div
                            key={`${type}-v-${version.version}`}
                            className="rounded-md border border-gray-200 p-3 bg-gray-50"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="text-sm font-medium text-gray-900">
                                v{version.version}
                                {isCurrent && (
                                  <span className="ml-2 text-xs text-green-700 bg-green-100 px-2 py-0.5 rounded-full">
                                    текущая
                                  </span>
                                )}
                              </div>
                              <div className="text-xs text-gray-500">
                                {version.created_at
                                  ? new Date(version.created_at).toLocaleString('ru-RU')
                                  : 'дата неизвестна'}
                              </div>
                            </div>
                            {version.description && (
                              <p className="text-xs text-gray-600 mt-1">{version.description}</p>
                            )}
                            <p className="text-xs text-gray-500 mt-2 line-clamp-2">
                              {version.prompt_text}
                            </p>
                            <div className="mt-2 flex items-center gap-2">
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => applyVersionToEditor(type, version)}
                              >
                                <Copy className="w-3 h-3 mr-1" />
                                Вставить в редактор
                              </Button>
                              {!isCurrent && (
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="secondary"
                                  disabled={publishingVersion === opKey}
                                  onClick={() => setDiffPreview({ promptType: type, version })}
                                >
                                  {publishingVersion === opKey ? (
                                    <>
                                      <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                                      Применение...
                                    </>
                                  ) : (
                                    'Diff и применить'
                                  )}
                                </Button>
                              )}
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}

      <Dialog open={!!diffPreview} onOpenChange={(open) => !open && setDiffPreview(null)}>
        <DialogContent className="max-w-5xl">
          <DialogHeader>
            <DialogTitle>
              Сравнение версий {diffPreview ? `(${diffPreview.promptType})` : ''}
            </DialogTitle>
            <DialogDescription>
              Слева текущий промпт, справа выбранная версия. Изменённые строки подсвечены.
            </DialogDescription>
          </DialogHeader>

          {diffPreview && (() => {
            const currentPrompt = prompts.find((p) => p.type === diffPreview.promptType);
            const diff = buildLineDiff(currentPrompt?.text || '', diffPreview.version.prompt_text || '');
            const changedCount = diff.filter((d) => d.changed).length;
            return (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-[60vh] overflow-auto">
                <div>
                  <div className="text-sm font-semibold mb-2">Текущая версия (v{currentPrompt?.current_version || 1})</div>
                  <div className="border rounded-md bg-white">
                    {diff.map((line) => (
                      <div
                        key={`current-${line.index}`}
                        className={`px-2 py-1 text-xs font-mono whitespace-pre-wrap border-b border-gray-100 ${line.changed ? 'bg-red-50' : ''}`}
                      >
                        <span className="text-gray-400 mr-2">{line.index}</span>
                        {line.current || ' '}
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-sm font-semibold mb-2">
                    Выбранная версия (v{diffPreview.version.version}) · изменений: {changedCount}
                  </div>
                  <div className="border rounded-md bg-white">
                    {diff.map((line) => (
                      <div
                        key={`selected-${line.index}`}
                        className={`px-2 py-1 text-xs font-mono whitespace-pre-wrap border-b border-gray-100 ${line.changed ? 'bg-green-50' : ''}`}
                      >
                        <span className="text-gray-400 mr-2">{line.index}</span>
                        {line.selected || ' '}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })()}

          <DialogFooter>
            <Button variant="outline" onClick={() => setDiffPreview(null)}>
              Отмена
            </Button>
            <Button
              disabled={!diffPreview || publishingVersion === `${diffPreview.promptType}:${diffPreview.version.version}`}
              onClick={async () => {
                if (!diffPreview) return;
                await publishVersionAsCurrent(diffPreview.promptType, diffPreview.version);
                setDiffPreview(null);
              }}
            >
              {diffPreview && publishingVersion === `${diffPreview.promptType}:${diffPreview.version.version}` ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Применение...
                </>
              ) : (
                'Сделать текущей'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
