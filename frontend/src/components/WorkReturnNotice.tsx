import { Link, useLocation } from 'react-router-dom';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { safeWorkReturn, workNavigationCopy } from '@/lib/workNavigation';
import { Button } from '@/components/ui/button';

export const WorkReturnNotice = () => {
 const location = useLocation(); const { language } = useLanguage();
 const target = safeWorkReturn(new URLSearchParams(location.search).get('return_to'));
 if (!target || target === location.pathname + location.search) return null;
 return <div className="mb-4"><Button variant="outline" asChild><Link to={target}>{workNavigationCopy(language).back}</Link></Button></div>;
};
