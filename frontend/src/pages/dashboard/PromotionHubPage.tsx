import { ArrowRight, Handshake, Megaphone, Sparkles } from 'lucide-react';
import { Link, useOutletContext } from 'react-router-dom';

import { DashboardPageHeader } from '@/components/dashboard/DashboardPrimitives';

type DashboardContext = {
  currentBusinessId?: string | null;
  currentBusiness?: { creator_promotion_available?: boolean } | null;
};

const PromotionChoice = ({
  title,
  description,
  bullets,
  href,
  icon: Icon,
  accent,
  available = true,
}: {
  title: string;
  description: string;
  bullets: string[];
  href: string;
  icon: typeof Handshake;
  accent: string;
  available?: boolean;
}) => {
  const content = (
    <div className={`rounded-2xl p-5 sm:p-7 ${accent}`}>
      <div className="flex items-start justify-between gap-4">
        <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-white/90 text-slate-950 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_2px_6px_rgba(15,23,42,0.08)]">
          <Icon className="h-6 w-6" />
        </span>
        {available ? <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-white/70 text-slate-700 transition-[background-color,transform] group-hover:translate-x-0.5 group-hover:bg-white"><ArrowRight className="h-5 w-5" /></span> : <span className="rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-slate-600">Подключаем поэтапно</span>}
      </div>
      <h2 className="mt-7 text-balance text-2xl font-semibold tracking-tight text-slate-950">{title}</h2>
      <p className="mt-3 max-w-xl text-pretty text-sm leading-6 text-slate-650">{description}</p>
      <ul className="mt-6 space-y-2 text-sm text-slate-700">
        {bullets.map((bullet) => (
          <li key={bullet} className="flex gap-2 text-pretty">
            <Sparkles className="mt-0.5 h-4 w-4 shrink-0 opacity-60" />
            <span>{bullet}</span>
          </li>
        ))}
      </ul>
    </div>
  );
  if (!available) {
    return <div aria-disabled="true" className="rounded-[28px] bg-white p-3 opacity-75 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_2px_4px_-2px_rgba(15,23,42,0.08)]">{content}</div>;
  }
  return <Link to={href} className="group rounded-[28px] bg-white p-3 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_2px_4px_-2px_rgba(15,23,42,0.08),0_16px_40px_-24px_rgba(15,23,42,0.22)] transition-[box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:shadow-[0_0_0_1px_rgba(15,23,42,0.09),0_4px_10px_-4px_rgba(15,23,42,0.12),0_24px_52px_-24px_rgba(15,23,42,0.28)] active:scale-[0.96]">{content}</Link>;
};

export const PromotionHubPage = () => {
  const { currentBusinessId, currentBusiness } = useOutletContext<DashboardContext>();

  if (!currentBusinessId) {
    return <div className="py-16 text-center text-sm text-slate-500">Выберите бизнес, который хотите продвигать.</div>;
  }
  return (
    <div className="space-y-8 pb-12 antialiased">
      <DashboardPageHeader
        eyebrow="Новые клиенты"
        title="Продвижение"
        description="Выберите способ выйти к новой аудитории. LocalOS найдёт подходящих кандидатов, подготовит следующий шаг и оставит внешние сообщения под вашим подтверждением."
        icon={Megaphone}
      />

      <section aria-labelledby="promotion-choice-title">
        <h2 id="promotion-choice-title" className="sr-only">Способ продвижения</h2>
        <div className="grid gap-5 lg:grid-cols-2">
          <PromotionChoice
            title="Партнёрские акции"
            description="Найдите соседние бизнесы с похожими клиентами и предложите совместную акцию или взаимное продвижение."
            bullets={['Совместимость аудиторий и услуг', 'Предложение и контролируемая коммуникация', 'История контактов и результат']}
            href="/dashboard/promotion/partnerships"
            icon={Handshake}
            accent="bg-gradient-to-br from-emerald-50 to-teal-100/70"
          />
          <PromotionChoice
            title="Локальные авторы"
            description="Найдите авторов, районные сообщества и локальные медиа, которые уже влияют на выбор вашей аудитории."
            bullets={['Поиск по географии и темам', 'Объяснимый shortlist вместо каталога подписчиков', 'Коллаборации, материалы и подтверждённые метрики']}
            href="/dashboard/influencers"
            icon={Megaphone}
            accent="bg-gradient-to-br from-amber-50 to-orange-100/80"
            available={currentBusiness?.creator_promotion_available === true}
          />
        </div>
      </section>

      <p className="max-w-3xl text-pretty text-sm leading-6 text-slate-500">
        Партнёрства и работа с авторами используют общую безопасную основу, но остаются разными рабочими сценариями. Подключение источника или подготовка сообщения сами по себе ничего не отправляют.
      </p>
    </div>
  );
};
