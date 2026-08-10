import { useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ArrowLeft,
  Bot,
  Building2,
  Check,
  ChevronRight,
  MapPinned,
  MessageCircle,
  Network,
  Sparkles,
  TrendingUp,
} from 'lucide-react';

type MobileOnboardingProps = {
  hasSwitcher: boolean;
  networkMode: boolean;
  onFinish: () => void;
};

type OnboardingStep = {
  key: string;
  eyebrow: string;
  title: string;
  description: string;
  icon: typeof Sparkles;
  points?: string[];
};

const spring = { type: 'spring', duration: 0.3, bounce: 0 };

export default function MobileOnboarding({ hasSwitcher, networkMode, onFinish }: MobileOnboardingProps) {
  const steps = useMemo<OnboardingStep[]>(() => {
    const result: OnboardingStep[] = [
      {
        key: 'welcome',
        eyebrow: 'ЛокалОС для вашего бизнеса',
        title: 'Получайте больше клиентов из карт, отзывов и соцсетей — без ручной рутины',
        description: 'ЛокалОС собирает данные из Яндекс Карт и 2ГИС, показывает отзывы и ошибки, помогает готовить контент и следить за важными изменениями.',
        icon: Sparkles,
        points: [
          'Показывает, что мешает карточкам приводить клиентов',
          'Готовит черновики ответов и публикаций',
          'Собирает публичные данные о конкурентах и партнёрах',
          'Открывает нужный раздел по поручению обычными словами',
        ],
      },
      {
        key: 'operator',
        eyebrow: 'Шаг 1',
        title: 'Поручайте работу обычными словами',
        description: 'Напишите задачу обычными словами. ЛокалОС откроет нужный раздел или подготовит черновик. Публикации, отправки и другие внешние действия потребуют вашего подтверждения.',
        icon: Bot,
      },
      {
        key: 'focus',
        eyebrow: 'Шаг 2',
        title: 'Сразу видно, что важно сейчас',
        description: 'ЛокалОС собирает рейтинг, отзывы, состояние карточек и текущие задачи. На экране «Сегодня» показывается одна самая срочная задача и причина её выбора.',
        icon: MessageCircle,
      },
    ];
    if (hasSwitcher) {
      result.push({
        key: 'scope',
        eyebrow: 'Шаг 3',
        title: networkMode ? 'Сеть целиком или одна точка' : 'Быстро переключайтесь между бизнесами',
        description: networkMode
          ? 'Откройте сводку сети или выберите конкретную точку. Все данные, рекомендации и действия будут относиться к выбранному уровню.'
          : 'После выбора бизнеса все данные, рекомендации и действия относятся только к нему. Выбор сохранится при следующем открытии.',
        icon: networkMode ? Network : Building2,
      });
    }
    result.push({
      key: 'progress',
      eyebrow: hasSwitcher ? 'Шаг 4' : 'Шаг 3',
      title: 'Один план вместо десятков задач',
      description: 'Карты и репутация, контент, партнёрства, автоматизация и допродажи собраны в одном месте. Для каждого направления видны выполненные шаги, проблемы и следующее действие.',
      icon: TrendingUp,
    });
    return result;
  }, [hasSwitcher, networkMode]);
  const [index, setIndex] = useState(0);
  const step = steps[index];
  const Icon = step.icon;
  const first = index === 0;
  const last = index === steps.length - 1;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-zinc-950/[0.72] px-4 py-[calc(18px+env(safe-area-inset-top))] backdrop-blur-xl">
      <AnimatePresence initial={false} mode="wait">
        <motion.section
          key={step.key}
          role="dialog"
          aria-modal="true"
          aria-labelledby="localos-onboarding-title"
          initial={{ opacity: 0, y: 12, filter: 'blur(4px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          exit={{ opacity: 0, y: -8, filter: 'blur(4px)' }}
          transition={spring}
          className="my-auto flex max-h-[calc(100dvh-36px-env(safe-area-inset-top)-env(safe-area-inset-bottom))] w-full max-w-md flex-col overflow-hidden rounded-[30px] bg-zinc-900 p-5 text-zinc-100 shadow-[0_28px_90px_rgba(0,0,0,0.58),0_0_0_1px_rgba(255,255,255,0.09)]"
        >
          <div className="min-h-0 overflow-y-auto overscroll-contain pr-1">
          <div className="flex items-center justify-between gap-3">
            <span className="grid h-12 w-12 place-items-center rounded-[17px] bg-primary/[0.14] text-primary shadow-[0_0_0_1px_rgba(255,92,51,0.18)]"><Icon className="h-6 w-6" /></span>
            <span className="text-xs tabular-nums text-zinc-600">{index + 1} / {steps.length}</span>
          </div>

          <small className="mt-6 block font-semibold uppercase tracking-[0.14em] text-primary">{step.eyebrow}</small>
          <h1 id="localos-onboarding-title" className="mt-2 text-balance text-[28px] font-semibold leading-[1.08] tracking-[-0.045em]">{step.title}</h1>
          <p className="mt-4 text-pretty text-sm leading-6 text-zinc-400">{step.description}</p>

          {step.points?.length ? (
            <div className="mt-5 divide-y divide-white/[0.06] rounded-[20px] bg-black/[0.18] px-4 shadow-[0_0_0_1px_rgba(255,255,255,0.055)]">
              {step.points.map((point) => <div key={point} className="flex min-h-12 items-center gap-3 py-2.5 text-sm text-zinc-300"><Check className="h-4 w-4 shrink-0 text-emerald-300" /><span className="text-pretty">{point}</span></div>)}
            </div>
          ) : (
            <div className="mt-6 overflow-hidden rounded-[22px] bg-black/20 p-4 shadow-[0_0_0_1px_rgba(255,255,255,0.06)]">
              <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-[14px] bg-primary/[0.12] text-primary"><Icon className="h-5 w-5" /></span><div className="min-w-0 flex-1"><span className="block h-2.5 w-3/4 rounded-full bg-white/[0.12]" /><span className="mt-2 block h-2 w-1/2 rounded-full bg-white/[0.055]" /></div></div>
              <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/[0.055]"><motion.div initial={false} animate={{ width: `${Math.round((index + 1) / steps.length * 100)}%` }} transition={spring} className="h-full rounded-full bg-primary" /></div>
            </div>
          )}
          </div>

          <div className="mt-4 flex shrink-0 gap-2 border-t border-white/[0.055] pt-4">
            {!first ? <button type="button" aria-label="Назад" onClick={() => setIndex((value) => Math.max(0, value - 1))} className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-white/[0.055] text-zinc-300 shadow-[0_0_0_1px_rgba(255,255,255,0.07)] transition-transform duration-150 ease-out active:scale-[0.96]"><ArrowLeft className="h-4 w-4" /></button> : null}
            <button type="button" onClick={() => { if (last) onFinish(); else setIndex((value) => value + 1); }} className="flex min-h-12 flex-1 items-center justify-center gap-2 rounded-2xl bg-primary pl-4 pr-3.5 text-sm font-semibold text-white shadow-[0_14px_38px_rgba(255,92,51,0.26)] transition-transform duration-150 ease-out active:scale-[0.96]">{first ? 'Проверить мой бизнес' : last ? 'Открыть Сегодня' : 'Дальше'}<ChevronRight className="h-4 w-4" /></button>
          </div>
          {first ? <button type="button" onClick={onFinish} className="mt-2 min-h-11 w-full text-xs font-medium text-zinc-600 transition-[color,transform] duration-150 active:scale-[0.96]">Пропустить знакомство</button> : null}
        </motion.section>
      </AnimatePresence>
      <MapPinned className="pointer-events-none fixed -bottom-12 -right-12 h-52 w-52 text-primary/[0.035]" />
    </div>
  );
}
