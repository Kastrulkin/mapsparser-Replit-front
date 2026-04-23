import { useState, useEffect } from "react";
import { Heart } from "lucide-react";
import { useLanguage } from "@/i18n/LanguageContext";

const Footer = () => {
  const { t, language } = useLanguage();
  const isRu = language === "ru";
  const industries = t.footer.madeWithLoveIndustries ?? [isRu ? "индустрии красоты" : "the beauty industry"];
  const prefix = t.footer.madeWithLovePrefix ?? (isRu ? "Сделано с любовью для " : "Made with love for ");
  const [index, setIndex] = useState(0);
  const [isExiting, setIsExiting] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setIsExiting(true);
      setTimeout(() => {
        setIndex((i) => (i + 1) % industries.length);
        setIsExiting(false);
      }, 400);
    }, 2600);
    return () => clearInterval(interval);
  }, [industries.length]);

  const footerLinks = {
    company: [
      { name: t.footer.whoWeAre, href: '/about' },
      { name: t.footer.contacts, href: '/contact' },
      { name: t.footer.requisites ?? (isRu ? 'Реквизиты' : 'Requisites'), href: '/requisites' },
    ],
    materials: [
      { name: "Статьи", href: "/articles" },
      { name: "Документы", href: "/documents" },
      { name: "Кейсы", href: "/cases" },
    ],
  };

  return (
    <footer className="bg-card border-t border-border">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="flex flex-col md:flex-row justify-between items-start gap-8">
          <div className="max-w-md">
            <h3 className="text-2xl font-bold text-foreground mb-4">{t.footer.title}</h3>
            <p className="text-muted-foreground mb-6 max-w-md">
              {t.footer.description}
            </p>
            <div className="flex items-center text-sm text-muted-foreground">
              <Heart className="w-4 h-4 mr-1.5 text-primary animate-pulse flex-shrink-0" />
              <span className="flex items-baseline gap-0.5 min-h-[1.5em]">
                {prefix}
                <span
                  className="inline-block text-primary font-semibold transition-all duration-400 ease-out"
                  style={{
                    opacity: isExiting ? 0 : 1,
                    transform: isExiting ? "translateY(-8px)" : "translateY(0)",
                    filter: isExiting ? "blur(4px)" : "blur(0)",
                  }}
                >
                  {industries[index]}
                </span>
              </span>
            </div>
          </div>

          <div className="ml-auto grid gap-8 sm:grid-cols-2">
            <div>
              <h4 className="font-semibold text-foreground mb-4 md:text-right">{t.footer.company}</h4>
              <ul className="space-y-2 md:text-right">
                {footerLinks.company.map((link) => (
                  <li key={link.name}>
                    <a href={link.href} className="text-muted-foreground hover:text-foreground transition-colors">
                      {link.name}
                    </a>
                  </li>
                ))}
                <li>
                  <a href="mailto:info@local.pro" className="text-muted-foreground hover:text-foreground transition-colors">
                    info@local.pro
                  </a>
                </li>
              </ul>
            </div>

            <div>
              <h4 className="font-semibold text-foreground mb-4 md:text-right">Материалы</h4>
              <ul className="space-y-2 md:text-right">
                {footerLinks.materials.map((link) => (
                  <li key={link.name}>
                    <a href={link.href} className="text-muted-foreground hover:text-foreground transition-colors">
                      {link.name}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        <div className="mt-12 pt-8 border-t border-border">
          <div className="mt-6 text-center text-sm text-muted-foreground">
            {t.footer.copyright}
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
