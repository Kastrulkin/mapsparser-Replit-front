import { ChevronDown } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import Footer from '@/components/Footer';
import SeoMeta from '@/components/SeoMeta';
import { PublicBrandBackdrop } from '@/components/PublicBrandBackdrop';
import { PromotionLeadDialog } from '@/components/promotion/PromotionLeadDialog';
import { promotionContent, promotionContextSearch, promotionFaqGroups, promotionLinkSearch, readPromotionDirection } from '@/content/promotionContent';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import '@/components/promotion/promotion.css';

export default function PromotionFaq() {
  const { language } = useLanguage();
  const location = useLocation();
  const english = language !== 'ru';
  const l = (ru: string, en: string) => english ? en : ru;
  const direction = readPromotionDirection(location.search) || 'home';
  const page = promotionContent(english)[direction];
  const context = promotionContextSearch(location.search, direction);
  const groups = promotionFaqGroups(english);
  useEffect(() => {
    if (!location.hash) { window.scrollTo(0, 0); return; }
    const timer = window.setTimeout(() => document.getElementById(location.hash.slice(1))?.scrollIntoView(), 100);
    return () => window.clearTimeout(timer);
  }, [location.hash]);
  return <div className="promotion-page relative isolate bg-background" lang={english ? 'en' : 'ru'} dir="ltr">
    <SeoMeta path="/faq" title={l('Вопросы и ответы о продвижении — LocalOS', 'Marketing questions and answers — LocalOS')} description={l('Как начать работу с LocalOS, предоставить доступы и согласовать материалы. Ответы о Картах, блогерах, партнёрах и стоимости.', 'Getting started, account access, approvals and pricing. Answers about maps, local creators and business partners.')} />
    <PublicBrandBackdrop />
    <main className="mx-auto max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
      <nav aria-label={l('Хлебные крошки', 'Breadcrumbs')} className="promotion-breadcrumbs"><Link to={`/${promotionLinkSearch(location.search)}`}>{l('Главная', 'Home')}</Link><span aria-hidden="true">/</span><span aria-current="page">{l('Вопросы', 'Questions')}</span></nav>
      <header className="max-w-3xl py-8 sm:py-10"><p className="promotion-eyebrow">LocalOS</p><h1 className="text-4xl font-semibold tracking-tight text-primary sm:text-5xl">{l('Вопросы и ответы', 'Questions and answers')}</h1><p className="mt-5 text-base leading-8 text-muted-foreground">{l('Как начинаем работу, какие доступы нужны и что входит в продвижение.', 'How we get started, which account access is needed and what marketing includes.')}</p></header>
      {direction !== 'home' && <div className="mb-8 flex flex-wrap items-center gap-x-5 gap-y-2 border-s-2 border-warning ps-4"><span className="text-sm">{l('Вы выбрали:', 'Selected:')} <strong className="font-medium">{page.label}</strong></span><Link to={page.path + context} className="inline-flex min-h-11 items-center text-sm underline underline-offset-4">{l('Вернуться к направлению', 'Back to the direction')}</Link></div>}
      <nav aria-label={l('Темы вопросов', 'Question topics')} className="promotion-faq-topics mb-8 flex flex-wrap gap-2">{groups.map((group) => <a href={`#${group.id}`} aria-current={location.hash === `#${group.id}` ? 'location' : undefined} key={group.id} className="inline-flex min-h-11 items-center rounded-full border border-border bg-card px-4 text-xs hover:bg-secondary">{group.title}</a>)}</nav>
      <div className="max-w-4xl">{groups.map((group) => <section id={group.id} key={group.id} className="promotion-faq-section mb-8"><h2 className="mb-4 text-2xl font-semibold tracking-tight text-primary">{group.title}</h2>{group.questions.map((item) => <details key={item.question} className="group border-b border-border"><summary className="flex min-h-16 cursor-pointer list-none items-center justify-between gap-5 py-5 text-base font-medium text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">{item.question}<ChevronDown size={18} className="shrink-0 transition-transform group-open:rotate-180" aria-hidden="true" /></summary><p className="max-w-3xl pb-6 text-sm leading-7 text-muted-foreground">{item.answer}</p></details>)}</section>)}</div>
      <div className="promotion-support-links border-t border-border pt-8"><div><h2 className="text-2xl font-semibold text-primary">{l('Не нашли ответ?', 'Still have a question?')}</h2><p className="mt-3 text-sm text-muted-foreground">{l('Оставьте заявку. Менеджер свяжется с вами и ответит на вопросы.', 'Send a request. A manager will contact you and answer your questions.')}</p></div><PromotionLeadDialog key={page.key} page={page} english={english} label={l('Задать вопрос', 'Ask a question')} /><Link to={`/pricing${context}`} className="inline-flex min-h-11 items-center text-sm underline underline-offset-4">{l('Посмотреть тарифы', 'View pricing')}</Link></div>
    </main><Footer />
  </div>;
}
