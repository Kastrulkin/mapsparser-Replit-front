import { ReactNode } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { AlertTriangle, ChevronRight, SendHorizontal } from 'lucide-react';

type Tone = 'default' | 'success' | 'warning' | 'danger' | 'info';

const toneStyles: Record<Tone, string> = {
  default: 'border-border bg-background',
  success: 'border-emerald-200 bg-emerald-50',
  warning: 'border-amber-200 bg-amber-50',
  danger: 'border-rose-200 bg-rose-50',
  info: 'border-sky-200 bg-sky-50',
};

const badgeVariantByTone: Record<Tone, 'outline' | 'secondary' | 'destructive' | 'default'> = {
  default: 'outline',
  success: 'secondary',
  warning: 'secondary',
  danger: 'destructive',
  info: 'outline',
};

export function LeadStatusBadge({ label, tone = 'default' }: { label: string; tone?: Tone }) {
  return <Badge variant={badgeVariantByTone[tone]}>{label}</Badge>;
}

export function ChannelWarning({ title, description, action }: { title?: string; description: string; action?: ReactNode }) {
  return (
    <Alert className="border-amber-200 bg-amber-50 text-amber-950">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>{title || 'Нужна проверка'}</AlertTitle>
      <AlertDescription className="mt-2 flex flex-wrap items-center gap-3">
        <span>{description}</span>
        {action}
      </AlertDescription>
    </Alert>
  );
}

export function ErrorSummary({
  title,
  description,
  actions,
}: {
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="text-sm font-semibold text-amber-950">{title}</div>
          <div className="mt-1 text-sm text-amber-900/90">{description}</div>
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
    </div>
  );
}

export function StickyBulkActionBar({
  count,
  label,
  children,
}: {
  count: number;
  label: string;
  children: ReactNode;
}) {
  if (count <= 0) {
    return null;
  }

  return (
    <div className="sticky bottom-4 z-20 rounded-2xl border border-slate-200 bg-white/95 p-3 shadow-lg backdrop-blur">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="text-sm font-medium text-slate-900">
          Выбрано: {count}. {label}
        </div>
        <div className="flex flex-wrap gap-2">{children}</div>
      </div>
    </div>
  );
}

export function LeadList({
  title,
  description,
  count,
  children,
  className,
}: {
  title: string;
  description: string;
  count: number;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn('min-h-[620px]', className)}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">{title}</CardTitle>
            <CardDescription className="mt-1">{description}</CardDescription>
          </div>
          <Badge variant="outline">{count}</Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <ScrollArea className="h-[560px] pr-3">{children}</ScrollArea>
      </CardContent>
    </Card>
  );
}

export function LeadListItem({
  title,
  subtitle,
  location,
  statusLabel,
  statusTone = 'default',
  channelLabel,
  languageLabel,
  lastActionLabel,
  contactBadges,
  warning,
  selected,
  onSelect,
  checked,
  onCheckedChange,
}: {
  title: string;
  subtitle?: string;
  location?: string;
  statusLabel: string;
  statusTone?: Tone;
  channelLabel?: string;
  languageLabel?: string;
  lastActionLabel?: string;
  contactBadges?: ReactNode;
  warning?: string;
  selected?: boolean;
  onSelect?: () => void;
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'w-full rounded-xl border p-3 text-left transition focus:outline-none focus:ring-2 focus:ring-primary/40',
        selected ? 'border-primary bg-primary/5 shadow-sm' : toneStyles[statusTone],
      )}
    >
      <div className="flex items-start gap-3">
        {onCheckedChange ? (
          <div className="pt-0.5" onClick={(event) => event.stopPropagation()}>
            <Checkbox checked={checked} onCheckedChange={(value) => onCheckedChange(Boolean(value))} aria-label={`Выбрать ${title}`} />
          </div>
        ) : null}
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-slate-950">{title}</div>
              {subtitle ? <div className="mt-1 text-xs text-slate-600">{subtitle}</div> : null}
            </div>
            <LeadStatusBadge label={statusLabel} tone={statusTone} />
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            {location ? <span>{location}</span> : null}
            {channelLabel ? <Badge variant="outline">{channelLabel}</Badge> : null}
            {languageLabel ? <Badge variant="outline">{languageLabel}</Badge> : null}
            {lastActionLabel ? <span>{lastActionLabel}</span> : null}
          </div>
          {contactBadges ? <div className="mt-3">{contactBadges}</div> : null}
          {warning ? (
            <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-2 text-xs text-amber-950">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{warning}</span>
            </div>
          ) : null}
        </div>
        <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-slate-400" />
      </div>
    </button>
  );
}

export function FollowUpEditor({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  hint?: string;
}) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-slate-900">{label}</label>
      <Textarea value={value} onChange={(event) => onChange(event.target.value)} className="min-h-[180px]" />
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function SendReviewPanel({
  title,
  description,
  message,
  children,
}: {
  title: string;
  description: string;
  message: string;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
        <SendHorizontal className="h-4 w-4" />
        {title}
      </div>
      <p className="mt-1 text-sm text-slate-600">{description}</p>
      <div className="mt-3 rounded-lg border bg-white p-3 text-sm whitespace-pre-wrap text-slate-900">
        {message || 'Текст сообщения пока пустой.'}
      </div>
      {children ? <div className="mt-3 flex flex-wrap gap-2">{children}</div> : null}
    </div>
  );
}

export function ReviewChecklist({
  title = 'Проверка перед отправкой',
  items,
}: {
  title?: string;
  items: Array<{ id: string; label: string; checked: boolean; hint?: string }>;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="text-sm font-semibold text-slate-950">{title}</div>
      <div className="mt-3 space-y-3">
        {items.map((item) => (
          <div key={item.id} className="flex items-start gap-3 rounded-lg border border-slate-200 px-3 py-2">
            <div
              aria-hidden="true"
              className={cn(
                'mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold',
                item.checked
                  ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
                  : 'border-amber-300 bg-amber-50 text-amber-700',
              )}
            >
              {item.checked ? '✓' : '!'}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium text-slate-900">{item.label}</div>
              {item.hint ? <div className="mt-1 text-xs text-slate-500">{item.hint}</div> : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function LeadDetailPane({
  title,
  description,
  statusBadge,
  warning,
  errorSummary,
  topMeta,
  channelSection,
  actions,
  editor,
  review,
  history,
  secondary,
  emptyTitle = 'Выберите лид',
  emptyDescription = 'Слева появится список лидов. Выберите одну запись, чтобы увидеть детали и следующее действие.',
}: {
  title?: string;
  description?: string;
  statusBadge?: ReactNode;
  warning?: ReactNode;
  errorSummary?: ReactNode;
  topMeta?: ReactNode;
  channelSection?: ReactNode;
  actions?: ReactNode;
  editor?: ReactNode;
  review?: ReactNode;
  history?: ReactNode;
  secondary?: ReactNode;
  emptyTitle?: string;
  emptyDescription?: string;
}) {
  if (!title) {
    return (
      <Card className="min-h-[620px] border-dashed">
        <CardContent className="flex h-full min-h-[620px] items-center justify-center px-8 py-12 text-center">
          <div>
            <div className="text-base font-semibold text-slate-900">{emptyTitle}</div>
            <p className="mt-2 max-w-md text-sm text-slate-500">{emptyDescription}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="min-h-[620px]">
      <CardHeader className="pb-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <CardTitle className="text-lg">{title}</CardTitle>
            {description ? <CardDescription className="mt-1 text-sm">{description}</CardDescription> : null}
          </div>
          {statusBadge}
        </div>
        {warning ? <div className="pt-2">{warning}</div> : null}
        {errorSummary ? <div className="pt-2">{errorSummary}</div> : null}
      </CardHeader>
      <CardContent className="space-y-5">
        {topMeta ? <div className="space-y-3">{topMeta}</div> : null}
        {channelSection ? <div className="space-y-3">{channelSection}</div> : null}
        {actions ? <div className="space-y-3">{actions}</div> : null}
        {editor ? <div className="space-y-3">{editor}</div> : null}
        {review ? <div className="space-y-3">{review}</div> : null}
        {history ? <div className="space-y-3">{history}</div> : null}
        {secondary ? <div className="space-y-3">{secondary}</div> : null}
      </CardContent>
    </Card>
  );
}
