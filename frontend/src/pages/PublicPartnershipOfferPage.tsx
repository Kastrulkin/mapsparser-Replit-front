import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { newAuth } from '@/lib/auth_new';

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
    health_label?: string;
    summary_text?: string;
    findings?: Array<{ title?: string; description?: string }>;
    recommended_actions?: Array<{ title?: string; description?: string }>;
    services_preview?: Array<{ current_name?: string }>;
  };
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
  const photos = Array.isArray(page.photo_urls) ? page.photo_urls || [] : [];

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 space-y-4">
      <div className="rounded-xl border bg-white p-6">
        <div className="flex flex-col md:flex-row gap-4 md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            {page.logo_url ? (
              <img
                src={page.logo_url}
                alt="Логотип компании"
                className="h-16 w-16 rounded-md border border-gray-200 object-cover bg-white"
              />
            ) : null}
            <div>
              <h1 className="text-2xl font-bold text-foreground">{page.name || 'Компания'}</h1>
              <p className="text-sm text-muted-foreground">
                {page.city || '—'} · {page.category || '—'}
              </p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm text-muted-foreground">Аудит карточки</div>
            <div className="text-2xl font-semibold text-foreground">{page.audit?.summary_score ?? 0}/100</div>
            <div className="text-xs text-muted-foreground">{page.audit?.health_label || '—'}</div>
          </div>
        </div>
        {page.address ? <p className="text-sm text-muted-foreground mt-3">{page.address}</p> : null}
      </div>

      {photos.length > 0 ? (
        <div className="rounded-xl border bg-white p-6">
          <h2 className="text-lg font-semibold mb-3">Фото карточки</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {photos.slice(0, 8).map((photo, index) => (
              <img
                key={`${photo}-${index}`}
                src={photo}
                alt={`Фото ${index + 1}`}
                className="h-24 w-full rounded-md border border-gray-200 object-cover bg-white"
              />
            ))}
          </div>
        </div>
      ) : null}

      <div className="rounded-xl border bg-white p-6 space-y-3">
        <h2 className="text-lg font-semibold">Что можно улучшить</h2>
        <p className="text-sm text-muted-foreground">{page.audit?.summary_text || '—'}</p>
        {findings.length > 0 ? (
          <div className="space-y-2">
            {findings.slice(0, 5).map((item, idx) => (
              <div key={`${item.title || 'finding'}-${idx}`} className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                <div className="font-medium text-sm">{item.title || 'Рекомендация'}</div>
                <div className="text-sm text-muted-foreground mt-1">{item.description || '—'}</div>
              </div>
            ))}
          </div>
        ) : null}
        {services.length > 0 ? (
          <div>
            <div className="text-sm font-medium mb-1">Текущие услуги в карточке</div>
            <div className="flex flex-wrap gap-2">
              {services.slice(0, 8).map((item, idx) => (
                <span key={`${item.current_name || 'service'}-${idx}`} className="inline-flex items-center rounded-full border border-gray-300 bg-white px-2 py-0.5 text-xs text-gray-700">
                  {item.current_name || 'Услуга'}
                </span>
              ))}
            </div>
          </div>
        ) : null}
        {actions.length > 0 ? (
          <div>
            <div className="text-sm font-medium mb-1">Рекомендованные шаги</div>
            <div className="space-y-1">
              {actions.slice(0, 5).map((item, idx) => (
                <div key={`${item.title || 'action'}-${idx}`} className="text-sm text-muted-foreground">
                  {idx + 1}. {item.title || 'Шаг'}{item.description ? ` — ${item.description}` : ''}
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-6 space-y-3">
        <h2 className="text-lg font-semibold">Предложение о партнёрстве</h2>
        {page.message ? (
          <div className="rounded-lg border border-amber-300 bg-white p-3 text-sm text-foreground whitespace-pre-wrap">
            {page.message}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">Текст оффера будет добавлен после генерации первого письма.</div>
        )}
        <div className="flex flex-wrap gap-2">
          {page.cta?.telegram_url ? (
            <a href={page.cta.telegram_url} target="_blank" rel="noreferrer">
              <Button>Написать в Telegram</Button>
            </a>
          ) : null}
          {page.cta?.whatsapp_url ? (
            <a href={page.cta.whatsapp_url} target="_blank" rel="noreferrer">
              <Button variant="outline">Написать в WhatsApp</Button>
            </a>
          ) : null}
          {page.cta?.email ? (
            <a href={`mailto:${page.cta.email}`}>
              <Button variant="outline">Отправить Email</Button>
            </a>
          ) : null}
          {page.cta?.website ? (
            <a href={page.cta.website} target="_blank" rel="noreferrer">
              <Button variant="outline">Сайт</Button>
            </a>
          ) : null}
          {page.source_url ? (
            <a href={page.source_url} target="_blank" rel="noreferrer">
              <Button variant="ghost">Открыть карточку на карте</Button>
            </a>
          ) : null}
        </div>
      </div>
    </div>
  );
};

export default PublicPartnershipOfferPage;
