import { AlertTriangle, CalendarDays, Clock3 } from 'lucide-react';

export type OutreachScheduleTouch = {
  id?: string;
  sequence_index?: number;
  channel?: string;
  scheduled_at?: string | null;
  day_offset?: number;
  subject?: string | null;
  text?: string | null;
  generated_text?: string | null;
  approved_text?: string | null;
  status?: string | null;
};

type OutreachScheduleCalendarProps = {
  touches: OutreachScheduleTouch[];
  modeLabel?: string;
};

const CHANNEL_LABELS: Record<string, string> = {
  telegram: 'Telegram',
  email: 'Email',
  max: 'MAX',
  vk: 'VK',
  whatsapp: 'WhatsApp',
  sms: 'SMS',
  manual: 'Вручную',
};

const CHANNEL_TONES: Record<string, string> = {
  telegram: 'bg-sky-50 text-sky-950 ring-sky-200',
  email: 'bg-violet-50 text-violet-950 ring-violet-200',
  max: 'bg-indigo-50 text-indigo-950 ring-indigo-200',
  vk: 'bg-blue-50 text-blue-950 ring-blue-200',
  whatsapp: 'bg-emerald-50 text-emerald-950 ring-emerald-200',
  sms: 'bg-amber-50 text-amber-950 ring-amber-200',
  manual: 'bg-slate-100 text-slate-900 ring-slate-200',
};

const STATUS_LABELS: Record<string, string> = {
  draft: 'Черновик',
  approved: 'Подтверждено',
  scheduled: 'Запланировано',
  queued: 'В очереди',
  sent: 'Отправлено',
  delivered: 'Доставлено',
  awaiting_manual_send: 'Нужно отправить вручную',
  manual_sent: 'Отправлено вручную',
  paused: 'На паузе',
  cancelled: 'Отменено',
  failed: 'Ошибка',
  reply_cancelled: 'Остановлено ответом',
};

const dateKey = (date: Date) => {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const startOfCalendarWeek = (date: Date) => {
  const result = new Date(date);
  result.setHours(0, 0, 0, 0);
  const weekday = result.getDay() || 7;
  result.setDate(result.getDate() - weekday + 1);
  return result;
};

const endOfCalendarWeek = (date: Date) => {
  const result = startOfCalendarWeek(date);
  result.setDate(result.getDate() + 6);
  result.setHours(23, 59, 59, 999);
  return result;
};

const touchDate = (touch: OutreachScheduleTouch) => {
  const date = new Date(String(touch.scheduled_at || ''));
  return Number.isNaN(date.getTime()) ? null : date;
};

const formatPeriod = (first: Date, last: Date) => {
  const formatter = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' });
  return `${formatter.format(first)} — ${formatter.format(last)}`;
};

const formatDayTitle = (date: Date) => new Intl.DateTimeFormat('ru-RU', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
}).format(date);

const formatTime = (date: Date) => date.toLocaleTimeString('ru-RU', {
  hour: '2-digit',
  minute: '2-digit',
});

export const defaultOutreachStartValue = (baseDate = new Date()) => {
  const result = new Date(baseDate);
  result.setSeconds(0, 0);
  if (result.getHours() >= 19) {
    result.setDate(result.getDate() + 1);
    result.setHours(10, 0, 0, 0);
  } else {
    result.setMinutes(result.getMinutes() < 30 ? 30 : 0);
    if (result.getMinutes() === 0) result.setHours(result.getHours() + 1);
  }
  const year = result.getFullYear();
  const month = `${result.getMonth() + 1}`.padStart(2, '0');
  const day = `${result.getDate()}`.padStart(2, '0');
  const hours = `${result.getHours()}`.padStart(2, '0');
  const minutes = `${result.getMinutes()}`.padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
};

export const outreachStartIso = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
};

export const buildProjectedOutreachTouches = (
  channels: string[],
  days: number[],
  startValue: string,
  sourceTouches: OutreachScheduleTouch[] = [],
) => {
  const start = new Date(startValue);
  if (Number.isNaN(start.getTime())) return [];
  return channels.map((channel, index) => {
    const scheduledAt = new Date(start);
    scheduledAt.setDate(start.getDate() + Math.max(0, Number(days[index] || 0)));
    const source = sourceTouches[index] || {};
    return {
      ...source,
      id: source.id || `projected-${index}`,
      sequence_index: index,
      channel,
      day_offset: Math.max(0, Number(days[index] || 0)),
      scheduled_at: scheduledAt.toISOString(),
      status: source.status || 'draft',
    };
  });
};

export function OutreachScheduleCalendar({
  touches,
  modeLabel = 'Предпросмотр',
}: OutreachScheduleCalendarProps) {
  const scheduledTouches = touches
    .map((touch) => ({ touch, date: touchDate(touch) }))
    .filter((item) => item.date !== null)
    .sort((left, right) => Number(left.date?.getTime() || 0) - Number(right.date?.getTime() || 0));

  if (scheduledTouches.length === 0) {
    return (
      <section className="rounded-2xl bg-white p-4 shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_1px_2px_-1px_rgba(15,23,42,0.06),0_2px_4px_rgba(15,23,42,0.04)]">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
            <CalendarDays className="h-5 w-5" />
          </span>
          <div>
            <h4 className="text-balance text-sm font-semibold text-slate-950">Календарь касаний</h4>
            <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">Выберите дату начала и подготовьте цепочку — здесь появятся шаги, даты и каналы.</p>
          </div>
        </div>
      </section>
    );
  }

  const firstDate = scheduledTouches[0].date || new Date();
  const lastDate = scheduledTouches[scheduledTouches.length - 1].date || firstDate;
  const calendarStart = startOfCalendarWeek(firstDate);
  const calendarEnd = endOfCalendarWeek(lastDate);
  const calendarDays: Date[] = [];
  const cursor = new Date(calendarStart);
  while (cursor <= calendarEnd && calendarDays.length < 42) {
    calendarDays.push(new Date(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }
  const touchesByDate = new Map<string, typeof scheduledTouches>();
  scheduledTouches.forEach((item) => {
    if (!item.date) return;
    const key = dateKey(item.date);
    touchesByDate.set(key, [...(touchesByDate.get(key) || []), item]);
  });
  const now = new Date();

  const renderEvent = (item: typeof scheduledTouches[number]) => {
    if (!item.date) return null;
    const channel = String(item.touch.channel || 'manual');
    const isPast = item.date.getTime() < now.getTime()
      && !['sent', 'delivered', 'manual_sent', 'cancelled', 'reply_cancelled'].includes(String(item.touch.status || ''));
    const label = CHANNEL_LABELS[channel] || channel;
    return (
      <article
        key={item.touch.id || `${item.touch.sequence_index}-${channel}`}
        className={`rounded-lg p-2.5 ring-1 ring-inset ${isPast ? 'bg-rose-50 text-rose-950 ring-rose-200' : CHANNEL_TONES[channel] || CHANNEL_TONES.manual}`}
      >
        <div className="flex flex-wrap items-center justify-between gap-1.5 text-[11px] font-semibold">
          <span>Шаг {Number(item.touch.sequence_index || 0) + 1}</span>
          <span className="inline-flex items-center gap-1 tabular-nums"><Clock3 className="h-3 w-3" />{formatTime(item.date)}</span>
        </div>
        <div className="mt-1.5 text-xs font-semibold">{label}</div>
        {isPast ? (
          <div className="mt-1.5 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.05em] text-rose-700">
            <AlertTriangle className="h-3 w-3" /> Дата уже прошла
          </div>
        ) : item.touch.status ? (
          <div className="mt-1.5 text-[10px] font-semibold uppercase tracking-[0.05em] opacity-70">
            {STATUS_LABELS[String(item.touch.status)] || item.touch.status}
          </div>
        ) : null}
      </article>
    );
  };

  return (
    <section className="rounded-2xl bg-white p-4 shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_1px_2px_-1px_rgba(15,23,42,0.06),0_2px_4px_rgba(15,23,42,0.04)]" aria-labelledby="outreach-calendar-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-orange-50 text-orange-700">
            <CalendarDays className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <h4 id="outreach-calendar-title" className="text-balance text-sm font-semibold text-slate-950">Календарь касаний</h4>
            <p className="mt-1 text-pretty text-xs leading-5 text-slate-600">Когда и через какой канал пройдёт каждый шаг цепочки.</p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs font-semibold text-slate-500">{modeLabel}</div>
          <div className="mt-1 text-sm font-semibold text-slate-950 tabular-nums">{formatPeriod(firstDate, lastDate)}</div>
        </div>
      </div>

      <div className="mt-4 space-y-2 sm:hidden">
        {scheduledTouches.map((item) => (
          <div key={item.touch.id || `${item.touch.sequence_index}-${item.touch.channel}`}>
            {item.date ? <div className="mb-1.5 text-xs font-semibold capitalize text-slate-500">{formatDayTitle(item.date)}</div> : null}
            {renderEvent(item)}
          </div>
        ))}
      </div>

      <div className="mt-4 hidden overflow-x-auto pb-1 sm:block">
        <div className="min-w-[760px]">
          <div className="grid grid-cols-7 gap-1 text-center text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-400">
            {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((weekday) => <div key={weekday} className="py-1">{weekday}</div>)}
          </div>
          <div className="mt-1 grid grid-cols-7 gap-1">
            {calendarDays.map((day) => {
              const dayTouches = touchesByDate.get(dateKey(day)) || [];
              const isToday = dateKey(day) === dateKey(now);
              return (
                <div key={dateKey(day)} className={`min-h-32 rounded-lg p-2 ${dayTouches.length ? 'bg-slate-50' : 'bg-slate-50/50'} ${isToday ? 'ring-1 ring-inset ring-orange-300' : ''}`}>
                  <div className={`text-xs font-semibold capitalize tabular-nums ${isToday ? 'text-orange-700' : 'text-slate-500'}`}>
                    {new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' }).format(day)}
                  </div>
                  <div className="mt-2 space-y-1.5">{dayTouches.map((item) => renderEvent(item))}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
