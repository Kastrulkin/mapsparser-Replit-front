import yandexMapsLogo from '@/assets/promotion/yandex-maps.png';
import googleMapsLogo from '@/assets/promotion/google-maps.png';
import twoGisLogo from '@/assets/promotion/2gis.png';
import directionMap from '@/assets/promotion/petersburg-map-clean-v2.webp';
import creatorPhoto from '@/assets/promotion/local-creator-v1.webp';
import { ArrowDown, ArrowRight, Check, MapPin, MoveUpRight } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import Footer from '@/components/Footer';
import SeoMeta from '@/components/SeoMeta';
import { PublicBrandBackdrop } from '@/components/PublicBrandBackdrop';
import { Button } from '@/components/ui/button';
import { PromotionLeadDialog } from '@/components/promotion/PromotionLeadDialog';
import { PromotionIllustration, PromotionExample } from '@/components/promotion/PromotionIllustration';
import { PromotionDirectionPreview } from '@/components/promotion/PromotionDirectionPreview';
import { promotionContent, promotionTrust, promotionLinkSearch, promotionContextSearch, promotionWorkSteps, type PromotionKey } from '@/content/promotionContent';
import { publishedCases } from '@/content/cases';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import '@/components/promotion/promotion.css';

export default function PromotionLanding({ direction = 'home' }: { direction?: PromotionKey }) {
  const { language } = useLanguage();
  const location = useLocation();
  const english = language !== 'ru';
  const content = promotionContent(english);
  const page = content[direction];
  const home = direction === 'home';
  const maps = direction === 'maps';
  const l = (ru: string, en: string) => english ? en : ru;
  const directions: PromotionKey[] = ['maps', 'bloggers', 'partners'];
  const context = promotionContextSearch(location.search, direction);
  const cases = publishedCases.slice(0, 1);

  useEffect(() => {
    if (!location.hash) { window.scrollTo(0, 0); return; }
    const timeout = window.setTimeout(() => document.getElementById(location.hash.slice(1))?.scrollIntoView(), 100);
    return () => window.clearTimeout(timeout);
  }, [location.pathname, location.hash]);

  return <div className="promotion-page relative isolate bg-background text-foreground" lang={english ? 'en' : 'ru'} dir="ltr" data-promotion-page={direction}>
    <SeoMeta title={page.seoTitle} description={page.description} path={page.path} />
    <PublicBrandBackdrop />
    <main id="main-content" className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      {!home && <nav aria-label={l('Хлебные крошки', 'Breadcrumbs')} className="promotion-breadcrumbs">
        <Link to={`/${promotionLinkSearch(location.search)}`}>{l('Главная', 'Home')}</Link>
        <span aria-hidden="true">/</span><span aria-current="page">{page.label}</span>
      </nav>}
      <section className={`promotion-hero grid items-center gap-10 lg:grid-cols-2 lg:gap-12 ${home ? 'py-8 lg:py-16' : 'pb-8 pt-4 lg:pb-14 lg:pt-6'}`} aria-labelledby="promotion-title">
        <div>
          <p className="promotion-eyebrow"><span />{page.eyebrow}</p>
          {maps && <ul className="mb-5 flex flex-wrap gap-x-4 gap-y-2 text-xs font-medium text-muted-foreground">
            <li className="flex items-center gap-1.5"><img src={yandexMapsLogo} alt="" width={18} height={18} />{l('Яндекс Карты', 'Yandex Maps')}</li>
            <li className="flex items-center gap-1.5"><img src={googleMapsLogo} alt="" width={18} height={18} />Google Maps</li>
            <li className="flex items-center gap-1.5"><img src={twoGisLogo} alt="" width={18} height={18} />{l('2ГИС', '2GIS')}</li>
          </ul>}
          <h1 id="promotion-title" className="whitespace-normal sm:whitespace-pre-line text-balance text-4xl font-semibold leading-[1.1] tracking-tight text-primary sm:text-5xl">{page.title}</h1>
          <p className="mt-6 max-w-xl text-base leading-8 text-muted-foreground sm:text-lg">{page.description}</p>
          <div className="mt-8 flex flex-wrap items-center gap-5">
            {home ? <Button variant="brand" size="lg" asChild className="min-h-12 px-7"><a href="#directions">{l('Выбрать направление', 'Choose a direction')}<ArrowDown size={16} className="ms-2" aria-hidden="true" /></a></Button>
              : <PromotionLeadDialog key={page.key} page={page} english={english} className="min-h-12 px-7" />}
            <a href={home ? '#how-it-works' : '#examples'} className="inline-flex min-h-11 items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">{home ? l('Как работаем', 'How we work') : l('Посмотреть пример', 'See an example')}<ArrowDown size={15} aria-hidden="true" /></a>
          </div>

        </div>
        {home ? <PromotionIllustration direction="home" english={english} /> : <PromotionDirectionPreview direction={direction} english={english} />}
      </section>
      {promotionTrust && <div className="promotion-trust mb-6 border-s-2 border-warning ps-4 text-sm leading-6 text-muted-foreground">{promotionTrust.text}</div>}

      <section id={home ? 'directions' : 'work-scope'} className="promotion-section scroll-mt-24 sm:scroll-mt-36 xl:scroll-mt-24" aria-labelledby="direction-title">
        <div className="promotion-section-heading">
          <p className="promotion-eyebrow">{home ? l('Направления', 'Directions') : l('Работа по направлению', 'Scope of work')}</p>
          <h2 id="direction-title">{home ? l('С чего хотите начать?', 'Where would you like to start?') : maps ? l('Как клиенты выбирают компанию на Картах', 'How customers choose a business on maps') : direction === 'bloggers' ? l('Как подбираем блогеров', 'How we select creators') : l('Как подбираем партнёров', 'How we select partners')}</h2>
          <p>{page.reason}</p>
        </div>
        <div className="grid gap-4 md:grid-cols-3">{page.sections.map((section, index) => {
                    const target = content[directions[index]];
          return <article className={home ? "promotion-direction" : "promotion-scope-step"} key={section.title}>
            {home && <div className={`promotion-direction-art promotion-direction-art-${target.key}`} aria-hidden="true"><img src={target.key === 'bloggers' ? creatorPhoto : directionMap} alt="" width={600} height={400} loading="lazy" decoding="async" />{target.key === 'maps' && <span className="promotion-direction-art-label"><MapPin size={14} />{l('Ваш бизнес', 'Your business')}</span>}{target.key === 'partners' && <><span className="promotion-direction-art-label">{l('Кофейня', 'Café')}</span><span className="promotion-direction-art-label">{l('Студия', 'Studio')}</span></>}</div>}
            {!home && <span className="promotion-step-number">0{index + 1}</span>}
            <h3 className="mt-4 text-xl font-semibold tracking-tight text-primary">{section.title}</h3>
            <p className="mt-3 text-sm leading-7 text-muted-foreground">{section.text}</p>
            {section.items && <ul className="mt-5 space-y-2 text-sm">{section.items.map((text) => <li key={text} className="flex items-start gap-2"><Check size={15} className="mt-0.5 shrink-0 text-muted-foreground" aria-hidden="true" />{text}</li>)}</ul>}
            {home && <Link className="promotion-direction-link mt-auto inline-flex min-h-11 items-center gap-2 pt-5 text-sm font-semibold text-primary underline-offset-4 hover:underline" to={`${target.path}${promotionLinkSearch(location.search)}`}><span className="sr-only">{target.label}: </span>{l('Подробнее', 'Learn more')}<ArrowRight size={16} aria-hidden="true" /></Link>}
          </article>;
        })}</div>
        {home && <Link to="/growth" className="mt-6 inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground underline underline-offset-4">{l('Все возможности LocalOS', 'All LocalOS capabilities')}<ArrowRight size={14} aria-hidden="true" /></Link>}
      </section>

      {!home && <section id="examples" className="promotion-section scroll-mt-24 sm:scroll-mt-36 xl:scroll-mt-24" aria-labelledby="example-title">
        <div className="promotion-section-heading"><p className="promotion-eyebrow">{l('Примеры', 'Examples')}</p><h2 id="example-title">{maps ? l('Что подготовим для карточки', 'What we prepare for your listing') : direction === 'bloggers' ? l('Пример подбора блогеров', 'A sample creator shortlist') : l('Пример совместной акции', 'A sample joint promotion')}</h2><p>{l('Тексты и условия подготовим с учётом ваших услуг и цен.', 'We prepare the text and terms using your services and prices.')}</p></div>
        <PromotionExample direction={direction} english={english} />
      </section>}

      <section id="how-it-works" className="promotion-section scroll-mt-24 sm:scroll-mt-36 xl:scroll-mt-24" aria-labelledby="process-title">
        {home && <span id="agents" className="block scroll-mt-36" aria-hidden="true" />}
        <div className="promotion-section-heading"><p className="promotion-eyebrow">{l('Начало работы', 'Getting started')}</p><h2 id="process-title">{l('Как начнём работу', 'How we get started')}</h2>{home && <p>{l('Вы рассказываете о бизнесе и предоставляете доступы. Мы занимаемся продвижением и показываем результат.', 'You share business details and provide access. We handle marketing and report on the work.')}</p>}</div>
        <ol className="promotion-process grid gap-5 md:grid-cols-2 lg:grid-cols-4">{promotionWorkSteps(english, direction).map((step, index) => <li key={step.title} className="border-t border-border pt-5"><span className="text-xs font-medium text-muted-foreground">0{index + 1}</span><h3 className="mt-4 text-lg font-semibold text-primary">{step.title}</h3><p className="mt-3 text-sm leading-7 text-muted-foreground">{step.text}</p></li>)}</ol>
      </section>

      {(home || maps) && <section className="promotion-section promotion-cases-section" aria-labelledby="case-title">
        <div className="promotion-section-heading"><p className="promotion-eyebrow">{l('Кейсы', 'Cases')}</p><h2 id="case-title">{home ? l('Как работали с карточкой компании', 'Work on a business listing') : l('Результаты работы с карточками', 'Results from business listings')}</h2><p>{l('Опубликованные результаты продвижения на Картах. Показатели зависят от бизнеса и исходного состояния карточки.', 'Published map marketing results. Outcomes depend on the business and the listing’s starting point.')}</p></div>
        <div className="promotion-home-case">{cases.map((item) => <article key={item.slug} className="promotion-case">
          <span className="text-xs font-medium text-muted-foreground">{l('КАРТЫ / ', 'MAPS / ')}{item.industry}</span>
          <h3 className="mt-5 text-xl font-semibold leading-snug tracking-tight text-primary">{item.title}</h3>
          <p className="my-5 text-sm leading-7 text-muted-foreground">{item.excerpt}</p>
          <ul className="mb-6 space-y-2">{item.metrics.map((metric) => <li key={metric.label} className="flex items-baseline justify-between gap-3 border-t border-border pt-2 text-xs text-muted-foreground"><span>{metric.label}</span><strong className="whitespace-nowrap text-lg font-semibold tabular-nums text-primary">{metric.value}</strong></li>)}</ul>
          <Link to={`/cases/${item.slug}`} className="mt-auto inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-primary hover:underline">{l('Читать кейс', 'Read case (Russian)')}<MoveUpRight size={15} aria-hidden="true" /></Link>
        </article>)}</div>
        {maps && <div className="promotion-more-cases">{publishedCases.slice(1, 3).map((item) => <Link key={item.slug} to={`/cases/${item.slug}`}><span>{item.industry}</span><strong>{item.title}</strong><ArrowRight size={18} aria-hidden="true" /></Link>)}</div>}
        {home && <Link to={`/cases${promotionLinkSearch(location.search)}`} className="mt-5 inline-flex min-h-11 items-center gap-2 text-sm underline underline-offset-4">{l('Все кейсы', 'All cases')}<ArrowRight size={14} aria-hidden="true" /></Link>}
      </section>}

      <section className="promotion-section" aria-labelledby="terms-title">
        <div className="promotion-support-links">
          <div><h2 id="terms-title" className="text-xl font-semibold text-primary">{home ? l('Тарифы и ответы на вопросы', 'Pricing and questions') : l('Условия и стоимость', 'Terms and pricing')}</h2><p className="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground">{home ? l('Стоимость подписки — в тарифах. Ответы о начале работы — в FAQ.', 'Find subscription prices and answers about getting started.') : l('Тарифы подписки собраны на отдельной странице. Работу команды и расходы на размещения обсудим до начала.', 'Subscription plans are on a separate page. Team service and placement costs are agreed before work starts.')}</p></div>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2"><Link to={`/pricing${context}`} className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold underline underline-offset-4">{l('Посмотреть тарифы', 'View pricing')}<ArrowRight size={15} aria-hidden="true" /></Link><Link to={`/faq${context}${home ? '' : `#${direction}`}`} className="inline-flex min-h-11 items-center gap-2 text-sm underline underline-offset-4">{l('Вопросы и ответы', 'Questions and answers')}<ArrowRight size={15} aria-hidden="true" /></Link></div>
        </div>
      </section>

      <section className="promotion-final mb-14 text-center" aria-labelledby="final-title">
        <p className="promotion-eyebrow justify-center">{l('Связаться с нами', 'Contact us')}</p>
        <h2 id="final-title" className="mx-auto max-w-2xl text-balance text-3xl font-semibold tracking-tight text-primary sm:text-4xl">{home ? l('Поможем выбрать способ продвижения', 'We can help you choose a marketing direction') : maps ? l('Обсудим продвижение на Картах', 'Let’s discuss map marketing') : direction === 'bloggers' ? l('Подберём блогеров для вашего бизнеса', 'Find creators for your business') : l('Найдём партнёров для совместной акции', 'Find partners for a joint offer')}</h2>
        <p className="mx-auto mt-5 max-w-xl text-sm leading-7 text-muted-foreground">{home ? l('Оставьте заявку. Менеджер уточнит задачу и предложит, с чего начать.', 'Send a request. A manager will discuss your task and suggest where to start.') : l('Менеджер уточнит задачу, состав работ и стоимость.', 'A manager will discuss the task, scope and cost.')}</p>
        <div className="mt-7"><PromotionLeadDialog key={page.key} page={page} english={english} /></div>
        <nav aria-label={l('Направления продвижения', 'Marketing directions')} className="mt-8 flex flex-wrap justify-center gap-x-7 gap-y-3">{directions.filter((key) => key !== direction).map((key) => <Link key={key} to={`${content[key].path}${promotionLinkSearch(location.search)}`} className="inline-flex min-h-11 items-center gap-1 text-xs text-muted-foreground underline underline-offset-4">{content[key].label}<ArrowRight size={12} aria-hidden="true" /></Link>)}</nav>
      </section>
    </main><Footer />
  </div>;
}
