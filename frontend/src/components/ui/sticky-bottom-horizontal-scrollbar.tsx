import * as React from "react";
import { cn } from "@/lib/utils";

type StickyBottomHorizontalScrollbarProps = {
  targetRef: React.RefObject<HTMLElement | null>;
  className?: string;
  bottomOffset?: number;
};

export function StickyBottomHorizontalScrollbar({
  targetRef,
  className,
  bottomOffset = 10,
}: StickyBottomHorizontalScrollbarProps) {
  const [visible, setVisible] = React.useState(false);
  const [barWidth, setBarWidth] = React.useState(0);
  const [barLeft, setBarLeft] = React.useState(0);
  const [maxScrollLeft, setMaxScrollLeft] = React.useState(0);
  const [scrollLeft, setScrollLeft] = React.useState(0);
  const syncingFromInput = React.useRef(false);
  const syncingFromTarget = React.useRef(false);

  const syncMetrics = React.useCallback(() => {
    const target = targetRef.current;
    if (!target) {
      setVisible(false);
      return;
    }

    const rect = target.getBoundingClientRect();
    const targetMaxScroll = Math.max(0, target.scrollWidth - target.clientWidth);
    const hasHorizontalOverflow = targetMaxScroll > 1;
    const inViewport = rect.bottom > 0 && rect.top < window.innerHeight;
    setVisible(hasHorizontalOverflow && inViewport);
    setBarLeft(Math.max(8, rect.left));
    setBarWidth(Math.max(120, Math.min(rect.width, window.innerWidth - rect.left - 8)));
    setMaxScrollLeft(targetMaxScroll);
    if (!syncingFromInput.current) {
      syncingFromTarget.current = true;
      setScrollLeft(target.scrollLeft);
      requestAnimationFrame(() => {
        syncingFromTarget.current = false;
      });
    }
  }, [targetRef]);

  React.useEffect(() => {
    const target = targetRef.current;
    if (!target) return;

    const onTargetScroll = () => {
      if (syncingFromInput.current) return;
      syncingFromTarget.current = true;
      setScrollLeft(target.scrollLeft);
      requestAnimationFrame(() => {
        syncingFromTarget.current = false;
      });
    };

    const observer = new ResizeObserver(() => syncMetrics());
    observer.observe(target);
    target.addEventListener("scroll", onTargetScroll, { passive: true });
    window.addEventListener("resize", syncMetrics, { passive: true });
    window.addEventListener("scroll", syncMetrics, { passive: true });
    syncMetrics();

    return () => {
      observer.disconnect();
      target.removeEventListener("scroll", onTargetScroll);
      window.removeEventListener("resize", syncMetrics);
      window.removeEventListener("scroll", syncMetrics);
    };
  }, [syncMetrics, targetRef]);

  if (!visible) return null;

  return (
    <div
      className={cn(
        "fixed z-[60] rounded-md border border-border bg-background/95 px-2 py-1.5 shadow-sm backdrop-blur",
        className
      )}
      style={{ left: barLeft, width: barWidth, bottom: bottomOffset }}
    >
      <input
        type="range"
        min={0}
        max={Math.max(1, maxScrollLeft)}
        step={1}
        value={Math.min(scrollLeft, Math.max(1, maxScrollLeft))}
        onChange={(event) => {
          const target = targetRef.current;
          if (!target) return;
          const next = Number(event.target.value || 0);
          syncingFromInput.current = true;
          setScrollLeft(next);
          target.scrollLeft = next;
          requestAnimationFrame(() => {
            syncingFromInput.current = false;
          });
        }}
        className="h-4 w-full cursor-ew-resize accent-slate-700"
        aria-label="Горизонтальный скролл таблицы"
      />
    </div>
  );
}
