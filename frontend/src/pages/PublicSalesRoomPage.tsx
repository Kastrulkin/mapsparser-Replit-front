import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ArrowUpRight, CheckCircle2, ExternalLink, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { newAuth } from '@/lib/auth_new';

type SalesRoomPayload = {
  slug?: string;
  public_url?: string;
  mode?: string;
  data_mode?: string;
  business?: {
    name?: string;
  };
  recipient?: {
    name?: string;
    category?: string;
    city?: string;
    address?: string;
    source_url?: string;
  };
  proposal?: {
    title?: string;
    summary?: string;
    bullets?: string[];
    next_step?: string;
  };
  audit?: {
    available?: boolean;
    public_url?: string | null;
    summary_score?: number | null;
    health_label?: string;
    summary_text?: string;
    findings?: Array<{ title?: string; description?: string } | string>;
    recommended_actions?: Array<{ title?: string; description?: string } | string>;
  };
  match?: {
    available?: boolean;
    match_score?: number | null;
    score_explanation?: string;
    offer_angles?: string[];
    reason_codes?: string[];
  };
  cta?: {
    primary_label?: string;
    secondary_label?: string;
    secondary_url?: string | null;
  };
  localos?: {
    badge?: string;
    description?: string;
  };
};

const textFromItem = (item: { title?: string; description?: string } | string) => {
  if (typeof item === 'string') return item;
  return item.title || item.description || '';
};

const roomModeLabel = (mode?: string) => {
  if (mode === 'partner_search') return 'Партнёрское предложение';
  if (mode === 'client_search') return 'Разбор роста';
  return 'Предложение LocalOS';
};

export default function PublicSalesRoomPage() {
  const { roomSlug } = useParams<{ roomSlug: string }>();
  const [room, setRoom] = useState<SalesRoomPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const run = async () => {
      if (!roomSlug) return;
      try {
        setLoading(true);
        setError(null);
        const response = await newAuth.makeRequest(`/sales-rooms/public/${encodeURIComponent(roomSlug)}`, {
          method: 'GET',
        });
        setRoom(response?.room || null);
      } catch (loadError) {
        const message = loadError instanceof Error ? loadError.message : 'Не удалось загрузить комнату';
        setError(message);
        setRoom(null);
      } finally {
        setLoading(false);
      }
    };
    void run();
  }, [roomSlug]);

  const bullets = useMemo(() => {
    const source = room?.proposal?.bullets;
    if (Array.isArray(source) && source.length > 0) return source.slice(0, 3);
    return [];
  }, [room?.proposal?.bullets]);

  const auditFindings = useMemo(() => {
    const source = room?.audit?.findings;
    if (!Array.isArray(source)) return [];
    return source.map(textFromItem).filter(Boolean).slice(0, 3);
  }, [room?.audit?.findings]);

  const recordEvent = async (eventType: string, metadata?: Record<string, unknown>) => {
    if (!roomSlug) return;
    try {
      await newAuth.makeRequest(`/sales-rooms/public/${encodeURIComponent(roomSlug)}/events`, {
        method: 'POST',
        body: JSON.stringify({ event_type: eventType, metadata: metadata || {} }),
      });
    } catch {
      // Public analytics should never block the recipient.
    }
  };

  const openSecondary = () => {
    const url = room?.cta?.secondary_url || room?.audit?.public_url || '';
    if (!url) return;
    void recordEvent(room?.audit?.public_url ? 'audit_open' : 'cta_click', { target: url });
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <div className="rounded-2xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-500 shadow-sm">
          Загружаем предложение...
        </div>
      </main>
    );
  }

  if (error || !room) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <div className="max-w-md rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">
          <div className="text-lg font-semibold text-slate-950">Комната не найдена</div>
          <p className="mt-2 text-sm leading-6 text-slate-500">{error || 'Ссылка устарела или была удалена.'}</p>
        </div>
      </main>
    );
  }

  const recipientName = room.recipient?.name || 'компания';
  const businessName = room.business?.name || 'LocalOS';
  const hasAudit = Boolean(room.audit?.available);
  const hasMatch = Boolean(room.match?.available);

  return (
    <main className="min-h-screen bg-[#f6f7fb] text-slate-950">
      <section className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-6 py-10 md:px-10 md:py-14">
        <div className="flex items-center justify-between gap-4">
          <div className="text-xs font-bold uppercase tracking-[0.28em] text-orange-500">LocalOS</div>
          <div className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-500">
            {room.localos?.badge || 'Сделано в LocalOS'}
          </div>
        </div>

        <div className="mt-14 max-w-4xl">
          <div className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500">{roomModeLabel(room.mode)}</div>
          <h1 className="mt-5 text-4xl font-black tracking-tight text-slate-950 md:text-6xl">
            {room.proposal?.title || `Предложение для ${recipientName}`}
          </h1>
          <p className="mt-6 max-w-3xl text-xl leading-8 text-slate-600">
            {room.proposal?.summary || `${businessName} подготовил короткое предложение для ${recipientName}.`}
          </p>
        </div>

        <div className="mt-14 grid gap-5 md:grid-cols-3">
          {bullets.map((item) => (
            <div key={item} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <CheckCircle2 className="h-5 w-5 text-orange-500" />
              <p className="mt-4 text-base font-semibold leading-6 text-slate-900">{item}</p>
            </div>
          ))}
        </div>

        <div className="mt-8 grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center gap-2 text-sm font-bold uppercase tracking-[0.18em] text-slate-500">
              <Sparkles className="h-4 w-4 text-orange-500" />
              {hasAudit ? 'Что нашёл LocalOS' : 'Основа предложения'}
            </div>
            <div className="mt-5 space-y-3">
              {hasAudit && room.audit?.summary_text ? (
                <p className="text-base leading-7 text-slate-600">{room.audit.summary_text}</p>
              ) : (
                <p className="text-base leading-7 text-slate-600">
                  Здесь собраны предложение, следующий шаг и материалы для обсуждения.
                </p>
              )}
              {auditFindings.length > 0 ? (
                <div className="grid gap-2 pt-2">
                  {auditFindings.map((item) => (
                    <div key={item} className="rounded-xl bg-slate-50 px-4 py-3 text-sm font-medium text-slate-700">
                      {item}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="text-sm font-bold uppercase tracking-[0.18em] text-slate-500">
              {hasMatch ? 'Match услуг' : 'Следующий шаг'}
            </div>
            {hasMatch ? (
              <div className="mt-5">
                <div className="text-5xl font-black text-orange-500">{room.match?.match_score ?? 0}%</div>
                <p className="mt-4 text-sm leading-6 text-slate-600">
                  {room.match?.score_explanation || 'LocalOS сопоставил услуги и нашёл основу для предложения.'}
                </p>
              </div>
            ) : (
              <p className="mt-5 text-base leading-7 text-slate-600">
                {room.proposal?.next_step || 'Откройте предложение и выберите удобный следующий шаг.'}
              </p>
            )}
            <div className="mt-6 flex flex-col gap-3">
              <Button className="justify-between bg-slate-950 text-white hover:bg-slate-800" onClick={() => void recordEvent('cta_click', { target: 'primary' })}>
                {room.cta?.primary_label || 'Обсудить предложение'}
                <ArrowUpRight className="h-4 w-4" />
              </Button>
              {(room.cta?.secondary_url || room.audit?.public_url) ? (
                <Button variant="outline" className="justify-between" onClick={openSecondary}>
                  {room.cta?.secondary_label || 'Посмотреть аудит'}
                  <ExternalLink className="h-4 w-4" />
                </Button>
              ) : null}
            </div>
          </section>
        </div>

        <div className="mt-auto pt-12 text-sm leading-6 text-slate-500">
          {room.localos?.description || 'LocalOS помогает локальному бизнесу превращать спрос в клиентов и выручку.'}
        </div>
      </section>
    </main>
  );
}
