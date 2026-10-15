import {
	BadgeDollarSign,
	BarChart3,
	Bot,
	Calendar,
	CircleEllipsis,
	DollarSign,
	FileText,
	Handshake,
	LayoutGrid,
	Map,
	Megaphone,
	Menu,
	MessageSquare,
	PanelLeftClose,
	PanelLeftOpen,
	Radar,
	Settings,
	Sparkles,
	TrendingUp,
	User,
	UsersRound,
	X,
} from 'lucide-react';
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import logo from '../assets/images/logo.png';
import { featureFlags } from '../config/featureFlags';
import { useLanguage } from '../i18n/LanguageContext.logic';
import { getDashboardNavigationCopy } from '../i18n/dashboardNavigationCopy';
import { getDashboardShellCopy } from '../i18n/dashboardShellCopy';
import { getDemoWorkspaceCopy } from '../i18n/demoWorkspaceCopy';
import { cn } from '../lib/utils';
import { workDestinations, workNavigationCopy } from '@/lib/workNavigation';
import { Button } from './ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from './ui/tooltip';

const influencerNavigationCopy = {
  ru: { label: 'Инфлюенсеры', hint: 'Подберите местных авторов, согласуйте условия и следите за размещениями.' },
  en: { label: 'Creators', hint: 'Find local creators, agree terms, and track placements.' },
  fr: { label: 'Créateurs', hint: 'Trouvez des créateurs locaux, convenez des conditions et suivez les placements.' },
  es: { label: 'Creadores', hint: 'Encuentra creadores locales, acuerda las condiciones y sigue las publicaciones.' },
  el: { label: 'Δημιουργοί', hint: 'Βρείτε τοπικούς δημιουργούς, συμφωνήστε τους όρους και παρακολουθήστε τις δημοσιεύσεις.' },
  de: { label: 'Creator', hint: 'Finden Sie lokale Creator, stimmen Sie Bedingungen ab und verfolgen Sie Platzierungen.' },
  th: { label: 'ครีเอเตอร์', hint: 'ค้นหาครีเอเตอร์ท้องถิ่น ตกลงเงื่อนไข และติดตามการเผยแพร่' },
  ar: { label: 'صناع المحتوى', hint: 'اعثر على صناع محتوى محليين، اتفق على الشروط وتابع النشر.' },
  ha: { label: 'Masu ƙirƙira', hint: 'Nemo masu ƙirƙira na yankinku, ku amince da sharudda kuma ku bi wallafe-wallafe.' },
  tr: { label: 'İçerik üreticileri', hint: 'Yerel içerik üreticilerini bulun, koşulları kararlaştırın ve yayınları takip edin.' },
};

interface DashboardSidebarProps {
  isMobile?: boolean;
  onClose?: () => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  webTrackingAvailable?: boolean;
}

export const DashboardSidebar: React.FC<DashboardSidebarProps> = ({
  isMobile = false,
  onClose,
  collapsed = false,
  onToggleCollapse,
  webTrackingAvailable = false,
}) => {
  const location = useLocation();
  const { t, language } = useLanguage();
  const demoCopy = getDemoWorkspaceCopy(language).sidebar;
  const navigationCopy = getDashboardNavigationCopy(language);
  const shellCopy = getDashboardShellCopy(language);
  const [isOpen, setIsOpen] = useState(false);

  const workCopy = workNavigationCopy(language);
  const icons: Record<string, typeof Calendar> = { today: Calendar, operator: Bot, maps: Map, content: FileText, partnerships: Handshake, influencers: UsersRound, upsells: BadgeDollarSign, automation: Sparkles, progress: TrendingUp, finance: DollarSign, profile: User, settings: Settings, more: CircleEllipsis };
  const menuItems = workDestinations.map(item => ({ ...item, label: workCopy.label(item.id), icon: icons[item.id] || LayoutGrid, tooltip: workCopy.label(item.id) }));

  const handleLinkClick = () => {
    if (isMobile) setIsOpen(false);
    if (isMobile && onClose) {
      onClose();
    }
  };

  const isActive = (path: string) => {
    if (path === '/dashboard/today') {
      return location.pathname === '/dashboard' || location.pathname === path;
    }
    if (path === '/dashboard/promotion') {
      return location.pathname === path || location.pathname.startsWith('/dashboard/promotion/');
    }
    return location.pathname === path || location.pathname.startsWith(path + '/');
  };

  const sidebarContent = (
    <div data-navigation="guided-v1" className={cn(
      "h-full flex flex-col border-r border-slate-200/70 transition-all duration-300",
      "bg-white/86 backdrop-blur-xl supports-[backdrop-filter]:bg-white/78",
      "shadow-[8px_0_32px_-20px_rgba(15,23,42,0.18)]"
    )}>
      {/* Logo Area */}
      <div className={cn("border-b border-slate-100", collapsed && !isMobile ? "px-3 py-5" : "p-6")}>
        <div className={cn("flex items-center gap-3", collapsed && !isMobile ? "justify-center" : "justify-between")}>
          <Link
            to="/dashboard/today"
            onClick={handleLinkClick}
            className={cn(
              "flex min-w-0 items-center gap-3 rounded-xl outline-none ring-blue-500/30 transition focus-visible:ring-2",
              collapsed && !isMobile ? "h-12 w-12 justify-center" : "overflow-hidden"
            )}
            aria-label="LocalOS"
          >
            {collapsed && !isMobile ? (
                <span className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
                  <span className="absolute inset-0 rounded-2xl bg-slate-900/5 blur-md" />
                  <img
                  src="/favicon.svg"
                  alt=""
                  aria-hidden="true"
                  className="relative z-10 h-8 w-8"
                />
              </span>
            ) : (
              <>
                <span className="relative flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
                  <span className="absolute inset-0 bg-slate-900/5 blur-md" />
                  <img
                    src={logo}
                    alt=""
                    aria-hidden="true"
                    className="relative z-10 h-11 w-11 object-cover object-top drop-shadow-sm transition-transform duration-300 hover:scale-105"
                  />
                </span>
                <span className="hidden truncate text-xl font-semibold tracking-tight text-slate-950 lg:block">
                  LocalOS
                </span>
              </>
            )}
          </Link>
          {!isMobile && onToggleCollapse ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className={cn("shrink-0", collapsed && "hidden")}
              onClick={onToggleCollapse}
              aria-label={collapsed ? navigationCopy.expand : navigationCopy.collapse}
            >
              {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
            </Button>
          ) : null}
        </div>
        {!isMobile && collapsed && onToggleCollapse ? (
          <div className="mt-3 flex justify-center">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={onToggleCollapse}
              aria-label={navigationCopy.expand}
            >
              <PanelLeftOpen className="h-4 w-4" />
            </Button>
          </div>
        ) : null}
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1.5 overflow-y-auto p-4 custom-scrollbar">
        {menuItems.map((item, index) => {
          const Icon = item.icon;
          const active = isActive(item.path);
          return (
            <div key={item.id}>
            {menuItems[index - 1]?.group !== item.group ? <p className={cn("px-3 pb-1 pt-4 text-xs font-medium text-slate-500", collapsed && !isMobile && "sr-only")}>{workCopy.groups[item.group]}</p> : null}
            <Tooltip>
              <TooltipTrigger asChild>
                <Link
                  to={item.path}
                  aria-label={item.label}
                  aria-current={active ? 'page' : undefined}
                  onClick={handleLinkClick}
                  data-tour-target={`nav-${item.id}`}
                  className={cn(
                    "group relative flex items-center gap-3 rounded-xl text-sm font-medium transition-all duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    collapsed && !isMobile ? "justify-center px-2 py-3 hover:translate-x-0" : "px-4 py-3",
                    active
                      ? "bg-slate-900 text-white shadow-sm"
                      : "text-slate-600 hover:bg-slate-100/90 hover:text-slate-950"
                  )}
                >
                  <div className={cn(
                    "p-2 rounded-lg transition-colors duration-300",
                    active ? "bg-white/14 text-white" : "bg-transparent text-slate-500 group-hover:bg-white group-hover:text-slate-700"
                  )}>
                    <Icon className="w-5 h-5" aria-hidden="true" />
                  </div>
                  <span className={cn("tracking-wide", collapsed && !isMobile && "hidden")}>{item.label}</span>

                  {active && (
                    <div className="absolute right-3 top-1/2 h-2.5 w-2.5 -translate-y-1/2 rounded-full bg-white/90" />
                  )}
                </Link>
              </TooltipTrigger>
              <TooltipContent side="right" className="max-w-xs text-xs leading-5">
                {item.tooltip}
              </TooltipContent>
            </Tooltip>
            </div>
          );
        })}
      </nav>

      <div className={cn(
        "m-4 rounded-2xl border border-slate-200 bg-slate-50/90 p-4",
        collapsed && !isMobile && "mx-3 px-2 py-3"
      )}>
        <div className="mb-2 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-slate-700" />
          <span className={cn("text-xs font-semibold uppercase tracking-[0.16em] text-slate-700", collapsed && !isMobile && "hidden")}>LocalOS</span>
        </div>
        <p className={cn("text-xs leading-relaxed text-slate-500", collapsed && !isMobile && "hidden")}>
          {t.dashboard.sidebar.greeting}
        </p>
      </div>
    </div>
  );

  if (isMobile) {
    return <Sheet open={isOpen} onOpenChange={setIsOpen}><SheetTrigger asChild><Button data-tour-target="mobile-menu" variant="ghost" className="flex min-h-14 w-16 flex-col gap-1 rounded-none p-1 text-xs md:hidden" aria-label={workCopy.menu}><Menu className="h-5 w-5" aria-hidden="true" /><span>{workCopy.menu}</span></Button></SheetTrigger><SheetContent side="left" className="w-72 p-0" closeLabel={({ru:"Закрыть меню",en:"Close menu",fr:"Fermer le menu",es:"Cerrar menú",el:"Κλείσιμο μενού",de:"Menü schließen",th:"ปิดเมนู",ar:"إغلاق القائمة",ha:"Rufe menu",tr:"Menüyü kapat",hy:"Փակել ընտրացանկը",kk:"Мәзірді жабу"})[language]}><SheetTitle className="sr-only">{workCopy.menu}</SheetTitle><SheetDescription className="sr-only">{Object.values(workCopy.groups).join(" · ")}</SheetDescription>{sidebarContent}</SheetContent></Sheet>;
  }

  return (
    <div className={cn("hidden md:flex md:flex-col md:fixed md:inset-y-0 md:left-0 z-30", collapsed ? "md:w-24" : "md:w-72")}>
      {sidebarContent}
    </div>
  );
};
