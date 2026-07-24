import { Check, Pencil, RotateCcw, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  OutreachTouchMessage,
  OutreachTouchMessageDraft,
  outreachTouchMessageDraft,
} from '@/components/prospecting/outreachTouchMessage';

type OutreachTouchMessageEditorProps = {
  touch: OutreachTouchMessage;
  draft?: OutreachTouchMessageDraft;
  editing: boolean;
  disabled?: boolean;
  onStart: () => void;
  onChange: (draft: OutreachTouchMessageDraft) => void;
  onFinish: () => void;
  onCancel: () => void;
  onReset: () => void;
};

export function OutreachTouchMessageEditor({
  touch,
  draft,
  editing,
  disabled = false,
  onStart,
  onChange,
  onFinish,
  onCancel,
  onReset,
}: OutreachTouchMessageEditorProps) {
  const current = draft || outreachTouchMessageDraft(touch);
  const updateDraft = (field: 'subject' | 'text', value: string) => {
    const next = { ...current, [field]: value };
    onChange({
      ...next,
      humanEdited: next.subject.trim() !== next.originalSubject || next.text.trim() !== next.originalText,
    });
  };

  if (editing) {
    return (
      <div className="mt-3 rounded-xl bg-slate-50 p-3 shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_1px_2px_-1px_rgba(15,23,42,0.06)]">
        {touch.channel === 'email' ? (
          <label className="block">
            <span className="text-xs font-semibold text-slate-700">Тема письма</span>
            <Input
              value={current.subject}
              onChange={(event) => updateDraft('subject', event.target.value)}
              maxLength={200}
              className="mt-1 h-11 bg-white"
            />
          </label>
        ) : null}
        <label className="mt-3 block">
          <span className="text-xs font-semibold text-slate-700">Текст сообщения</span>
          <Textarea
            value={current.text}
            onChange={(event) => updateDraft('text', event.target.value)}
            maxLength={3000}
            className="mt-1 min-h-32 resize-y bg-white text-sm leading-6"
          />
        </label>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-pretty text-xs leading-5 text-slate-500">
            Правка не отправится автоматически. Сначала LocalOS проверит факты, затем сохранит новую версию цепочки.
          </p>
          <div className="flex shrink-0 gap-2">
            <Button type="button" variant="ghost" onClick={onCancel} className="min-h-10 transition-transform active:scale-[0.96]">
              <X className="mr-1.5 h-4 w-4" /> Отмена
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={onFinish}
              disabled={!current.text.trim()}
              className="min-h-10 bg-white transition-transform active:scale-[0.96]"
            >
              <Check className="mr-1.5 h-4 w-4" /> Применить правку
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-2">
      {current.subject ? <div className="text-sm font-semibold text-slate-950">Тема: {current.subject}</div> : null}
      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-800">{current.text}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={onStart}
          disabled={disabled}
          className="min-h-10 bg-white transition-transform active:scale-[0.96]"
        >
          <Pencil className="mr-1.5 h-4 w-4" /> Редактировать
        </Button>
        {current.humanEdited ? (
          <>
            <span className="rounded-full bg-orange-50 px-2.5 py-1 text-xs font-semibold text-orange-800">Изменено вручную</span>
            <Button type="button" variant="ghost" onClick={onReset} className="min-h-10 transition-transform active:scale-[0.96]">
              <RotateCcw className="mr-1.5 h-4 w-4" /> Вернуть исходный текст
            </Button>
          </>
        ) : null}
      </div>
    </div>
  );
}
