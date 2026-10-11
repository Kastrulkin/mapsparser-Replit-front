import { Link, useOutletContext } from 'react-router-dom';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { workCoherenceCopy } from '@/i18n/workCoherenceCopy';
import { workNavigationCopy } from '@/lib/workNavigation';
import { featureFlags } from '@/config/featureFlags';
import { Route, MessageSquare, Radar, BarChart3, ArrowRight } from 'lucide-react';

export const MorePage = () => {
 const { language } = useLanguage(); const copy = workNavigationCopy(language); const extra = workCoherenceCopy(language);
 const { currentBusiness } = useOutletContext<{ currentBusiness?: { web_tracking_available?: boolean } | null }>();
 const items = [
  { path: '/dashboard/growth-paths', icon: Route, tour: 'nav-growth-paths' },
  { path: '/dashboard/work-journal', icon: MessageSquare, tour: 'nav-work-journal' },
  { path: '/dashboard/chats', icon: MessageSquare, tour: 'nav-chats' },
  { path: '/dashboard/telegram-radar', icon: Radar, tour: 'nav-telegram-radar' },
  ...(featureFlags.webTracking && currentBusiness?.web_tracking_available ? [{ path: '/dashboard/web-analytics', icon: BarChart3, tour: 'nav-web-analytics' }] : []),
 ];
 return <div className="space-y-6 pb-10"><header><h1 className="text-3xl font-semibold">{copy.label('more')}</h1><p className="mt-2 text-sm text-muted-foreground">{extra.moreIntro}</p></header><div className="divide-y rounded-xl border bg-card">{items.map((item, index) => <Link key={item.path} to={item.path} data-tour-target={item.tour} className="flex min-h-16 items-center gap-4 p-4 hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><item.icon className="h-5 w-5 shrink-0" aria-hidden="true" /><span className="min-w-0 flex-1 text-sm font-medium">{extra.utilities[index]}</span><ArrowRight className="h-4 w-4 shrink-0" aria-hidden="true" /></Link>)}</div></div>;
};
