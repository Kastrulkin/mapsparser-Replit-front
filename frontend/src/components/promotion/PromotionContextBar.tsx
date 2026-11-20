import './promotion.css';
import { ArrowLeft } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { promotionContent, promotionContextSearch, readPromotionDirection } from '@/content/promotionContent';
import { PromotionLeadDialog } from './PromotionLeadDialog';

export function PromotionContextBar() {
  const { language } = useLanguage();
  const location = useLocation();
  const direction = readPromotionDirection(location.search) || 'home';
  const english = language !== 'ru';
  const page = promotionContent(english)[direction];
  const context = promotionContextSearch(location.search, direction);
  return <div className="border-b border-border bg-card">
    <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
      <div><Link to={page.path + context} className="inline-flex min-h-11 items-center gap-2 text-sm underline underline-offset-4"><ArrowLeft size={15} aria-hidden="true" />{english ? 'Back to ' : 'Вернуться: '}{direction === 'home' ? (english ? 'Home' : 'Главная') : page.label}</Link><p className="text-xs text-muted-foreground">{direction === 'home' ? (english ? 'Not sure which plan to choose? We can discuss your task.' : 'Не знаете, какой тариф выбрать? Обсудим вашу задачу.') : (english ? 'Your selected direction will be included in the request.' : 'Выбранное направление сохранится в заявке.')}</p></div>
      <PromotionLeadDialog key={page.key} page={page} english={english} label={direction === 'home' ? (english ? 'Help me choose' : 'Помогите выбрать') : (english ? 'Discuss this direction' : 'Обсудить направление')} />
    </div>
  </div>;
}
