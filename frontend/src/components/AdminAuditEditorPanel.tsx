import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, RotateCcw, Save, UploadCloud } from 'lucide-react';
import { api } from '@/services/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';

type SummaryBlock = {
  title: string;
  body: string;
};

type ListBlock = {
  title: string;
  items: string[];
};

type TopIssueItem = {
  title: string;
  body: string;
  priority: string;
};

type TopIssuesBlock = {
  title: string;
  items: TopIssueItem[];
};

type ActionPlanSection = {
  key: string;
  title: string;
  items: string[];
};

type ActionPlanBlock = {
  title: string;
  sections: ActionPlanSection[];
};

type EditorBlocks = {
  summary: SummaryBlock;
  strong_demand: ListBlock;
  weak_demand: ListBlock;
  why: ListBlock;
  top_issues: TopIssuesBlock;
  action_plan: ActionPlanBlock;
};

type BlockDiff = {
  changed_in_draft: boolean;
  changed_in_published: boolean;
  edit_kind: string;
};

type EditorResponse = {
  success?: boolean;
  edit_status?: string;
  generated: EditorBlocks;
  edited: EditorBlocks;
  published: EditorBlocks;
  diff: Record<string, BlockDiff>;
  meta?: {
    edited_at?: string | null;
    published_at?: string | null;
    lead_name?: string | null;
  };
};

type AdminAuditEditorPanelProps = {
  leadId?: string;
  enabled: boolean;
  onPublished?: () => void;
};

const DEMAND_BLOCKS: Array<{ key: keyof EditorBlocks; label: string }> = [
  { key: 'strong_demand', label: 'Сильный спрос' },
  { key: 'weak_demand', label: 'Слабый спрос' },
  { key: 'why', label: 'Почему' },
];

const formatDateTime = (value?: string | null) => {
  if (!value) return '—';
  return new Date(value).toLocaleString('ru-RU');
};

const editKindLabel = (value?: string) => {
  switch (value) {
    case 'minor_copy_edit':
      return 'Копирайт';
    case 'structure_edit':
      return 'Структура';
    case 'semantic_rewrite':
      return 'Смысл';
    default:
      return 'Без изменений';
  }
};

const duplicateBlocks = (blocks: EditorBlocks): EditorBlocks => ({
  summary: { ...blocks.summary },
  strong_demand: { ...blocks.strong_demand, items: [...blocks.strong_demand.items] },
  weak_demand: { ...blocks.weak_demand, items: [...blocks.weak_demand.items] },
  why: { ...blocks.why, items: [...blocks.why.items] },
  top_issues: {
    ...blocks.top_issues,
    items: blocks.top_issues.items.map((item) => ({ ...item })),
  },
  action_plan: {
    ...blocks.action_plan,
    sections: blocks.action_plan.sections.map((section) => ({
      ...section,
      items: [...section.items],
    })),
  },
});

const StringListEditor = ({
  block,
  onChange,
}: {
  block: ListBlock;
  onChange: (next: ListBlock) => void;
}) => {
  const updateItem = (index: number, value: string) => {
    onChange({
      ...block,
      items: block.items.map((item, itemIndex) => (itemIndex === index ? value : item)),
    });
  };

  const removeItem = (index: number) => {
    onChange({
      ...block,
      items: block.items.filter((_, itemIndex) => itemIndex !== index),
    });
  };

  const moveItem = (index: number, direction: -1 | 1) => {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= block.items.length) return;
    const nextItems = [...block.items];
    const current = nextItems[index];
    nextItems[index] = nextItems[targetIndex];
    nextItems[targetIndex] = current;
    onChange({ ...block, items: nextItems });
  };

  return (
    <div className="space-y-3">
      <Input value={block.title} onChange={(event) => onChange({ ...block, title: event.target.value })} />
      <div className="space-y-2">
        {block.items.map((item, index) => (
          <div key={`${block.title}-${index}`} className="flex items-start gap-2">
            <Textarea
              value={item}
              onChange={(event) => updateItem(index, event.target.value)}
              rows={2}
              className="min-h-[72px]"
            />
            <div className="flex flex-col gap-1">
              <Button type="button" variant="outline" size="sm" onClick={() => moveItem(index, -1)} disabled={index === 0}>
                ↑
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => moveItem(index, 1)}
                disabled={index === block.items.length - 1}
              >
                ↓
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={() => removeItem(index)}>
                ✕
              </Button>
            </div>
          </div>
        ))}
      </div>
      <Button type="button" variant="outline" size="sm" onClick={() => onChange({ ...block, items: [...block.items, ''] })}>
        Добавить строку
      </Button>
    </div>
  );
};

const TopIssuesEditor = ({
  block,
  onChange,
}: {
  block: TopIssuesBlock;
  onChange: (next: TopIssuesBlock) => void;
}) => {
  const updateItem = (index: number, patch: Partial<TopIssueItem>) => {
    onChange({
      ...block,
      items: block.items.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    });
  };

  const removeItem = (index: number) => {
    onChange({
      ...block,
      items: block.items.filter((_, itemIndex) => itemIndex !== index),
    });
  };

  const moveItem = (index: number, direction: -1 | 1) => {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= block.items.length) return;
    const nextItems = [...block.items];
    const current = nextItems[index];
    nextItems[index] = nextItems[targetIndex];
    nextItems[targetIndex] = current;
    onChange({ ...block, items: nextItems });
  };

  return (
    <div className="space-y-3">
      <Input value={block.title} onChange={(event) => onChange({ ...block, title: event.target.value })} />
      <div className="space-y-3">
        {block.items.map((item, index) => (
          <div key={`top-issue-${index}`} className="rounded-lg border border-slate-200 p-3 space-y-2">
            <div className="flex items-start gap-2">
              <div className="flex-1 space-y-2">
                <Input value={item.title} placeholder="Заголовок" onChange={(event) => updateItem(index, { title: event.target.value })} />
                <Input value={item.priority} placeholder="Приоритет" onChange={(event) => updateItem(index, { priority: event.target.value })} />
                <Textarea
                  value={item.body}
                  placeholder="Пояснение"
                  rows={3}
                  onChange={(event) => updateItem(index, { body: event.target.value })}
                />
              </div>
              <div className="flex flex-col gap-1">
                <Button type="button" variant="outline" size="sm" onClick={() => moveItem(index, -1)} disabled={index === 0}>
                  ↑
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => moveItem(index, 1)}
                  disabled={index === block.items.length - 1}
                >
                  ↓
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => removeItem(index)}>
                  ✕
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => onChange({ ...block, items: [...block.items, { title: '', body: '', priority: '' }] })}
      >
        Добавить проблему
      </Button>
    </div>
  );
};

const ActionPlanEditor = ({
  block,
  onChange,
}: {
  block: ActionPlanBlock;
  onChange: (next: ActionPlanBlock) => void;
}) => {
  const updateSectionItems = (sectionKey: string, items: string[]) => {
    onChange({
      ...block,
      sections: block.sections.map((section) => (section.key === sectionKey ? { ...section, items } : section)),
    });
  };

  return (
    <div className="space-y-3">
      <Input value={block.title} onChange={(event) => onChange({ ...block, title: event.target.value })} />
      <div className="space-y-4">
        {block.sections.map((section) => (
          <div key={section.key} className="rounded-lg border border-slate-200 p-3">
            <div className="text-sm font-medium text-slate-900 mb-2">{section.title}</div>
            <StringListEditor
              block={{ title: section.title, items: section.items }}
              onChange={(next) => updateSectionItems(section.key, next.items)}
            />
          </div>
        ))}
      </div>
    </div>
  );
};

const renderReadonlyLines = (lines: string[]) => (
  <div className="space-y-2 text-sm text-slate-700">
    {lines.length > 0 ? lines.map((line, index) => <div key={`${line}-${index}`}>• {line}</div>) : <div>—</div>}
  </div>
);

const AdminAuditEditorPanel: React.FC<AdminAuditEditorPanelProps> = ({
  leadId,
  enabled,
  onPublished,
}) => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<EditorResponse | null>(null);
  const [draft, setDraft] = useState<EditorBlocks | null>(null);

  const loadEditor = async () => {
    if (!leadId || !enabled) {
      setResponse(null);
      setDraft(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const apiResponse = await api.get(`/admin/prospecting/lead/${leadId}/audit-editor`);
      const nextResponse: EditorResponse = apiResponse.data;
      setResponse(nextResponse);
      setDraft(duplicateBlocks(nextResponse.edited));
    } catch (loadError: unknown) {
      const message = loadError instanceof Error ? loadError.message : 'Не удалось загрузить редактор аудита';
      setError(message);
      setResponse(null);
      setDraft(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadEditor();
  }, [leadId, enabled]);

  const hasChanges = useMemo(() => {
    if (!response || !draft) return false;
    return JSON.stringify(response.edited) !== JSON.stringify(draft);
  }, [draft, response]);

  const saveDraft = async () => {
    if (!leadId || !draft) return;
    setSaving(true);
    setError(null);
    try {
      const apiResponse = await api.put(`/admin/prospecting/lead/${leadId}/audit-editor`, { blocks: draft });
      const nextResponse: EditorResponse = apiResponse.data;
      setResponse(nextResponse);
      setDraft(duplicateBlocks(nextResponse.edited));
      toast.success('Черновик аудита сохранён');
    } catch (saveError: unknown) {
      const message = saveError instanceof Error ? saveError.message : 'Не удалось сохранить черновик';
      setError(message);
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  const publish = async () => {
    if (!leadId) return;
    setPublishing(true);
    setError(null);
    try {
      const apiResponse = await api.post(`/admin/prospecting/lead/${leadId}/audit-editor/publish`, {});
      const nextResponse: EditorResponse = apiResponse.data;
      setResponse(nextResponse);
      setDraft(duplicateBlocks(nextResponse.edited));
      toast.success('Аудит опубликован');
      if (onPublished) onPublished();
    } catch (publishError: unknown) {
      const message = publishError instanceof Error ? publishError.message : 'Не удалось опубликовать аудит';
      setError(message);
      toast.error(message);
    } finally {
      setPublishing(false);
    }
  };

  const resetBlock = async (blockKey: keyof EditorBlocks) => {
    if (!leadId) return;
    try {
      const apiResponse = await api.post(`/admin/prospecting/lead/${leadId}/audit-editor/reset-block`, { block: blockKey });
      const nextResponse: EditorResponse = apiResponse.data;
      setResponse(nextResponse);
      setDraft(duplicateBlocks(nextResponse.edited));
      toast.success('Блок сброшен к автогену');
    } catch (resetError: unknown) {
      const message = resetError instanceof Error ? resetError.message : 'Не удалось сбросить блок';
      setError(message);
      toast.error(message);
    }
  };

  if (!enabled) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Редактор аудита</CardTitle>
          <CardDescription>Сначала создайте публичную страницу аудита, потом можно будет править блоки вручную.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Редактор аудита</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-2 text-sm text-slate-600">
          <Loader2 className="h-4 w-4 animate-spin" />
          Загружаем editor state…
        </CardContent>
      </Card>
    );
  }

  if (error && !response) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Редактор аудита</CardTitle>
          <CardDescription>{error}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button type="button" variant="outline" onClick={() => void loadEditor()}>
            Повторить
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!response || !draft) {
    return null;
  }

  const diff = response.diff || {};
  const renderBlockMeta = (blockKey: keyof EditorBlocks) => {
    const current = diff[String(blockKey)] || { changed_in_draft: false, changed_in_published: false, edit_kind: 'unchanged' };
    return (
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={current.changed_in_draft ? 'default' : 'outline'}>
          {current.changed_in_draft ? 'Есть draft-правки' : 'Без draft-правок'}
        </Badge>
        <Badge variant="outline">{editKindLabel(current.edit_kind)}</Badge>
        {current.changed_in_published ? <Badge variant="secondary">Опубликовано</Badge> : null}
      </div>
    );
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <CardTitle>Редактор аудита</CardTitle>
            <CardDescription>
              Generated / Edited / Published для public audit. Пишите конкретно, без внутренних терминов системы.
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">Статус: {response.edit_status || 'generated'}</Badge>
            <Badge variant="outline">Черновик: {formatDateTime(response.meta?.edited_at)}</Badge>
            <Badge variant="outline">Публикация: {formatDateTime(response.meta?.published_at)}</Badge>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 pt-2">
          <Button type="button" variant="outline" onClick={() => void loadEditor()}>
            Обновить
          </Button>
          <Button type="button" variant="outline" onClick={() => void saveDraft()} disabled={saving || !hasChanges}>
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Сохранить черновик
          </Button>
          <Button type="button" onClick={() => void publish()} disabled={publishing || saving}>
            {publishing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <UploadCloud className="mr-2 h-4 w-4" />}
            Опубликовать
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {error ? <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div> : null}

        <div className="grid grid-cols-1 gap-4 rounded-xl border border-slate-200 p-4 lg:grid-cols-2">
          <div className="space-y-3">
            <div className="text-sm font-semibold text-slate-900">Generated</div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div className="text-sm font-medium text-slate-900">{response.generated.summary.title}</div>
              <div className="mt-2 text-sm text-slate-700 whitespace-pre-wrap">{response.generated.summary.body || '—'}</div>
            </div>
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-semibold text-slate-900">Edited</div>
              {renderBlockMeta('summary')}
            </div>
            <div className="rounded-lg border border-slate-200 p-3">
              <Input value={draft.summary.title} onChange={(event) => setDraft({ ...draft, summary: { ...draft.summary, title: event.target.value } })} />
              <Textarea
                value={draft.summary.body}
                onChange={(event) => setDraft({ ...draft, summary: { ...draft.summary, body: event.target.value } })}
                rows={5}
                className="mt-2"
              />
              <Button type="button" variant="outline" size="sm" className="mt-3" onClick={() => void resetBlock('summary')}>
                <RotateCcw className="mr-2 h-4 w-4" />
                Сбросить блок
              </Button>
            </div>
          </div>
        </div>

        {DEMAND_BLOCKS.map(({ key, label }) => (
          <div key={key} className="grid grid-cols-1 gap-4 rounded-xl border border-slate-200 p-4 lg:grid-cols-2">
            <div className="space-y-3">
              <div className="text-sm font-semibold text-slate-900">Generated · {label}</div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="text-sm font-medium text-slate-900">{response.generated[key].title}</div>
                <div className="mt-2">{renderReadonlyLines(response.generated[key].items)}</div>
              </div>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div className="text-sm font-semibold text-slate-900">Edited · {label}</div>
                {renderBlockMeta(key)}
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <StringListEditor block={draft[key]} onChange={(next) => setDraft({ ...draft, [key]: next })} />
                <Button type="button" variant="outline" size="sm" className="mt-3" onClick={() => void resetBlock(key)}>
                  <RotateCcw className="mr-2 h-4 w-4" />
                  Сбросить блок
                </Button>
              </div>
            </div>
          </div>
        ))}

        <div className="grid grid-cols-1 gap-4 rounded-xl border border-slate-200 p-4 lg:grid-cols-2">
          <div className="space-y-3">
            <div className="text-sm font-semibold text-slate-900">Generated · Топ-проблемы</div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-3">
              {response.generated.top_issues.items.length > 0 ? response.generated.top_issues.items.map((item, index) => (
                <div key={`generated-top-${index}`} className="rounded-lg border border-slate-200 bg-white p-3">
                  <div className="text-sm font-medium text-slate-900">{item.title}</div>
                  <div className="text-xs text-slate-500 mt-1">{item.priority || '—'}</div>
                  <div className="mt-2 text-sm text-slate-700 whitespace-pre-wrap">{item.body || '—'}</div>
                </div>
              )) : <div>—</div>}
            </div>
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-semibold text-slate-900">Edited · Топ-проблемы</div>
              {renderBlockMeta('top_issues')}
            </div>
            <div className="rounded-lg border border-slate-200 p-3">
              <TopIssuesEditor block={draft.top_issues} onChange={(next) => setDraft({ ...draft, top_issues: next })} />
              <Button type="button" variant="outline" size="sm" className="mt-3" onClick={() => void resetBlock('top_issues')}>
                <RotateCcw className="mr-2 h-4 w-4" />
                Сбросить блок
              </Button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 rounded-xl border border-slate-200 p-4 lg:grid-cols-2">
          <div className="space-y-3">
            <div className="text-sm font-semibold text-slate-900">Generated · План внедрения</div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-3">
              {response.generated.action_plan.sections.map((section) => (
                <div key={`generated-plan-${section.key}`}>
                  <div className="text-sm font-medium text-slate-900">{section.title}</div>
                  <div className="mt-2">{renderReadonlyLines(section.items)}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-semibold text-slate-900">Edited · План внедрения</div>
              {renderBlockMeta('action_plan')}
            </div>
            <div className="rounded-lg border border-slate-200 p-3">
              <ActionPlanEditor block={draft.action_plan} onChange={(next) => setDraft({ ...draft, action_plan: next })} />
              <Button type="button" variant="outline" size="sm" className="mt-3" onClick={() => void resetBlock('action_plan')}>
                <RotateCcw className="mr-2 h-4 w-4" />
                Сбросить блок
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default AdminAuditEditorPanel;
