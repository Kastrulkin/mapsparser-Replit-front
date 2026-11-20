import creatorVisit from '@/assets/promotion/local-creator-v1.webp';
import neighbourhoodMap from '@/assets/promotion/petersburg-map-clean-v2.webp';
import { ArrowRight, Building2, Check, Coffee, Dumbbell, MapPin, MessageCircle, Newspaper, Star, Users } from 'lucide-react';
import type { PromotionKey } from '@/content/promotionContent';

export function PromotionDirectionPreview({ direction, english }: { direction: PromotionKey; english: boolean }) {
  const l = (ru: string, en: string) => english ? en : ru;
  if (direction === 'maps') return <aside className="promotion-preview promotion-listing-preview" aria-label={l('Карты, отзывы и публикации', 'Maps, reviews and posts')}>
    <div className="promotion-listing-map">
      <img src={neighbourhoodMap} alt="" width={1448} height={1086} loading="eager" decoding="async" />
      <span className="promotion-listing-map-title"><MapPin size={14} aria-hidden="true" />{l('Карты', 'Maps')}</span>
      <div className="promotion-listing-business"><div><strong>{l('Ваш бизнес', 'Your business')}</strong><span className="promotion-map-stars" aria-label={l('Пять звёзд на иллюстрации', 'Five illustrated stars')}>{[1, 2, 3, 4, 5].map((star) => <Star key={star} size={10} fill="currentColor" strokeWidth={0} aria-hidden="true" />)}</span></div><span className="promotion-listing-pin" /></div>
    </div>
    <div className="promotion-listing-details"><Building2 size={18} strokeWidth={1.5} aria-hidden="true" /><p>{l('Услуги, фото и контакты', 'Services, photos and contact details')}</p><Check size={15} className="ms-auto" aria-hidden="true" /></div>
    <div className="promotion-listing-work">
      <div className="promotion-listing-review"><h2><MessageCircle size={17} strokeWidth={1.5} aria-hidden="true" />{l('Отзывы', 'Reviews')}</h2><p className="promotion-listing-subtitle">{l('Ответ клиенту', 'A reply to a customer')}</p><p className="promotion-listing-copy">{l('«Спасибо за отзыв! Рады, что вам понравилось. До следующей встречи».', '“Thank you for your review! We are glad you enjoyed your visit. See you again.”')}</p></div>
      <div className="promotion-listing-post"><h2><Newspaper size={17} strokeWidth={1.5} aria-hidden="true" />{l('Публикации', 'Posts')}</h2><p className="promotion-listing-subtitle">{l('Новости компании', 'Business news')}</p><p className="promotion-listing-copy">{l('Новые услуги, сезонные предложения и акции — в карточке вашего бизнеса.', 'New services, seasonal offers and promotions in your business listing.')}</p></div>
    </div>
  </aside>;
  if (direction === 'bloggers') return <aside className="promotion-preview promotion-creator-preview" aria-label={l('Подбор блогера и подготовка размещения', 'Creator selection and placement preparation')}>
    <div className="promotion-creator-photo"><img src={creatorVisit} alt={l('Автор снимает местное кафе на телефон', 'A creator filming a local café on a phone')} width={1200} height={800} loading="eager" decoding="async" /></div>
    <div className="promotion-creator-story"><span className="promotion-creator-story-icon"><Newspaper size={22} strokeWidth={1.5} aria-hidden="true" /></span><div><h2>{l('Обзор вашего бизнеса', 'A feature about your business')}</h2><p>{l('Визит автора, фото и видео для подписчиков', 'A creator’s visit, photos and video for their followers')}</p></div></div>
    <div className="promotion-creator-work">
      <div><h3><Users size={17} strokeWidth={1.5} aria-hidden="true" />{l('Кого подберём', 'Who we look for')}</h3><ul><li>{l('Пишет о вашем районе и теме', 'Covers your area and topic')}</li><li>{l('Географию аудитории проверим по статистике', 'We check audience location using their statistics')}</li></ul></div>
      <div><h3><MessageCircle size={17} strokeWidth={1.5} aria-hidden="true" />{l('Что согласуем', 'What we agree')}</h3><ul><li>{l('Формат и содержание рекламы', 'The format and content of the ad')}</li><li>{l('Стоимость, сроки и условия размещения', 'Price, schedule and placement terms')}</li></ul></div>
    </div>
    <div className="promotion-creator-audience"><MapPin size={15} strokeWidth={1.5} aria-hidden="true" /><span>{l('Ваш бизнес → местный автор → жители района', 'Your business → local creator → local residents')}</span></div>
  </aside>;
  return <aside className="promotion-preview promotion-partner-preview" aria-label={l('Соседние компании и взаимные предложения клиентам', 'Neighbouring businesses and offers for each other’s customers')}>
    <div className="promotion-partner-map">
      <img src={neighbourhoodMap} alt="" width={1448} height={1086} loading="eager" decoding="async" />
      <span className="promotion-partner-connection" aria-hidden="true" />
      <div className="promotion-partner-location promotion-partner-cafe"><span><Coffee size={18} strokeWidth={1.5} aria-hidden="true" /><strong>{l('Кофейня', 'Café')}</strong></span><i aria-hidden="true" /></div>
      <div className="promotion-partner-location promotion-partner-studio"><span><Dumbbell size={18} strokeWidth={1.5} aria-hidden="true" /><strong>{l('Студия', 'Studio')}</strong></span><i aria-hidden="true" /></div>
      <span className="promotion-partner-nearby"><MapPin size={13} aria-hidden="true" />{l('В одном районе', 'In the same neighbourhood')}</span>
    </div>
    <div className="promotion-partner-offers">
      <h2>{l('Рекомендуйте друг друга', 'Recommend each other')}</h2>
      <div className="promotion-partner-offer"><span className="promotion-partner-offer-icon"><Coffee size={20} strokeWidth={1.5} aria-hidden="true" /></span><div><p>{l('Гостям кофейни', 'For café guests')}</p><strong>{l('Бонус на занятия в студии', 'An offer on studio classes')}</strong></div><ArrowRight size={18} strokeWidth={1.5} aria-hidden="true" /></div>
      <div className="promotion-partner-offer"><span className="promotion-partner-offer-icon"><Dumbbell size={20} strokeWidth={1.5} aria-hidden="true" /></span><div><p>{l('Клиентам студии', 'For studio clients')}</p><strong>{l('Предложение на кофе после тренировки', 'An offer on coffee after training')}</strong></div><ArrowRight size={18} strokeWidth={1.5} aria-hidden="true" /></div>
    </div>
  </aside>;
}
