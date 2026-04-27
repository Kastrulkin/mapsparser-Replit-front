import { ReactNode } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const toneClassMap: Record<string, string> = {
  default: 'border-border/70 bg-muted/20',
  success: 'border-emerald-200 bg-emerald-50',
  warning: 'border-amber-200 bg-amber-50',
  info: 'border-sky-200 bg-sky-50',
  danger: 'border-rose-200 bg-rose-50',
};

type ContactPresenceBadgesProps = {
  title?: string;
  website?: string | null;
  phone?: string | null;
  email?: string | null;
  telegramUrl?: string | null;
  whatsappUrl?: string | null;
  hasMessenger?: boolean;
  showMissing?: boolean;
  className?: string;
};

export function ContactPresenceBadges({
  title,
  website,
  phone,
  email,
  telegramUrl,
  whatsappUrl,
  hasMessenger,
  showMissing = true,
  className,
}: ContactPresenceBadgesProps) {
  const messengerVisible = Boolean(hasMessenger || telegramUrl || whatsappUrl);
  const channels = [
    {
      key: 'phone',
      label: 'Телефон',
      present: Boolean(phone),
    },
    {
      key: 'telegram',
      label: 'Telegram',
      present: Boolean(telegramUrl),
    },
    {
      key: 'whatsapp',
      label: 'WhatsApp',
      present: Boolean(whatsappUrl),
    },
    {
      key: 'email',
      label: 'Email',
      present: Boolean(email),
    },
  ];

  const visibleChannels = showMissing ? channels : channels.filter((item) => item.present);

  return (
    <div className={cn('space-y-2', className)}>
      {title ? (
        <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {title}
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        {website ? (
          <Badge variant="secondary" className="border-sky-200 bg-sky-50 text-sky-700">
            Сайт
          </Badge>
        ) : showMissing ? (
          <Badge variant="outline" className="border-border/70 text-muted-foreground/70">
            Сайт —
          </Badge>
        ) : null}
        {visibleChannels.map((channel) => (
          <Badge
            key={channel.key}
            variant={channel.present ? 'secondary' : 'outline'}
            className={channel.present ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-border/70 text-muted-foreground/70'}
          >
            {channel.label}
            {channel.present ? ' ✓' : ' —'}
          </Badge>
        ))}
        {!website && !messengerVisible && !phone && !email ? (
          <span className="text-[11px] text-muted-foreground">Каналы связи не найдены</span>
        ) : null}
      </div>
    </div>
  );
}

type StatusSummaryCardProps = {
  title: string;
  statusLabel: string;
  statusVariant?: 'default' | 'secondary' | 'outline' | 'destructive';
  primaryText: string;
  secondaryText?: string;
  tone?: 'default' | 'success' | 'warning' | 'info' | 'danger';
  className?: string;
};

export function StatusSummaryCard({
  title,
  statusLabel,
  statusVariant = 'outline',
  primaryText,
  secondaryText,
  tone = 'default',
  className,
}: StatusSummaryCardProps) {
  return (
    <div className={cn('rounded-lg border p-3', toneClassMap[tone] || toneClassMap.default, className)}>
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</div>
        <Badge variant={statusVariant}>{statusLabel}</Badge>
      </div>
      <div className="mt-2 text-sm font-medium">{primaryText}</div>
      {secondaryText ? <div className="mt-1 text-xs text-muted-foreground">{secondaryText}</div> : null}
    </div>
  );
}

type WorkflowActionItem = {
  label: string;
  onClick?: () => void;
  href?: string;
  variant?: 'default' | 'secondary' | 'outline' | 'ghost' | 'destructive';
  disabled?: boolean;
  icon?: ReactNode;
};

type WorkflowActionRowProps = {
  primary: WorkflowActionItem;
  secondary?: WorkflowActionItem[];
  className?: string;
};

export function WorkflowActionRow({ primary, secondary = [], className }: WorkflowActionRowProps) {
  const renderItem = (item: WorkflowActionItem, key: string, isPrimary = false) => {
    const button = (
      <Button
        key={key}
        size="sm"
        variant={item.variant || (isPrimary ? 'default' : 'outline')}
        onClick={item.href ? undefined : item.onClick}
        disabled={item.disabled}
      >
        {item.icon ? <span className="mr-2 inline-flex items-center">{item.icon}</span> : null}
        {item.label}
      </Button>
    );

    if (item.href) {
      return (
        <a key={key} href={item.href} target="_blank" rel="noreferrer">
          {button}
        </a>
      );
    }

    return button;
  };

  return (
    <div className={cn('flex flex-wrap gap-2', className)}>
      {renderItem(primary, 'primary', true)}
      {secondary.map((item, index) => renderItem(item, `secondary-${index}`))}
    </div>
  );
}
