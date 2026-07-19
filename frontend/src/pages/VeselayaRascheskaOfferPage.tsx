import { type FormEvent, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  CalendarCheck,
  Check,
  ChevronDown,
  Clock3,
  Heart,
  MapPin,
  Scissors,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import SeoMeta from "@/components/SeoMeta";
import FestivalPoster from "@/components/veselaya-rascheska/FestivalPoster";

const PAGE_PATH = "/veselaya-rascheska-hit";
type PageView = "offer" | "festival";

const locations = [
  {
    name: "Точка «Весёлой расчёски» №1",
    address: "Адрес будет добавлен",
    note: "Часы работы будут добавлены",
  },
  {
    name: "Точка «Весёлой расчёски» №2",
    address: "Адрес будет добавлен",
    note: "Часы работы будут добавлены",
  },
];

const conditions = [
  "Период предложения — будет указан перед публикацией",
  "Точная цена и состав стрижки будут указаны после согласования",
  "Условие подтверждения статуса клиента «Х» будет уточнено",
  "Совместимость с другими скидками и дополнительными услугами будет уточнена",
];

const faqItems = [
  {
    question: "Что входит в стрижку «Хит»?",
    answer: "Точный состав услуги будет добавлен после согласования. До публикации мы явно покажем, что входит в стоимость.",
  },
  {
    question: "Что делать, если ребёнок боится стричься?",
    answer: "Скажите об этом при записи. Мастер сможет заложить больше времени на знакомство и провести визит без спешки.",
  },
  {
    question: "Как подтвердить, что мы клиенты «Х»?",
    answer: "Способ подтверждения пока не указан. Мы добавим его в условия до запуска страницы.",
  },
  {
    question: "Можно ли выбрать любую точку сети?",
    answer: "Да, если иное не будет указано в финальных условиях. В форме можно отметить удобную точку.",
  },
];

const VeselayaRascheskaOfferPage = () => {
  const [activeView, setActiveView] = useState<PageView>(() => (
    new URLSearchParams(window.location.search).get("tab") === "festival" ? "festival" : "offer"
  ));
  const [openFaq, setOpenFaq] = useState(0);
  const [submitted, setSubmitted] = useState(false);
  const firstInputRef = useRef<HTMLInputElement>(null);

  const schema = useMemo(() => ([
    {
      "@context": "https://schema.org",
      "@type": "HairSalon",
      "@id": `https://localos.pro${PAGE_PATH}#business`,
      name: "Весёлая расчёска",
      url: `https://localos.pro${PAGE_PATH}`,
      description: "Сеть детских парикмахерских с бережным подходом к детям.",
    },
    {
      "@context": "https://schema.org",
      "@type": "Offer",
      "@id": `https://localos.pro${PAGE_PATH}#offer`,
      name: "Стрижка «Хит» по цене обычной для клиентов «Х»",
      url: `https://localos.pro${PAGE_PATH}#offer`,
      seller: { "@id": `https://localos.pro${PAGE_PATH}#business` },
      description: "Персональное предложение. Точная цена, период и условия будут добавлены до публикации.",
    },
  ]), []);

  const goToBooking = (locationName?: string) => {
    if (locationName) {
      const select = document.getElementById("location");
      if (select instanceof HTMLSelectElement) {
        select.value = locationName;
      }
    }
    document.getElementById("booking")?.scrollIntoView({ behavior: "smooth", block: "start" });
    window.setTimeout(() => firstInputRef.current?.focus({ preventScroll: true }), 500);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    setSubmitted(true);
  };

  const selectView = (view: PageView) => {
    const url = new URL(window.location.href);
    if (view === "festival") {
      url.searchParams.set("tab", "festival");
    } else {
      url.searchParams.delete("tab");
    }
    window.history.replaceState({}, "", url);
    setActiveView(view);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className="min-h-screen scroll-smooth bg-amber-300 font-['Trebuchet_MS',sans-serif] text-slate-900 antialiased">
      <SeoMeta
        title="Весёлая расчёска — детская стрижка и предложение для клиентов «Х»"
        description="Детская парикмахерская «Весёлая расчёска»: бережный подход, выбор точки и стрижка «Хит» по цене обычной для клиентов «Х»."
        path={PAGE_PATH}
        image="/veselaya-rascheska-og.png"
        schema={schema}
      />

      <nav aria-label="Служебное переключение макетов" className="sticky top-0 z-50 bg-slate-950 px-3 py-2 shadow-[0_8px_24px_rgba(15,23,42,0.22)] sm:px-6">
        <div role="tablist" aria-label="Макеты страницы" className="mx-auto flex max-w-6xl gap-1 rounded-2xl bg-white/10 p-1">
          <button
            type="button"
            role="tab"
            aria-selected={activeView === "offer"}
            onClick={() => selectView("offer")}
            className={`min-h-11 flex-1 rounded-xl px-4 text-sm font-extrabold transition-[background-color,color,transform,box-shadow] active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white ${activeView === "offer" ? "bg-white text-slate-950 shadow-sm" : "text-slate-300 hover:bg-white/10 hover:text-white"}`}
          >
            Текущая страница
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeView === "festival"}
            onClick={() => selectView("festival")}
            className={`min-h-11 flex-1 rounded-xl px-4 text-sm font-extrabold transition-[background-color,color,transform,box-shadow] active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white ${activeView === "festival" ? "bg-white text-slate-950 shadow-sm" : "text-slate-300 hover:bg-white/10 hover:text-white"}`}
          >
            Афиша 25 июля
          </button>
        </div>
      </nav>

      {activeView === "festival" ? (
        <FestivalPoster />
      ) : (
        <>

      <header className="relative z-20 border-b border-orange-950/10 bg-amber-100/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <a href="#top" className="flex min-h-11 items-center gap-3 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pink-600 focus-visible:ring-offset-2">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-pink-600 text-white shadow-[0_8px_24px_rgba(219,39,119,0.22)]">
              <Scissors className="h-5 w-5" aria-hidden="true" />
            </span>
            <span>
              <span className="block text-sm font-black leading-none text-pink-700 sm:text-base">Весёлая расчёска</span>
              <span className="mt-1 block text-xs text-slate-500">Детская парикмахерская</span>
            </span>
          </a>
          <button
            type="button"
            onClick={() => goToBooking()}
            className="hidden min-h-11 rounded-xl bg-pink-600 px-5 text-sm font-bold text-white shadow-sm transition-[background-color,transform] hover:bg-pink-700 active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pink-500 focus-visible:ring-offset-2 sm:inline-flex sm:items-center"
          >
            Записаться
          </button>
        </div>
      </header>

      <main id="top">
        <section className="relative overflow-hidden bg-gradient-to-b from-orange-300 via-amber-200 to-yellow-100 px-5 pb-16 pt-6 sm:px-8 sm:pb-24 sm:pt-10">
          <div className="pointer-events-none absolute -right-24 top-20 h-72 w-72 rounded-full bg-pink-400/20 blur-3xl" />
          <div className="pointer-events-none absolute -left-24 bottom-0 h-64 w-64 rounded-full bg-sky-400/20 blur-3xl" />
          <div className="relative mx-auto max-w-6xl overflow-hidden rounded-[2rem] bg-white p-2 shadow-[0_2px_4px_rgba(120,53,15,0.12),0_24px_70px_rgba(120,53,15,0.2)]">
            <img
              src="https://vraschyoska.ru/sites/all/themes/merrycomb/images/top.png"
              alt="Фирменная иллюстрация сети детских парикмахерских «Весёлая расчёска»"
              width="1012"
              height="356"
              loading="eager"
              className="media-outline h-auto w-full rounded-[1.5rem] object-cover"
            />
          </div>
          <div className="relative mx-auto mt-10 grid max-w-6xl items-center gap-10 lg:grid-cols-[1.08fr_0.92fr] lg:gap-16">
            <div>
              <span className="inline-flex min-h-9 items-center gap-2 rounded-full bg-white px-3.5 py-2 text-xs font-bold uppercase tracking-[0.12em] text-pink-700 shadow-[0_1px_2px_rgba(120,53,15,0.06),0_8px_24px_rgba(120,53,15,0.1)]">
                <Sparkles className="h-4 w-4" aria-hidden="true" />
                Персональное предложение для клиентов «Х»
              </span>
              <h1 className="mt-6 max-w-3xl text-balance text-4xl font-black leading-[1.04] tracking-[-0.04em] text-slate-950 sm:text-5xl lg:text-6xl">
                Стрижка «Хит» по цене обычной
              </h1>
              <p className="mt-6 max-w-2xl text-pretty text-lg leading-8 text-slate-700 sm:text-xl">
                В сети «Весёлая расчёска» детей стригут спокойно, бережно и без лишней спешки. Для клиентов «Х» готовим особое условие на популярную стрижку.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <button
                  type="button"
                  onClick={() => goToBooking()}
                  className="inline-flex min-h-14 items-center justify-center gap-2 rounded-2xl bg-pink-600 px-7 text-base font-extrabold text-white shadow-[0_10px_30px_rgba(219,39,119,0.24)] transition-[background-color,transform,box-shadow] hover:bg-pink-700 hover:shadow-[0_14px_34px_rgba(219,39,119,0.3)] active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pink-600 focus-visible:ring-offset-2"
                >
                  Выбрать точку и записаться
                  <ArrowRight className="h-5 w-5" aria-hidden="true" />
                </button>
                <a
                  href="#offer"
                  className="inline-flex min-h-14 items-center justify-center rounded-2xl bg-white px-7 text-base font-bold text-slate-800 shadow-[0_1px_2px_rgba(15,23,42,0.05),0_8px_24px_rgba(15,23,42,0.07)] transition-[background-color,transform] hover:bg-slate-50 active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2"
                >
                  Узнать условия
                </a>
              </div>
              <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-sm font-bold text-slate-700">
                {["Бережно к ребёнку", "Понятная запись", "Несколько точек"].map((item) => (
                  <span key={item} className="inline-flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-sky-100 text-sky-700"><Check className="h-3.5 w-3.5" aria-hidden="true" /></span>
                    {item}
                  </span>
                ))}
              </div>
            </div>

            <div className="relative mx-auto w-full max-w-lg rounded-[2rem] bg-white p-3 shadow-[0_2px_4px_rgba(120,53,15,0.08),0_28px_70px_rgba(120,53,15,0.16)]">
              <div className="relative overflow-hidden rounded-[1.25rem] bg-gradient-to-br from-sky-400 to-cyan-500 p-7 text-white sm:p-9">
                <div className="absolute -right-12 -top-12 h-44 w-44 rounded-full bg-yellow-300/40" />
                <p className="relative text-sm font-black uppercase tracking-[0.14em] text-sky-950">Специально для клиентов «Х»</p>
                <p className="relative mt-5 text-balance text-4xl font-black leading-none sm:text-5xl">«Хит»</p>
                <p className="relative mt-3 text-balance text-2xl font-black text-yellow-200">по цене обычной стрижки</p>
                <div className="relative mt-7 rounded-2xl bg-white/95 p-5 text-slate-800 shadow-[0_10px_30px_rgba(3,105,161,0.2)]">
                  <p className="text-sm font-black text-pink-700">Детская стрижка без лишнего стресса</p>
                  <p className="mt-1 text-sm leading-6 text-slate-600">Знакомимся, слушаем ребёнка и не торопим.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="bg-white px-5 py-16 sm:px-8 sm:py-24" aria-labelledby="about-title">
          <div className="mx-auto max-w-6xl">
            <div className="grid gap-10 lg:grid-cols-[0.85fr_1.15fr] lg:gap-20">
              <div>
                <p className="text-sm font-extrabold uppercase tracking-[0.16em] text-pink-700">О сети</p>
                <h2 id="about-title" className="mt-3 text-balance text-3xl font-black tracking-[-0.03em] text-slate-950 sm:text-4xl">
                  Место, где ребёнку помогают освоиться
                </h2>
                <p className="mt-5 text-pretty text-base leading-7 text-slate-600 sm:text-lg">
                  «Весёлая расчёска» — сеть детских парикмахерских. Здесь важен не только аккуратный результат, но и самочувствие ребёнка во время визита.
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                {[
                  { icon: Heart, title: "Бережный подход", text: "Мастер знакомится с ребёнком и даёт ему время привыкнуть." },
                  { icon: ShieldCheck, title: "Спокойнее родителям", text: "Понятный план визита и возможность заранее рассказать об особенностях." },
                  { icon: Clock3, title: "Без лишней спешки", text: "Стрижка подстраивается под темп ребёнка, насколько это возможно." },
                  { icon: CalendarCheck, title: "Удобная запись", text: "Выберите точку и оставьте контакт — администратор уточнит детали." },
                ].map(({ icon: Icon, title, text }) => (
                  <article key={title} className="rounded-3xl bg-amber-50 p-6 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.04)]">
                    <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-100 text-sky-700"><Icon className="h-5 w-5" aria-hidden="true" /></span>
                    <h3 className="mt-5 text-lg font-extrabold text-slate-900">{title}</h3>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{text}</p>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="px-5 py-16 sm:px-8 sm:py-24" aria-labelledby="locations-title">
          <div className="mx-auto max-w-6xl">
            <div className="max-w-2xl">
              <p className="text-sm font-extrabold uppercase tracking-[0.16em] text-pink-700">Наши точки</p>
              <h2 id="locations-title" className="mt-3 text-balance text-3xl font-black tracking-[-0.03em] text-slate-950 sm:text-4xl">
                Выберите, куда удобнее приехать
              </h2>
              <p className="mt-4 text-base leading-7 text-slate-600">В финальной версии здесь будут точные адреса, часы работы и ссылки на маршрут.</p>
            </div>
            <div className="mt-10 grid gap-5 md:grid-cols-2">
              {locations.map((location, index) => (
                <article key={location.name} className="rounded-[2rem] bg-white p-3 shadow-[0_1px_2px_rgba(15,23,42,0.04),0_16px_45px_rgba(15,23,42,0.08)]">
                  <div className="rounded-[1.25rem] bg-gradient-to-br from-pink-50 via-amber-50 to-sky-50 p-6 sm:p-8">
                    <div className="flex items-start justify-between gap-4">
                      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-sky-700 shadow-sm"><MapPin className="h-6 w-6" aria-hidden="true" /></span>
                      <span className="rounded-full bg-pink-600 px-3 py-1.5 text-xs font-extrabold text-white">Точка {index + 1}</span>
                    </div>
                    <h3 className="mt-7 text-xl font-black text-slate-950">{location.name}</h3>
                    <p className="mt-3 text-base font-semibold text-slate-700">{location.address}</p>
                    <p className="mt-1 text-sm text-slate-500">{location.note}</p>
                    <button
                      type="button"
                      onClick={() => goToBooking(location.name)}
                      className="mt-7 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-pink-600 px-5 text-sm font-extrabold text-white transition-[background-color,transform] hover:bg-pink-700 active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pink-500 focus-visible:ring-offset-2"
                    >
                      Записаться в эту точку
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="offer" className="bg-pink-600 px-5 py-16 text-white sm:px-8 sm:py-24" aria-labelledby="offer-title">
          <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[1fr_0.9fr] lg:gap-16">
            <div>
              <span className="inline-flex rounded-full bg-amber-300 px-3.5 py-2 text-xs font-black uppercase tracking-[0.12em] text-amber-950">Для клиентов «Х»</span>
              <h2 id="offer-title" className="mt-5 text-balance text-3xl font-black tracking-[-0.03em] sm:text-5xl">
                «Хит» по цене обычной стрижки
              </h2>
              <p className="mt-5 max-w-2xl text-pretty text-lg leading-8 text-pink-50/90">
                Вы получаете популярную стрижку «Хит» по стоимости обычной стрижки. Точные цифры и ограничения появятся здесь до запуска.
              </p>
              <div className="mt-8 grid gap-4 sm:grid-cols-3">
                {["Оставьте заявку", "Подтвердите статус", "Выберите время"].map((step, index) => (
                  <div key={step} className="rounded-2xl bg-white/10 p-4 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.12)]">
                    <span className="font-mono text-sm font-black text-amber-300">0{index + 1}</span>
                    <p className="mt-2 text-sm font-bold leading-5">{step}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-[2rem] bg-white p-3 text-slate-900 shadow-[0_24px_70px_rgba(131,24,67,0.3)]">
              <div className="rounded-[1.25rem] bg-orange-50 p-6 sm:p-8">
                <h3 className="text-xl font-black">Что важно знать</h3>
                <ul className="mt-6 space-y-4">
                  {conditions.map((condition) => (
                    <li key={condition} className="flex gap-3 text-sm leading-6 text-slate-600">
                      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-200 text-amber-900"><Check className="h-3.5 w-3.5" aria-hidden="true" /></span>
                      {condition}
                    </li>
                  ))}
                </ul>
                <p className="mt-6 rounded-xl bg-amber-100 px-4 py-3 text-xs font-semibold leading-5 text-amber-950">Страница — черновик. Предложение не действует, пока не опубликованы точные условия.</p>
              </div>
            </div>
          </div>
        </section>

        <section className="bg-white px-5 py-16 sm:px-8 sm:py-24" aria-labelledby="faq-title">
          <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[0.7fr_1.3fr] lg:gap-20">
            <div>
              <p className="text-sm font-extrabold uppercase tracking-[0.16em] text-sky-700">Вопросы</p>
              <h2 id="faq-title" className="mt-3 text-balance text-3xl font-black tracking-[-0.03em] text-slate-950 sm:text-4xl">
                Коротко о главном
              </h2>
            </div>
            <div className="divide-y divide-slate-200">
              {faqItems.map((item, index) => {
                const isOpen = openFaq === index;
                const panelId = `faq-panel-${index}`;
                return (
                  <div key={item.question}>
                    <button
                      type="button"
                      aria-expanded={isOpen}
                      aria-controls={panelId}
                      onClick={() => setOpenFaq(isOpen ? -1 : index)}
                      className="flex min-h-16 w-full items-center justify-between gap-5 py-5 text-left text-base font-extrabold text-slate-900 transition-colors hover:text-pink-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-pink-600"
                    >
                      {item.question}
                      <ChevronDown className={`h-5 w-5 shrink-0 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} aria-hidden="true" />
                    </button>
                    <div id={panelId} hidden={!isOpen} className="pb-5 pr-10 text-sm leading-6 text-slate-600">
                      {item.answer}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <section id="booking" className="scroll-mt-6 px-5 py-16 sm:px-8 sm:py-24" aria-labelledby="booking-title">
          <div className="mx-auto grid max-w-6xl overflow-hidden rounded-[2rem] bg-white shadow-[0_2px_4px_rgba(15,23,42,0.06),0_28px_80px_rgba(15,23,42,0.12)] lg:grid-cols-[0.82fr_1.18fr]">
            <div className="bg-gradient-to-br from-yellow-200 via-pink-100 to-sky-100 p-7 sm:p-10 lg:p-12">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-pink-700 shadow-sm"><CalendarCheck className="h-6 w-6" aria-hidden="true" /></span>
              <h2 id="booking-title" className="mt-7 text-balance text-3xl font-black tracking-[-0.03em] text-slate-950 sm:text-4xl">
                Оставьте контакт для записи
              </h2>
              <p className="mt-5 text-pretty text-base leading-7 text-slate-700">Администратор уточнит точку, время, возраст ребёнка и условия предложения.</p>
              <div className="mt-8 rounded-2xl bg-white/75 p-5 shadow-[inset_0_0_0_1px_rgba(0,0,0,0.04)]">
                <p className="text-xs font-black uppercase tracking-[0.12em] text-slate-500">Контакты</p>
                <p className="mt-2 text-sm font-bold text-slate-900">Будут добавлены перед публикацией</p>
              </div>
            </div>
            <form onSubmit={handleSubmit} className="p-7 sm:p-10 lg:p-12" aria-describedby="form-note">
              {submitted ? (
                <div role="status" className="flex min-h-[360px] flex-col items-center justify-center text-center">
                  <span className="flex h-16 w-16 items-center justify-center rounded-full bg-sky-100 text-sky-700"><Check className="h-8 w-8" aria-hidden="true" /></span>
                  <h3 className="mt-6 text-2xl font-black text-slate-950">Форма готова к подключению</h3>
                  <p className="mt-3 max-w-md text-sm leading-6 text-slate-600">Это черновик: данные никуда не отправлены. Перед запуском здесь будет подключен реальный канал записи.</p>
                  <button type="button" onClick={() => setSubmitted(false)} className="mt-6 min-h-11 rounded-xl bg-slate-900 px-5 text-sm font-bold text-white transition-[background-color,transform] hover:bg-slate-700 active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500 focus-visible:ring-offset-2">Вернуться к форме</button>
                </div>
              ) : (
                <>
                  <div className="grid gap-5 sm:grid-cols-2">
                    <label className="block text-sm font-bold text-slate-800">
                      Имя ребёнка
                      <input ref={firstInputRef} required name="childName" autoComplete="off" className="mt-2 min-h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-base font-normal outline-none transition-[border-color,box-shadow] focus:border-pink-600 focus:ring-4 focus:ring-pink-600/10" />
                    </label>
                    <label className="block text-sm font-bold text-slate-800">
                      Возраст
                      <input required name="childAge" inputMode="numeric" min="1" max="17" type="number" className="mt-2 min-h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-base font-normal outline-none transition-[border-color,box-shadow] focus:border-pink-600 focus:ring-4 focus:ring-pink-600/10" />
                    </label>
                    <label className="block text-sm font-bold text-slate-800 sm:col-span-2">
                      Имя родителя или представителя
                      <input required name="adultName" autoComplete="name" className="mt-2 min-h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-base font-normal outline-none transition-[border-color,box-shadow] focus:border-pink-600 focus:ring-4 focus:ring-pink-600/10" />
                    </label>
                    <label className="block text-sm font-bold text-slate-800">
                      Телефон
                      <input required name="phone" type="tel" autoComplete="tel" placeholder="+7" className="mt-2 min-h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-base font-normal outline-none transition-[border-color,box-shadow] focus:border-pink-600 focus:ring-4 focus:ring-pink-600/10" />
                    </label>
                    <label className="block text-sm font-bold text-slate-800">
                      Удобная точка
                      <select required id="location" name="location" defaultValue="" className="mt-2 min-h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-base font-normal outline-none transition-[border-color,box-shadow] focus:border-pink-600 focus:ring-4 focus:ring-pink-600/10">
                        <option value="" disabled>Выберите точку</option>
                        {locations.map((location) => <option key={location.name} value={location.name}>{location.name}</option>)}
                      </select>
                    </label>
                    <label className="block text-sm font-bold text-slate-800 sm:col-span-2">
                      Комментарий <span className="font-normal text-slate-400">(необязательно)</span>
                      <textarea name="comment" rows={3} placeholder="Например: ребёнок волнуется перед стрижкой" className="mt-2 w-full resize-y rounded-xl border border-slate-300 bg-white px-4 py-3 text-base font-normal outline-none transition-[border-color,box-shadow] focus:border-pink-600 focus:ring-4 focus:ring-pink-600/10" />
                    </label>
                  </div>
                  <label className="mt-5 flex cursor-pointer items-start gap-3 text-sm leading-6 text-slate-600">
                    <input required type="checkbox" name="consent" className="mt-1 h-5 w-5 shrink-0 rounded border-slate-300 text-pink-600 focus:ring-pink-600" />
                    <span>Я согласен(а) на обработку персональных данных. Ссылка на политику будет добавлена до публикации.</span>
                  </label>
                  <button type="submit" className="mt-6 inline-flex min-h-14 w-full items-center justify-center gap-2 rounded-2xl bg-pink-600 px-7 text-base font-extrabold text-white shadow-[0_10px_30px_rgba(219,39,119,0.22)] transition-[background-color,transform,box-shadow] hover:bg-pink-700 hover:shadow-[0_14px_34px_rgba(219,39,119,0.28)] active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pink-600 focus-visible:ring-offset-2">
                    Оставить заявку
                    <ArrowRight className="h-5 w-5" aria-hidden="true" />
                  </button>
                  <p id="form-note" className="mt-3 text-center text-xs leading-5 text-slate-500">Черновик: форма пока не отправляет данные.</p>
                </>
              )}
            </form>
          </div>
        </section>
      </main>

      <footer className="border-t border-orange-950/10 bg-amber-100 px-5 py-8 sm:px-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-extrabold text-slate-900">Весёлая расчёска</p>
            <p className="mt-1">Детские стрижки в доброй атмосфере</p>
          </div>
          <div className="sm:text-right">
            <p>Контакты и юридическая информация будут добавлены</p>
            <p className="mt-1">© {new Date().getFullYear()} «Весёлая расчёска»</p>
          </div>
        </div>
      </footer>
        </>
      )}
    </div>
  );
};

export default VeselayaRascheskaOfferPage;
