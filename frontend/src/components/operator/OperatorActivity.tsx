import { useEffect, useRef, useState } from 'react';
import { Bot, CheckCircle2, Clock3, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

// Reveal only fresh replies. The complete server response is already available;
// this is a presentation effect, never a claim of model streaming or job progress.
export function OperatorReply({ text, animate = false }: { text: string; animate?: boolean }) {
  const skipped = useRef(false);
  const [visible, setVisible] = useState(animate ? 0 : text.length);
  useEffect(() => {
    if (!animate || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      setVisible(text.length);
      return;
    }
    skipped.current = false;
    setVisible(0);
    const started = performance.now();
    let frame = 0;
    const duration = Math.min(1200, Math.max(240, text.length * 12));
    const reveal = (now: number) => {
      if (skipped.current) return;
      const count = Math.min(text.length, Math.ceil((now - started) / duration * text.length));
      setVisible(count);
      if (count < text.length) frame = requestAnimationFrame(reveal);
    };
    frame = requestAnimationFrame(reveal);
    return () => cancelAnimationFrame(frame);
  }, [text, animate]);
  const typing = visible < text.length;
  if (!typing) return <div translate="no" className="notranslate whitespace-pre-wrap">{text}</div>;
  return <div>
    <span className="sr-only">{text}</span>
    <div className="grid"><div aria-hidden="true" className="invisible col-start-1 row-start-1 whitespace-pre-wrap">{text}</div><div aria-hidden="true" translate="no" className="notranslate col-start-1 row-start-1 whitespace-pre-wrap">{text.slice(0, visible)}{typing && <span className="ml-0.5 inline-block h-4 w-0.5 bg-current align-middle motion-safe:animate-pulse" />}</div></div>
    {typing && <Button type="button" variant="ghost" size="sm" onClick={() => { skipped.current = true; setVisible(text.length); }}>Показать сразу</Button>}
  </div>;
}

export function OperatorActivity({ phase, accepted, waiting = false }: { phase: string; accepted: boolean; waiting?: boolean }) {
  return <div className="flex justify-start" role="status" aria-live="polite" aria-atomic="true">
    <div className="flex max-w-3xl items-center gap-3 rounded-2xl border bg-background px-4 py-3 shadow-sm">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-muted"><Bot className="h-5 w-5" aria-hidden="true" /></div>
      <div>
        <p className="flex items-center gap-2 text-sm font-medium">{waiting ? <Clock3 className="h-4 w-4" aria-hidden="true" /> : <Loader2 className="h-4 w-4 motion-safe:animate-spin" aria-hidden="true" />}{phase}</p>
        <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">{accepted && <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />}{accepted ? 'Команда принята · можно дождаться результата здесь' : 'Ждём подтверждения от сервера'}</p>
      </div>
    </div>
  </div>;
}
