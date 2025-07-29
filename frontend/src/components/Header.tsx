import { Button } from "./ui/button";
import { Menu, X } from "lucide-react";
import { useState, useEffect } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { supabase } from "../lib/supabase";
import { auth } from "../lib/auth";

const Header = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isAuth, setIsAuth] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    // Проверяем аутентификацию через Supabase Auth
    supabase.auth.getUser().then(({ data }) => {
      console.log('Supabase Auth check:', !!data.user);
      setIsAuth(!!data.user);
    });
    
    // Проверяем аутентификацию через нашу систему
    const currentUser = auth.getCurrentUser();
    console.log('Local Auth check:', !!currentUser);
    if (currentUser) {
      setIsAuth(true);
    }
    
    const { data: listener } = supabase.auth.onAuthStateChange((event, session) => {
      console.log('Auth state change:', event, !!session?.user);
      setIsAuth(!!session?.user);
    });
    return () => { listener?.subscription.unsubscribe(); };
  }, []);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    await auth.signOut();
    setIsAuth(false);
    navigate("/");
  };

  const navigation = [
    { name: 'ИИ Агенты', href: '/#agents' },
    { name: 'Кто мы?', href: '/about' },
    { name: 'Цены', href: '/#cta' },
  ];

  useEffect(() => {
    if (window.location.hash === "#agents") {
      const el = document.getElementById("agents");
      if (el) {
        el.scrollIntoView({ behavior: "smooth" });
      }
    }
  }, []);

  return (
    <header className="bg-card border-b border-border">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center py-4">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Link to="/" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} className="text-2xl font-bold text-foreground hover:text-primary transition-colors" style={{ textDecoration: 'none' }}>
                BeautyBot
              </Link>
            </div>
          </div>
          
          <nav className="hidden md:flex items-center space-x-14">
            {navigation.map((item) => (
              item.name === 'ИИ Агенты' ? (
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
              ) : item.name === 'Цены' ? (
                <Link
                  key={item.name}
                  to={{ pathname: "/", hash: "#cta" }}
                  className="text-muted-foreground hover:text-foreground transition-colors"
                  onClick={() => {}}
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
            {console.log('Header render - isAuth:', isAuth)}
            {!isAuth ? (
              <>
                <Link to="/login"><Button variant="ghost">Вход</Button></Link>
                <Link to={{ pathname: "/", hash: "#hero-form" }}>
                  <Button>Попробовать бесплатно</Button>
                </Link>
              </>
            ) : (
              <>
                <Link to="/dashboard"><Button variant="ghost">Личный кабинет</Button></Link>
                <Button variant="ghost" onClick={handleLogout}>Выход</Button>
              </>
            )}
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
          <div className="md:hidden">
            <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
              {navigation.map((item) => (
                item.name === 'ИИ Агенты' ? (
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
                ) : item.name === 'Цены' ? (
                  <Link
                    key={item.name}
                    to={{ pathname: "/", hash: "#cta" }}
                    className="block px-3 py-2 text-muted-foreground hover:text-foreground transition-colors"
                    onClick={() => {}}
                  >
                    {item.name}
                  </Link>
                ) : (
                  <a
                    key={item.name}
                    href={item.href}
                    className="block px-3 py-2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {item.name}
                  </a>
                )
              ))}
              <div className="pt-4 space-y-2">
                {!isAuth ? (
                  <>
                    <Link to="/login" className="w-full block">
                      <Button variant="ghost" className="w-full justify-start">Вход</Button>
                    </Link>
                    <Link to={{ pathname: "/", hash: "#hero-form" }} className="w-full block">
                      <Button className="w-full justify-start">Попробовать бесплатно</Button>
                    </Link>
                  </>
                ) : (
                  <>
                    <Link to="/dashboard" className="w-full block">
                      <Button variant="ghost" className="w-full justify-start">Личный кабинет</Button>
                    </Link>
                    <Button variant="ghost" className="w-full justify-start" onClick={handleLogout}>Выход</Button>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </header>
  );
};

export default Header;