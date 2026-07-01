import { useState, useEffect } from "react";
import { Heart } from "lucide-react";
import { Language, useLanguage } from "@/i18n/LanguageContext";

const footerIndustryFallbacks: Record<Language, string[]> = {
  ru: [
    "индустрии красоты",
    "медицинских центров",
    "фитнес-студий",
    "кафе и ресторанов",
    "автосервисов",
    "магазинов",
    "школ и курсов",
    "сервисных компаний",
  ],
  en: [
    "the beauty industry",
    "medical centers",
    "fitness studios",
    "cafes and restaurants",
    "auto services",
    "local shops",
    "schools and courses",
    "service businesses",
  ],
  fr: ["salons de beauté", "artisans", "ateliers", "magasins", "écoles", "garages", "cliniques", "cafés", "stations-service"],
  es: ["salones de belleza", "maestros", "talleres", "tiendas", "escuelas", "talleres de autos", "clínicas", "cafeterías", "gasolineras"],
  el: ["κομμωτήρια", "τεχνίτες", "εργαστήρια", "καταστήματα", "σχολεία", "συνεργεία αυτοκινήτων", "κλινικές", "καφετέριες", "πρατήρια καυσίμων"],
  de: ["Friseursalons", "Handwerker", "Werkstätten", "Geschäfte", "Schulen", "Autowerkstätten", "Kliniken", "Cafés", "Tankstellen"],
  th: ["ร้านเสริมสวย", "ช่างฝีมือ", "เวิร์กช็อป", "ร้านค้า", "โรงเรียน", "อู่ซ่อมรถ", "คลินิก", "ร้านกาแฟ", "ปั๊มน้ำมัน"],
  ar: ["صالونات التجميل", "الحرفيين", "الورش", "المتاجر", "المدارس", "خدمات السيارات", "العيادات", "المقاهي", "محطات الوقود"],
  ha: ["salons na kyau", "masu sana'a", "aikin hannu", "shaguna", "makarantu", "tallace-tallace mota", "asibiti", "gidajen abinci", "tashoshin man fetur"],
  tr: [
    "güzellik sektörü",
    "sağlık merkezleri",
    "fitness stüdyoları",
    "kafe ve restoranlar",
    "oto servisleri",
    "yerel mağazalar",
    "okullar ve kurslar",
    "hizmet işletmeleri",
  ],
};

const Footer = () => {
  const { t, language } = useLanguage();
  const isRu = language === "ru";
  const translatedIndustries = t.footer.madeWithLoveIndustries;
  const industries = Array.isArray(translatedIndustries) && translatedIndustries.length > 1
    ? translatedIndustries
    : footerIndustryFallbacks[language];
  const prefix = t.footer.madeWithLovePrefix ?? (isRu ? "Сделано с любовью для " : "Made with love for ");
  const [index, setIndex] = useState(0);
  const [isExiting, setIsExiting] = useState(false);

  useEffect(() => {
    setIndex(0);
    setIsExiting(false);
  }, [industries.length]);

  useEffect(() => {
    if (industries.length < 2) {
      setIsExiting(false);
      return;
    }

    let timeoutId: ReturnType<typeof setTimeout>;
    const interval = setInterval(() => {
      setIsExiting(true);
      timeoutId = setTimeout(() => {
        setIndex((i) => (i + 1) % industries.length);
        setIsExiting(false);
      }, 400);
    }, 2600);
    return () => {
      clearInterval(interval);
      clearTimeout(timeoutId);
    };
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
