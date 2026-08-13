import { Button } from "./ui/button";
import { ChevronDown, LogIn, Menu, X } from "lucide-react";
import { useState, useEffect } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { newAuth } from "../lib/auth_new";
import { Language, useLanguage } from "../i18n/LanguageContext";
import { LanguageSwitcher } from "./LanguageSwitcher";
import logo from "@/assets/images/logo.png"; // Импортируем логотип
import { contentCopy } from "@/content/contentCopy";

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
  };

  const navigation = [
    { name: publicNavigationCopy[language].how, href: '/#agents' },
    { name: publicNavigationCopy[language].about, href: '/about' },
    { name: t.header.prices, href: '/about#pricing' },
  ];

  const materialsCopy = contentCopy[language];
  const materialsNavigation = [
    { ...materialsCopy.navigation.articles, href: "/articles" },
    { ...materialsCopy.navigation.documents, href: "/documents" },
    { ...materialsCopy.navigation.cases, href: "/cases" },
    { ...materialsCopy.navigation.documentation, href: "/docs" },
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
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex min-h-[4.5rem] justify-between items-center py-2.5">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Link to="/" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} className="flex min-h-11 items-center rounded-lg pr-2 transition-opacity hover:opacity-75" style={{ textDecoration: 'none' }}>
                <img
                  src={logo}
                  alt="Local OS"
                  className="h-10 w-auto"
                />
              </Link>
            </div>
          </div>

          <nav className="hidden items-center gap-8 lg:flex">
            {navigation.map((item) => (
              item.href === '/#agents' ? (
                <Link
                  key={item.name}
                  to={{ pathname: "/", hash: "#agents" }}
                  className="inline-flex min-h-11 items-center text-sm font-semibold text-slate-600 transition-colors hover:text-slate-950"
                  onClick={() => {
                    // Ничего не делаем, обработка теперь на главной через useEffect
                  }}
                >
                  {item.name}
                </Link>
              ) : item.href === '/about#pricing' ? (
                <Link
                  key={item.name}
                  to={{ pathname: "/about", hash: "#pricing" }}
                  className="inline-flex min-h-11 items-center text-sm font-semibold text-slate-600 transition-colors hover:text-slate-950"
                  onClick={(e) => {
                    // Если уже на странице /about, прокручиваем сразу
                    if (location.pathname === '/about') {
                      e.preventDefault();
                      const el = document.getElementById("pricing");
                      if (el) {
                        el.scrollIntoView({ behavior: "smooth" });
                        // Обновляем URL без перезагрузки
                        window.history.pushState(null, '', '/about#pricing');
                      }
                    }
                  }}
                >
                  {item.name}
                </Link>
              ) : (
                <a
                  key={item.name}
                  href={item.href}
                  className="inline-flex min-h-11 items-center text-sm font-semibold text-slate-600 transition-colors hover:text-slate-950"
                >
                  {item.name}
                </a>
              )
            ))}
            <div className="group relative">
              <button className="flex min-h-11 items-center gap-1 text-sm font-semibold text-slate-600 transition-colors hover:text-slate-950" type="button">
                {materialsCopy.materials}
                <ChevronDown className="h-4 w-4 transition-transform group-hover:rotate-180" />
              </button>
              <div className="invisible absolute left-1/2 top-full w-72 -translate-x-1/2 pt-3 opacity-0 transition-[opacity,visibility] group-hover:visible group-hover:opacity-100">
                <div className="rounded-2xl bg-white p-2 shadow-[0_0_0_1px_rgba(0,0,0,0.06),0_18px_45px_rgba(15,23,42,0.12)]">
                  {materialsNavigation.map((item) => (
                    <Link
                      className="block rounded-xl px-4 py-3 transition-colors hover:bg-orange-50"
                      key={item.href}
                      to={item.href}
                    >
                      <span className="block font-semibold text-gray-950">{item.name}</span>
                      <span className="mt-1 block text-sm text-muted-foreground">{item.description}</span>
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          </nav>

          <div className="hidden items-center gap-3 lg:flex">
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
            <Button asChild className="min-h-10 rounded-xl px-4 shadow-[0_8px_22px_rgba(249,115,22,0.18)] transition-[box-shadow,scale] active:scale-[0.96]">
              <Link to="/login">{t.header.tryFree}</Link>
            </Button>
          </div>

          <div className="lg:hidden">
            <Button
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
          <div className="absolute left-0 right-0 border-b border-black/5 bg-[#f7f7f5] shadow-[0_18px_45px_rgba(15,23,42,0.12)] lg:hidden">
            <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
              {navigation.map((item) => (
                item.href === '/#agents' ? (
                  <Link
                    key={item.name}
                    to={{ pathname: "/", hash: "#agents" }}
                    className="block px-3 py-2 text-muted-foreground hover:text-foreground transition-colors"
                    onClick={() => {
                      setIsMenuOpen(false);
                    }}
                  >
                    {item.name}
                  </Link>
                ) : item.href === '/about#pricing' ? (
                  <Link
                    key={item.name}
                    to={{ pathname: "/about", hash: "#pricing" }}
                    className="block px-3 py-2 text-muted-foreground hover:text-foreground transition-colors"
                    onClick={(e) => {
                      // Если уже на странице /about, прокручиваем сразу
                      if (location.pathname === '/about') {
                        e.preventDefault();
                        const el = document.getElementById("pricing");
                        if (el) {
                          el.scrollIntoView({ behavior: "smooth" });
                          // Обновляем URL без перезагрузки
                          window.history.pushState(null, '', '/about#pricing');
                        }
                      }
                      setIsMenuOpen(false);
                    }}
                  >
                    {item.name}
                  </Link>
                ) : (
                  <a
                    key={item.name}
                    href={item.href}
                    className="block px-3 py-2 text-muted-foreground hover:text-foreground transition-colors"
                    onClick={() => setIsMenuOpen(false)}
                  >
                    {item.name}
                  </a>
                )
              ))}
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
                <Button asChild className="mx-3 w-[calc(100%-1.5rem)] justify-start btn-iridescent">
                  <Link to="/login" onClick={() => setIsMenuOpen(false)}>{t.header.tryFree}</Link>
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
