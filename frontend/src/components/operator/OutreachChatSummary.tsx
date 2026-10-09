import { Button } from '@/components/ui/button';
import type { GroupPresentation } from '@/components/prospecting/OutreachGroupCard';

export function OutreachChatSummary({ name, presentation, onContinue }: {
  name: string;
  presentation?: GroupPresentation;
  onContinue: (command: string) => void;
}) {
  if (!presentation) return <p role="status">Обновляем результат поиска…</p>;
  const p = presentation;
  return <div className="space-y-2" aria-label={`Результат поиска: ${name}`}>
    <p className="font-medium">{name}</p>
    <p role="status" aria-live="polite">{p.label}</p>
    <p>Найдено: {p.metrics.found}. Подходят: {p.metrics.eligible}{p.metrics.target == null ? '' : ` из ${p.metrics.target}`}. Письма: {p.metrics.prepared}.</p>
    {p.reason && <p>{p.reason}</p>}
    <p className="text-muted-foreground">Списано: {p.expenses.charged == null ? 'уточняется' : `${p.expenses.charged} кр.`}</p>
    <Button size="sm" variant="outline" onClick={() => onContinue(p.status === 'needs_attention' ? 'Покажи причину остановки этого поиска и предложи изменение условий. Ничего не запускай без подтверждения.' : 'Покажи краткий результат этого поиска и предложи следующий шаг.')}>
      Продолжить в чате
    </Button>
    {p.metrics.eligible > 0 && p.metrics.prepared === 0 && !p.active && <Button size="sm" variant="outline" onClick={() => onContinue('Подготовь условия создания индивидуальных писем для подходящих компаний этого поиска. Не отправляй письма.')}>
      Подготовить письма
    </Button>}
  </div>;
}
