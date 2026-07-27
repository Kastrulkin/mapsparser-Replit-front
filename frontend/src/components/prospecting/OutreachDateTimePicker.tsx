import { useMemo, useState } from 'react';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { CalendarDays, Check, Clock3 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

type OutreachDateTimePickerProps = {
  value: string;
  onChange: (value: string) => void;
  ariaLabel?: string;
};

const parseLocalDateTime = (value: string) => {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) return null;
  const date = new Date(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
    Number(match[4]),
    Number(match[5]),
    0,
    0,
  );
  return Number.isNaN(date.getTime()) ? null : date;
};

const localDateTimeValue = (date: Date) => {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  const hours = `${date.getHours()}`.padStart(2, '0');
  const minutes = `${date.getMinutes()}`.padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
};

const dateWithDefaultTime = (source?: Date) => {
  const date = source ? new Date(source) : new Date();
  if (!source) date.setHours(10, 0, 0, 0);
  return date;
};

export function OutreachDateTimePicker({
  value,
  onChange,
  ariaLabel = 'Дата и время первого касания',
}: OutreachDateTimePickerProps) {
  const [open, setOpen] = useState(false);
  const selected = useMemo(() => parseLocalDateTime(value), [value]);
  const selectedTime = selected ? format(selected, 'HH:mm') : '10:00';

  const chooseDay = (day?: Date) => {
    if (!day) return;
    const next = dateWithDefaultTime(selected || undefined);
    next.setFullYear(day.getFullYear(), day.getMonth(), day.getDate());
    onChange(localDateTimeValue(next));
  };

  const chooseRelativeDay = (offset: number) => {
    const day = new Date();
    day.setHours(0, 0, 0, 0);
    day.setDate(day.getDate() + offset);
    chooseDay(day);
  };

  const chooseTime = (time: string) => {
    const match = /^(\d{2}):(\d{2})$/.exec(time);
    if (!match) return;
    const next = dateWithDefaultTime(selected || undefined);
    next.setHours(Number(match[1]), Number(match[2]), 0, 0);
    onChange(localDateTimeValue(next));
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={ariaLabel}
          className="mt-2 flex min-h-12 w-full max-w-sm items-center gap-3 rounded-xl bg-white px-3.5 text-left shadow-[0_0_0_1px_rgba(15,23,42,0.12),0_1px_2px_-1px_rgba(15,23,42,0.08),0_4px_12px_-6px_rgba(15,23,42,0.16)] transition-[transform,box-shadow] hover:shadow-[0_0_0_1px_rgba(249,115,22,0.35),0_2px_5px_-2px_rgba(15,23,42,0.16)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-400 focus-visible:ring-offset-2 active:scale-[0.96]"
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-orange-50 text-orange-600">
            <CalendarDays className="h-4.5 w-4.5" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold text-slate-950">
              {selected ? format(selected, 'd MMMM, EEEE', { locale: ru }) : 'Выберите дату'}
            </span>
            <span className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500">
              <Clock3 className="h-3.5 w-3.5" />
              <span className="tabular-nums">{selected ? selectedTime : 'Укажите время'}</span>
            </span>
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        sideOffset={8}
        className="w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-2xl border-0 bg-white p-0 shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_12px_32px_-12px_rgba(15,23,42,0.28),0_4px_12px_-6px_rgba(15,23,42,0.18)]"
      >
        <div className="bg-slate-50 px-4 py-3 shadow-[inset_0_-1px_0_rgba(15,23,42,0.06)]">
          <div className="text-balance text-sm font-semibold text-slate-950">Когда отправить первый шаг</div>
          <div className="mt-1 text-pretty text-xs leading-5 text-slate-600">Следующие касания автоматически сдвинутся по заданным интервалам.</div>
          <div className="mt-3 flex gap-2">
            <Button type="button" variant="outline" size="sm" onClick={() => chooseRelativeDay(0)} className="min-h-10 flex-1 bg-white active:scale-[0.96]">
              Сегодня
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={() => chooseRelativeDay(1)} className="min-h-10 flex-1 bg-white active:scale-[0.96]">
              Завтра
            </Button>
          </div>
        </div>

        <Calendar
          mode="single"
          selected={selected || undefined}
          onSelect={chooseDay}
          locale={ru}
          weekStartsOn={1}
          className="mx-auto p-4"
          classNames={{
            caption_label: 'text-sm font-semibold capitalize text-slate-900',
            head_cell: 'w-9 rounded-md text-[0.72rem] font-medium uppercase text-slate-400',
            day: 'h-9 w-9 rounded-lg p-0 text-sm font-medium tabular-nums transition-[transform,background-color,color] hover:bg-orange-50 hover:text-orange-900 active:scale-[0.96]',
            day_selected: 'bg-orange-500 text-white hover:bg-orange-600 hover:text-white focus:bg-orange-500 focus:text-white',
            day_today: 'bg-slate-100 font-semibold text-slate-950',
            nav_button: 'h-9 w-9 rounded-lg border-0 bg-white p-0 text-slate-600 shadow-[0_0_0_1px_rgba(15,23,42,0.1)] opacity-100 transition-transform hover:bg-slate-50 active:scale-[0.96]',
          }}
        />

        <div className="flex items-end gap-3 bg-slate-50 px-4 py-3 shadow-[inset_0_1px_0_rgba(15,23,42,0.06)]">
          <label className="min-w-0 flex-1">
            <span className="text-xs font-semibold text-slate-700">Время отправки</span>
            <input
              type="time"
              value={selectedTime}
              onChange={(event) => chooseTime(event.target.value)}
              className="mt-1 min-h-11 w-full rounded-lg bg-white px-3 text-sm font-semibold tabular-nums text-slate-950 shadow-[0_0_0_1px_rgba(15,23,42,0.12)] focus:outline-none focus:ring-2 focus:ring-orange-400"
            />
          </label>
          <Button type="button" onClick={() => setOpen(false)} disabled={!selected} className="min-h-11 bg-slate-950 px-4 text-white hover:bg-slate-800 active:scale-[0.96]">
            <Check className="mr-2 h-4 w-4" />
            Готово
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
