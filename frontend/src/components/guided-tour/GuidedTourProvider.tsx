import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { AnimatePresence, LayoutGroup, motion, useReducedMotion } from 'framer-motion';
import { ArrowLeft, ArrowRight, Check, ExternalLink, Pause, Play, RotateCcw, Sparkles, X } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';

import logo from '@/assets/images/logo.png';
import { Button } from '@/components/ui/button';
import { useLanguage } from '@/i18n/LanguageContext';
import { newAuth, type User } from '@/lib/auth_new';
import { cn } from '@/lib/utils';
import { fillGuidedTourTemplate, guidedTourCopyForLanguage } from './guidedTourCopy';
import {
  GUIDED_TOUR_KEY,
  GUIDED_TOUR_VERSION,
  guidedTourStepsForLanguage,
  type GuidedTourStep,
} from './tourConfig';


type TourStatus = 'not_started' | 'active' | 'paused' | 'skipped' | 'completed';

type TourProgress = {
  status: TourStatus;
  chapter_key?: string | null;
  step_key?: string | null;
  completed_steps?: string[];
  updated_at?: string | null;
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
  const { language } = useLanguage();
  const prefersReducedMotion = useReducedMotion();
  const [loaded, setLoaded] = useState(false);
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<TourStatus>('not_started');
  const [currentIndex, setCurrentIndex] = useState(0);
  const [completedSteps, setCompletedSteps] = useState<string[]>([]);
  const [targetRect, setTargetRect] = useState<TargetRect | null>(null);
  const [targetMissing, setTargetMissing] = useState(false);
  const [progressError, setProgressError] = useState<string | null>(null);
  const [welcomeTransitioning, setWelcomeTransitioning] = useState(false);
  const [targetEmphasisKey, setTargetEmphasisKey] = useState(0);
  const missingEventStepRef = useRef<string | null>(null);
  const initialRouteSyncedRef = useRef(false);
  const panelRef = useRef<HTMLElement | null>(null);
  const launcherRef = useRef<HTMLButtonElement | null>(null);
  const copy = useMemo(() => guidedTourCopyForLanguage(language), [language]);
  const steps = useMemo(() => guidedTourStepsForLanguage(language), [language]);
  const currentStep = steps[currentIndex] || steps[0];
  const isDemo = Boolean(user.demo_mode);
  const localProgressKey = `localos:guided-tour:${GUIDED_TOUR_KEY}:v${GUIDED_TOUR_VERSION}:${user.id}`;
  const isWelcome = currentStep.key === 'welcome';
  const robotState = status === 'not_started'
    ? 'waiting'
    : currentStep.final || status === 'completed'
      ? 'success'
      : 'explaining';

  const completedPercent = useMemo(
    () => Math.round((completedSteps.length / steps.length) * 100),
    [completedSteps.length, steps.length],
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
    const localProgress = { ...progressForStep(nextStatus, step, nextCompletedSteps), updated_at: new Date().toISOString() };
    window.sessionStorage.setItem(localProgressKey, JSON.stringify(localProgress));
    void persistProgress(nextStatus, step, nextCompletedSteps)
      .then(() => setProgressError(null))
      .catch((progressSaveError) => console.warn('Guided tour progress will be synchronized later:', progressSaveError));
    return true;
  }, [localProgressKey, persistProgress]);

  useEffect(() => {
    if (!isDemo) return;
    let cancelled = false;
    const rawLocalProgress = window.sessionStorage.getItem(localProgressKey);
    let localProgress: TourProgress | null = null;
    if (rawLocalProgress) {
      try {
        const parsed = JSON.parse(rawLocalProgress);
        if (parsed && typeof parsed === 'object') localProgress = parsed;
      } catch (parseError) {
        console.warn('Invalid local guided tour progress was ignored:', parseError);
      }
    }
    const applyProgress = (progress: TourProgress) => {
      const nextStatus = progress.status || 'not_started';
      const nextIndex = Math.max(0, steps.findIndex((step) => step.key === progress.step_key));
      setStatus(nextStatus);
      setCurrentIndex(nextIndex);
      setCompletedSteps(Array.isArray(progress.completed_steps) ? progress.completed_steps : []);
      setOpen(nextStatus === 'not_started' || nextStatus === 'active');
      setLoaded(true);
    };
    newAuth.makeRequest(`/guided-tours/${GUIDED_TOUR_KEY}/progress`, { method: 'GET' })
      .then((response) => {
        if (cancelled) return;
        const serverProgress: TourProgress = response.progress || {};
        const localUpdated = Date.parse(localProgress?.updated_at || '');
        const serverUpdated = Date.parse(serverProgress.updated_at || '');
        const selectedProgress = localProgress && (!Number.isFinite(serverUpdated) || localUpdated >= serverUpdated) ? localProgress : serverProgress;
        applyProgress(selectedProgress);
        if (selectedProgress === localProgress && localProgress?.step_key) {
          const localStep = steps.find((step) => step.key === localProgress?.step_key) || steps[0];
          void persistProgress(localProgress.status, localStep, localProgress.completed_steps || []);
        }
      })
      .catch((progressError) => {
        if (cancelled) return;
        console.warn('Guided tour progress was not loaded:', progressError);
        applyProgress(localProgress || { status: 'not_started', completed_steps: [] });
      });
    return () => {
      cancelled = true;
    };
  }, [isDemo, localProgressKey, persistProgress, steps]);

  useEffect(() => {
    if (!open || !isWelcome) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isWelcome, open]);

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

  const emphasizeCurrentTarget = () => {
    setTargetEmphasisKey((value) => value + 1);
    const targetLocated = locateTarget(currentStep, true);
    if (!targetLocated) {
      showStep(currentStep);
    }
  };

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
  }, [currentIndex, loaded, open]);

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
    if (welcomeTransitioning) return;
    const nextIndex = Math.min(1, steps.length - 1);
    const nextStep = steps[nextIndex];
    const nextCompletedSteps = [currentStep.key];
    const saved = await persistProgressSafely('active', nextStep, nextCompletedSteps);
    if (!saved) return;
    setWelcomeTransitioning(true);
    if (!prefersReducedMotion) {
      await new Promise<void>((resolve) => window.setTimeout(resolve, 180));
    }
    setStatus('active');
    setCurrentIndex(nextIndex);
    setCompletedSteps(nextCompletedSteps);
    await recordEvent('started', currentStep);
    await recordEvent('step_viewed', nextStep);
    showStep(nextStep);
    window.setTimeout(() => setWelcomeTransitioning(false), prefersReducedMotion ? 0 : 650);
  };

  const moveTo = async (nextIndex: number, nextCompletedSteps: string[], nextStatus: TourStatus = 'active') => {
    const boundedIndex = Math.max(0, Math.min(nextIndex, steps.length - 1));
    const nextStep = steps[boundedIndex];
    const saved = await persistProgressSafely(nextStatus, nextStep, nextCompletedSteps);
    if (!saved) return;
    setTargetEmphasisKey(0);
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
    if (currentStep.final || currentIndex === steps.length - 1) {
      const saved = await persistProgressSafely('completed', currentStep, nextCompleted);
      if (!saved) return;
      setCompletedSteps(nextCompleted);
      setStatus('completed');
      setTargetRect(null);
      await recordEvent('completed', currentStep);
      return;
    }
    const nextStep = steps[currentIndex + 1];
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
    const firstStep = steps[0];
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
      window.open(`/room/${encodeURIComponent(user.demo_room_slug)}?lang=${encodeURIComponent(language)}`, '_blank', 'noopener,noreferrer');
    }
  };

  const register = async () => {
    await recordEvent('registration_clicked', currentStep);
    newAuth.deactivateDemoSession(true);
    window.location.assign('/login?tab=register&source=interactive_demo');
  };

  if (!isDemo) return <>{children}</>;

  return (
    <>
      {children}
      {targetRect && open ? (
        <div
          key={`${currentStep.key}-${targetEmphasisKey}`}
          data-tour-highlight="true"
          className="pointer-events-none fixed z-[65] rounded-lg border-2 border-orange-500 transition-[top,left,width,height] duration-200 motion-reduce:transition-none"
          style={{
            top: targetRect.top - 5,
            left: targetRect.left - 5,
            width: targetRect.width + 10,
            height: targetRect.height + 10,
            boxShadow: targetEmphasisKey > 0 && prefersReducedMotion
              ? '0 0 0 8px rgba(249,115,22,0.32)'
              : '0 0 0 5px rgba(249,115,22,0.16)',
            animation: targetEmphasisKey > 0 && !prefersReducedMotion
              ? 'guided-tour-target-pulse 1.35s ease-in-out'
              : undefined,
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
          aria-label={status === 'completed' ? copy.controls.launcherOpenAgain : copy.controls.launcherContinue}
        >
          <img src={logo} alt="" className="h-24 w-24 -translate-y-1 scale-150 object-cover object-top" aria-hidden="true" />
        </button>
      ) : null}

      <LayoutGroup id="guided-tour-panel">
        <AnimatePresence initial={false}>
          {open && isWelcome ? (
            <motion.div
              key="guided-tour-welcome"
              className="fixed inset-0 z-[70] flex items-center justify-center overflow-hidden px-4 py-6"
              initial={false}
              animate={{ backgroundColor: 'rgba(15, 23, 42, 0.45)', backdropFilter: 'blur(4px)' }}
              exit={{ backgroundColor: 'rgba(15, 23, 42, 0)', backdropFilter: 'blur(0px)' }}
              transition={{ duration: prefersReducedMotion ? 0 : 0.35 }}
            >
              <motion.section
                layoutId="guided-tour-panel"
                transition={{
                  layout: prefersReducedMotion
                    ? { duration: 0 }
                    : { type: 'spring', duration: 0.55, bounce: 0 },
                }}
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="demo-welcome-title"
            className="my-auto flex max-h-[calc(100vh-2rem)] w-full max-w-[860px] flex-col overflow-hidden rounded-lg bg-white shadow-[0_24px_80px_rgba(15,23,42,0.24),0_3px_14px_rgba(15,23,42,0.1)] ring-1 ring-black/10 focus:outline-none"
            tabIndex={-1}
          >
            <motion.div
              className="min-h-0 overflow-y-auto p-5 sm:p-8"
              animate={{ opacity: welcomeTransitioning ? 0 : 1 }}
              transition={{ duration: prefersReducedMotion ? 0 : 0.16 }}
            >
              <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_72px] sm:items-start sm:gap-x-8">
                <div className="min-w-0">
                  <p className="text-xs font-medium text-slate-500">{copy.welcome.eyebrow}</p>
                  <h1 id="demo-welcome-title" className="mt-2 text-balance text-2xl font-semibold leading-tight text-slate-950 sm:text-3xl">
                    {copy.welcome.headline}
                  </h1>
                </div>

                <div className="order-first flex justify-center sm:order-none sm:justify-end">
                  <div className="relative h-16 w-16 overflow-hidden sm:h-[72px] sm:w-[72px]">
                    <img
                      src={logo}
                      alt={copy.controls.robotAlt}
                      className="absolute left-1/2 top-0 h-auto w-[175%] max-w-none -translate-x-1/2 -translate-y-[10%] object-contain mix-blend-multiply"
                    />
                  </div>
                </div>

                <p className="text-pretty text-sm leading-6 text-slate-600 sm:col-span-2 sm:max-w-3xl sm:text-base sm:leading-7">
                  {copy.welcome.intro}
                </p>
              </div>

              <div className="mt-6 border-t border-slate-200 pt-5">
                <h2 className="text-sm font-semibold text-slate-950">{copy.welcome.capabilitiesTitle}</h2>
                <ul className="mt-3 grid gap-x-8 gap-y-2.5 text-sm leading-5 text-slate-700 sm:grid-cols-2">
                  {copy.welcome.capabilities.map((item) => (
                    <li key={item} className="grid grid-cols-[18px_minmax(0,1fr)] gap-2">
                      <Check className="mt-0.5 h-4 w-4 text-orange-600" aria-hidden="true" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="mt-6 grid gap-1 border-t border-slate-200 pt-5 sm:grid-cols-[170px_minmax(0,1fr)] sm:gap-6">
                <h2 className="font-semibold text-slate-950">{steps[0].title}</h2>
                <p className="text-pretty text-sm leading-6 text-slate-600">
                  {steps[0].body}
                </p>
              </div>

              {progressError ? (
                <p role="alert" className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm leading-5 text-red-800">
                  {progressError}
                </p>
              ) : null}
            </motion.div>
            <motion.div
              className="shrink-0 border-t border-slate-200 bg-slate-50/80 px-5 py-3 sm:px-8"
              animate={{ opacity: welcomeTransitioning ? 0 : 1 }}
              transition={{ duration: prefersReducedMotion ? 0 : 0.16 }}
            >
              <Button
                type="button"
                className="min-h-12 w-full gap-2 sm:w-auto sm:min-w-56"
                onClick={() => void startFromWelcome()}
                disabled={welcomeTransitioning}
              >
                {copy.controls.start}
                <ArrowRight className="h-4 w-4" />
              </Button>
            </motion.div>
              </motion.section>
            </motion.div>
          ) : null}

          {open && !isWelcome ? (
            <motion.section
              key="guided-tour-step"
              layoutId="guided-tour-panel"
              transition={{
                layout: prefersReducedMotion
                  ? { duration: 0 }
                  : { type: 'spring', duration: 0.55, bounce: 0 },
              }}
              ref={panelRef}
              className="fixed inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] z-[70] mx-auto max-h-[calc(100vh-1.5rem)] max-w-md overflow-y-auto rounded-lg border border-slate-200 bg-white p-4 shadow-2xl focus:outline-none sm:inset-x-auto sm:right-5 sm:w-[390px]"
              aria-live="polite"
              aria-label={copy.controls.tourLabel}
              tabIndex={-1}
            >
          {!prefersReducedMotion ? (
            <motion.div
              className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-white"
              initial={{ opacity: 1 }}
              animate={{ opacity: 0 }}
              transition={{ delay: 0.3, duration: 0.14 }}
              aria-hidden="true"
            >
              <div className="relative h-14 w-14 overflow-hidden">
                <img
                  src={logo}
                  alt=""
                  className="absolute left-1/2 top-0 h-auto w-[175%] max-w-none -translate-x-1/2 -translate-y-[10%] object-contain mix-blend-multiply"
                />
              </div>
            </motion.div>
          ) : null}
          <motion.div
            initial={prefersReducedMotion ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              delay: prefersReducedMotion ? 0 : 0.36,
              duration: prefersReducedMotion ? 0 : 0.18,
            }}
          >
          <div className="flex items-start gap-3">
            <div className="relative h-14 w-14 shrink-0">
              <div className="absolute inset-0 overflow-hidden">
                <img
                  src={logo}
                  alt={robotState === 'success' ? copy.controls.robotSuccessAlt : copy.controls.robotAlt}
                  className="absolute left-1/2 top-0 h-auto w-[175%] max-w-none -translate-x-1/2 -translate-y-[10%] object-contain mix-blend-multiply"
                />
              </div>
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
                  <p className="mt-1 text-xs tabular-nums text-slate-500">
                    {fillGuidedTourTemplate(copy.controls.stepTemplate, { current: currentIndex + 1, total: steps.length })}
                  </p>
                </div>
                <Button type="button" variant="ghost" size="icon" className="h-10 w-10 shrink-0" onClick={pause} aria-label={copy.controls.pauseLabel} data-tour-pause="true">
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100" aria-label={fillGuidedTourTemplate(copy.controls.progressTemplate, { percent: completedPercent })}>
                <div className="h-full rounded-full bg-orange-500 transition-[width] duration-200 motion-reduce:transition-none" style={{ width: `${completedPercent}%` }} />
              </div>
            </div>
          </div>

          <h2 className="mt-4 text-balance text-lg font-semibold text-slate-950">{currentStep.title}</h2>
          <p className="mt-2 text-pretty text-sm leading-6 text-slate-600">{currentStep.body}</p>
          {targetMissing && currentStep.target ? (
            <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
              {copy.controls.targetMissing}
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
              {copy.controls.start}
            </Button>
          ) : currentStep.final || status === 'completed' ? (
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              <Button type="button" className="gap-2" onClick={() => void openRoom()} disabled={!user.demo_room_slug}>
                <ExternalLink className="h-4 w-4" />
                {copy.controls.openRoom}
              </Button>
              <Button type="button" variant="outline" className="gap-2" onClick={() => void register()}>
                <Sparkles className="h-4 w-4" />
                {copy.controls.createAccount}
              </Button>
              {status !== 'completed' ? (
                <Button type="button" variant="outline" className="gap-2 sm:col-span-2" onClick={() => void next()}>
                  {copy.controls.finish}
                </Button>
              ) : null}
              <Button type="button" variant="ghost" className="gap-2 sm:col-span-2" onClick={() => void restart()}>
                <RotateCcw className="h-4 w-4" />
                {copy.controls.restart}
              </Button>
            </div>
          ) : (
            <>
              {currentStep.target ? (
                <Button type="button" variant="outline" className="mt-4 w-full gap-2" onClick={emphasizeCurrentTarget}>
                  <Sparkles className="h-4 w-4" />
                  {copy.controls.highlight}
                </Button>
              ) : null}
              <div className="mt-3 flex gap-2">
                <Button type="button" variant="outline" size="icon" className="h-10 w-10 shrink-0" onClick={() => void previous()} disabled={currentIndex === 0} aria-label={copy.controls.previous}>
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <Button type="button" className="min-h-10 flex-1 gap-2" onClick={() => void next()}>
                  {copy.controls.next}
                  <ArrowRight className="h-4 w-4" />
                </Button>
                <Button type="button" variant="outline" size="icon" className="h-10 w-10 shrink-0" onClick={() => void pause()} aria-label={copy.controls.pause}>
                  <Pause className="h-4 w-4" />
                </Button>
              </div>
              <button type="button" className="mt-3 min-h-10 w-full text-xs font-medium text-slate-500 hover:text-slate-900" onClick={() => void skip()}>
                {copy.controls.skip}
              </button>
            </>
          )}
          </motion.div>
            </motion.section>
          ) : null}
        </AnimatePresence>
      </LayoutGroup>
    </>
  );
}

export function DemoModeBanner() {
  const { language } = useLanguage();
  const copy = guidedTourCopyForLanguage(language);
  const register = () => {
    newAuth.deactivateDemoSession(true);
  };
  return (
    <div className="border-b border-orange-200 bg-orange-50 px-4 py-2 text-orange-950">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-2 text-sm">
        <span className="font-medium">{copy.banner.notice}</span>
        <a href="/login?tab=register&source=interactive_demo" onClick={register} className={cn('inline-flex min-h-10 items-center rounded-lg bg-orange-600 px-4 text-sm font-semibold text-white shadow-sm', 'transition-[background-color,box-shadow,transform] hover:bg-orange-700 hover:shadow-md active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 focus-visible:ring-offset-2')}>
          {copy.banner.createAccount}
        </a>
      </div>
    </div>
  );
}
