import logo from "@/assets/images/logo.png"; // Импортируем логотип
import { contentCopy } from "@/content/contentCopy";
import { ChevronDown, LogIn, Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Language, useLanguage } from '../i18n/LanguageContext.logic';
import { newAuth } from "../lib/auth_new";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { Button } from "./ui/button";
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from './ui/dropdown-menu';
import { promotionContent, promotionLinkSearch, promotionContextSearch, readPromotionDirection } from '@/content/promotionContent';

const Header = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isAuth, setIsAuth] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { t, language } = useLanguage();

  // ЛК отключён: всегда скрываем элементы аутентификации
  // Скрываем Header на странице Dashboard (там свой хедер)
  useEffect(() => {
    setIsAuth(false);
  }, []);

  useEffect(() => {
    if (window.location.hash === "#agents") {
      const el = document.getElementById("agents");
      if (el) {
        el.scrollIntoView({ behavior: "smooth" });
      }
    }
  }, []);

  useEffect(() => {
    const desktop = window.matchMedia('(min-width: 640px)');
    const closeMobileMenu = () => setIsMenuOpen(false);
    desktop.addEventListener('change', closeMobileMenu);
    return () => desktop.removeEventListener('change', closeMobileMenu);
  }, []);

  // Handle scroll effect
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 10);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleLogout = async () => {
    try {
      await newAuth.signOut();
      setIsAuth(false);
      navigate("/");
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  const publicNavigationCopy: Record<Language, { how: string; about: string }> = {
    ru: { how: 'Как работает LocalOS', about: 'О LocalOS' },
    en: { how: 'How LocalOS works', about: 'About LocalOS' },
    fr: { how: 'Comment fonctionne LocalOS', about: 'À propos de LocalOS' },
    es: { how: 'Cómo funciona LocalOS', about: 'Sobre LocalOS' },
    el: { how: 'Πώς λειτουργεί το LocalOS', about: 'Σχετικά με το LocalOS' },
    de: { how: 'So funktioniert LocalOS', about: 'Über LocalOS' },
    th: { how: 'LocalOS ทำงานอย่างไร', about: 'เกี่ยวกับ LocalOS' },
    ar: { how: 'كيف يعمل LocalOS', about: 'عن LocalOS' },
    ha: { how: 'Yadda LocalOS ke aiki', about: 'Game da LocalOS' },
    tr: { how: 'LocalOS nasıl çalışır', about: 'LocalOS hakkında' },
    hy: { how: "Ինչպես է աշխատում LocalOS-ը", about: "LocalOS-ի մասին" },
    kk: { how: "LocalOS қалай жұмыс істейді", about: "LocalOS туралы" },
  };

  const promotion = promotionContent(language !== 'ru');
  const directions = Object.values(promotion).filter((page) => page.key !== 'home');
  const currentDirection = directions.find((page) => page.path === location.pathname)?.key;
  const selectedDirection = currentDirection || readPromotionDirection(location.search);
  const context = promotionContextSearch(location.search, selectedDirection);
  const directionLabel = language === 'ru' ? 'Направления' : 'Directions';
  const navigation = [
    { name: directionLabel, href: '#directions' },
    { name: language === 'ru' ? 'Как работаем' : 'How we work', href: '/#how-it-works' },
    { name: language === 'ru' ? 'Кейсы' : 'Cases', href: '/cases' + promotionLinkSearch(location.search) },
    { name: language === 'ru' ? 'Тарифы' : 'Pricing', href: '/pricing' + context },
    { name: language === 'ru' ? 'Вопросы' : 'Questions', href: '/faq' + context },
  ];

  const materialsCopy = contentCopy[language];
  const materialsNavigation = [
    { name: publicNavigationCopy[language].about, description: language === 'ru' ? 'Команда и история LocalOS' : 'The LocalOS team and story', href: '/about' },
    { ...materialsCopy.navigation.articles, href: "/articles" },
    { ...materialsCopy.navigation.documents, href: "/documents" },
    { ...materialsCopy.navigation.cases, href: "/cases" },
    { ...materialsCopy.navigation.documentation, href: "/docs" },
    { name: language === 'ru' ? 'Контакты' : 'Contact', description: language === 'ru' ? 'Связаться с командой' : 'Contact the team', href: '/contact' },
  ];

  // Не показываем Header на страницах кабинета (/dashboard...)
  if (location.pathname.startsWith('/dashboard')) {
    return null;
  }

  return (
    <header
      className={`sticky top-0 z-50 border-b backdrop-blur-xl transition-[background-color,border-color,box-shadow] duration-200 ${isScrolled
        ? "border-black/5 bg-[#f7f7f5]/92 shadow-[0_8px_24px_rgba(15,23,42,0.05)]"
        : "border-transparent bg-[#f7f7f5]/72"
        }`}
    >
      <svg width="0" height="0" className="absolute pointer-events-none" aria-hidden="true" focusable="false">
        <defs>
          <filter id="public-logo-clear-background" colorInterpolationFilters="sRGB">
            <feColorMatrix type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  -1 -1 -1 0 3" />
            <feComponentTransfer><feFuncA type="linear" slope="1.2" intercept="-0.12" /></feComponentTransfer>
          </filter>
        </defs>
      </svg>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex min-h-[4.5rem] flex-wrap justify-between items-center py-2.5">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Link to={`/${promotionLinkSearch(location.search)}`} onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} className="flex min-h-11 items-center rounded-lg pr-2 transition-opacity hover:opacity-75" style={{ textDecoration: 'none' }}>
                <span className="public-logo-crop"><img
                  src={logo}
                  alt="Local OS"
                  className="public-logo-image"
                /></span>
              </Link>
            </div>
          </div>

          <nav aria-label={language === 'ru' ? 'Основная навигация' : 'Main navigation'} className="order-3 mt-2 hidden w-full flex-wrap items-center justify-center gap-x-4 gap-y-1 border-t border-border pt-2 sm:flex xl:order-none xl:mt-0 xl:w-auto xl:gap-7 xl:border-0 xl:pt-0">
            {navigation.map((item) => item.href === '#directions' ? (
              <DropdownMenu key={item.href}>
                <DropdownMenuTrigger aria-current={currentDirection ? 'true' : undefined} className={`inline-flex min-h-11 items-center gap-1 text-sm font-semibold ${currentDirection ? 'text-primary' : 'text-slate-600'} hover:text-slate-950`}>{directionLabel}<ChevronDown size={14} aria-hidden="true" /></DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-64 rounded-xl p-2">{directions.map((page) => <DropdownMenuItem key={page.key} asChild><Link className={`min-h-11 ${page.key === currentDirection ? 'bg-secondary font-semibold' : ''}`} aria-current={page.key === currentDirection ? 'page' : undefined} to={page.path + promotionLinkSearch(location.search)}>{page.label}</Link></DropdownMenuItem>)}</DropdownMenuContent>
              </DropdownMenu>
            ) : <Link key={item.href} to={item.href} aria-current={location.pathname === item.href.split('?')[0] ? 'page' : undefined} className={`inline-flex min-h-11 items-center text-sm font-semibold transition-colors hover:text-slate-950 ${location.pathname === item.href.split('?')[0] ? 'text-primary underline underline-offset-8' : 'text-slate-600'}`}>{item.name}</Link>)}
            <DropdownMenu>
              <DropdownMenuTrigger className="flex min-h-11 items-center gap-1 text-sm font-semibold text-slate-600 hover:text-slate-950">{materialsCopy.materials}<ChevronDown size={14} aria-hidden="true" /></DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-72 rounded-xl p-2">{materialsNavigation.map((item) => <DropdownMenuItem key={item.href} asChild><Link className="block px-4 py-3" to={item.href}><span className="block font-semibold">{item.name}</span><span className="mt-1 block text-xs text-muted-foreground">{item.description}</span></Link></DropdownMenuItem>)}</DropdownMenuContent>
            </DropdownMenu>
          </nav>

          <div className="hidden items-center gap-3 sm:flex">
            <LanguageSwitcher />
            <Button
              asChild
              variant="outline"
              size="sm"
              className="flex min-h-10 items-center gap-2 rounded-xl bg-white/60 transition-[background-color,scale] active:scale-[0.96]"
            >
              <Link to="/login">
                <LogIn className="w-4 h-4" />
                <span>{t.header.login}</span>
              </Link>
            </Button>
            <Button asChild variant="outline" className="min-h-10 rounded-xl px-4">
              <a href="/demo" rel="noopener noreferrer" target="_blank">{language === 'ru' ? 'Посмотреть демо' : 'View demo'}</a>
            </Button>
          </div>

          <div className="sm:hidden">
            <Button
              aria-expanded={isMenuOpen}
              aria-controls="public-mobile-menu"
              aria-label={isMenuOpen ? (language === 'ru' ? 'Закрыть меню' : 'Close menu') : (language === 'ru' ? 'Открыть меню' : 'Open menu')}
              variant="ghost"
              size="icon"
              className="min-h-11 min-w-11 rounded-xl transition-[background-color,scale] active:scale-[0.96]"
              onClick={() => setIsMenuOpen(!isMenuOpen)}
            >
              {isMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </Button>
          </div>
        </div>

        {isMenuOpen && (
          <div id="public-mobile-menu" className="absolute left-0 right-0 max-h-[calc(100dvh-4.5rem)] overflow-y-auto border-b border-black/5 bg-[#f7f7f5] shadow-[0_18px_45px_rgba(15,23,42,0.12)] sm:hidden">
            <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
              {navigation.map((item) => item.href === '#directions' ? (
                <details key={item.href} className="px-3"><summary className="flex min-h-11 cursor-pointer items-center gap-2 text-muted-foreground">{directionLabel}<ChevronDown size={14} aria-hidden="true" /></summary><div className="border-s border-border ps-3">{directions.map((page) => <Link key={page.key} className={`flex min-h-11 items-center text-sm ${page.key === currentDirection ? 'font-semibold text-primary underline underline-offset-4' : 'text-foreground'}`} aria-current={page.key === currentDirection ? 'page' : undefined} to={page.path + promotionLinkSearch(location.search)} onClick={() => setIsMenuOpen(false)}>{page.label}</Link>)}</div></details>
              ) : <Link key={item.href} to={item.href} aria-current={location.pathname === item.href.split('?')[0] ? 'page' : undefined} className="flex min-h-11 items-center px-3 text-muted-foreground hover:text-foreground" onClick={() => setIsMenuOpen(false)}>{item.name}</Link>)}
              <div className="border-t border-border pt-3">
                <div className="px-3 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  {materialsCopy.materials}
                </div>
                {materialsNavigation.map((item) => (
                  <Link
                    className="block px-3 py-2 text-muted-foreground transition-colors hover:text-foreground"
                    key={item.href}
                    onClick={() => setIsMenuOpen(false)}
                    to={item.href}
                  >
                    {item.name}
                  </Link>
                ))}
              </div>
              <div className="pt-4 space-y-2 pb-4">
                <div className="px-3 py-2">
                  <LanguageSwitcher />
                </div>
                <Button
                  asChild
                  variant="outline"
                  size="sm"
                  className="mx-3 w-[calc(100%-1.5rem)] justify-start"
                >
                  <Link to="/login" onClick={() => setIsMenuOpen(false)}>
                    <LogIn className="w-4 h-4 mr-2" />
                    {t.header.login}
                  </Link>
                </Button>
                <Button asChild variant="outline" className="mx-3 w-[calc(100%-1.5rem)] justify-start">
                  <a href="/demo" onClick={() => setIsMenuOpen(false)} rel="noopener noreferrer" target="_blank">{language === 'ru' ? 'Посмотреть демо' : 'View demo'}</a>
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </header>
  );
};

export default Header;
