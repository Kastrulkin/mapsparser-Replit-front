import { LockKeyhole } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { todayClarityCopy } from '@/i18n/todayClarityCopy';
import { safeWorkReturn } from '@/lib/workNavigation';
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export type AccessState = 'available' | 'registration_required' | 'payment_required' | 'setup_required' | 'approval_required' | 'unavailable';

export type BlockAccess = {
  status: AccessState;
  reason: string;
  cta_label: string;
  cta_target: { screen?: string; action_id?: string | null; url?: string; focus?: string };
  entitlement_source?: string;
};

export const targetForAccess = (access: BlockAccess, returnTo?: string): string | null => {
 const target = safeWorkReturn(access.cta_target.url);
 const base = target || (access.status === 'payment_required' ? '/dashboard/profile?focus=subscription#subscription'
 : access.status === 'setup_required' ? '/dashboard/settings?focus=' + encodeURIComponent(access.cta_target.focus || 'integrations')
 : access.status === 'approval_required' && access.cta_target.action_id ? '/dashboard/operator?journey_action=' + encodeURIComponent(access.cta_target.action_id)
 : access.status === 'registration_required' ? '/login' : null);
 if (!base) return null;
 const url = new URL(base, 'https://localos.pro'); const back = safeWorkReturn(returnTo);
 if (back) url.searchParams.set('return_to', back);
 return url.pathname + url.search + url.hash;
};

export const AccessPreview = ({ access, className, title, businessId }: { access: BlockAccess; className?: string; title?: string; businessId?: string }) => {
  const location = useLocation();
  const { language } = useLanguage();
  const targetValue = targetForAccess(access, location.pathname + location.search);
  const target = targetValue && businessId ? (() => { const url = new URL(targetValue, 'https://localos.pro'); url.searchParams.set('business_id', businessId); url.searchParams.set('scope_type', 'business'); return url.pathname + url.search + url.hash; })() : targetValue;
  if (access.status === 'available') return null;
  return (
    <div className={cn('rounded-2xl border border-amber-200/80 bg-amber-50/80 p-4', className)} role="note">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white text-amber-700 shadow-sm ring-1 ring-amber-200">
          <LockKeyhole className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-amber-950">{title || todayClarityCopy(language).details}</p>
          <p className="mt-1 text-pretty text-sm leading-5 text-amber-900/75">{access.reason}</p>
          {target ? <Link
            to={target}
            className="mt-3 inline-flex min-h-10 items-center justify-center rounded-xl bg-slate-950 px-4 text-sm font-semibold text-white transition-[background-color,transform] duration-150 hover:bg-slate-800 active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-950 focus-visible:ring-offset-2"
          >
            {access.cta_label}
          </Link> : null}
        </div>
      </div>
    </div>
  );
};

export const AccessBoundary = ({ access, children }: { access: BlockAccess; children: ReactNode }) => {
  const available = access.status === 'available';
  return (
    <section className="relative">
      <div className={available ? undefined : 'select-none opacity-55'} aria-hidden={!available || undefined}>
        {children}
      </div>
      {!available ? <AccessPreview access={access} className="mt-3" /> : null}
    </section>
  );
};
