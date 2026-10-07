import { LockKeyhole } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export type AccessState = 'available' | 'registration_required' | 'payment_required' | 'setup_required' | 'approval_required' | 'unavailable';

export type BlockAccess = {
  status: AccessState;
  reason: string;
  cta_label: string;
  cta_target: { screen?: string; action_id?: string | null };
  entitlement_source?: string;
};

const targetForAccess = (access: BlockAccess) => {
  if (access.cta_target.screen === 'settings') return '/dashboard/profile?focus=subscription#subscription';
  return '/dashboard/growth-paths';
};

export const AccessPreview = ({ access, className }: { access: BlockAccess; className?: string }) => {
  if (access.status === 'available') return null;
  return (
    <div className={cn('rounded-2xl border border-amber-200/80 bg-amber-50/80 p-4', className)} role="note">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white text-amber-700 shadow-sm ring-1 ring-amber-200">
          <LockKeyhole className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-amber-950">Что откроется</p>
          <p className="mt-1 text-pretty text-sm leading-5 text-amber-900/75">{access.reason}</p>
          <Link
            to={targetForAccess(access)}
            className="mt-3 inline-flex min-h-10 items-center justify-center rounded-xl bg-slate-950 px-4 text-sm font-semibold text-white transition-[background-color,transform] duration-150 hover:bg-slate-800 active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-950 focus-visible:ring-offset-2"
          >
            {access.cta_label}
          </Link>
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
