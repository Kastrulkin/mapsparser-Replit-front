import { useCallback, useEffect, useState } from 'react';
import { newAuth } from '@/lib/auth_new';
import { Button } from '@/components/ui/button';

type ProviderBudget = {
  limits: { daily_tokens: number; monthly_tokens: number; daily_calls: number; operation_calls: number };
  used: { daily_tokens: number; monthly_tokens: number; daily_calls: number };
  warning: boolean;
};
type Budget = ProviderBudget & { providers?: Record<string, ProviderBudget> };
const number = (value: number) => new Intl.NumberFormat('ru-RU').format(value);

export const OutreachBudgetStatus = () => {
  const [budget, setBudget] = useState<Budget | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);
  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const value = await newAuth.makeRequest('/admin/prospecting/ai-budget');
      const providers: ProviderBudget[] = Object.values(value?.providers || { gigachat: value });
      if (!value?.success || !providers.length || providers.some(item => !Number.isFinite(item?.limits?.daily_tokens) || !Number.isFinite(item?.used?.daily_tokens))) throw new Error('invalid budget');
      setBudget(value);
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  const providers = budget ? Object.entries(budget.providers || { gigachat: budget }) : [];
  return <section aria-label="Лимиты подготовки обращений" className="m-4 space-y-2 rounded-xl border border-border bg-muted/30 p-4 text-sm sm:mx-6">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="font-medium">Подготовка обращений — только по вашей команде</p>
      <Button size="sm" variant="outline" disabled={loading} onClick={() => void refresh()}>{loading ? 'Обновление…' : 'Обновить расход'}</Button>
    </div>
    {error ? <p role="alert">Бюджет AI недоступен. Новые генерации заблокированы.</p> : budget ? <>
      {providers.map(([provider, value]) => <div key={provider} role="group" aria-label={provider === 'deepseek' ? 'DeepSeek' : 'GigaChat'} className="space-y-1">
        <p className="font-medium">{provider === 'deepseek' ? 'DeepSeek' : 'GigaChat'}</p>
        <p>За сутки: {number(value.used.daily_tokens)} / {number(value.limits.daily_tokens)} токенов; {value.used.daily_calls} / {value.limits.daily_calls} вызовов.</p>
        <p>За месяц: {number(value.used.monthly_tokens)} / {number(value.limits.monthly_tokens)} токенов. На одну команду — до {value.limits.operation_calls} вызовов.</p>
        {value.warning ? <p role="alert" className="font-medium">{provider === 'deepseek' ? 'DeepSeek' : 'GigaChat'}: использовано не менее 80% одного из лимитов. При достижении предела подготовка остановится.</p> : null}
      </div>)}
      <p className="text-xs text-muted-foreground">Общий расход задач LocalOS с момента включения защиты, включая резервы, повторы и теневые вызовы. Лимиты учитываются отдельно от баланса провайдеров. Старые обращения автоматически не обновляются. Embeddings учитываются отдельно и в эти лимиты не входят.</p>
    </> : <p role="status">Проверяем лимиты AI…</p>}
  </section>;
};
