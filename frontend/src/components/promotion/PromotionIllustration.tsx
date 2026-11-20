import petersburgMap from '@/assets/promotion/petersburg-map-clean-v2.webp';
import { Building2, MapPin, Star, Users } from 'lucide-react';
import type { PromotionKey } from '@/content/promotionContent';

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
  const maps = direction === 'maps';
  return <div className="promotion-example">

    <div className="grid gap-6 md:grid-cols-2 md:gap-10">
      <div><span className="mb-4 flex size-11 items-center justify-center rounded-xl bg-secondary">{maps ? <MapPin size={22} /> : direction === 'bloggers' ? <Users size={22} /> : <Building2 size={22} />}</span><h3 className="text-2xl font-semibold tracking-tight">{maps ? l('Массаж спины', 'Back massage') : direction === 'bloggers' ? l('Автор о жизни района', 'A neighbourhood creator') : l('Кофейня + студия рядом', 'A café + nearby studio')}</h3><p className="mt-3 text-sm leading-7 text-muted-foreground">{maps ? l('Услугу размещаем отдельно: с названием, описанием и способом записи.', 'Replace a generic “Massage” with a specific service, a clear description and a way to book.') : direction === 'bloggers' ? l('В публикациях — места и события района. Тематика подходит бизнесу; географию аудитории ещё нужно подтвердить статистикой автора.', 'Posts cover local places and events. The topic fits the business; audience geography still needs verification from creator statistics.') : l('Клиенты студии могут зайти за кофе после занятия. Гости кофейни могут заинтересоваться тренировкой поблизости.', 'Studio clients may enjoy a coffee after class. Café customers may be interested in a nearby workout.')}</p></div>
      <div className="border-s-2 border-warning ps-6"><p className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">{maps ? l('Пример описания услуги', 'Sample service description') : l('Предложение к обсуждению', 'A proposal to discuss')}</p><p className="text-lg leading-relaxed">{maps ? l('«Массаж спины. Чтобы записаться, позвоните или напишите нам. Администратор подскажет продолжительность сеанса, цену и свободное время».', '“Back massage: tell us your preferences and we will help choose a suitable session. Ask about duration, price and availability when booking.”') : direction === 'bloggers' ? l('«Здравствуйте! Хотим предложить вам обзор нашей услуги для жителей района. Пришлите, пожалуйста, условия размещения и статистику аудитории по городам».', '“We would like to introduce our service and discuss a review for local residents. Let’s first agree the format, terms and enquiry tracking.”') : l('«Здравствуйте! Наша студия работает рядом с вашей кофейней. Предлагаем обсудить бонус на занятия для ваших гостей и предложение на кофе для наших клиентов. Вам это интересно?»', '“Let’s discuss mutual recommendations: an offer for café guests and a benefit for studio clients. We’ll agree each side’s contribution and terms.”')}</p></div>
    </div>

  </div>;
}
