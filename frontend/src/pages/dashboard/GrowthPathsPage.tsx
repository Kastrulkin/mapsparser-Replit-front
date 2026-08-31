import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, Bot, FileText, MapPinned, RefreshCw, Users, WandSparkles } from 'lucide-react';
import { Link, useOutletContext } from 'react-router-dom';
import { AccessPreview, type BlockAccess } from '@/components/access/AccessBoundary';
import { Button } from '@/components/ui/button';
import { newAuth } from '@/lib/auth_new';
import { journeyActionRoute, type JourneyAction } from '@/lib/leadJourney';
import { cn } from '@/lib/utils';

type GrowthFlow = 'maps' | 'content' | 'influencer' | 'partnership' | 'automation';

type GrowthPath = {
  flow_type: GrowthFlow;
  title: string;
  status: string;
  opportunity: string;
  obstacle?: string;
  access: BlockAccess;
  action?: JourneyAction | null;
};

type GrowthPathsResponse = {
  paths?: GrowthPath[];
  focus_action?: JourneyAction | null;
};

const pathMeta = {
  maps: { title: 'Больше клиентов из карт', icon: MapPinned, tone: 'bg-sky-50 text-sky-700 ring-sky-100', route: '/dashboard/card' },
  content: { title: 'Контент без рутины', icon: FileText, tone: 'bg-violet-50 text-violet-700 ring-violet-100', route: '/dashboard/content' },
  influencer: { title: 'Инфлюенсеры рядом', icon: WandSparkles, tone: 'bg-rose-50 text-rose-700 ring-rose-100', route: '/dashboard/influencers' },
  partnership: { title: 'Партнёры рядом', icon: Users, tone: 'bg-emerald-50 text-emerald-700 ring-emerald-100', route: '/dashboard/promotion/partnerships' },
  automation: { title: 'Автоматизировать работу', icon: Bot, tone: 'bg-orange-50 text-orange-700 ring-orange-100', route: '/dashboard/agents' },
};

const statusCopy = (path: GrowthPath) => {
  if (path.access.status === 'payment_required') return 'Откроется после оплаты';
  if (path.status === 'blocked') return 'Нужно внимание';
  if (path.action) return 'Есть следующий шаг';
  return 'Можно начать';
};

export const GrowthPathsPage = () => {
  const { currentBusinessId } = useOutletContext<{ currentBusinessId?: string | null }>();
  const [data, setData] = useState<GrowthPathsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    if (!currentBusinessId) return;
    setLoading(true);
    setError('');
    try {
      const response = await newAuth.makeRequest(`/growth-paths?business_id=${encodeURIComponent(currentBusinessId)}`);
      setData(response);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить пути роста.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [currentBusinessId]);

  const paths = useMemo(() => {
    const items = data?.paths || [];
    const focusFlow = data?.focus_action?.flow_type;
    return [...items].sort((left, right) => Number(right.flow_type === focusFlow) - Number(left.flow_type === focusFlow));
  }, [data]);

  if (!currentBusinessId) return <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">Выберите бизнес, чтобы увидеть пути роста.</div>;

  return (
    <div className="space-y-6 pb-10">
      <header className="rounded-[28px] border border-slate-200/80 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-orange-700">Пути роста</p>
        <h1 className="mt-2 max-w-3xl text-balance text-3xl font-semibold tracking-tight text-slate-950">Выберите направление</h1>
        <p className="mt-3 max-w-2xl text-pretty text-sm leading-6 text-slate-600">В каждом направлении LocalOS покажет, с чего начать, и проведёт по следующим шагам. Ваш текущий маршрут всегда идёт первым.</p>
      </header>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2" aria-label="Загрузка путей роста">
          {[0, 1, 2, 3].map((item) => <div key={item} className="h-64 animate-pulse rounded-[24px] bg-slate-200/70" />)}
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-900">
          <p>{error}</p>
          <Button type="button" variant="outline" className="mt-3 min-h-10" onClick={() => void load()}><RefreshCw className="mr-2 h-4 w-4" />Повторить</Button>
        </div>
      ) : paths.length ? (
        <div className="grid gap-4 md:grid-cols-2">
          {paths.map((path, index) => {
            const meta = pathMeta[path.flow_type];
            const Icon = meta.icon;
            const actionRoute = path.action ? journeyActionRoute(path.action) : meta.route;
            const locked = path.access.status !== 'available';
            const centeredLastCard = paths.length % 2 === 1 && index === paths.length - 1;
            return (
              <article key={path.flow_type} className={cn('rounded-[24px] border bg-white p-5 shadow-sm', centeredLastCard && 'md:col-span-2 md:w-[calc(50%-0.5rem)] md:justify-self-center', index === 0 && path.action ? 'border-orange-300 ring-2 ring-orange-100' : 'border-slate-200')}>
                <div className="flex items-start justify-between gap-4">
                  <span className={cn('grid h-12 w-12 shrink-0 place-items-center rounded-2xl ring-1', meta.tone)}><Icon className="h-5 w-5" aria-hidden="true" /></span>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">{statusCopy(path)}</span>
                </div>
                <h2 className="mt-5 text-balance text-xl font-semibold text-slate-950">{meta.title}</h2>
                <p className="mt-2 min-h-12 text-pretty text-sm leading-6 text-slate-600">{path.opportunity}</p>
                {path.obstacle ? <p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">Препятствие: {path.obstacle}</p> : null}
                {locked ? <AccessPreview access={path.access} className="mt-4" /> : (
                  <Link to={actionRoute} className="mt-5 inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-slate-950 px-4 text-sm font-semibold text-white transition-[background-color,transform] duration-150 hover:bg-slate-800 active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-950 focus-visible:ring-offset-2">
                    {path.action?.cta_label || path.access.cta_label}<ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                )}
              </article>
            );
          })}
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-slate-950">Пути пока не загрузились</h2>
          <p className="mt-2 text-sm text-slate-600">Проверьте, что journey-функция включена для тестовой группы.</p>
        </div>
      )}
    </div>
  );
};
