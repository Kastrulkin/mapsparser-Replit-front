import { Button } from "./ui/button";
import { Menu, X } from "lucide-react";
import { useState, useEffect } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { newAuth } from "../lib/auth_new";
import logo from "../assets/images/logo.png"; // Импортируем логотип

const Header = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isAuth, setIsAuth] = useState(false);
  const navigate = useNavigate();

  // ЛК отключён: всегда скрываем элементы аутентификации
  useEffect(() => {
    setIsAuth(false);
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
              <Link to="/" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} className="flex items-center hover:opacity-80 transition-opacity" style={{ textDecoration: 'none' }}>
                <img 
                  src={logo} 
                  alt="BeautyBot Logo" 
                  className="h-32 w-auto"
                  style={{ maxHeight: '128px' }}
                />
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
            <Link to={{ pathname: "/", hash: "#hero-form" }}>
              <Button>Попробовать бесплатно</Button>
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
                <Link to={{ pathname: "/", hash: "#hero-form" }} className="w-full block">
                  <Button className="w-full justify-start">Попробовать бесплатно</Button>
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