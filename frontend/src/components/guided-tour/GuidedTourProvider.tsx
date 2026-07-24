import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ArrowLeft, ArrowRight, ExternalLink, Pause, Play, RotateCcw, Sparkles, X } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';

import logo from '@/assets/images/logo.png';
import { Button } from '@/components/ui/button';
import { newAuth, type User } from '@/lib/auth_new';
import { cn } from '@/lib/utils';
import {
  GUIDED_TOUR_KEY,
  GUIDED_TOUR_STEPS,
  GUIDED_TOUR_VERSION,
  type GuidedTourStep,
} from './tourConfig';


type TourStatus = 'not_started' | 'active' | 'paused' | 'skipped' | 'completed';

type TourProgress = {
  status: TourStatus;
  chapter_key?: string | null;
  step_key?: string | null;
  completed_steps?: string[];
};

type TargetRect = {
  top: number;
  left: number;
  width: number;
  height: number;
};

type GuidedTourProviderProps = {
  user: User;
  children: ReactNode;
};

const progressForStep = (status: TourStatus, step: GuidedTourStep, completedSteps: string[]) => ({
  tour_version: GUIDED_TOUR_VERSION,
  status,
  chapter_key: step.chapter,
  step_key: step.key,
  completed_steps: completedSteps,
});

const routePathname = (route: string) => route.split('?', 1)[0];

export function GuidedTourProvider({ user, children }: GuidedTourProviderProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [loaded, setLoaded] = useState(false);
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<TourStatus>('not_started');
  const [currentIndex, setCurrentIndex] = useState(0);
  const [completedSteps, setCompletedSteps] = useState<string[]>([]);
  const [targetRect, setTargetRect] = useState<TargetRect | null>(null);
  const [targetMissing, setTargetMissing] = useState(false);
  const [progressError, setProgressError] = useState<string | null>(null);
  const missingEventStepRef = useRef<string | null>(null);
  const initialRouteSyncedRef = useRef(false);
  const panelRef = useRef<HTMLElement | null>(null);
  const launcherRef = useRef<HTMLButtonElement | null>(null);
  const currentStep = GUIDED_TOUR_STEPS[currentIndex] || GUIDED_TOUR_STEPS[0];
  const isDemo = Boolean(user.demo_mode);
  const isWelcome = currentStep.key === 'welcome';
  const robotState = status === 'not_started'
    ? 'waiting'
    : currentStep.final || status === 'completed'
      ? 'success'
      : 'explaining';

  const completedPercent = useMemo(
    () => Math.round((completedSteps.length / GUIDED_TOUR_STEPS.length) * 100),
    [completedSteps.length],
  );

  const recordEvent = useCallback(async (eventType: string, step: GuidedTourStep, metadata: Record<string, unknown> = {}) => {
    try {
      await newAuth.makeRequest(`/guided-tours/${GUIDED_TOUR_KEY}/events`, {
        method: 'POST',
        body: JSON.stringify({
          event_type: eventType,
          chapter_key: step.chapter,
          step_key: step.key,
          route: window.location.pathname,
          metadata,
        }),
      });
    } catch (eventError) {
      console.warn('Guided tour event was not recorded:', eventError);
    }
  }, []);

  const persistProgress = useCallback(async (
    nextStatus: TourStatus,
    step: GuidedTourStep,
    nextCompletedSteps: string[],
  ) => {
    await newAuth.makeRequest(`/guided-tours/${GUIDED_TOUR_KEY}/progress`, {
      method: 'PUT',
      body: JSON.stringify(progressForStep(nextStatus, step, nextCompletedSteps)),
    });
  }, []);

  const persistProgressSafely = useCallback(async (
    nextStatus: TourStatus,
    step: GuidedTourStep,
    nextCompletedSteps: string[],
  ) => {
    setProgressError(null);
    try {
      await persistProgress(nextStatus, step, nextCompletedSteps);
      return true;
    } catch (progressSaveError) {
      console.warn('Guided tour progress was not saved:', progressSaveError);
      setProgressError('Не удалось сохранить прогресс. Попробуйте ещё раз.');
      return false;
    }
  }, [persistProgress]);

  useEffect(() => {
    if (!isDemo) return;
    let cancelled = false;
    newAuth.makeRequest(`/guided-tours/${GUIDED_TOUR_KEY}/progress`, { method: 'GET' })
      .then((response) => {
        if (cancelled) return;
        const progress: TourProgress = response.progress || {};
        const nextStatus = progress.status || 'not_started';
        const nextIndex = Math.max(0, GUIDED_TOUR_STEPS.findIndex((step) => step.key === progress.step_key));
        setStatus(nextStatus);
        setCurrentIndex(nextIndex);
        setCompletedSteps(Array.isArray(progress.completed_steps) ? progress.completed_steps : []);
        setOpen(nextStatus === 'not_started' || nextStatus === 'active');
        setLoaded(true);
      })
      .catch((progressError) => {
        if (cancelled) return;
        console.warn('Guided tour progress was not loaded:', progressError);
        setLoaded(true);
        setOpen(true);
      });
    return () => {
      cancelled = true;
    };
  }, [isDemo]);

  const locateTarget = useCallback((step: GuidedTourStep, scrollIntoView: boolean) => {
    if (!step.target) {
      setTargetRect(null);
      setTargetMissing(false);
      return true;
    }
    const element = document.querySelector<HTMLElement>(`[data-tour-target="${step.target}"]`);
    if (!element) {
      setTargetRect(null);
      setTargetMissing(true);
      return false;
    }
    const rect = element.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
      setTargetRect(null);
      setTargetMissing(true);
      return false;
    }
    if (scrollIntoView) {
      const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      element.scrollIntoView({
        behavior: prefersReducedMotion ? 'auto' : 'smooth',
        block: 'center',
        inline: 'nearest',
      });
    }
    setTargetRect({ top: rect.top, left: rect.left, width: rect.width, height: rect.height });
    setTargetMissing(false);
    return true;
  }, []);

  const showStep = useCallback((step: GuidedTourStep, scrollIntoView = true) => {
    if (`${location.pathname}${location.search}` !== step.route) {
      navigate(step.route);
      window.setTimeout(() => locateTarget(step, scrollIntoView), 500);
      return;
    }
    window.setTimeout(() => locateTarget(step, scrollIntoView), 80);
  }, [locateTarget, location.pathname, location.search, navigate]);

  useEffect(() => {
    if (!isDemo || !loaded || !open) {
      setTargetRect(null);
      return;
    }
    if (!initialRouteSyncedRef.current) {
      initialRouteSyncedRef.current = true;
      showStep(currentStep, false);
      return;
    }
    if (location.pathname === routePathname(currentStep.route)) {
      window.setTimeout(() => locateTarget(currentStep, false), 80);
      return;
    }
    setTargetRect(null);
    setTargetMissing(false);
  }, [currentStep, isDemo, loaded, locateTarget, location.pathname, open, showStep]);

  useEffect(() => {
    if (!open || !currentStep.target) return;
    const update = () => locateTarget(currentStep, false);
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  }, [currentStep, locateTarget, open]);

  useEffect(() => {
    if (!loaded) return;
    const focusTarget = open ? panelRef.current : launcherRef.current;
    window.setTimeout(() => focusTarget?.focus(), 0);
  }, [loaded, open]);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      panelRef.current?.querySelector<HTMLButtonElement>('[data-tour-pause="true"]')?.click();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open]);

  useEffect(() => {
    if (!targetMissing || missingEventStepRef.current === currentStep.key) return;
    missingEventStepRef.current = currentStep.key;
    void recordEvent('target_missing', currentStep);
  }, [currentStep, recordEvent, targetMissing]);

  const start = async () => {
    const saved = await persistProgressSafely('active', currentStep, completedSteps);
    if (!saved) return;
    setStatus('active');
    setOpen(true);
    await recordEvent(status === 'paused' ? 'resumed' : 'started', currentStep);
    showStep(currentStep);
  };

  const startFromWelcome = async () => {
    const nextIndex = Math.min(1, GUIDED_TOUR_STEPS.length - 1);
    const nextStep = GUIDED_TOUR_STEPS[nextIndex];
    const nextCompletedSteps = [currentStep.key];
    const saved = await persistProgressSafely('active', nextStep, nextCompletedSteps);
    if (!saved) return;
    setStatus('active');
    setCurrentIndex(nextIndex);
    setCompletedSteps(nextCompletedSteps);
    await recordEvent('started', currentStep);
    await recordEvent('step_viewed', nextStep);
    showStep(nextStep);
  };

  const moveTo = async (nextIndex: number, nextCompletedSteps: string[], nextStatus: TourStatus = 'active') => {
    const boundedIndex = Math.max(0, Math.min(nextIndex, GUIDED_TOUR_STEPS.length - 1));
    const nextStep = GUIDED_TOUR_STEPS[boundedIndex];
    const saved = await persistProgressSafely(nextStatus, nextStep, nextCompletedSteps);
    if (!saved) return;
    setCurrentIndex(boundedIndex);
    setCompletedSteps(nextCompletedSteps);
    setStatus(nextStatus);
    if (nextStatus === 'active') {
      await recordEvent('step_viewed', nextStep);
      showStep(nextStep);
    }
  };

  const next = async () => {
    const nextCompleted = completedSteps.includes(currentStep.key)
      ? completedSteps
      : [...completedSteps, currentStep.key];
    if (currentStep.final || currentIndex === GUIDED_TOUR_STEPS.length - 1) {
      const saved = await persistProgressSafely('completed', currentStep, nextCompleted);
      if (!saved) return;
      setCompletedSteps(nextCompleted);
      setStatus('completed');
      setTargetRect(null);
      await recordEvent('completed', currentStep);
      return;
    }
    const nextStep = GUIDED_TOUR_STEPS[currentIndex + 1];
    if (nextStep.chapter !== currentStep.chapter) {
      await recordEvent('chapter_completed', currentStep);
    }
    await moveTo(currentIndex + 1, nextCompleted);
  };

  const previous = async () => {
    if (currentIndex <= 0) return;
    await moveTo(currentIndex - 1, completedSteps);
  };

  const pause = async () => {
    const saved = await persistProgressSafely('paused', currentStep, completedSteps);
    if (!saved) return;
    setStatus('paused');
    setOpen(false);
    setTargetRect(null);
    await recordEvent('paused', currentStep);
  };

  const skip = async () => {
    const saved = await persistProgressSafely('skipped', currentStep, completedSteps);
    if (!saved) return;
    setStatus('skipped');
    setOpen(false);
    setTargetRect(null);
    await recordEvent('skipped', currentStep);
  };

  const restart = async () => {
    const firstStep = GUIDED_TOUR_STEPS[0];
    const saved = await persistProgressSafely('active', firstStep, []);
    if (!saved) return;
    setCurrentIndex(0);
    setCompletedSteps([]);
    setStatus('active');
    setOpen(true);
    await recordEvent('restarted', firstStep);
    showStep(firstStep);
  };

  const openRoom = async () => {
    await recordEvent('room_opened', currentStep);
    if (user.demo_room_slug) {
      window.open(`/room/${encodeURIComponent(user.demo_room_slug)}`, '_blank', 'noopener,noreferrer');
    }
  };

  const register = async () => {
    await recordEvent('registration_clicked', currentStep);
    newAuth.deactivateDemoSession();
    window.location.href = '/login?tab=register&source=interactive_demo';
  };

  if (!isDemo) return <>{children}</>;

  return (
    <>
      {children}
      {targetRect && open ? (
        <div
          className="pointer-events-none fixed z-[65] rounded-lg border-2 border-orange-500 shadow-[0_0_0_5px_rgba(249,115,22,0.16)] transition-[top,left,width,height] duration-200 motion-reduce:transition-none"
          style={{
            top: Math.max(4, targetRect.top - 5),
            left: Math.max(4, targetRect.left - 5),
            width: targetRect.width + 10,
            height: targetRect.height + 10,
          }}
          aria-hidden="true"
        />
      ) : null}

      {!open && loaded ? (
        <button
          ref={launcherRef}
          type="button"
          onClick={() => {
            setOpen(true);
            if (status === 'paused' || status === 'skipped') void start();
          }}
          className="fixed bottom-[max(1rem,env(safe-area-inset-bottom))] right-4 z-[70] flex h-16 w-16 items-center justify-center overflow-hidden rounded-full border border-slate-200 bg-white shadow-lg transition-[transform,box-shadow] duration-150 hover:scale-105 hover:shadow-xl active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 focus-visible:ring-offset-2 motion-reduce:transition-none motion-reduce:hover:scale-100"
          aria-label={status === 'completed' ? 'Открыть обучение снова' : 'Продолжить обучение'}
        >
          <img src={logo} alt="" className="h-24 w-24 -translate-y-1 scale-150 object-cover object-top" aria-hidden="true" />
        </button>
      ) : null}

      {open && isWelcome ? (
        <div className="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto bg-slate-950/45 px-4 py-6 backdrop-blur-sm">
          <section
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="demo-welcome-title"
            className="my-auto w-full max-w-3xl overflow-hidden rounded-lg bg-white shadow-[0_24px_80px_rgba(15,23,42,0.28),0_3px_14px_rgba(15,23,42,0.12)]"
            tabIndex={-1}
          >
            <div className="grid gap-6 p-6 sm:p-8 lg:grid-cols-[minmax(0,1fr)_160px] lg:gap-10 lg:p-10">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-orange-700">Интерактивное демо LocalOS</p>
                <h1 id="demo-welcome-title" className="mt-3 text-balance text-2xl font-semibold leading-tight text-slate-950 sm:text-3xl">
                  Получайте больше клиентов из карт, отзывов и соцсетей — без ручной рутины
                </h1>
                <p className="mt-4 text-pretty text-sm leading-6 text-slate-600 sm:text-base sm:leading-7">
                  LocalOS помогает владельцу малого бизнеса вести Яндекс Карты, 2ГИС и Google, отвечать на отзывы, готовить посты и новости, смотреть конкурентов рядом и понимать, что влияет на заявки, выручку и средний чек.
                </p>

                <div className="mt-6">
                  <h2 className="text-base font-semibold text-slate-950">Что можно сделать в LocalOS</h2>
                  <ul className="mt-3 grid gap-x-6 gap-y-2 text-sm leading-6 text-slate-700 sm:grid-cols-2">
                    {[
                      'Понять, что исправить в карточке бизнеса',
                      'Улучшить услуги, описания, фото и новости для карт',
                      'Отвечать на отзывы и повышать рейтинг',
                      'Готовить посты для соцсетей без вопроса «что выкладывать?»',
                      'Смотреть, что делают конкуренты рядом',
                      'Находить партнёров со схожей аудиторией',
                      'Поручать повторяющиеся задачи обычным языком',
                    ].map((item) => (
                      <li key={item} className="grid grid-cols-[20px_minmax(0,1fr)] gap-2">
                        <span className="mt-2 h-1.5 w-1.5 rounded-full bg-orange-500" aria-hidden="true" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="mt-6 border-l-2 border-orange-400 pl-4">
                  <h2 className="font-semibold text-slate-950">Я помогу освоиться</h2>
                  <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">
                    За 8–10 минут мы посмотрим состояние сети, карточку на картах, контент и партнёрство. Вы можете свободно исследовать кабинет и в любой момент вернуться к маршруту.
                  </p>
                </div>

                {progressError ? (
                  <p role="alert" className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm leading-5 text-red-800">
                    {progressError}
                  </p>
                ) : null}

                <Button
                  type="button"
                  className="mt-6 min-h-12 w-full gap-2 sm:w-auto sm:min-w-56"
                  onClick={() => void startFromWelcome()}
                >
                  Начать знакомство
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>

              <div className="order-first flex items-center justify-center lg:order-none lg:items-start">
                <div className="relative h-28 w-28 overflow-hidden rounded-full bg-white shadow-[0_10px_32px_rgba(15,23,42,0.15)] ring-1 ring-black/10 lg:h-36 lg:w-36">
                  <img
                    src={logo}
                    alt="Робот LocalOS"
                    className="h-44 w-44 -translate-x-8 -translate-y-2 scale-125 object-cover object-top lg:h-52 lg:w-52 lg:-translate-x-9"
                  />
                </div>
              </div>
            </div>
          </section>
        </div>
      ) : null}

      {open && !isWelcome ? (
        <section
          ref={panelRef}
          className="fixed inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] z-[70] mx-auto max-h-[calc(100vh-1.5rem)] max-w-md overflow-y-auto rounded-lg border border-slate-200 bg-white p-4 shadow-2xl sm:inset-x-auto sm:right-5 sm:w-[390px]"
          aria-live="polite"
          aria-label="Интерактивное обучение LocalOS"
          tabIndex={-1}
        >
          <div className="flex items-start gap-3">
            <div className={cn(
              'relative h-14 w-14 shrink-0 overflow-hidden rounded-full border bg-white',
              robotState === 'waiting' && 'border-slate-200',
              robotState === 'explaining' && 'border-orange-200',
              robotState === 'success' && 'border-emerald-200',
            )}>
              <img
                src={logo}
                alt={robotState === 'success' ? 'Робот LocalOS завершил обучение' : 'Робот LocalOS'}
                className="h-20 w-20 -translate-x-3 -translate-y-1 scale-125 object-cover object-top"
              />
              <span className={cn(
                'absolute bottom-0.5 right-0.5 flex h-5 w-5 items-center justify-center rounded-full text-white shadow-sm',
                robotState === 'waiting' && 'bg-slate-500',
                robotState === 'explaining' && 'bg-orange-500',
                robotState === 'success' && 'bg-emerald-600',
              )} aria-hidden="true">
                {robotState === 'waiting' ? <Play className="h-3 w-3 translate-x-px" /> : <Sparkles className="h-3 w-3" />}
              </span>
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold uppercase text-orange-700">{currentStep.chapterTitle}</p>
                  <p className="mt-1 text-xs tabular-nums text-slate-500">Шаг {currentIndex + 1} из {GUIDED_TOUR_STEPS.length}</p>
                </div>
                <Button type="button" variant="ghost" size="icon" className="h-10 w-10 shrink-0" onClick={pause} aria-label="Поставить обучение на паузу" data-tour-pause="true">
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100" aria-label={`Прогресс ${completedPercent}%`}>
                <div className="h-full rounded-full bg-orange-500 transition-[width] duration-200 motion-reduce:transition-none" style={{ width: `${completedPercent}%` }} />
              </div>
            </div>
          </div>

          <h2 className="mt-4 text-balance text-lg font-semibold text-slate-950">{currentStep.title}</h2>
          <p className="mt-2 text-pretty text-sm leading-6 text-slate-600">{currentStep.body}</p>
          {targetMissing && currentStep.target ? (
            <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
              Элемент ещё не загрузился. Можно показать его повторно или перейти дальше.
            </p>
          ) : null}
          {progressError ? (
            <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm leading-5 text-red-800">
              {progressError}
            </p>
          ) : null}

          {status === 'not_started' ? (
            <Button type="button" className="mt-4 w-full gap-2" onClick={() => void start()}>
              <Play className="h-4 w-4" />
              Начать знакомство
            </Button>
          ) : currentStep.final || status === 'completed' ? (
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              <Button type="button" className="gap-2" onClick={() => void openRoom()} disabled={!user.demo_room_slug}>
                <ExternalLink className="h-4 w-4" />
                Открыть комнату
              </Button>
              <Button type="button" variant="outline" className="gap-2" onClick={() => void register()}>
                <Sparkles className="h-4 w-4" />
                Создать аккаунт
              </Button>
              {status !== 'completed' ? (
                <Button type="button" variant="outline" className="gap-2 sm:col-span-2" onClick={() => void next()}>
                  Завершить маршрут
                </Button>
              ) : null}
              <Button type="button" variant="ghost" className="gap-2 sm:col-span-2" onClick={() => void restart()}>
                <RotateCcw className="h-4 w-4" />
                Начать заново
              </Button>
            </div>
          ) : (
            <>
              {currentStep.target ? (
                <Button type="button" variant="outline" className="mt-4 w-full gap-2" onClick={() => showStep(currentStep)}>
                  <Sparkles className="h-4 w-4" />
                  Показать на странице
                </Button>
              ) : null}
              <div className="mt-3 flex gap-2">
                <Button type="button" variant="outline" size="icon" className="h-10 w-10 shrink-0" onClick={() => void previous()} disabled={currentIndex === 0} aria-label="Предыдущий шаг">
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <Button type="button" className="min-h-10 flex-1 gap-2" onClick={() => void next()}>
                  Дальше
                  <ArrowRight className="h-4 w-4" />
                </Button>
                <Button type="button" variant="outline" size="icon" className="h-10 w-10 shrink-0" onClick={() => void pause()} aria-label="Пауза">
                  <Pause className="h-4 w-4" />
                </Button>
              </div>
              <button type="button" className="mt-3 min-h-10 w-full text-xs font-medium text-slate-500 hover:text-slate-900" onClick={() => void skip()}>
                Пропустить обучение
              </button>
            </>
          )}
        </section>
      ) : null}
    </>
  );
}

export function DemoModeBanner() {
  const register = () => {
    newAuth.deactivateDemoSession();
    window.location.href = '/login?tab=register&source=interactive_demo';
  };
  return (
    <div className="border-b border-orange-200 bg-orange-50 px-4 py-2 text-orange-950">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-2 text-sm">
        <span className="font-medium">Демо-режим · данные не изменяются</span>
        <button type="button" onClick={register} className={cn('min-h-10 rounded-md px-3 text-sm font-semibold text-orange-900', 'hover:bg-orange-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500')}>
          Создать свой аккаунт
        </button>
      </div>
    </div>
  );
}
