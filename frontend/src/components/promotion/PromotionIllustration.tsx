import petersburgMap from '@/assets/promotion/petersburg-map-clean-v2.webp';
import { Building2, Star } from 'lucide-react';
import { promotionCreatorExamples, promotionExamples, type PromotionKey } from '@/content/promotionContent';

export function PromotionIllustration({ english = false }: { direction: PromotionKey; english?: boolean }) {
  const l = (ru: string, en: string) => english ? en : ru;
  return <div className="promotion-visual" role="img" aria-label={l(
    'Объёмная карта квартала: ваш бизнес с пятью звёздами, партнёр и блогер.',
    'Three-dimensional neighbourhood map: your business with five stars, a partner and a blogger.',
  )}>
    <div className="promotion-map-window" aria-hidden="true">
      <img src={petersburgMap} alt="" width={1448} height={1086} loading="eager" decoding="async" className="promotion-neighbourhood" />
      <svg className="promotion-map-routes" viewBox="0 0 640 480" fill="none">
        <path d="M122 130C154 201 209 277 245 322S300 346 333 325L333 264" />
        <path d="M333 325C365 353 419 368 506 394" />
      </svg>
      <div className="promotion-map-node promotion-map-business">
        <div className="promotion-map-tag"><strong>{l('Ваш бизнес', 'Your business')}</strong><span className="promotion-map-stars">{[1, 2, 3, 4, 5].map((star) => <Star key={star} size={11} strokeWidth={0} fill="currentColor" />)}</span></div>
        <span className="promotion-map-anchor" />
      </div>
      <div className="promotion-map-node promotion-map-partner"><span className="promotion-map-tag">{l('Партнёр', 'Partner')}</span><span className="promotion-map-anchor" /></div>
      <div className="promotion-map-node promotion-map-blogger"><span className="promotion-map-tag">{l('Блогер', 'Blogger')}</span><span className="promotion-map-anchor" /></div>
    </div>
  </div>;
}

export function PromotionExample({ direction, english }: { direction: PromotionKey; english: boolean }) {
  const l = (ru: string, en: string) => english ? en : ru;
  if (direction === 'maps') {
    return <div className="promotion-example">
      <ul className="grid gap-5 sm:grid-cols-2">
        {promotionExamples(english).map((example) => (
          <li key={example.title} className="min-w-0 border-s-2 border-warning ps-4">
            <h3 className="text-base font-semibold text-primary">{example.title}</h3>
            <p className="mt-2 text-sm leading-7 text-muted-foreground">{example.text}</p>
          </li>
        ))}
      </ul>
    </div>;
  }
  if (direction === 'bloggers') {
    return <div className="promotion-example space-y-6">
      <ul className="grid gap-5 md:grid-cols-3">
        {promotionCreatorExamples(english).map((example) => (
          <li key={example.title} className="min-w-0 border-s-2 border-warning ps-4">
            <h3 className="text-base font-semibold text-primary">{example.title}</h3>
            <p className="mt-2 text-sm leading-7 text-muted-foreground">{example.text}</p>
          </li>
        ))}
      </ul>
      <p className="text-sm leading-7 text-muted-foreground">{l('Перед размещением проверим географию аудитории выбранных авторов.', 'Before placement, we check where the shortlisted creators’ audiences are based.')}</p>
      <blockquote className="border-t border-border pt-4 text-base leading-7">
        {l('«Здравствуйте! В вашем путеводителе много мест рядом с нашей студией. Приглашаем вас на массаж спины: можно показать читателям, как проходит визит и как нас найти. Пришлите, пожалуйста, условия размещения и статистику аудитории по городам».', '“Hello! Your guide covers plenty of places near our studio. We’d like to invite you for a back massage so you can show readers what a visit is like and how to find us. Could you share your placement terms and audience statistics by city?”')}
      </blockquote>
    </div>;
  }

  return <div className="promotion-example">

    <div className="grid gap-6 md:grid-cols-2 md:gap-10">
      <div><span className="mb-4 flex size-11 items-center justify-center rounded-xl bg-secondary"><Building2 size={22} /></span><h3 className="text-2xl font-semibold tracking-tight">{l('Кофейня + студия рядом', 'A café + nearby studio')}</h3><p className="mt-3 text-sm leading-7 text-muted-foreground">{l('Клиенты студии могут зайти за кофе после занятия. Гости кофейни могут заинтересоваться тренировкой поблизости.', 'Studio clients may enjoy a coffee after class. Café customers may be interested in a nearby workout.')}</p></div>
      <div className="border-s-2 border-warning ps-6"><p className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">{l('«Здравствуйте! Наша студия работает рядом с вашей кофейней. Предлагаем обсудить бонус на занятия для ваших гостей и предложение на кофе для наших клиентов. Вам это интересно?»', '“Let’s discuss mutual recommendations: an offer for café guests and a benefit for studio clients. We’ll agree each side’s contribution and terms.”')}</p></div>
    </div>

  </div>;
}
