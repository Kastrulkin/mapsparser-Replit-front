import {
  CalendarDays,
  Clock3,
  MapPin,
  PartyPopper,
  Scissors,
  Sparkles,
  Star,
} from "lucide-react";

const hairstyles = [
  "Четырёхпрядная коса",
  "Боксёрские косы",
  "Быстрая причёска за 5 минут",
];

const festivalHighlights = [
  "Аниматорская программа",
  "Шоу мыльных пузырей",
  "Лазертаг",
  "Сладкая вата",
  "Сладкий стол от Cinnabon",
  "Лотерея",
];

const festivalProgram = [
  { time: "14:14–15:00", title: "Аниматорская программа" },
  { time: "15:30–16:00", title: "Шоу мыльных пузырей" },
  { time: "16:30–17:00", title: "Лотерея" },
];

const FestivalPoster = () => (
  <main className="bg-slate-100 px-3 py-8 sm:px-8 sm:py-12">
    <div className="mx-auto max-w-6xl">
      <div className="mx-auto mb-5 flex max-w-[900px] flex-col gap-1 px-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-extrabold text-slate-900">Афиша для публикации</p>
          <p className="mt-1 text-sm text-slate-500">Вертикальный макет 4:5 для соцсетей и карточек на картах.</p>
        </div>
        <p className="text-xs font-semibold text-slate-400">Сделайте снимок только цветного блока</p>
      </div>

      <article
        id="festival-poster"
        aria-labelledby="festival-poster-title"
        className="relative mx-auto flex w-full max-w-[900px] flex-col overflow-hidden rounded-[2rem] bg-gradient-to-br from-amber-300 via-orange-200 to-pink-200 p-5 text-slate-950 shadow-[0_0_0_1px_rgba(0,0,0,0.06),0_2px_4px_rgba(120,53,15,0.08),0_30px_90px_rgba(120,53,15,0.22)] sm:aspect-[4/5] sm:rounded-[3rem] sm:p-10 lg:p-12"
      >
        <div className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 rounded-full bg-sky-400/40 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 -left-20 h-80 w-80 rounded-full bg-pink-500/25 blur-3xl" />
        <Star className="pointer-events-none absolute right-[9%] top-[25%] h-12 w-12 rotate-12 fill-yellow-300 text-yellow-500/70 sm:h-16 sm:w-16" aria-hidden="true" />

        <div className="relative flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
          <div className="flex min-w-0 items-center gap-3 sm:gap-4">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[1.15rem] bg-pink-600 text-white shadow-[0_10px_30px_rgba(219,39,119,0.28)] sm:h-16 sm:w-16 sm:rounded-[1.4rem]">
              <Scissors className="h-6 w-6 sm:h-8 sm:w-8" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="text-lg font-black leading-none text-pink-700 sm:text-2xl">Весёлая расчёска</p>
              <p className="mt-1 text-xs font-bold text-slate-600 sm:text-sm">Детская парикмахерская</p>
            </div>
          </div>
          <span className="inline-flex min-h-10 shrink-0 items-center rounded-full bg-white px-3.5 text-xs font-black uppercase tracking-[0.08em] text-sky-700 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_8px_24px_rgba(15,23,42,0.08)] sm:px-5 sm:text-sm">
            Вход свободный
          </span>
        </div>

        <div className="relative mt-7 grid gap-5 sm:mt-9 sm:grid-cols-[1fr_auto] sm:items-end sm:gap-8">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full bg-sky-500 px-3.5 py-2 text-xs font-black uppercase tracking-[0.12em] text-white shadow-[0_8px_24px_rgba(14,165,233,0.22)] sm:text-sm">
              <PartyPopper className="h-4 w-4" aria-hidden="true" />
              Фестиваль «Просто детский»
            </span>
            <h1 id="festival-poster-title" className="mt-4 max-w-2xl text-balance text-4xl font-black leading-[0.98] tracking-[-0.045em] sm:text-6xl lg:text-7xl">
              Заплетаем лето вместе!
            </h1>
          </div>
          <div className="flex gap-3 sm:flex-col">
            <div className="flex min-h-16 flex-1 items-center gap-3 rounded-2xl bg-white/90 px-4 shadow-[0_1px_2px_rgba(15,23,42,0.05),0_10px_30px_rgba(120,53,15,0.12)] sm:min-w-52">
              <CalendarDays className="h-6 w-6 shrink-0 text-pink-600" aria-hidden="true" />
              <div>
                <p className="text-xl font-black leading-none sm:text-2xl">25 июля</p>
                <p className="mt-1 text-xs font-bold text-slate-500">суббота</p>
              </div>
            </div>
            <div className="flex min-h-16 flex-1 items-center gap-3 rounded-2xl bg-slate-950 px-4 text-white shadow-[0_10px_30px_rgba(15,23,42,0.18)] sm:min-w-52">
              <Clock3 className="h-6 w-6 shrink-0 text-yellow-300" aria-hidden="true" />
              <div>
              <p className="whitespace-nowrap text-base font-black leading-none tabular-nums sm:text-2xl">14:00–17:00</p>
                <p className="mt-1 text-xs font-bold text-slate-300">мастер-классы</p>
              </div>
            </div>
          </div>
        </div>

        <div className="relative mt-6 rounded-[1.75rem] bg-white p-2.5 shadow-[0_1px_2px_rgba(15,23,42,0.05),0_18px_55px_rgba(120,53,15,0.16)] sm:mt-8 sm:rounded-[2.5rem] sm:p-3">
          <div className="rounded-[1.15rem] bg-gradient-to-br from-sky-50 via-white to-pink-50 p-5 sm:rounded-[1.75rem] sm:p-7 lg:p-8">
            <div className="flex items-start gap-4">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-pink-100 text-pink-700 sm:h-14 sm:w-14">
                <Sparkles className="h-6 w-6 sm:h-7 sm:w-7" aria-hidden="true" />
              </span>
              <div>
                <p className="text-xs font-black uppercase tracking-[0.14em] text-pink-700 sm:text-sm">Мастер-класс «Весёлой расчёски»</p>
                <h2 className="mt-2 text-balance text-2xl font-black tracking-[-0.03em] sm:text-4xl">Выбери свою причёску</h2>
              </div>
            </div>
            <div className="mt-5 grid gap-2.5 sm:mt-6 sm:grid-cols-3 sm:gap-3">
              {hairstyles.map((hairstyle, index) => (
                <div key={hairstyle} className="flex min-h-14 items-center gap-3 rounded-2xl bg-white px-4 py-3 shadow-[0_0_0_1px_rgba(0,0,0,0.05),0_4px_14px_rgba(15,23,42,0.05)] sm:min-h-24 sm:flex-col sm:items-start sm:justify-between sm:p-4">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-yellow-300 text-xs font-black text-amber-950">{index + 1}</span>
                  <p className="text-pretty text-sm font-black leading-5 text-slate-800 sm:text-base">{hairstyle}</p>
                </div>
              ))}
            </div>
            <p className="mt-4 text-pretty rounded-2xl bg-amber-100 px-4 py-3 text-sm font-bold leading-5 text-amber-950 sm:mt-5 sm:text-base">
              Можно присоединиться в любое время — дети участвуют по мере освобождения мест.
            </p>
          </div>
        </div>

        <div className="relative mt-5 sm:mt-7">
          <p className="text-xs font-black uppercase tracking-[0.12em] text-slate-600">Главное в программе</p>
          <div className="mt-2.5 grid gap-2 sm:grid-cols-3 sm:gap-3">
            {festivalProgram.map((item) => (
              <div key={item.time} className="flex items-center gap-3 rounded-2xl bg-white/70 px-4 py-3 shadow-[0_0_0_1px_rgba(0,0,0,0.04)] sm:block sm:min-h-24 sm:p-4">
                <p className="shrink-0 text-sm font-black text-pink-700 tabular-nums sm:text-base">{item.time}</p>
                <p className="text-pretty text-xs font-bold leading-4 text-slate-700 sm:mt-2 sm:text-sm sm:leading-5">{item.title}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="relative mt-6 grid gap-4 sm:mt-auto sm:grid-cols-[0.8fr_1.2fr] sm:items-end sm:gap-7">
          <div className="flex items-center gap-3 rounded-2xl bg-pink-600 px-4 py-3 text-white shadow-[0_10px_30px_rgba(219,39,119,0.24)] sm:px-5 sm:py-4">
            <MapPin className="h-6 w-6 shrink-0" aria-hidden="true" />
            <div>
              <p className="text-xs font-bold text-pink-100">Место встречи</p>
              <p className="mt-0.5 text-lg font-black leading-tight sm:text-xl">ТРК «Гранд Каньон»</p>
            </div>
          </div>
          <div>
            <p className="text-xs font-black uppercase tracking-[0.12em] text-slate-600">А ещё на празднике</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {festivalHighlights.map((item) => (
                <span key={item} className="rounded-full bg-white/75 px-2.5 py-1 text-[11px] font-bold leading-4 text-slate-700 shadow-[0_0_0_1px_rgba(0,0,0,0.04)] sm:text-xs">
                  {item}
                </span>
              ))}
            </div>
          </div>
        </div>
      </article>
    </div>
  </main>
);

export default FestivalPoster;
