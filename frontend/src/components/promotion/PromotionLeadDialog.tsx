import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useLocation } from 'react-router-dom';
import { CircleCheck, Loader2, Phone } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { promotionGoal } from '@/lib/promotionAnalytics';
import { promotionAttribution, type PromotionPage } from '@/content/promotionContent';


export function PromotionLeadDialog({ page, english, label, className }: {
  page: PromotionPage; english: boolean; label?: string; className?: string;
}) {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [consent, setConsent] = useState(false);
  const [validation, setValidation] = useState('');
  const [status, setStatus] = useState<'idle' | 'sending' | 'success' | 'error'>('idle');
  const lock = useRef(false);
  const attribution = useRef<Record<string, string>>({});
  const l = (ru: string, en: string) => english ? en : ru;

  useEffect(() => {
    const current = promotionAttribution(location.search);
    try {
      const stored: unknown = JSON.parse(sessionStorage.getItem('localos-promotion-source') || '{}');
      const safe: Record<string, string> = {};
      if (stored && typeof stored === 'object') {
        for (const [key, value] of Object.entries(stored)) {
          if (key.startsWith('utm_') && typeof value === 'string') safe[key] = value.slice(0, 160);
        }
      }
      attribution.current = Object.keys(current).length ? current : safe;
      if (Object.keys(current).length) sessionStorage.setItem('localos-promotion-source', JSON.stringify(current));
    } catch { attribution.current = current; }
  }, [location.search]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (lock.current || !consent) return;
    const digits = phone.replace(/\D/g, '').length;
    if (!name.trim() || !/^[+0-9() .−-]+$/.test(phone.trim()) || digits < 7 || digits > 15) {
      setValidation(l('Укажите имя и телефон: от 7 до 15 цифр, можно с кодом страны.', 'Enter your name and a phone number with 7 to 15 digits, including the country code if needed.'));
      return;
    }
    setValidation('');
    lock.current = true;
    setStatus('sending');
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch('/api/public/contact', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ request_kind: 'promotion', name: name.trim(), phone: phone.trim(), direction: page.key, page: page.path, attribution: attribution.current, personal_data_consent: true }),
      });
      const result: unknown = await response.json();
      if (!response.ok || !result || typeof result !== 'object' || !('success' in result) || result.success !== true) throw new Error('delivery_failed');
      setStatus('success');
      promotionGoal('promotion_request_accepted', page.key);
    } catch { setStatus('error'); promotionGoal('promotion_request_error', page.key); }
    finally { window.clearTimeout(timeout); lock.current = false; }
  };

  return <Dialog open={open} onOpenChange={(next) => {
    if (lock.current) return;
    setOpen(next);
    if (next) promotionGoal('promotion_form_open', page.key);
    if (next && status === 'success') { setStatus('idle'); setName(''); setPhone(''); setConsent(false); }
  }}>
    <DialogTrigger asChild><Button variant="brand" size="lg" className={className} data-localos-cta={`promotion-${page.key}`}>{label || l('Хочу клиентов', 'Find more customers')}</Button></DialogTrigger>
    <DialogContent className="promotion-dialog max-h-[90dvh] w-[calc(100%-2rem)] overflow-y-auto rounded-2xl bg-card p-6 sm:p-8">
      <DialogHeader>
        <span className="mb-3 inline-flex size-11 items-center justify-center rounded-xl bg-secondary text-primary"><Phone size={20} aria-hidden="true" /></span>
        <DialogTitle className="text-2xl">{status === 'success' ? l('Спасибо! Заявка принята', 'Thank you! Request received') : l('Обсудим вашу задачу', 'Let’s discuss your business')}</DialogTitle>
        <DialogDescription className="pt-2 leading-relaxed">{status === 'success' ? l('Менеджер свяжется с вами и обсудит продвижение.', 'A manager will contact you to discuss marketing and the next steps.') : l('Оставьте имя и телефон. Менеджер уточнит задачу и предложит состав работ.', 'Leave your name and phone number. A manager will contact you to discuss how we can help.')}</DialogDescription>
      </DialogHeader>
      {status === 'success' ? <div role="status" className="space-y-5"><CircleCheck className="size-10 text-success" aria-hidden="true" /><Button className="w-full" variant="outline" onClick={() => setOpen(false)}>{l('Вернуться на страницу', 'Back to the page')}</Button></div> : <form name={`promotion-${page.key}`} onSubmit={submit} className="space-y-5">
        <p className="text-sm text-muted-foreground">{l('Направление', 'Direction')}: <strong className="font-medium text-foreground">{page.key === 'home' ? l('Помогите выбрать', 'Help me choose') : page.label}</strong></p>
        <label className="block text-sm font-medium">{l('Имя', 'Name')}<Input className="mt-2 h-12 bg-card" name="name" autoComplete="name" required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} disabled={status === 'sending'} /></label>
        <label className="block text-sm font-medium">{l('Номер телефона', 'Phone number')}<Input className="mt-2 h-12 bg-card" name="phone" type="tel" inputMode="tel" autoComplete="tel" placeholder="+7 …" required minLength={7} maxLength={32} value={phone} onChange={(e) => setPhone(e.target.value)} disabled={status === 'sending'} /></label>
        <label className="flex cursor-pointer items-start gap-3 text-xs leading-relaxed text-muted-foreground"><input type="checkbox" required checked={consent} onChange={(e) => setConsent(e.target.checked)} disabled={status === 'sending'} className="mt-0.5 size-4 shrink-0 accent-primary" /><span>{l('Согласен на обработку персональных данных для ответа на заявку. ', 'I consent to processing my details to respond to this request. ')}<a className="underline underline-offset-2" href="/policy" target="_blank" rel="noreferrer">{l('Политика конфиденциальности', 'Privacy policy')}</a></span></label>
        {validation && <p role="alert" className="text-sm text-destructive">{validation}</p>}
        {status === 'error' && <p role="alert" className="text-sm text-destructive">{l('Не удалось подтвердить отправку. Данные сохранены в форме. Попробуйте позже или свяжитесь с нами через страницу «Контакты».', 'We could not confirm delivery. Your entries remain in the form. Try later or use the Contact page.')} <a href="/contact" className="underline">{l('Контакты', 'Contact')}</a></p>}
        <Button variant="brand" size="lg" type="submit" disabled={status === 'sending'} className="w-full">{status === 'sending' && <Loader2 className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />}{status === 'sending' ? l('Отправляем…', 'Sending…') : l('Отправить заявку', 'Send request')}</Button>
        <p className="text-center text-xs text-muted-foreground">{l('Заявка бесплатная. Условия работы обсудим с вами.', 'No registration or automatic service activation')}</p>
      </form>}
    </DialogContent>
  </Dialog>;
}
