import { ReactNode } from 'react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

type AnalyticsSectionProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
};

export function AnalyticsSection({
  title,
  description,
  actions,
  children,
}: AnalyticsSectionProps) {
  return (
    <div className="rounded-xl border bg-white p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">{title}</h2>
          {description ? <div className="text-xs text-muted-foreground mt-1">{description}</div> : null}
        </div>
        {actions ? <div className="flex gap-2">{actions}</div> : null}
      </div>
      {children}
    </div>
  );
}

type AnalyticsSummaryItem = {
  key: string;
  label: string;
  value: string | number;
  helper: string;
  tone?: string;
};

export function AnalyticsSummaryGrid({
  items,
  columnsClassName = 'md:grid-cols-4 xl:grid-cols-6',
}: {
  items: AnalyticsSummaryItem[];
  columnsClassName?: string;
}) {
  return (
    <div className={`grid gap-3 ${columnsClassName}`}>
      {items.map((item) => (
        <Card key={item.key} className="border-border/70 shadow-none">
          <CardContent className="p-4">
            <div className={`text-xs uppercase ${item.tone || 'text-muted-foreground'}`}>{item.label}</div>
            <div className="mt-2 text-2xl font-semibold">{item.value}</div>
            <div className="mt-1 text-xs text-muted-foreground">{item.helper}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

type AnalyticsMetricItem = {
  key: string;
  label: string;
  hint: string;
  count: string | number;
  conversion: string;
  dropOff: string;
};

export function AnalyticsMetricGrid({
  items,
  columnsClassName = 'md:grid-cols-2 xl:grid-cols-3',
}: {
  items: AnalyticsMetricItem[];
  columnsClassName?: string;
}) {
  return (
    <div className={`grid gap-3 ${columnsClassName}`}>
      {items.map((item) => (
        <div key={item.key} className="rounded-xl border border-border/70 bg-background p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold">{item.label}</div>
              <div className="mt-1 text-xs text-muted-foreground">{item.hint}</div>
            </div>
            <Badge variant="outline">{item.count}</Badge>
          </div>
          <div className="mt-4 flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Конверсия</span>
            <span className="font-medium">{item.conversion}</span>
          </div>
          <div className="mt-2 flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Потеря / сбой</span>
            <span className="font-medium">{item.dropOff}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

type AnalyticsWindowStat = {
  key: string;
  label: string;
  value: string | number;
  helper: string;
};

type AnalyticsWindowItem = {
  key: string;
  label: string;
  badgeLabel: string;
  badgeValue: string | number;
  stats: AnalyticsWindowStat[];
};

export function AnalyticsWindowGrid({
  title,
  description,
  items,
}: {
  title: string;
  description?: string;
  items: AnalyticsWindowItem[];
}) {
  return (
    <div className="rounded-xl border border-border/70 bg-background p-4">
      <div className="mb-4">
        <div className="text-sm font-semibold">{title}</div>
        {description ? <div className="text-xs text-muted-foreground">{description}</div> : null}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {items.map((item) => (
          <div key={item.key} className="rounded-lg border border-border/70 p-4">
            <div className="flex items-center justify-between">
              <div className="font-medium">{item.label}</div>
              <Badge variant="outline">{item.badgeLabel}: {item.badgeValue}</Badge>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
              {item.stats.map((stat) => (
                <div key={stat.key} className="rounded-md bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">{stat.label}</div>
                  <div className="mt-1 font-semibold">{stat.value}</div>
                  <div className="text-xs text-muted-foreground">{stat.helper}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
