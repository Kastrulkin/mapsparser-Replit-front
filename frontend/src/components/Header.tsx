import { Button } from "./ui/button";
import { Menu, X, LogIn } from "lucide-react";
import { useState, useEffect } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { newAuth } from "../lib/auth_new";
import { useLanguage } from "../i18n/LanguageContext";
import { LanguageSwitcher } from "./LanguageSwitcher";
import logo from "@/assets/images/logo.png"; // Импортируем логотип

const Header = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isAuth, setIsAuth] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useLanguage();

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

  const navigation = [
    { name: t.header.whatWeDo, href: '/#agents' },
    { name: t.header.whoWeAre, href: '/about' },
    { name: t.header.prices, href: '/about#pricing' },
  ];

  // Не показываем Header на страницах кабинета (/dashboard...)
  if (location.pathname.startsWith('/dashboard')) {
    return null;
  }

  return (
    <header
      className={`sticky top-0 z-50 transition-all duration-300 ${isScrolled
        ? "bg-background/80 backdrop-blur-md border-b border-border shadow-sm"
        : "bg-transparent border-transparent"
        }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center py-4">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Link to="/" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} className="flex items-center hover:opacity-80 transition-opacity" style={{ textDecoration: 'none' }}>
                <img
                  src={logo}
                  alt="Local OS"
                  className="h-12 w-auto"
                />
              </Link>
            </div>
          </div>

          <nav className="hidden md:flex items-center space-x-14">
            {navigation.map((item) => (
              item.href === '/#agents' ? (
                <Link
                  key={item.name}
                  to={{ pathname: "/", hash: "#agents" }}
                  className="text-muted-foreground hover:text-foreground transition-colors"
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
                  className="text-muted-foreground hover:text-foreground transition-colors"
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
                  className="text-muted-foreground hover:text-foreground transition-colors"
                >
                  {item.name}
                </a>
              )
            ))}
          </nav>

          <div className="hidden md:flex items-center space-x-4">
            <LanguageSwitcher />
            <Link to="/login">
              <Button
                variant="outline"
                size="sm"
                className="flex items-center gap-2"
              >
                <LogIn className="w-4 h-4" />
                <span>{t.header.login}</span>
              </Button>
            </Link>
            <Link to={{ pathname: "/", hash: "#hero-form" }}>
              <Button className="btn-iridescent">{t.header.tryFree}</Button>
            </Link>
          </div>

          <div className="md:hidden">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsMenuOpen(!isMenuOpen)}
            >
              {isMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </Button>
          </div>
        </div>

        {isMenuOpen && (
          <div className="md:hidden bg-background border-b border-border absolute left-0 right-0 shadow-lg">
            <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
              {navigation.map((item) => (
                item.href === '/#agents' ? (
                  <Link
                    key={item.name}
                    to={{ pathname: "/", hash: "#agents" }}
                    className="block px-3 py-2 text-muted-foreground hover:text-foreground transition-colors"
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
              <div className="pt-4 space-y-2 pb-4">
                <div className="px-3 py-2">
                  <LanguageSwitcher />
                </div>
                <Link to="/login" className="w-full block mx-3">
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-start"
                  >
                    <LogIn className="w-4 h-4 mr-2" />
                    {t.header.login}
                  </Button>
                </Link>
                <Link to={{ pathname: "/", hash: "#hero-form" }} className="w-full block">
                  <Button className="w-full justify-start mx-3 btn-iridescent">{t.header.tryFree}</Button>
                </Link>
              </div>
            </div>
          </div>
        )}
      </div>
    </header>
  );
};

export default Header;