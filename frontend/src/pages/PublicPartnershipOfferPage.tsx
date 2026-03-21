import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { newAuth } from '@/lib/auth_new';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  CircleDollarSign,
  ExternalLink,
  Globe,
  Mail,
  MapPin,
  MessageCircle,
  ShieldCheck,
  Sparkles,
  Star,
} from 'lucide-react';

type OfferPagePayload = {
  name?: string;
  category?: string;
  city?: string;
  address?: string;
  source_url?: string;
  logo_url?: string | null;
  photo_urls?: string[];
  audit?: {
    summary_score?: number;
    health_level?: string;
    health_label?: string;
    summary_text?: string;
    findings?: Array<{ title?: string; description?: string }>;
    recommended_actions?: Array<{ title?: string; description?: string }>;
    services_preview?: Array<{ current_name?: string; improved_name?: string; source?: string }>;
    reviews_preview?: Array<{ text?: string; author?: string; rating?: number; org_reply?: string }>;
    news_preview?: Array<{ title?: string; text?: string }>;
    subscores?: Record<string, number>;
    current_state?: {
      rating?: number | null;
      reviews_count?: number;
      unanswered_reviews_count?: number;
      services_count?: number;
      services_with_price_count?: number;
      has_website?: boolean;
      has_recent_activity?: boolean;
      photos_state?: string;
    };
    parse_context?: {
      last_parse_at?: string;
      last_parse_status?: string;
      no_new_services_found?: boolean;
    };
    revenue_potential?: {
      total_min?: number;
      total_max?: number;
      dominant_driver?: string;
    };
  };
  audit_full?: Record<string, any>;
  match?: {
    match_score?: number;
    score_explanation?: string;
    offer_angles?: string[];
  };
  message?: string | null;
  cta?: {
    telegram_url?: string | null;
    whatsapp_url?: string | null;
    email?: string | null;
    website?: string | null;
  };
  updated_at?: string;
};

const formatNum = (value?: number | null): string => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return Number(value).toLocaleString('ru-RU');
};

const stateBadgeClass = (score?: number) => {
  const safe = Number(score || 0);
  if (safe >= 80) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (safe >= 55) return 'bg-amber-50 text-amber-700 border-amber-200';
  return 'bg-rose-50 text-rose-700 border-rose-200';
};

const PublicPartnershipOfferPage: React.FC = () => {
  const { offerSlug } = useParams<{ offerSlug: string }>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<OfferPagePayload | null>(null);

  useEffect(() => {
    const run = async () => {
      if (!offerSlug) return;
      try {
        setLoading(true);
        setError(null);
        const data = await newAuth.makeRequest(`/partnership/public/offer/${encodeURIComponent(offerSlug)}`, {
          method: 'GET',
        });
        setPage((data?.page || null) as OfferPagePayload | null);
      } catch (e: any) {
        setError(e.message || 'Не удалось загрузить страницу');
        setPage(null);
      } finally {
        setLoading(false);
      }
    };
    void run();
  }, [offerSlug]);

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <div className="rounded-xl border bg-white p-6 text-sm text-muted-foreground">Загрузка страницы оффера...</div>
      </div>
    );
  }

  if (error || !page) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
          {error || 'Страница оффера не найдена'}
        </div>
      </div>
    );
  }

  const findings = Array.isArray(page.audit?.findings) ? page.audit?.findings || [] : [];
  const actions = Array.isArray(page.audit?.recommended_actions) ? page.audit?.recommended_actions || [] : [];
  const services = Array.isArray(page.audit?.services_preview) ? page.audit?.services_preview || [] : [];
  const reviews = Array.isArray(page.audit?.reviews_preview) ? page.audit?.reviews_preview || [] : [];
  const news = Array.isArray(page.audit?.news_preview) ? page.audit?.news_preview || [] : [];
  const photos = Array.isArray(page.photo_urls) ? page.photo_urls || [] : [];
  const state = page.audit?.current_state || {};
  const parse = page.audit?.parse_context || {};
  const revenue = page.audit?.revenue_potential || {};
  const score = Number(page.audit?.summary_score || 0);
  const canContact = Boolean(page.cta?.telegram_url || page.cta?.whatsapp_url || page.cta?.email || page.cta?.website);

  const quickState = [
    {
      label: 'Услуги в карточке',
      ok: Number(state.services_count || 0) > 0,
      hint: Number(state.services_count || 0) > 0 ? `${state.services_count} найдено` : 'Не заполнены или не распознаны',
    },
    {
      label: 'Сайт',
      ok: Boolean(state.has_website),
      hint: state.has_website ? 'Есть ссылка на сайт' : 'Сайт не указан',
    },
    {
      label: 'Работа с отзывами',
      ok: Number(state.unanswered_reviews_count || 0) <= 3,
      hint:
        Number(state.unanswered_reviews_count || 0) > 0
          ? `Без ответа: ${state.unanswered_reviews_count}`
          : 'Ответы на отзывы есть',
    },
    {
      label: 'Активность карточки',
      ok: Boolean(state.has_recent_activity),
      hint: state.has_recent_activity ? 'Есть свежие обновления' : 'Нужны новости/обновления',
    },
  ];

  return (
    <div className="min-h-screen bg-[radial-gradient(ellipse_at_top_right,_rgba(56,189,248,0.18),_transparent_45%),radial-gradient(ellipse_at_bottom_left,_rgba(14,165,233,0.16),_transparent_40%),linear-gradient(to_bottom,_#f8fafc,_#ffffff)]">
      <div className="mx-auto max-w-6xl px-4 py-8 space-y-5">
        <section className="rounded-2xl border border-sky-100 bg-white/90 backdrop-blur-sm p-6 md:p-8 shadow-sm">
          <div className="flex flex-col md:flex-row gap-4 md:items-start md:justify-between">
            <div className="flex items-center gap-4">
            {page.logo_url ? (
              <img
                src={page.logo_url}
                alt="Логотип компании"
                className="h-16 w-16 md:h-20 md:w-20 rounded-xl border border-sky-100 object-cover bg-white"
              />
            ) : null}
              <div>
                <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">{page.name || 'Компания'}</h1>
                <p className="mt-1 text-sm text-slate-600 flex flex-wrap gap-2 items-center">
                  <span className="inline-flex items-center gap-1">
                    <MapPin className="w-4 h-4" />
                    {page.city || 'Город не указан'}
                  </span>
                  <span>•</span>
                  <span>{page.category || 'Категория не указана'}</span>
                </p>
                {page.address ? <p className="text-sm text-slate-500 mt-1">{page.address}</p> : null}
                {parse.last_parse_at ? (
                  <p className="text-xs text-slate-500 mt-2">
                    Последний аудит: {new Date(parse.last_parse_at).toLocaleString('ru-RU')}
                  </p>
                ) : null}
              </div>
            </div>
            <div className="md:text-right">
              <div className="text-xs uppercase tracking-wider text-slate-500">Оценка карточки</div>
              <div className="text-3xl font-bold text-slate-900 mt-1">{score}/100</div>
              <div className={`inline-flex mt-2 px-3 py-1 rounded-full border text-xs font-semibold ${stateBadgeClass(score)}`}>
                {page.audit?.health_label || 'Состояние не определено'}
              </div>
            </div>
          </div>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-xs text-slate-500">Рейтинг</div>
              <div className="mt-1 text-xl font-semibold text-slate-900 flex items-center gap-2">
                <Star className="w-4 h-4 text-amber-500" />
                {state.rating ? Number(state.rating).toFixed(1) : '—'}
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-xs text-slate-500">Отзывы</div>
              <div className="mt-1 text-xl font-semibold text-slate-900">{formatNum(state.reviews_count)}</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-xs text-slate-500">Услуги</div>
              <div className="mt-1 text-xl font-semibold text-slate-900">{formatNum(state.services_count)}</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-xs text-slate-500">Потенциал в месяц</div>
              <div className="mt-1 text-sm font-semibold text-slate-900">
                {revenue.total_min || revenue.total_max
                  ? `${formatNum(revenue.total_min)} — ${formatNum(revenue.total_max)} ₽`
                  : 'Оценка недоступна'}
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-sky-600" />
            Текущее состояние карточки
          </h2>
          <p className="text-sm text-slate-600 mt-1">
            Это срез по ключевым зонам. Ниже сразу видно, что уже в порядке, а что теряет заявки.
          </p>
          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
            {quickState.map((row) => (
              <div key={row.label} className="rounded-xl border border-slate-200 p-4 bg-slate-50/70">
                <div className="flex items-center gap-2">
                  {row.ok ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-rose-600" />
                  )}
                  <span className="font-medium text-slate-900">{row.label}</span>
                </div>
                <p className="mt-1 text-sm text-slate-600">{row.hint}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-violet-600" />
            Что улучшить в первую очередь
          </h2>
          {page.audit?.summary_text ? <p className="text-sm text-slate-600 mt-1">{page.audit.summary_text}</p> : null}
          <div className="mt-4 space-y-3">
            {(findings.length > 0 ? findings : actions).slice(0, 6).map((item, idx) => (
              <div key={`${item.title || 'item'}-${idx}`} className="rounded-xl border border-violet-100 bg-violet-50/50 p-4">
                <div className="text-sm font-semibold text-slate-900">{idx + 1}. {item.title || 'Рекомендация'}</div>
                <div className="text-sm text-slate-700 mt-1">{item.description || 'Описание не указано'}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Услуги в карточке</h2>
          {services.length > 0 ? (
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
              {services.slice(0, 12).map((item, idx) => (
                <div key={`${item.current_name || 'service'}-${idx}`} className="rounded-xl border border-slate-200 p-4">
                  <div className="text-sm text-slate-500">Сейчас</div>
                  <div className="font-medium text-slate-900 mt-1">{item.current_name || 'Без названия'}</div>
                  {item.improved_name ? (
                    <>
                      <div className="text-sm text-slate-500 mt-3">Можно показать так</div>
                      <div className="font-medium text-sky-700 mt-1">{item.improved_name}</div>
                    </>
                  ) : null}
                  {item.source ? <div className="text-xs text-slate-500 mt-2">Источник: {item.source}</div> : null}
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
              Услуги не заполнены или недоступны в карточке.
            </div>
          )}
        </section>

        {photos.length > 0 ? (
          <section className="rounded-2xl border bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">Фото и визуал карточки</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">
              {photos.slice(0, 8).map((photo, index) => (
                <img
                  key={`${photo}-${index}`}
                  src={photo}
                  alt={`Фото ${index + 1}`}
                  className="h-24 w-full rounded-md border border-slate-200 object-cover bg-white"
                />
              ))}
            </div>
          </section>
        ) : null}

        {(reviews.length > 0 || news.length > 0) ? (
          <section className="rounded-2xl border bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">Активность карточки</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
              <div className="rounded-xl border border-slate-200 p-4">
                <div className="text-sm font-semibold text-slate-900">Отзывы (пример)</div>
                {reviews.length > 0 ? (
                  <div className="space-y-2 mt-2">
                    {reviews.slice(0, 3).map((item, idx) => (
                      <div key={`review-${idx}`} className="text-sm text-slate-700 border-b border-slate-100 pb-2">
                        <div className="font-medium">{item.author || 'Клиент'}</div>
                        <div>{item.text || 'Текст отзыва'}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500 mt-2">Свежих отзывов нет в срезе.</p>
                )}
              </div>
              <div className="rounded-xl border border-slate-200 p-4">
                <div className="text-sm font-semibold text-slate-900">Новости/посты (пример)</div>
                {news.length > 0 ? (
                  <div className="space-y-2 mt-2">
                    {news.slice(0, 3).map((item, idx) => (
                      <div key={`news-${idx}`} className="text-sm text-slate-700 border-b border-slate-100 pb-2">
                        <div className="font-medium">{item.title || 'Публикация'}</div>
                        <div>{item.text || 'Описание публикации'}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500 mt-2">Публикаций в срезе не найдено.</p>
                )}
              </div>
            </div>
          </section>
        ) : null}

        <section className="rounded-2xl border border-sky-200 bg-sky-50/70 p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <CircleDollarSign className="w-5 h-5 text-sky-700" />
            Что делать дальше
          </h2>
          <p className="text-sm text-slate-700 mt-1">
            Можно внедрить улучшения самостоятельно по шагам выше. Если нужна помощь, подключимся и сделаем это вместе с вами.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {page.cta?.telegram_url ? (
              <a href={page.cta.telegram_url} target="_blank" rel="noreferrer">
                <Button className="bg-sky-600 hover:bg-sky-700 text-white">
                  <MessageCircle className="w-4 h-4 mr-1" />
                  Связаться в Telegram
                </Button>
              </a>
            ) : null}
            {page.cta?.whatsapp_url ? (
              <a href={page.cta.whatsapp_url} target="_blank" rel="noreferrer">
                <Button variant="outline" className="border-sky-300 text-sky-800">
                  <MessageCircle className="w-4 h-4 mr-1" />
                  Связаться в WhatsApp
                </Button>
              </a>
            ) : null}
            {page.cta?.email ? (
              <a href={`mailto:${page.cta.email}`}>
                <Button variant="outline">
                  <Mail className="w-4 h-4 mr-1" />
                  Написать на Email
                </Button>
              </a>
            ) : null}
            {page.cta?.website ? (
              <a href={page.cta.website} target="_blank" rel="noreferrer">
                <Button variant="outline">
                  <Globe className="w-4 h-4 mr-1" />
                  Перейти на сайт
                </Button>
              </a>
            ) : null}
            {page.source_url ? (
              <a href={page.source_url} target="_blank" rel="noreferrer">
                <Button variant="ghost">
                  <ExternalLink className="w-4 h-4 mr-1" />
                  Открыть карточку на карте
                </Button>
              </a>
            ) : null}
            {canContact ? null : (
              <a href="/contact">
                <Button className="bg-slate-900 text-white hover:bg-slate-800">
                  Оставить заявку
                  <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              </a>
            )}
          </div>
          {page.message ? (
            <div className="mt-4 rounded-xl border border-sky-200 bg-white p-4">
              <div className="text-xs uppercase tracking-wide text-slate-500">Черновик первого обращения</div>
              <div className="text-sm text-slate-800 whitespace-pre-wrap mt-2">{page.message}</div>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
};

export default PublicPartnershipOfferPage;
