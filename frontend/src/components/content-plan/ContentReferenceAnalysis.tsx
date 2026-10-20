import { useState } from 'react';
import { ChevronDown, ExternalLink } from 'lucide-react';
import { ContentSourceEvidence, researchDate, type SourceResearch } from './ContentSourceResearch';
import { Button } from '@/components/ui/button';

export type EditorialReference = {
  id: string; source_name: string; source_url: string; techniques: string[];
  scope: string; owned: boolean; enabled: boolean; moderation: string;
  moderation_note?: string; strength?: string; version: number;
};

function publicAddress(url: string) {
  try {
    const parsed = new URL(url);
    if (!['https:', 'http:'].includes(parsed.protocol) || parsed.username || parsed.password) return null;
    return parsed;
  } catch { return null; }
}

export function ContentReferenceAnalysis({ items, industryLabel, canManage, busy, ru,
  onToggle, onRemove, research }: {
  research?: SourceResearch | null;
  items: EditorialReference[]; industryLabel: string; canManage: boolean; busy: boolean; ru: boolean;
  onToggle: (item: EditorialReference) => void; onRemove: (item: EditorialReference) => void;
}) {
  const [selected, setSelected] = useState('');
  return <section aria-label={ru ? 'Источники и подходы' : 'Sources and approaches'} className="space-y-4">
    <div className="rounded-xl border bg-muted/30 p-4">
      <p className="text-xs font-medium text-muted-foreground">{ru ? 'Перед составлением контент-плана' : 'Before building a content plan'}</p>
      <h3 className="mt-2 text-lg font-semibold leading-snug">{industryLabel}</h3>
      <p className="mt-2 text-sm leading-6">{ru ? 'Смотрим, как другие компании рассказывают о своей работе. Из каждого примера выбираем полезный приём: структуру текста, стиль, ракурс или способ показать результат.' : 'Study how other companies present their work, then identify useful writing, structure and visual approaches.'}</p>
      <p className="mt-3 text-sm font-medium">{ru ? '1. Изучаем примеры → 2. Обсуждаем подходы с владельцем → 3. Составляем план' : '1. Study examples → 2. Discuss with the owner → 3. Build the plan'}</p>
      <p className="mt-3 text-xs leading-5 text-muted-foreground">{research
        ? (ru ? `${research.sources.length} источников изучено · ${researchDate(research.reviewed_at)}. Подходы предложены для обсуждения, согласование ещё впереди.` : `${research.sources.length} sources reviewed · ${researchDate(research.reviewed_at)}. Proposals await owner discussion.`)
        : (ru ? 'Это подборка ориентиров. Датированное исследование страниц пока не сохранено.' : 'This is a reference set. Dated page research has not been saved yet.')}</p>
    </div>
    <div><h4 className="font-semibold">{ru ? 'Источники: что полезного берём из каждого' : 'Sources: what each example can teach us'}</h4>
      <p className="mt-1 text-sm text-muted-foreground">{ru ? 'Откройте источник: пример → приём → предложение для вашей компании.' : 'Open a source: example → approach → adaptation for your company.'}</p></div>
    {!items.length && <p className="rounded-xl border border-dashed p-4 text-sm leading-6">{ru ? 'Добавьте публичную ссылку и поясните, что в примере полезно: например, короткое начало, последовательность кейса или показ деталей.' : 'Add a public link and explain what makes it useful: an opening, case structure or details.'}</p>}
    {items.map(item => {
      const evidence = research?.sources.find(source => source.reference_id === item.id);
      const address = publicAddress(item.source_url);
      const open = selected === item.id;
      return <article key={item.id} aria-label={`${ru ? 'Источник' : 'Source'}: ${item.source_name}`} className="overflow-hidden rounded-xl border">
        <h4><button type="button" aria-label={item.source_name} aria-expanded={open} aria-controls={`source-approach-${item.id}`}
          onClick={() => setSelected(open ? '' : item.id)} className="flex min-h-14 w-full items-start gap-3 p-4 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">
          <span className="min-w-0 flex-1"><span className="block font-semibold">{item.source_name}</span>
            <span className="mt-1 block text-sm font-normal leading-6 text-muted-foreground">{evidence?.conclusion || item.techniques.find(text => text.trim()) || (ru ? 'Открыть пример' : 'Open example')}</span></span>
          <ChevronDown aria-hidden="true" className={`mt-1 size-4 shrink-0 ${open ? 'rotate-180' : ''}`} />
        </button></h4>
        {open && <div id={`source-approach-${item.id}`} className="space-y-4 border-t p-4">
          {address && <a href={item.source_url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 max-w-full items-center gap-2 break-all text-sm underline underline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">{ru ? 'Открыть оригинал' : 'Open original'} · {address.hostname}<ExternalLink aria-hidden="true" className="size-3.5 shrink-0" /></a>}
          {research && evidence ? <ContentSourceEvidence report={research} referenceId={item.id} ru={ru} /> : <>
            <p className="text-sm leading-6 text-muted-foreground">{ru ? 'Сохранён редакционный ориентир; цитаты и дата изучения страницы ещё не добавлены. Это предложение для обсуждения.' : 'Saved editorial guidance; page quotations and review date have not been added. This is a proposal for discussion.'}</p>
            <h5 className="text-sm font-semibold">{ru ? 'Что предлагаем взять' : 'Approach to consider'}</h5>
            <ul className="list-disc space-y-2 pl-5 text-sm leading-6">{item.techniques.filter(text => text.trim()).map((text, index) => <li key={`${index}-${text}`}>{text}</li>)}</ul>
          </>}
          <details className="border-t pt-2 text-sm"><summary className="min-h-11 cursor-pointer py-2 font-medium">{ru ? 'Использование ориентира в новых черновиках' : 'Use this reference in new drafts'}</summary>
            <p className="mb-3 leading-6 text-muted-foreground">{item.enabled ? (ru ? 'Ориентир доступен при подготовке новых черновиков. Эта настройка не означает согласование подхода с владельцем.' : 'Available for new drafts. This setting does not mean owner approval.') : (ru ? 'Ориентир исключён из подготовки новых черновиков. Его по-прежнему можно изучать.' : 'Excluded from new drafts. You can still study it.')}</p>
            <div className="flex flex-wrap gap-2"><Button variant="outline" className="min-h-11" disabled={!canManage || busy} aria-label={`${item.enabled ? (ru ? 'Отключить' : 'Disable') : (ru ? 'Включить' : 'Enable')} ${item.source_name}`} onClick={() => onToggle(item)}>{item.enabled ? (ru ? 'Отключить' : 'Disable') : (ru ? 'Включить' : 'Enable')}</Button>
            {item.owned && item.scope !== 'industry' && canManage && <Button variant="ghost" className="h-auto min-h-11 whitespace-normal" disabled={busy} onClick={() => onRemove(item)}>{ru ? 'Убрать из моих ориентиров' : 'Remove my reference'}</Button>}</div>
            {(item.strength || item.moderation_note) && <p className="mt-3 whitespace-pre-wrap text-muted-foreground">{item.strength} {item.moderation_note}</p>}
          </details>
        </div>}
      </article>;
    })}
    {research && <details className="rounded-xl border p-4 text-sm"><summary className="min-h-11 cursor-pointer py-2 font-medium">{ru ? 'Как проводили исследование' : 'Research method'}</summary>
      <p className="mt-2 leading-6">{research.methodology}</p><ul className="mt-3 list-disc space-y-2 pl-5 leading-6">{research.limitations.map(text => <li key={text}>{text}</li>)}</ul>
    </details>}
    <p className="text-xs leading-5 text-muted-foreground">{ru ? 'Берём принципы подачи. Чужие тексты, фотографии, клиенты, технологии и обещания не становятся материалами или фактами вашей компании.' : 'Learn the editorial principles. Other companies’ copy, photos, clients, processes and promises are not your company’s facts or assets.'}</p>
  </section>;
}
