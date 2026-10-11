import { Link, useLocation, useOutletContext } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { workChatRoute, workNavigationCopy } from '@/lib/workNavigation';

export const WorkContextBridge = () => {
 const { currentBusinessId } = useOutletContext<{ currentBusinessId?: string | null }>();
 const location = useLocation(); const { language } = useLanguage(); const params = new URLSearchParams(location.search);
 const actionId = params.get('journey_action');
 const hasRecord = ['item_id','lead','lead_id','campaign_id','collaboration_id','run_id','draft_id','entry'].some(key => params.has(key));
 if (!currentBusinessId || actionId || !hasRecord || location.pathname === '/dashboard/operator') return null;
 return <div className="flex justify-end"><Button variant="outline" asChild><Link to={workChatRoute(location.pathname + location.search, currentBusinessId)}>{workNavigationCopy(language).discuss}</Link></Button></div>;
};
