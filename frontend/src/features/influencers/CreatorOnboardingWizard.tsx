import { ArrowLeft, ArrowRight, Check, Link2, Loader2, MapPin, Sparkles, UserRound } from 'lucide-react';
import { useMemo, useState } from 'react';

import logo from '@/assets/images/logo.png';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { CreatorCityCombobox } from './CreatorCityCombobox';

type CreatorChannel = { platform: string; url?: string };

type CreatorOnboardingProfile = {
  display_name: string;
  description?: string;
  home_city?: string;
  home_district?: string;
  primary_city?: string;
  primary_area?: string;
  phone?: string;
  travel_radius?: string;
  accepts_barter?: boolean;
  formats?: string[];
  channels?: CreatorChannel[];
};

type CreatorOnboardingWizardProps = {
  profile: CreatorOnboardingProfile;
  cityOptions: string[];
  onComplete: (payload: Record<string, unknown>) => Promise<void>;
};

const platforms = [
  { key: 'telegram', label: 'Telegram', placeholder: 't.me/username' },
  { key: 'instagram', label: 'Instagram', placeholder: 'instagram.com/username' },
  { key: 'vk', label: 'VK', placeholder: 'vk.com/username' },
  { key: 'youtube', label: 'YouTube', placeholder: 'youtube.com/@username' },
  { key: 'threads', label: 'Threads', placeholder: 'threads.net/@username' },
  { key: 'tiktok', label: 'TikTok', placeholder: 'tiktok.com/@username' },
];

const formats = [
  { key: 'post', label: 'Пост' },
  { key: 'story', label: 'Stories' },
  { key: 'short_video', label: 'Короткое видео' },
  { key: 'video', label: 'Видео или выпуск' },
  { key: 'review', label: 'Обзор места или услуги' },
];

const travelOptions = [
  { key: 'district', label: 'Только свой район' },
  { key: 'city', label: 'По всему городу' },
  { key: 'region', label: 'Город и область' },
  { key: 'other_cities', label: 'Готов(а) ездить в другие города' },
];

const toggle = (values: string[], value: string) => values.includes(value)
  ? values.filter((item) => item !== value)
  : [...values, value];

export const CreatorOnboardingWizard = ({ profile, cityOptions, onComplete }: CreatorOnboardingWizardProps) => {
  const initialChannels = useMemo(() => Object.fromEntries((profile.channels || []).map((channel) => [channel.platform, channel.url || ''])), [profile.channels]);
  const [step, setStep] = useState(1);
  const [displayName, setDisplayName] = useState(profile.display_name || '');
  const [description, setDescription] = useState(profile.description || '');
  const [phone, setPhone] = useState(profile.phone || '');
  const [selectedPlatforms, setSelectedPlatforms] = useState((profile.channels || []).map((channel) => channel.platform).filter((platform) => platforms.some((item) => item.key === platform)));
  const [selectedFormats, setSelectedFormats] = useState(profile.formats || []);
  const [acceptsBarter, setAcceptsBarter] = useState<boolean | null>(typeof profile.accepts_barter === 'boolean' ? profile.accepts_barter : null);
  const [homeCity, setHomeCity] = useState(profile.home_city || profile.primary_city || '');
  const [homeDistrict, setHomeDistrict] = useState(profile.home_district || profile.primary_area || '');
  const [metroStations, setMetroStations] = useState('');
  const [travelRadius, setTravelRadius] = useState(profile.travel_radius || '');
  const [channelUrls, setChannelUrls] = useState<Record<string, string>>(initialChannels);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const stepValid = step === 1
    ? Boolean(displayName.trim())
    : step === 2
      ? selectedPlatforms.length > 0 && selectedFormats.length > 0 && acceptsBarter !== null
      : step === 3
        ? Boolean(homeCity && travelRadius)
        : selectedPlatforms.every((platform) => Boolean(channelUrls[platform]?.trim()));

  const next = () => { setError(''); if (stepValid) setStep((current) => Math.min(current + 1, 4)); };
  const back = () => { setError(''); setStep((current) => Math.max(current - 1, 1)); };
  const submit = async () => {
    if (!stepValid || acceptsBarter === null) return;
    setBusy(true); setError('');
    try {
      const travelLabel = travelOptions.find((item) => item.key === travelRadius)?.label || '';
      await onComplete({
        display_name: displayName.trim(),
        description: description.trim(),
        phone: phone.trim(),
        primary_city: homeCity,
        primary_area: homeDistrict.trim(),
        home_city: homeCity,
        home_district: homeDistrict.trim(),
        metro_stations: metroStations.split(',').map((item) => item.trim()).filter(Boolean),
        content_geographies: [homeCity, homeDistrict.trim()].filter(Boolean),
        formats: selectedFormats,
        accepts_barter: acceptsBarter,
        availability_text: travelLabel,
        travel_radius: travelRadius,
        channels: selectedPlatforms.map((platform) => ({ platform, url: channelUrls[platform].trim() })),
        onboarding_completed: true,
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось завершить регистрацию.');
    } finally {
      setBusy(false);
    }
  };

  const headings = [
    ['Расскажите о себе', 'Эти данные помогут LocalOS обращаться к вам и подобрать релевантные предложения.'],
    ['Где и как вы публикуете', 'Выберите площадки, форматы и подходящие условия сотрудничества.'],
    ['Где вы готовы работать', 'Уточните город и расстояние, на которое готовы выезжать.'],
    ['Добавьте свои площадки', 'Укажите ссылки на страницы, где вы публикуете контент.'],
  ];
  const [heading, descriptionText] = headings[step - 1];

  return <main className="min-h-screen bg-slate-50 px-4 py-6 text-slate-950 antialiased sm:py-10">
    <section className="mx-auto w-full max-w-3xl rounded-[32px] bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_28px_80px_-42px_rgba(15,23,42,0.42)] sm:p-9">
      <header className="flex items-center justify-between gap-4"><div className="flex items-center gap-3"><img src={logo} alt="LocalOS" className="h-10 w-10 rounded-xl object-cover outline outline-1 -outline-offset-1 outline-black/10" /><div><strong className="block text-sm">LocalOS</strong><span className="text-xs text-slate-500">регистрация автора</span></div></div><span className="text-sm font-semibold tabular-nums text-slate-500">{step} из 4</span></header>
      <div className="mt-7 grid grid-cols-4 gap-2" aria-label={`Шаг ${step} из 4`}>{[1, 2, 3, 4].map((item) => <span key={item} className={cn('h-1.5 rounded-full transition-colors', item <= step ? 'bg-orange-500' : 'bg-slate-200')} />)}</div>
      <div className="mt-8 flex items-start gap-4"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-orange-50 font-bold text-orange-700 tabular-nums">{step}</span><div><h1 className="text-balance text-2xl font-semibold tracking-tight sm:text-3xl">{heading}</h1><p className="mt-2 text-pretty text-sm leading-6 text-slate-500">{descriptionText}</p></div></div>

      <div className="mt-8 min-h-[330px]">
        {step === 1 ? <div className="grid gap-5 sm:grid-cols-2"><label className="text-sm font-semibold text-slate-700 sm:col-span-2">Имя или название блога <span className="text-rose-600">*</span><Input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Как к вам обращаться" className="mt-2 min-h-12 rounded-xl" /></label><label className="text-sm font-semibold text-slate-700">Телефон <span className="font-normal text-slate-400">необязательно</span><Input value={phone} onChange={(event) => setPhone(event.target.value)} type="tel" placeholder="+7 999 000-00-00" className="mt-2 min-h-12 rounded-xl" /></label><div className="hidden sm:block" /><label className="text-sm font-semibold text-slate-700 sm:col-span-2">О чём вы пишете <span className="font-normal text-slate-400">необязательно</span><Textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Например: рассказываю о семейных местах Петербурга и полезных услугах для родителей" className="mt-2 min-h-28 rounded-xl" /></label></div> : null}

        {step === 2 ? <div className="space-y-7"><fieldset><legend className="text-sm font-semibold text-slate-800">Площадки <span className="text-rose-600">*</span></legend><p className="mt-1 text-xs text-slate-500">Можно выбрать несколько.</p><div className="mt-3 grid gap-2 sm:grid-cols-3">{platforms.map((platform) => { const selected = selectedPlatforms.includes(platform.key); return <button key={platform.key} type="button" role="checkbox" aria-checked={selected} onClick={() => setSelectedPlatforms(toggle(selectedPlatforms, platform.key))} className={cn('flex min-h-12 items-center justify-between rounded-xl px-4 text-sm font-semibold transition-[background-color,color,box-shadow,transform] active:scale-[0.96]', selected ? 'bg-slate-950 text-white shadow-sm' : 'bg-slate-50 text-slate-700 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]')}><span>{platform.label}</span><Check className={cn('h-4 w-4 transition-opacity', selected ? 'opacity-100' : 'opacity-0')} /></button>; })}</div></fieldset><fieldset><legend className="text-sm font-semibold text-slate-800">Форматы <span className="text-rose-600">*</span></legend><div className="mt-3 grid gap-2 sm:grid-cols-2">{formats.map((format) => { const selected = selectedFormats.includes(format.key); return <button key={format.key} type="button" role="checkbox" aria-checked={selected} onClick={() => setSelectedFormats(toggle(selectedFormats, format.key))} className={cn('flex min-h-12 items-center justify-between rounded-xl px-4 text-left text-sm transition-[background-color,color,box-shadow,transform] active:scale-[0.96]', selected ? 'bg-orange-50 font-semibold text-orange-900 shadow-[inset_0_0_0_1px_rgba(234,88,12,0.2)]' : 'bg-slate-50 text-slate-700 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]')}><span>{format.label}</span><Check className={cn('h-4 w-4 text-orange-700 transition-opacity', selected ? 'opacity-100' : 'opacity-0')} /></button>; })}</div></fieldset><fieldset><legend className="text-sm font-semibold text-slate-800">Рассматриваете бартер? <span className="text-rose-600">*</span></legend><div className="mt-3 grid grid-cols-2 gap-2"><button type="button" aria-pressed={acceptsBarter === true} onClick={() => setAcceptsBarter(true)} className={cn('min-h-12 rounded-xl px-4 text-sm font-semibold transition-[background-color,color,box-shadow,transform] active:scale-[0.96]', acceptsBarter === true ? 'bg-emerald-700 text-white' : 'bg-slate-50 text-slate-700 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]')}>Да, рассматриваю</button><button type="button" aria-pressed={acceptsBarter === false} onClick={() => setAcceptsBarter(false)} className={cn('min-h-12 rounded-xl px-4 text-sm font-semibold transition-[background-color,color,box-shadow,transform] active:scale-[0.96]', acceptsBarter === false ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-700 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]')}>Только оплата</button></div></fieldset></div> : null}

        {step === 3 ? <div className="space-y-6"><CreatorCityCombobox label="Основной город *" value={homeCity} options={cityOptions} onChange={setHomeCity} className="text-sm text-slate-700" /><div className="grid gap-4 sm:grid-cols-2"><label className="text-sm font-semibold text-slate-700">Район<Input value={homeDistrict} onChange={(event) => setHomeDistrict(event.target.value)} placeholder="Например: Выборгский" className="mt-2 min-h-12 rounded-xl" /></label><label className="text-sm font-semibold text-slate-700">Метро<Input value={metroStations} onChange={(event) => setMetroStations(event.target.value)} placeholder="Озерки, Проспект Просвещения" className="mt-2 min-h-12 rounded-xl" /></label></div><fieldset><legend className="text-sm font-semibold text-slate-800">Куда готовы выезжать? <span className="text-rose-600">*</span></legend><div className="mt-3 grid gap-2 sm:grid-cols-2">{travelOptions.map((option) => <button key={option.key} type="button" aria-pressed={travelRadius === option.key} onClick={() => setTravelRadius(option.key)} className={cn('flex min-h-12 items-center gap-3 rounded-xl px-4 text-left text-sm transition-[background-color,color,box-shadow,transform] active:scale-[0.96]', travelRadius === option.key ? 'bg-slate-950 font-semibold text-white' : 'bg-slate-50 text-slate-700 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]')}><MapPin className="h-4 w-4 shrink-0" />{option.label}</button>)}</div></fieldset></div> : null}

        {step === 4 ? <div className="grid gap-4">{selectedPlatforms.map((platformKey) => { const platform = platforms.find((item) => item.key === platformKey); if (!platform) return null; return <label key={platform.key} className="text-sm font-semibold text-slate-700">{platform.label} <span className="text-rose-600">*</span><span className="relative mt-2 block"><Link2 className="pointer-events-none absolute left-3 top-4 h-4 w-4 text-slate-400" /><Input value={channelUrls[platform.key] || ''} onChange={(event) => setChannelUrls({ ...channelUrls, [platform.key]: event.target.value })} placeholder={platform.placeholder} className="min-h-12 rounded-xl pl-10" /></span></label>; })}</div> : null}
      </div>

      {error ? <p role="alert" className="mt-5 rounded-xl bg-rose-50 p-3 text-sm text-rose-800">{error}</p> : null}
      <footer className="mt-8 flex items-center justify-between gap-3">{step > 1 ? <Button type="button" variant="ghost" onClick={back} disabled={busy} className="min-h-11 gap-2 rounded-xl transition-transform active:scale-[0.96]"><ArrowLeft className="h-4 w-4" />Назад</Button> : <span />}<Button type="button" onClick={step === 4 ? () => void submit() : next} disabled={!stepValid || busy} className="min-h-12 gap-2 rounded-xl bg-slate-950 px-6 transition-transform active:scale-[0.96]">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : step === 4 ? <Sparkles className="h-4 w-4" /> : <UserRound className="h-4 w-4" />}{step === 4 ? 'Завершить регистрацию' : 'Продолжить'}{step < 4 ? <ArrowRight className="h-4 w-4" /> : null}</Button></footer>
    </section>
  </main>;
};
