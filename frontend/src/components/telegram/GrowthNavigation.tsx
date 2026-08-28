import {
  Bot,
  Building2,
  ChevronRight,
  CircleEllipsis,
  CreditCard,
  FileText,
  MapPinned,
  MessageCircle,
  Network,
  Settings,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
} from 'lucide-react';

export type GrowthNavigationEntry = {
  key: string;
  label: string;
  status: 'available' | 'read_only' | 'hidden';
  reason?: string;
};

type GrowthNavigationProps = {
  navigation: GrowthNavigationEntry[];
  onOpen: (key: string) => void;
  onOpenProgress: () => void;
  onLocked: (item: GrowthNavigationEntry) => void;
  onRestartTour: () => void;
};

type Outcome = {
  key: string;
  title: string;
  description: string;
  icon: typeof Sparkles;
  secondaryKey?: string;
  secondaryLabel?: string;
};

const outcomes: Outcome[] = [
  { key: 'cards', title: 'Больше клиентов из карт', description: 'Следить за карточками, рейтингом и отзывами.', icon: MapPinned, secondaryKey: 'reviews', secondaryLabel: 'Ответить на отзывы' },
  { key: 'content', title: 'Контент без рутины', description: 'Работать с планом и готовить публикации.', icon: FileText },
  { key: 'influencers', title: 'Инфлюенсеры рядом', description: 'Получите клиентов от местных авторов через взаимовыгодный обмен.', icon: Sparkles },
  { key: 'partnerships', title: 'Партнёры рядом', description: 'Получите новых клиентов через совместные предложения с бизнесами, у которых похожая аудитория.', icon: Users },
  { key: 'finance', title: 'Больше выручки', description: 'Видеть продажи, загрузку и точки роста.', icon: CreditCard, secondaryKey: 'services', secondaryLabel: 'Улучшить меню услуг' },
  { key: 'agents', title: 'Поручить регулярную работу', description: 'Запускать и проверять работу ИИ-сотрудников.', icon: Bot },
];

const utilityIcons: Record<string, typeof Sparkles> = {
  community_sources: Network,
  company: Building2,
  companies: Building2,
  settings: Settings,
  diagnostics: ShieldCheck,
};

const utilityTitles: Record<string, string> = {
  community_sources: 'О чём говорит рынок',
  company: 'Как выглядит моя компания',
  companies: 'Компании в поле зрения',
  settings: 'Настройки и подключения',
  diagnostics: 'Контроль системы',
};

const isPaymentLocked = (item?: GrowthNavigationEntry) => item?.status === 'read_only' && Boolean(item.reason?.toLowerCase().includes('оплат'));

export default function GrowthNavigation({ navigation, onOpen, onOpenProgress, onLocked, onRestartTour }: GrowthNavigationProps) {
  const visible = new Map(navigation.filter((item) => item.status !== 'hidden').map((item) => [item.key, item]));
  const visibleOutcomes = outcomes.filter((item) => visible.has(item.key) || Boolean(item.secondaryKey && visible.has(item.secondaryKey)));
  const utilities = ['community_sources', 'company', 'companies', 'settings', 'diagnostics']
    .map((key) => visible.get(key))
    .filter((item): item is GrowthNavigationEntry => Boolean(item));

  return (
    <div>
      {visible.has('progress') ? (
        <section className="rounded-[24px] bg-gradient-to-b from-primary/[0.11] to-white/[0.035] p-5 shadow-[0_18px_54px_rgba(0,0,0,0.24),0_0_0_1px_rgba(255,92,51,0.15)]">
          <span className="flex items-center gap-2 text-xs font-semibold text-primary"><TrendingUp className="h-4 w-4" />Не знаете, с чего начать?</span>
          <h2 className="mt-3 text-balance text-xl font-semibold">Начните с главной задачи</h2>
          <p className="mt-2 text-pretty text-xs leading-5 text-zinc-500">Первая задача в плане выбрана по свежести данных, серьёзности проблемы и ожидаемому результату.</p>
          <button type="button" onClick={() => { const item = visible.get('progress'); if (isPaymentLocked(item) && item) onLocked(item); else onOpenProgress(); }} className="mt-4 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-primary pl-4 pr-3.5 text-sm font-semibold text-white shadow-[0_12px_32px_rgba(255,92,51,0.22)] transition-transform duration-150 ease-out active:scale-[0.96]">Открыть план роста<ChevronRight className="h-4 w-4" /></button>
        </section>
      ) : null}

      <section className="mt-7">
        <h2 className="text-balance text-lg font-semibold">Чего хотите добиться?</h2>
        <p className="mt-1 text-pretty text-xs leading-5 text-zinc-600">Выберите цель — откроется нужный раздел и первое действие.</p>
        <div className="mt-3 space-y-2">
          {visibleOutcomes.map((outcome) => {
            const primary = visible.get(outcome.key);
            const secondary = outcome.secondaryKey ? visible.get(outcome.secondaryKey) : undefined;
            const target = primary?.key || secondary?.key;
            const Icon = outcome.icon;
            if (!target) return null;
            return (
              <article key={outcome.key} className="overflow-hidden rounded-[22px] bg-white/[0.038] shadow-[0_0_0_1px_rgba(255,255,255,0.07)]">
                <button type="button" onClick={() => { if (isPaymentLocked(primary) && primary) onLocked(primary); else onOpen(target); }} className="flex min-h-[78px] w-full items-center gap-3 px-4 py-3 text-left transition-[background-color,transform] duration-150 active:scale-[0.96]">
                  <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[15px] bg-primary/[0.12] text-primary"><Icon className="h-5 w-5" /></span>
                  <span className="min-w-0 flex-1"><b className="block text-balance text-sm">{outcome.title}</b><small className="mt-1 block text-pretty leading-4 text-zinc-600">{outcome.description}</small>{primary?.status === 'read_only' && primary.reason ? <small className="mt-1 block text-pretty leading-4 text-amber-300/70">{primary.reason}</small> : null}</span>
                  <ChevronRight className="h-4 w-4 shrink-0 text-zinc-700" />
                </button>
                {secondary ? <button type="button" onClick={() => { if (isPaymentLocked(secondary)) onLocked(secondary); else onOpen(secondary.key); }} className="flex min-h-11 w-full items-center justify-between border-t border-white/[0.055] px-4 text-left text-xs font-semibold text-zinc-400 transition-[background-color,color,transform] duration-150 active:scale-[0.96]"><span className="flex items-center gap-2"><MessageCircle className="h-4 w-4 text-primary" />{outcome.secondaryLabel}</span><ChevronRight className="h-4 w-4 text-zinc-700" /></button> : null}
              </article>
            );
          })}
        </div>
      </section>

      {utilities.length ? (
        <section className="mt-7">
          <h2 className="text-balance text-lg font-semibold">Контроль и настройки</h2>
          <div className="mt-3 divide-y divide-white/[0.055] rounded-[22px] bg-white/[0.03] px-2 shadow-[0_0_0_1px_rgba(255,255,255,0.065)]">
            {utilities.map((item) => { const Icon = utilityIcons[item.key] || CircleEllipsis; return <button type="button" key={item.key} onClick={() => onOpen(item.key)} className="flex min-h-14 w-full items-center gap-3 rounded-[16px] px-2 text-left transition-[background-color,transform] duration-150 active:scale-[0.96]"><span className="grid h-10 w-10 place-items-center rounded-[14px] bg-white/[0.045] text-zinc-400"><Icon className="h-4 w-4" /></span><span className="min-w-0 flex-1"><b className="block text-sm">{utilityTitles[item.key] || item.label}</b>{item.status === 'read_only' && item.reason ? <small className="mt-0.5 block truncate text-amber-300/60">{item.reason}</small> : null}</span><ChevronRight className="h-4 w-4 text-zinc-700" /></button>; })}
          </div>
        </section>
      ) : null}

      <button type="button" onClick={onRestartTour} className="mt-6 flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-white/[0.035] text-xs font-semibold text-zinc-500 shadow-[0_0_0_1px_rgba(255,255,255,0.06)] transition-[color,transform] duration-150 active:scale-[0.96]"><Sparkles className="h-4 w-4" />Как работает ЛокалОС</button>
    </div>
  );
}
