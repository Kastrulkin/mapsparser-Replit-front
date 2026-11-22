import { destinations, type Section } from './usePreparedCabinet';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import { newAuth } from '@/lib/auth_new';

export function PreparedDot() {
  return <>
    <span aria-hidden="true" className="inline-block h-2 w-2 shrink-0 rounded-full bg-orange-500" />
    <span className="sr-only">Есть новые материалы</span>
  </>;
}

export function PreparedCabinetPanel({ sections, active, businessId }: {
  businessId?: string | null;
  sections: Section[];
  active?: Section;
}) {
  const { toast } = useToast();
  if (!sections.length) return null;
  const first = sections.find(section => section.unread) || sections[0];

  if (!active) return (
    <section className="mx-auto mb-6 max-w-5xl space-y-3 rounded-2xl border bg-card p-4 sm:p-6" aria-labelledby="prepared-cabinet-title">
      <h2 id="prepared-cabinet-title" className="text-xl font-semibold">Подготовили для вашей компании</h2>
      <p className="text-sm text-muted-foreground">Посмотрите и скопируйте готовые материалы или попросите нас помочь с ведением.</p>
      <ul className="flex flex-wrap gap-x-5 gap-y-2">
        {sections.map(section => (
          <li key={section.key}>
            <Link className="inline-flex min-h-9 items-center gap-2 text-sm font-medium underline-offset-4 hover:underline" to={destinations[section.key].href}>
              {destinations[section.key].label} · {section.items.length}
              {section.unread && <PreparedDot />}
            </Link>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <Button asChild><Link to={destinations[first.key].href}>Посмотреть материалы</Link></Button>
        <Button variant="outline" asChild><Link to="/dashboard/settings">Дать доступ команде</Link></Button>
      </div>
    </section>
  );

  return (
    <section className="mx-auto mb-6 max-w-5xl space-y-4 rounded-2xl border bg-card p-4 sm:p-6" aria-labelledby="prepared-section-title">
      {destinations[active.key].menu === 'maps' && (
        <nav aria-label="Подготовленные материалы для карт" className="flex flex-wrap gap-2">
          {sections.filter(section => destinations[section.key].menu === 'maps').map(section => (
            <Button variant={section.key === active.key ? 'secondary' : 'ghost'} key={section.key} asChild>
              <Link to={destinations[section.key].href} aria-current={section.key === active.key ? 'page' : undefined}>
                {destinations[section.key].label}{section.unread && <PreparedDot />}
              </Link>
            </Button>
          ))}
        </nav>
      )}
      <h2 id="prepared-section-title" className="text-xl font-semibold">Подготовленные материалы · {destinations[active.key].label}</h2>
      {!active.items.length && <p className="text-sm text-muted-foreground">Материалы этого раздела сейчас недоступны. Команда может подготовить их заново.</p>}
      {active.items.map((item, index) => (
        <article className="space-y-2 rounded-xl border p-4" key={index}>
          <h3 className="font-semibold">{item.title}</h3>
          <p className="whitespace-pre-wrap break-words text-sm">{item.text}</p>
          <Button variant="outline" size="sm" onClick={async () => {
            try {
              await navigator.clipboard.writeText(item.text);
              toast({ title: 'Текст скопирован' });
              if (businessId) void newAuth.makeRequest('/business/' + encodeURIComponent(businessId) + '/prepared-cabinet', {
                method: 'POST', body: JSON.stringify({ key: active.key, version: active.version, action: 'copied' }),
              }).catch(() => undefined);
            } catch {
              toast({ title: 'Выделите текст и скопируйте его вручную', variant: 'destructive' });
            }
          }}>Скопировать</Button>
        </article>
      ))}
      <Link className="inline-block text-sm underline" to="/dashboard/today">Все подготовленные материалы</Link>
    </section>
  );
}
