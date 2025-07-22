import { Button } from "@/components/ui/button";
import { Heart, Mail, Phone, MapPin } from "lucide-react";

const Footer = () => {
  const footerLinks = {
    company: [
      { name: 'Кто мы?', href: '/about' },
      { name: 'Контакты', href: '/contact' },
    ],
  };

  return (
    <footer className="bg-card border-t border-border">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="flex flex-col md:flex-row justify-between items-start gap-8">
          <div className="max-w-md">
            <h3 className="text-2xl font-bold text-foreground mb-4">BeautyBot</h3>
            <p className="text-muted-foreground mb-6 max-w-md">
              ИИ-агенты для автоматизации салонов красоты. Увеличьте доходы и улучшите клиентский опыт с помощью умных технологий.
            </p>
            <div className="flex items-center text-sm text-muted-foreground">
              <Heart className="w-4 h-4 mr-1 text-primary" />
              Сделано с любовью для индустрии красоты
            </div>
          </div>

          <div className="ml-auto">
            <h4 className="font-semibold text-foreground mb-4 text-right">Компания</h4>
            <ul className="space-y-2 text-right">
              {footerLinks.company.map((link) => (
                <li key={link.name}>
                  <a href={link.href} className="text-muted-foreground hover:text-foreground transition-colors">
                    {link.name}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-12 pt-8 border-t border-border">
          <div className="mt-6 text-center text-sm text-muted-foreground">
            © 2024 BeautyBot. Все права защищены.
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;