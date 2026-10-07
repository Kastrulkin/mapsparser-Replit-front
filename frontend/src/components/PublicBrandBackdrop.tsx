import { cn } from '@/lib/utils';

export const PublicBrandBackdrop = ({ fullHeight = false }: { fullHeight?: boolean }) => {
  const bounds = fullHeight ? 'inset-0' : 'inset-x-0 top-0 h-[44rem]';

  return <>
    <div className={cn('pointer-events-none absolute -z-10 bg-[radial-gradient(circle_at_18%_10%,rgba(249,115,22,0.14),transparent_32%),radial-gradient(circle_at_82%_18%,rgba(251,191,36,0.10),transparent_28%)]', bounds)} aria-hidden="true" />
    <div className={cn('pointer-events-none absolute -z-20 bg-[linear-gradient(to_right,rgba(15,23,42,0.035)_1px,transparent_1px),linear-gradient(to_bottom,rgba(15,23,42,0.035)_1px,transparent_1px)] bg-[size:48px_48px] [mask-image:linear-gradient(to_bottom,black,transparent_88%)]', bounds)} data-brand-background="localos-grid" aria-hidden="true" />
  </>;
};
