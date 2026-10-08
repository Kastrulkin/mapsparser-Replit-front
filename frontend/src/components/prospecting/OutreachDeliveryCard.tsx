import { useEffect, useState } from 'react';
import { newAuth } from '@/lib/auth_new';
import { Button } from '@/components/ui/button';

type Delivery = { touch_id: string; delivery_status: string; provider_message_id?: string; error_text?: string; sent_at?: string };
type Campaign = { business_id: string; touches: Array<{ id: string; recipient?: string; sender_identity?: string; subject?: string; generated_text?: string; status: string }>; deliveries: Delivery[]; inbound_events?: Array<{ id: string; event_type: string }> };
const labels: Record<string, string> = { queued: 'В очереди', retry: 'Ожидает повторной попытки', sending: 'Отправляется', sent: 'Отправлено', delivered: 'Доставлено', failed: 'Не отправлено', paused: 'На паузе', scheduled: 'Ожидает отправки' };

/** Read the exact native campaign; this view never triggers or retries a send. */
export function OutreachDeliveryCard({ campaignId, businessId }: { campaignId?: string | null; businessId?: string | null }) {
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    setCampaign(null); setError('');
    if (!campaignId || !businessId) return;
    let active = true;
    const refresh = async () => {
      try {
        const payload = await newAuth.makeRequest(`/outreach/campaigns/${encodeURIComponent(campaignId)}`);
        if (!active) return;
        if (!payload.campaign || payload.campaign.business_id !== businessId) {
          setCampaign(null); setError('Письмо недоступно для выбранного бизнеса.'); return;
        }
        setCampaign(payload.campaign); setError('');
      } catch {
        if (active) setError('Не удалось обновить статус письма.');
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, [campaignId, businessId, retry]);
  if (!campaignId || !businessId) return null;
  return <section aria-label="Проверка отправки письма" className="rounded-xl border bg-background p-4 space-y-4">
    <div className="flex items-center justify-between gap-3"><h2 className="text-lg font-semibold">Ваше письмо</h2><Button variant="outline" size="sm" onClick={() => setRetry(value => value + 1)}>Обновить статус</Button></div>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {!campaign && !error && <p role="status">Загружаем письмо…</p>}
    {campaign?.touches.map(touch => {
      const delivery = campaign.deliveries.find(item => item.touch_id === touch.id);
      const status = delivery?.delivery_status || touch.status;
      const sent = ['sent', 'delivered'].includes(status);
      return <div key={touch.id} className="space-y-3">
        <p role="status" className="font-medium">{labels[status] || 'Статус требует проверки'}</p>
        <dl className="text-sm space-y-1"><div><dt className="inline text-muted-foreground">Кому: </dt><dd className="inline">{touch.recipient || 'Не указан'}</dd></div><div><dt className="inline text-muted-foreground">От: </dt><dd className="inline">{touch.sender_identity || 'Не указан'}</dd></div></dl>
        <h3 className="font-medium">{touch.subject}</h3><p className="whitespace-pre-wrap text-sm">{touch.generated_text}</p>
        <p className="text-sm text-muted-foreground">{sent ? 'Почтовый сервис подтвердил отправку. Это не подтверждение попадания во входящие.' : 'Подтверждения отправки пока нет. Повторно отправлять письмо не нужно.'}</p>
        {delivery?.error_text && <details><summary className="cursor-pointer text-sm">Причина остановки</summary><p className="text-sm">{delivery.error_text}</p></details>}
        {delivery?.sent_at && <p className="text-sm text-muted-foreground">Отправлено: {new Date(delivery.sent_at).toLocaleString()}</p>}
      </div>;
    })}
    {campaign && <p className="text-sm text-muted-foreground">Входящих событий: {campaign.inbound_events?.length || 0}</p>}
  </section>;
}
