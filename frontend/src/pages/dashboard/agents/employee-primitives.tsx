import { cn } from '@/lib/utils';
import { humanizeStatus, statusTone } from './model';
import { userFacingAgentTechText } from './normalization';

export const StatusBadge = ({ status }: { status: string }) => (
  <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1', statusTone[status] || 'bg-slate-50 text-slate-600 ring-slate-200')}>
    {userFacingAgentTechText(humanizeStatus(status))}
  </span>
);

export const AgentMiniMetric = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-lg bg-white px-3 py-2 ring-1 ring-current/10">
    <div className="text-[11px] font-medium opacity-70">{label}</div>
    <div className="mt-1 text-base font-semibold">{value}</div>
  </div>
);
