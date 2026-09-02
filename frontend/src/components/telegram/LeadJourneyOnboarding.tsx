import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowLeft, BadgeDollarSign, Bot, Check, ChevronRight, FilePenLine, Handshake, MapPinned, Megaphone, Sparkles } from 'lucide-react';

import { getLeadJourneyDirection, leadJourneyDirections, saveLeadJourneyIntent, type LeadJourneyKey } from '@/lib/leadJourney';

type LeadJourneyOnboardingProps = {
  onFinish: (direction?: LeadJourneyKey) => void;
};

type JourneyStep = 'choose' | 'detail' | 'result';

const spring = { type: 'spring', duration: 0.3, bounce: 0 };

const directionIcon = (key: LeadJourneyKey) => {
  if (key === 'influencers') return Megaphone;
  if (key === 'partnerships') return Handshake;
  if (key === 'content') return FilePenLine;
  if (key === 'automation') return Bot;
  if (key === 'average_ticket') return BadgeDollarSign;
  return MapPinned;
};

export default function LeadJourneyOnboarding({ onFinish }: LeadJourneyOnboardingProps) {
  const [step, setStep] = useState<JourneyStep>('choose');
  const [selectedKey, setSelectedKey] = useState<LeadJourneyKey | null>(null);
  const selected = getLeadJourneyDirection(selectedKey);

  const choose = (key: LeadJourneyKey) => {
    setSelectedKey(key);
    setStep('detail');
  };

  const back = () => {
    if (step === 'result') setStep('detail');
    else {
      setSelectedKey(null);
      setStep('choose');
    }
  };

  const finish = () => {
    if (selected) saveLeadJourneyIntent(selected.key);
    onFinish(selected?.key);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-zinc-950/[0.78] px-4 py-[calc(18px+env(safe-area-inset-top))] backdrop-blur-xl">
      <AnimatePresence initial={false} mode="wait">
        <motion.section
          key={`${step}-${selectedKey || 'none'}`}
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
              <span className="grid h-12 w-12 place-items-center rounded-[17px] bg-primary/[0.14] text-primary shadow-[0_0_0_1px_rgba(255,92,51,0.18)]"><Sparkles className="h-6 w-6" /></span>
              <span className="text-xs tabular-nums text-zinc-600">{step === 'choose' ? '1' : step === 'detail' ? '2' : '3'} / 3</span>
            </div>

            {step === 'choose' ? (
              <>
                <small className="mt-6 block font-semibold uppercase tracking-[0.14em] text-primary">Первое полезное действие</small>
                <h1 id="localos-onboarding-title" className="mt-2 text-balance text-[28px] font-semibold leading-[1.08] tracking-[-0.045em]">Откуда привести следующего клиента?</h1>
                <p className="mt-4 text-pretty text-sm leading-6 text-zinc-400">Выберите направление. Сначала покажем конкретную возможность и часть готового результата.</p>
                <div className="mt-5 space-y-2">
                  {leadJourneyDirections.map((direction) => {
                    const Icon = directionIcon(direction.key);
                    return (
                      <button key={direction.key} type="button" onClick={() => choose(direction.key)} className="flex min-h-20 w-full items-center gap-3 rounded-[20px] bg-black/[0.18] p-3 text-left shadow-[0_0_0_1px_rgba(255,255,255,0.065)] transition-transform active:scale-[0.96]">
                        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[15px] bg-primary/[0.12] text-primary"><Icon className="h-5 w-5" /></span>
                        <span className="min-w-0 flex-1"><b className="block text-sm">{direction.eyebrow}</b><small className="mt-1 block text-pretty text-[11px] leading-4 text-zinc-500">{direction.preview}</small></span>
                        <ChevronRight className="h-4 w-4 shrink-0 text-zinc-700" />
                      </button>
                    );
                  })}
                </div>
              </>
            ) : selected ? (
              <>
                <small className="mt-6 block font-semibold uppercase tracking-[0.14em] text-primary">{selected.eyebrow}</small>
                <h1 id="localos-onboarding-title" className="mt-2 text-balance text-[28px] font-semibold leading-[1.08] tracking-[-0.045em]">{step === 'result' ? selected.resultTitle : selected.detailTitle}</h1>
                <p className="mt-4 text-pretty text-sm leading-6 text-zinc-400">{step === 'result' ? 'Вот из чего будет состоять первый рабочий результат. Ничего не отправляется и не изменяется без вашего подтверждения.' : selected.detail}</p>
                {step === 'detail' ? (
                  <div className="mt-6 rounded-[22px] bg-black/20 p-4 shadow-[0_0_0_1px_rgba(255,255,255,0.06)]">
                    <b className="block text-sm text-zinc-200">Следующий конкретный шаг</b>
                    <p className="mt-2 text-pretty text-xs leading-5 text-zinc-500">{selected.prepareLabel}. Перед действием вы увидите готовый материал и сможете его проверить.</p>
                  </div>
                ) : (
                  <>
                    <div className="mt-5 divide-y divide-white/[0.06] rounded-[20px] bg-black/[0.18] px-4 shadow-[0_0_0_1px_rgba(255,255,255,0.055)]">
                      {selected.resultPreview.map((item) => <div key={item} className="flex min-h-12 items-center gap-3 py-2.5 text-sm text-zinc-300"><Check className="h-4 w-4 shrink-0 text-emerald-300" /><span className="text-pretty">{item}</span></div>)}
                    </div>
                    <div className="mt-4 grid grid-cols-3 gap-1.5 text-center text-[10px] leading-4 text-zinc-600">
                      <span className="rounded-[12px] bg-white/[0.04] px-2 py-2"><b className="block text-zinc-300">Действие</b>первый шаг</span>
                      <span className="rounded-[12px] bg-white/[0.04] px-2 py-2"><b className="block text-zinc-300">Статус</b>что вышло</span>
                      <span className="rounded-[12px] bg-white/[0.04] px-2 py-2"><b className="block text-zinc-300">Дальше</b>по результату</span>
                    </div>
                  </>
                )}
              </>
            ) : null}
          </div>

          <div className="mt-4 flex shrink-0 gap-2 border-t border-white/[0.055] pt-4">
            {step !== 'choose' ? <button type="button" aria-label="Назад" onClick={back} className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-white/[0.055] text-zinc-300 shadow-[0_0_0_1px_rgba(255,255,255,0.07)] transition-transform active:scale-[0.96]"><ArrowLeft className="h-4 w-4" /></button> : null}
            {selected && step !== 'choose' ? <button type="button" onClick={() => { if (step === 'detail') setStep('result'); else finish(); }} className="flex min-h-12 flex-1 items-center justify-center gap-2 rounded-2xl bg-primary pl-4 pr-3.5 text-sm font-semibold text-white shadow-[0_14px_38px_rgba(255,92,51,0.26)] transition-transform active:scale-[0.96]">{step === 'detail' ? selected.prepareLabel : 'Открыть рабочий шаг'}<ChevronRight className="h-4 w-4" /></button> : null}
          </div>
          {step === 'choose' ? <button type="button" onClick={() => onFinish()} className="mt-3 min-h-11 w-full text-xs font-medium text-zinc-600 transition-[color,transform] active:scale-[0.96]">Открыть текущие задачи</button> : null}
        </motion.section>
      </AnimatePresence>
    </div>
  );
}
