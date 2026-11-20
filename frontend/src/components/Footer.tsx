import { useLocation } from 'react-router-dom';
import { promotionContent, promotionContextSearch, readPromotionDirection } from '@/content/promotionContent';
import { contentCopy } from "@/content/contentCopy";
import { Language, useLanguage } from '@/i18n/LanguageContext.logic';

const Footer = () => {
  const { t, language } = useLanguage();
  const isRu = language === "ru";
  const location = useLocation();
  const direction = Object.values(promotionContent()).find((page) => page.path === location.pathname)?.key || readPromotionDirection(location.search);
  const context = promotionContextSearch(location.search, direction);
  const descriptions: Record<Language, string> = {
    ru: "LocalOS помогает продвигать бизнес на Картах, работать с отзывами, находить блогеров и партнёров.",
    en: "LocalOS helps you manage map listings and reviews, find local creators and arrange business partnerships.",
    fr: "LocalOS prend en charge le travail récurrent lié à l'acquisition de clients, à la réputation, aux services et au suivi de l'activité.",
    es: "LocalOS se encarga del trabajo recurrente de captación de clientes, reputación, servicios y control del negocio.",
    el: "Το LocalOS αναλαμβάνει τις επαναλαμβανόμενες εργασίες για πελάτες, φήμη, υπηρεσίες και έλεγχο της επιχείρησης.",
    de: "LocalOS übernimmt wiederkehrende Aufgaben rund um Kundengewinnung, Reputation, Leistungen und Unternehmenssteuerung.",
    th: "LocalOS รับช่วงงานประจำด้านการหาลูกค้า ชื่อเสียง บริการ และการควบคุมธุรกิจ",
    ar: "يتولى LocalOS العمل المتكرر في استقطاب العملاء والسمعة والخدمات ومتابعة العمل.",
    ha: "LocalOS yana gudanar da ayyukan da ake maimaitawa na samo kwastomomi, suna, ayyuka da kula da kasuwanci.",
    tr: "LocalOS müşteri kazanımı, itibar, hizmetler ve işletme kontrolündeki tekrarlanan işleri üstlenir.",
    hy: "LocalOS-ն իրականացնում է հաճախորդի ձեռքբերման, հեղինակության, ծառայությունների և բիզնեսի վերահսկման հետ կապված պարբերական աշխատանքը:",
    kk: "LocalOS тұтынушыларды сатып алу, бедел, қызметтер және бизнесті бақылаудың тұрақты жұмысын қамтамасыз етеді.",
  };
  const aboutLabels: Record<Language, string> = {
    ru: "О LocalOS",
    en: "About LocalOS",
    fr: "À propos de LocalOS",
    es: "Sobre LocalOS",
    el: "Σχετικά με το LocalOS",
    de: "Über LocalOS",
    th: "เกี่ยวกับ LocalOS",
    ar: "عن LocalOS",
    ha: "Game da LocalOS",
    tr: "LocalOS hakkında",
    hy: "LocalOS-ի մասին",
    kk: "LocalOS туралы",
  };

  const footerLinks = {
    company: [
      { name: isRu ? 'Тарифы' : 'Pricing', href: '/pricing' + context },
      { name: isRu ? 'Вопросы' : 'Questions', href: '/faq' + context },
      { name: aboutLabels[language], href: '/about' },
      { name: t.footer.contacts, href: '/contact' },
      ...(isRu ? [{ name: t.footer.requisites ?? 'Реквизиты', href: '/requisites' }] : []),
    ],
    materials: [
      { name: contentCopy[language].navigation.articles.name, href: "/articles" },
      { name: contentCopy[language].navigation.documents.name, href: "/documents" },
      { name: contentCopy[language].navigation.cases.name, href: "/cases" },
    ],
  };

  return (
    <footer className="border-t border-white/[0.08] bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8 lg:py-12">
        <div className="flex flex-col md:flex-row justify-between items-start gap-8">
          <div className="max-w-md">
            <h3 className="mb-4 text-2xl font-bold text-white">{t.footer.title}</h3>
            <p className="mb-2 max-w-md text-pretty leading-7 text-slate-400">
              {descriptions[language]}
            </p>

          </div>

          <div className="grid w-full grid-cols-2 gap-6 md:ml-auto md:w-auto md:gap-10">
            <div>
              <h4 className="mb-4 font-semibold text-white text-left">{t.footer.company}</h4>
              <ul className="space-y-1 text-left">
                {footerLinks.company.map((link) => (
                  <li key={link.name}>
                    <a href={link.href} className="inline-flex min-h-10 items-center text-slate-400 transition-colors hover:text-white">
                      {link.name}
                    </a>
                  </li>
                ))}
                <li>
                  <a href="mailto:info@localos.pro" className="inline-flex min-h-10 items-center text-slate-400 transition-colors hover:text-white">
                    info@localos.pro
                  </a>
                </li>
              </ul>
            </div>

            <div>
              <h4 className="mb-4 font-semibold text-white text-left">{contentCopy[language].materials}</h4>
              <ul className="space-y-1 text-left">
                {footerLinks.materials.map((link) => (
                  <li key={link.name}>
                    <a href={link.href} className="inline-flex min-h-10 items-center text-slate-400 transition-colors hover:text-white">
                      {link.name}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        <div className="mt-8 border-t border-white/[0.08] pt-5">
          <div className="mt-2 text-center text-sm text-slate-500">
            {t.footer.copyright}
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
