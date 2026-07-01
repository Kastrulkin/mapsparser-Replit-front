import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { AlertTriangle, Loader2, MessageSquareWarning } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { api } from '@/services/api';
import { useToast } from '@/hooks/use-toast';

type BetaFeedbackBannerProps = {
  area: 'agents' | 'operator' | 'bookings';
  title: string;
  description: string;
  businessId?: string | null;
  businessName?: string | null;
};

export const BetaFeedbackBanner = ({
  area,
  title,
  description,
  businessId,
  businessName,
}: BetaFeedbackBannerProps) => {
  const location = useLocation();
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    const normalizedMessage = message.trim();
    if (!normalizedMessage) {
      toast({
        title: 'Опишите проблему',
        description: 'Добавьте пару слов: что именно сломалось или выглядит неправильно.',
        variant: 'destructive',
      });
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/dashboard-feedback', {
        area,
        business_id: businessId || null,
        business_name: businessName || '',
        page_path: location.pathname,
        message: normalizedMessage,
      });
      toast({
        title: 'Сообщение отправлено',
        description: 'Спасибо. Мы сохранили проблему и вернёмся к ней в beta-разборе.',
      });
      setOpen(false);
      setMessage('');
    } catch (error) {
      toast({
        title: 'Не удалось отправить сообщение',
        description: error instanceof Error ? error.message : 'Попробуйте ещё раз через минуту.',
        variant: 'destructive',
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div className="rounded-3xl border border-amber-200/80 bg-amber-50/90 px-5 py-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 space-y-1.5">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-700">
              <AlertTriangle className="h-3.5 w-3.5" />
              Beta
            </div>
            <div className="text-base font-semibold text-slate-950">{title}</div>
            <p className="max-w-3xl text-sm leading-6 text-slate-700">{description}</p>
          </div>
          <div className="flex shrink-0 items-center">
            <Button type="button" variant="outline" className="min-h-10 rounded-xl bg-white/90" onClick={() => setOpen(true)}>
              <MessageSquareWarning className="mr-2 h-4 w-4" />
              Сообщить о проблеме
            </Button>
          </div>
        </div>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl rounded-3xl border-slate-200 p-0">
          <div className="px-6 py-6">
            <DialogHeader>
              <DialogTitle>Сообщить о проблеме</DialogTitle>
              <DialogDescription>
                Опишите, что вы увидели в разделе. Мы сохраним сообщение вместе с контекстом страницы и бизнеса.
              </DialogDescription>
            </DialogHeader>
            <div className="mt-5 space-y-3">
              <div className="rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-sm text-slate-600">
                Раздел: <span className="font-medium text-slate-900">{title}</span>
                {businessName ? <span className="ml-2 text-slate-500">· {businessName}</span> : null}
              </div>
              <Textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Например: после запуска теста не видно результат, кнопка не срабатывает, таблица выглядит сломанной..."
                className="min-h-[150px] rounded-2xl"
              />
            </div>
          </div>
          <DialogFooter className="border-t border-slate-100 px-6 py-4">
            <Button type="button" variant="outline" onClick={() => setOpen(false)} disabled={submitting}>
              Отмена
            </Button>
            <Button type="button" onClick={submit} disabled={submitting || !message.trim()}>
              {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Отправить
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};
