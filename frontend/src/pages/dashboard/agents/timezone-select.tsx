import { useMemo, useState } from 'react';
import { Check, ChevronsUpDown, Globe2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';

const FALLBACK_TIMEZONES = [
  'UTC',
  'Africa/Cairo',
  'Africa/Casablanca',
  'Africa/Johannesburg',
  'America/Anchorage',
  'America/Argentina/Buenos_Aires',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Mexico_City',
  'America/New_York',
  'America/Sao_Paulo',
  'America/Toronto',
  'America/Vancouver',
  'Asia/Almaty',
  'Asia/Baku',
  'Asia/Bangkok',
  'Asia/Dubai',
  'Asia/Hong_Kong',
  'Asia/Jakarta',
  'Asia/Jerusalem',
  'Asia/Kolkata',
  'Asia/Novosibirsk',
  'Asia/Seoul',
  'Asia/Shanghai',
  'Asia/Singapore',
  'Asia/Tbilisi',
  'Asia/Tokyo',
  'Asia/Vladivostok',
  'Asia/Yekaterinburg',
  'Australia/Brisbane',
  'Australia/Melbourne',
  'Australia/Perth',
  'Australia/Sydney',
  'Europe/Amsterdam',
  'Europe/Athens',
  'Europe/Belgrade',
  'Europe/Berlin',
  'Europe/Brussels',
  'Europe/Bucharest',
  'Europe/Budapest',
  'Europe/Copenhagen',
  'Europe/Helsinki',
  'Europe/Istanbul',
  'Europe/Kaliningrad',
  'Europe/Kyiv',
  'Europe/Lisbon',
  'Europe/London',
  'Europe/Madrid',
  'Europe/Minsk',
  'Europe/Moscow',
  'Europe/Oslo',
  'Europe/Paris',
  'Europe/Prague',
  'Europe/Riga',
  'Europe/Rome',
  'Europe/Samara',
  'Europe/Stockholm',
  'Europe/Tallinn',
  'Europe/Vienna',
  'Europe/Vilnius',
  'Europe/Warsaw',
  'Europe/Zurich',
  'Pacific/Auckland',
  'Pacific/Honolulu',
];

const CITY_NAMES: Record<string, string> = {
  'Europe/Moscow': 'Москва',
  'Europe/Tallinn': 'Таллин',
  'Europe/Helsinki': 'Хельсинки',
  'Europe/Riga': 'Рига',
  'Europe/Vilnius': 'Вильнюс',
  'Europe/Kyiv': 'Киев',
  'Europe/Minsk': 'Минск',
  'Asia/Almaty': 'Алматы',
  'Asia/Yekaterinburg': 'Екатеринбург',
  'Asia/Novosibirsk': 'Новосибирск',
  'Asia/Vladivostok': 'Владивосток',
  UTC: 'UTC',
};

const supportedTimezones = () => {
  try {
    const values = Intl.supportedValuesOf('timeZone');
    return Array.from(new Set(['UTC', ...values])).sort((left, right) => left.localeCompare(right));
  } catch {
    return FALLBACK_TIMEZONES;
  }
};

const timezoneCityName = (timezone: string) => {
  if (CITY_NAMES[timezone]) return CITY_NAMES[timezone];
  const parts = timezone.split('/');
  return String(parts[parts.length - 1] || timezone).replaceAll('_', ' ');
};

const timezoneOffset = (timezone: string) => {
  try {
    const part = new Intl.DateTimeFormat('ru-RU', {
      timeZone: timezone,
      timeZoneName: 'shortOffset',
      hour: '2-digit',
    }).formatToParts(new Date()).find((item) => item.type === 'timeZoneName');
    return String(part?.value || '').replace('GMT', 'UTC');
  } catch {
    return '';
  }
};

export const TimezoneSelect = ({
  value,
  onChange,
  className,
  ariaLabel = 'Часовой пояс',
}: {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  ariaLabel?: string;
}) => {
  const [open, setOpen] = useState(false);
  const options = useMemo(() => {
    const timezones = supportedTimezones();
    const values = value && !timezones.includes(value) ? [value, ...timezones] : timezones;
    return values.map((timezone) => ({
      timezone,
      city: timezoneCityName(timezone),
      offset: timezoneOffset(timezone),
    }));
  }, [value]);
  const selected = options.find((option) => option.timezone === value) || options[0];

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-label={ariaLabel}
          className={cn('min-h-10 w-full justify-between bg-white px-3 font-normal active:scale-[0.96] transition-transform', className)}
        >
          <span className="flex min-w-0 items-center gap-2 text-left">
            <Globe2 className="h-4 w-4 shrink-0 text-slate-500" />
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium text-slate-900">{selected?.city || value}</span>
              <span className="block truncate text-xs text-slate-500">{selected?.timezone || value}{selected?.offset ? ` · ${selected.offset}` : ''}</span>
            </span>
          </span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 text-slate-400" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[min(24rem,calc(100vw-2rem))] p-0">
        <Command>
          <CommandInput placeholder="Найти город или Europe/Paris" />
          <CommandList className="max-h-80">
            <CommandEmpty>Часовой пояс не найден</CommandEmpty>
            <CommandGroup heading={`${options.length} часовых поясов`}>
              {options.map((option) => (
                <CommandItem
                  key={option.timezone}
                  value={`${option.city} ${option.timezone} ${option.offset}`}
                  onSelect={() => {
                    onChange(option.timezone);
                    setOpen(false);
                  }}
                  className="min-h-12 gap-3"
                >
                  <Check className={cn('h-4 w-4 shrink-0', value === option.timezone ? 'opacity-100' : 'opacity-0')} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-slate-900">{option.city}</span>
                    <span className="block truncate text-xs text-slate-500">{option.timezone}{option.offset ? ` · ${option.offset}` : ''}</span>
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
};
