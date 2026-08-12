import { useEffect, useState } from "react";
import {
  ArrowRight,
  BarChart3,
  Building2,
  Check,
  ChevronRight,
  CircleDollarSign,
  ClipboardCheck,
  Eye,
  FileCheck2,
  Handshake,
  Layers3,
  Loader2,
  MapPinned,
  MessageSquareText,
  Network,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import Footer from "@/components/Footer";
import SeoMeta from "@/components/SeoMeta";
import { Button } from "@/components/ui/button";
import { publishedCases } from "@/content/cases";
import { Language, useLanguage } from "@/i18n/LanguageContext";
import landingTranslations from "@/i18n/homeLandingTranslations.json";

type TaskCard = {
  title: string;
  description: string;
};

type WorkStep = {
  title: string;
  description: string;
};

type LandingCopy = {
  metaTitle: string;
  metaDescription: string;
  eyebrow: string;
  title: string;
  intro: string;
  seeTasks: string;
  freeAudit: string;
  formTitle: string;
  formDescription: string;
  emailLabel: string;
  emailPlaceholder: string;
  mapsLabel: string;
  mapsPlaceholder: string;
  submit: string;
  submitting: string;
  success: string;
  error: string;
  scale: string;
  problemTitle: string;
  problemParagraphs: string[];
  networkTitle: string;
  networkParagraphs: string[];
  networkPrivacy: string;
  networkLabels: string[];
  tasksEyebrow: string;
  tasksTitle: string;
  tasksIntro: string;
  tasks: TaskCard[];
  retentionNote: string;
  workEyebrow: string;
  workTitle: string;
  workIntro: string;
  steps: WorkStep[];
  workSummary: string;
  casesEyebrow: string;
  casesTitle: string;
  casesIntro: string;
  situation: string;
  workDone: string;
  result: string;
  allCases: string;
  auditTitle: string;
  auditText: string;
  finalTitle: string;
  finalText: string;
  tryFree: string;
  talkExpert: string;
};

const ruCopy: LandingCopy = {
  metaTitle: "LocalOS — меньше рутины для владельца локального бизнеса",
  metaDescription:
    "LocalOS проверяет карты и отзывы, готовит публикации, анализирует услуги и показатели и выполняет регулярные задачи. Владелец подключается только там, где нужно решение.",
  eyebrow: "LocalOS для локального бизнеса",
  title: "Владелец нужен бизнесу для решений, а не для рутины",
  intro:
    "LocalOS следит за тем, что обычно приходится держать в голове: карточками на картах, отзывами, публикациями, услугами, цифрами и партнёрствами. Регулярную работу система выполняет сама. Вы подключаетесь, когда нужно выбрать, проверить или подтвердить.",
  seeTasks: "Посмотреть, что можно передать LocalOS",
  freeAudit: "Получить бесплатный аудит",
  formTitle: "Начните с аудита карт",
  formDescription: "Проверим, как клиенты видят ваш бизнес и что стоит исправить в первую очередь.",
  emailLabel: "Email",
  emailPlaceholder: "you@example.com",
  mapsLabel: "Ссылка на карточку",
  mapsPlaceholder: "https://yandex.ru/maps/org/...",
  submit: "Получить аудит",
  submitting: "Отправляем…",
  success: "Спасибо! Заявка принята.",
  error: "Не удалось отправить заявку. Попробуйте ещё раз.",
  scale: "LocalOS уже работает более чем в 240 точках малого бизнеса — от отдельных компаний до сетей.",
  problemTitle: "Если без вас всё останавливается, вы остаётесь на работе даже после рабочего дня",
  problemParagraphs: [
    "Ответить на отзыв. Проверить карточку. Придумать публикацию. Обновить цены. Посмотреть цифры. Каждая задача занимает немного времени, но вместе они не оставляют владельцу возможности заниматься самим бизнесом.",
    "Новые сервисы редко снимают эту нагрузку. Обычно у владельца появляется ещё одно место, которое нужно открывать и контролировать.",
    "LocalOS превращает повторяющуюся работу в регулярные задачи, выполняет их и показывает владельцу только то, что требует решения.",
  ],
  networkTitle: "У вас может быть одна точка. Опыт — как у сети",
  networkParagraphs: [
    "Сеть не решает одну и ту же задачу отдельно в каждом филиале. Если способ сработал, его проверяют и используют снова.",
    "LocalOS делает этот подход доступным отдельному бизнесу. Мы собираем рабочие практики, проверяем их и превращаем в готовые сценарии. Поэтому следующая компания начинает не с пустого листа.",
  ],
  networkPrivacy: "Данные компаний и клиентов не передаются другим бизнесам. Общими становятся только проверенные правила и обезличенные способы работы.",
  networkLabels: ["Один бизнес находит решение", "LocalOS проверяет практику", "Другие начинают не с нуля"],
  tasksEyebrow: "Работа LocalOS",
  tasksTitle: "Что больше не нужно держать на себе",
  tasksIntro: "Пять задач, которые обычно возвращаются к владельцу.",
  tasks: [
    { title: "Следить, находят ли вас клиенты", description: "LocalOS проверяет карточки на картах, услуги, цены, фотографии, публикации и отзывы. Показывает, что мешает клиенту выбрать компанию, и готовит исправления." },
    { title: "Искать клиентов только через рекламу", description: "LocalOS находит подходящие бизнесы рядом, готовит предложения о сотрудничестве и ведёт историю контактов. Внешние сообщения отправляются только после подтверждения." },
    { title: "Прерывать день из-за каждого отзыва и публикации", description: "LocalOS собирает отзывы без ответа, готовит черновики и поддерживает очередь публикаций. Владельцу остаётся проверить важное и разрешить отправку." },
    { title: "Разбираться в услугах и ценах вслепую", description: "LocalOS показывает, какие услуги продаются, как меняются средний чек и загрузка, где меню запутывает клиента и какие предложения стоит проверить." },
    { title: "Собирать картину бизнеса вручную", description: "LocalOS сводит выполненную работу, финансовые показатели и задачи, требующие внимания. Владелец видит, что произошло и какое решение нужно принять сегодня." },
  ],
  retentionNote: "При подключении клиентских данных LocalOS также может находить клиентов, которые давно не возвращались, и готовить предложения для повторного визита.",
  workEyebrow: "Порядок работы",
  workTitle: "Система работает. Владелец принимает решения",
  workIntro: "LocalOS забирает регулярную работу, но не принимает важные решения за владельца.",
  steps: [
    { title: "Подключаем бизнес", description: "LocalOS получает доступ только к выбранным данным: карточкам, отзывам, услугам, финансовым показателям и подключённым каналам." },
    { title: "Находим работу, которую можно снять с владельца", description: "Система отделяет разовую проблему от задачи, которую нужно выполнять регулярно." },
    { title: "Выполняем по проверенному сценарию", description: "LocalOS проверяет данные, готовит материалы и запускает разрешённые действия по расписанию." },
    { title: "Показываем то, что требует решения", description: "Публикации, сообщения, массовые изменения и другие важные действия ждут подтверждения владельца." },
    { title: "Сохраняем результат", description: "Если способ работы подтвердил пользу, его можно повторить в этом бизнесе и использовать как обобщённую практику для других компаний." },
  ],
  workSummary: "ИИ используется для анализа и подготовки. Повторяющаяся работа выполняется по правилам. Контроль остаётся у владельца.",
  casesEyebrow: "Кейсы",
  casesTitle: "Что владельцы уже сняли с себя",
  casesIntro: "Исходная ситуация, выполненная работа и изменения за указанный период.",
  situation: "Было",
  workDone: "Сделали",
  result: "Изменилось",
  allCases: "Посмотреть все кейсы",
  auditTitle: "Снимите с себя одну задачу для начала",
  auditText: "Мы проверим карточку вашего бизнеса и покажем, что мешает клиентам найти и выбрать вас. Вы получите конкретное первое действие без большого отчёта и общих советов.",
  finalTitle: "Перестаньте быть человеком, без которого ничего не происходит",
  finalText: "Передайте LocalOS регулярную работу. Оставьте себе решения, которые действительно требуют владельца.",
  tryFree: "Попробовать бесплатно",
  talkExpert: "Обсудить с экспертом",
};

const enCopy: LandingCopy = {
  ...ruCopy,
  metaTitle: "LocalOS — less routine work for local business owners",
  metaDescription: "LocalOS checks listings and reviews, prepares content, analyses services and numbers, and handles recurring work. The owner steps in when a decision is needed.",
  eyebrow: "LocalOS for local businesses",
  title: "Your business needs you for decisions, not routine work",
  intro: "LocalOS watches the work owners usually keep in their heads: listings, reviews, content, services, numbers, and partnerships. The system handles recurring tasks. You step in when something needs a choice, a review, or approval.",
  seeTasks: "See what LocalOS can take over",
  freeAudit: "Get a free audit",
  formTitle: "Start with a listings audit",
  formDescription: "See how customers find your business and what should be fixed first.",
  emailLabel: "Email",
  emailPlaceholder: "you@example.com",
  mapsLabel: "Business listing link",
  mapsPlaceholder: "Link to your business on maps",
  submit: "Get the audit",
  submitting: "Sending…",
  success: "Thank you. Your request has been received.",
  error: "We could not send your request. Please try again.",
  scale: "LocalOS already works across more than 240 small-business locations, from independent companies to networks.",
  problemTitle: "If everything stops without you, you are still at work after the working day ends",
  problemParagraphs: [
    "Reply to a review. Check a listing. Plan a post. Update prices. Look at the numbers. Each task is small, but together they leave the owner no time to work on the business itself.",
    "New software rarely removes this load. It usually gives the owner one more place to open and monitor.",
    "LocalOS turns recurring work into scheduled tasks, completes them, and shows the owner only what needs a decision.",
  ],
  networkTitle: "You may have one location. Your experience can work like a network's",
  networkParagraphs: [
    "A network does not solve the same problem from scratch in every branch. Once a method works, it is checked and used again.",
    "LocalOS brings that approach to independent businesses. We collect working practices, review them, and turn them into reusable procedures. The next company does not start with a blank page.",
  ],
  networkPrivacy: "Company and customer data is never passed to other businesses. Only reviewed rules and anonymised ways of working are shared.",
  networkLabels: ["One business finds a solution", "LocalOS reviews the practice", "Others do not start from zero"],
  tasksEyebrow: "Work handled by LocalOS",
  tasksTitle: "What you no longer need to carry alone",
  tasksIntro: "Five jobs that usually find their way back to the owner.",
  tasks: [
    { title: "Check whether customers can find you", description: "LocalOS checks map listings, services, prices, photos, posts, and reviews. It shows what gets in the way of a customer's choice and prepares the fixes." },
    { title: "Rely on advertising as the only source of customers", description: "LocalOS finds relevant nearby businesses, prepares partnership proposals, and keeps the contact history. External messages are sent only after approval." },
    { title: "Interrupt the day for every review and post", description: "LocalOS collects unanswered reviews, prepares drafts, and maintains the publishing queue. The owner reviews what matters and approves publication." },
    { title: "Guess what to do with services and prices", description: "LocalOS shows which services sell, how average spend and capacity change, where the menu confuses customers, and which offers are worth testing." },
    { title: "Assemble the business picture by hand", description: "LocalOS brings together completed work, financial indicators, and items that need attention. The owner sees what happened and what decision is needed today." },
  ],
  retentionNote: "When customer data is connected, LocalOS can also identify customers who have not returned and prepare an offer for a repeat visit.",
  workEyebrow: "How the work is handled",
  workTitle: "The system does the work. The owner makes the decisions",
  workIntro: "LocalOS takes recurring work off the owner's plate without taking important decisions away from them.",
  steps: [
    { title: "Connect the business", description: "LocalOS accesses only the data you choose: listings, reviews, services, financial indicators, and connected channels." },
    { title: "Find work that can leave the owner's desk", description: "The system separates a one-off problem from a task that needs to run regularly." },
    { title: "Run a reviewed procedure", description: "LocalOS checks data, prepares materials, and runs permitted actions on schedule." },
    { title: "Show what needs a decision", description: "Posts, messages, bulk changes, and other important external actions wait for the owner's approval." },
    { title: "Keep the result", description: "When a way of working proves useful, it can be repeated in the business and used as an anonymised practice for other companies." },
  ],
  workSummary: "AI is used for analysis and preparation. Recurring work follows clear rules. The owner stays in control.",
  casesEyebrow: "Case studies",
  casesTitle: "What owners have already taken off their plates",
  casesIntro: "The starting situation, the work completed, and what changed over a stated period.",
  situation: "Before",
  workDone: "Work completed",
  result: "What changed",
  allCases: "View all case studies",
  auditTitle: "Take one task off your plate first",
  auditText: "We will check your business listing and show what gets in the way of customers finding and choosing you. You will get one concrete first action, without a long report or generic advice.",
  finalTitle: "Stop being the person without whom nothing happens",
  finalText: "Give recurring work to LocalOS. Keep the decisions that genuinely need the owner.",
  tryFree: "Try for free",
  talkExpert: "Talk to an expert",
};

const taskIcons = [MapPinned, Handshake, MessageSquareText, CircleDollarSign, BarChart3];
const stepIcons = [Building2, Eye, Layers3, ClipboardCheck, FileCheck2];

const copyForLanguage = (language: Language): LandingCopy => {
  switch (language) {
    case "ru":
      return ruCopy;
    case "en":
      return enCopy;
    case "fr":
      return landingTranslations.fr;
    case "es":
      return landingTranslations.es;
    case "el":
      return landingTranslations.el;
    case "de":
      return landingTranslations.de;
    case "th":
      return landingTranslations.th;
    case "ar":
      return landingTranslations.ar;
    case "ha":
      return landingTranslations.ha;
    case "tr":
      return landingTranslations.tr;
  }
};

const Index = () => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { language } = useLanguage();
  const location = useLocation();
  const copy = copyForLanguage(language);

  useEffect(() => {
    if (!["#agents", "#cta", "#hero-form"].includes(location.hash)) return;
    const element = document.getElementById(location.hash.slice(1));
    if (!element) return;
    const timeoutId = window.setTimeout(() => element.scrollIntoView({ behavior: "smooth" }), 100);
    return () => window.clearTimeout(timeoutId);
  }, [location.hash]);

  const scrollToAudit = () => {
    const form = document.getElementById("hero-form");
    form?.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => form?.querySelector<HTMLInputElement>("input")?.focus(), 450);
  };

  return (
    <div className="min-h-screen overflow-hidden bg-white text-slate-950">
      <SeoMeta
        description={copy.metaDescription}
        image="/images/articles/pochemu-predprinimateli-vygorayut-cover.png"
        path="/"
        title={copy.metaTitle}
      />

      <main>
        <section className="relative isolate overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(251,146,60,0.18),_transparent_42%),linear-gradient(to_bottom_right,#fff7ed,#ffffff_48%,#fffbeb)] px-4 py-14 sm:px-6 sm:py-20 lg:px-8 lg:py-24">
          <div className="absolute -right-24 top-16 -z-10 h-80 w-80 rounded-full bg-orange-200/30 blur-3xl" aria-hidden="true" />
          <div className="mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-[minmax(0,1.08fr)_minmax(380px,0.92fr)] lg:gap-16">
            <div>
              <div className="inline-flex min-h-10 items-center gap-2 rounded-full bg-white/80 px-4 py-2 text-sm font-semibold text-orange-700 shadow-[0_8px_30px_rgba(249,115,22,0.10)] ring-1 ring-black/5 backdrop-blur">
                <Sparkles className="h-4 w-4 text-orange-500" aria-hidden="true" />
                {copy.eyebrow}
              </div>
              <h1 className="mt-7 max-w-4xl text-4xl font-bold leading-[1.06] tracking-[-0.04em] text-slate-950 sm:text-5xl lg:text-6xl">
                {copy.title}
              </h1>
              <p className="mt-7 max-w-3xl text-lg leading-8 text-slate-600 sm:text-xl">{copy.intro}</p>
              <div className="mt-9 flex flex-col gap-3 sm:flex-row">
                <Button asChild className="h-auto min-h-12 whitespace-normal rounded-xl px-6 py-3 text-base shadow-lg shadow-orange-500/20" size="lg">
                  <Link to={{ pathname: "/", hash: "#agents" }}>
                    {copy.seeTasks}
                    <ArrowRight className="h-5 w-5" aria-hidden="true" />
                  </Link>
                </Button>
                <Button className="h-auto min-h-12 whitespace-normal rounded-xl bg-white px-6 py-3 text-base" onClick={scrollToAudit} size="lg" variant="outline">
                  {copy.freeAudit}
                </Button>
              </div>
            </div>

            <div className="rounded-[2rem] bg-white/90 p-3 shadow-[0_30px_80px_rgba(15,23,42,0.14)] ring-1 ring-black/5 backdrop-blur">
              <div className="rounded-[1.25rem] bg-slate-950 p-6 text-white sm:p-8">
                <div className="mb-7 flex h-12 w-12 items-center justify-center rounded-xl bg-orange-500 shadow-lg shadow-orange-950/30">
                  <MapPinned className="h-6 w-6" aria-hidden="true" />
                </div>
                <h2 className="text-2xl font-bold tracking-tight">{copy.formTitle}</h2>
                <p className="mt-3 leading-7 text-slate-300">{copy.formDescription}</p>
                <form
                  className="mt-7 space-y-4"
                  id="hero-form"
                  onSubmit={async (event) => {
                    event.preventDefault();
                    if (isSubmitting) return;
                    setIsSubmitting(true);
                    const form = event.currentTarget;
                    const emailInput = form.elements.namedItem("email");
                    const mapsInput = form.elements.namedItem("yandexUrl");
                    if (!(emailInput instanceof HTMLInputElement) || !(mapsInput instanceof HTMLInputElement)) {
                      setIsSubmitting(false);
                      return;
                    }
                    try {
                      const response = await fetch("/api/public/request-report", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ email: emailInput.value, url: mapsInput.value }),
                      });
                      const result: unknown = await response.json().catch(() => null);
                      const payload = result && typeof result === "object" ? result : null;
                      const errorMessage = payload && "error" in payload && typeof payload.error === "string"
                        ? payload.error
                        : payload && "message" in payload && typeof payload.message === "string"
                          ? payload.message
                          : copy.error;
                      if (!response.ok) throw new Error(errorMessage);
                      const publicUrl = payload && "public_url" in payload && typeof payload.public_url === "string"
                        ? payload.public_url.trim()
                        : "";
                      if (publicUrl) {
                        window.location.href = publicUrl;
                        return;
                      }
                      form.reset();
                      window.alert(copy.success);
                    } catch (error) {
                      window.alert(error instanceof Error ? error.message : copy.error);
                    } finally {
                      setIsSubmitting(false);
                    }
                  }}
                >
                  <label className="block">
                    <span className="mb-2 block text-sm font-semibold text-slate-200">{copy.emailLabel}</span>
                    <input className="min-h-12 w-full rounded-xl border-0 bg-white px-4 text-slate-950 outline-none ring-1 ring-white/20 transition-[box-shadow] placeholder:text-slate-400 focus:ring-4 focus:ring-orange-400/30" name="email" placeholder={copy.emailPlaceholder} required type="email" />
                  </label>
                  <label className="block">
                    <span className="mb-2 block text-sm font-semibold text-slate-200">{copy.mapsLabel}</span>
                    <input className="min-h-12 w-full rounded-xl border-0 bg-white px-4 text-slate-950 outline-none ring-1 ring-white/20 transition-[box-shadow] placeholder:text-slate-400 focus:ring-4 focus:ring-orange-400/30" name="yandexUrl" placeholder={copy.mapsPlaceholder} required type="url" />
                  </label>
                  <Button className="min-h-12 w-full rounded-xl text-base shadow-lg shadow-orange-950/30" disabled={isSubmitting} type="submit">
                    {isSubmitting ? <Loader2 className="h-5 w-5 animate-spin motion-reduce:animate-none" aria-hidden="true" /> : <ArrowRight className="h-5 w-5" aria-hidden="true" />}
                    {isSubmitting ? copy.submitting : copy.submit}
                  </Button>
                </form>
              </div>
            </div>
          </div>
        </section>

        <section className="bg-slate-950 px-4 py-6 text-white sm:px-6 lg:px-8" aria-label={copy.scale}>
          <div className="mx-auto flex max-w-7xl items-center justify-center gap-3 text-center text-base font-semibold sm:text-lg">
            <Users className="h-5 w-5 shrink-0 text-orange-400" aria-hidden="true" />
            <p>{copy.scale}</p>
          </div>
        </section>

        <section className="px-4 py-20 sm:px-6 lg:px-8 lg:py-28">
          <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:gap-20">
            <div>
              <span className="text-sm font-bold uppercase tracking-[0.16em] text-orange-600">01</span>
              <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">{copy.problemTitle}</h2>
            </div>
            <div className="space-y-5 text-lg leading-8 text-slate-600">
              {copy.problemParagraphs.map((paragraph, index) => (
                <p className={index === copy.problemParagraphs.length - 1 ? "font-semibold text-slate-950" : ""} key={paragraph}>{paragraph}</p>
              ))}
            </div>
          </div>
        </section>

        <section className="bg-orange-50/70 px-4 py-20 sm:px-6 lg:px-8 lg:py-28">
          <div className="mx-auto max-w-7xl">
            <div className="max-w-4xl">
              <span className="text-sm font-bold uppercase tracking-[0.16em] text-orange-600">02</span>
              <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">{copy.networkTitle}</h2>
              <div className="mt-7 grid gap-5 text-lg leading-8 text-slate-600 md:grid-cols-2">
                {copy.networkParagraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
              </div>
            </div>
            <div className="mt-12 grid items-stretch gap-4 md:grid-cols-[1fr_auto_1fr_auto_1fr]">
              {copy.networkLabels.map((label, index) => {
                const Icon = index === 0 ? Building2 : index === 1 ? ShieldCheck : Network;
                return (
                  <div className="contents" key={label}>
                    <div className="flex min-h-44 flex-col justify-between rounded-2xl bg-white p-6 shadow-[0_18px_50px_rgba(15,23,42,0.08)] ring-1 ring-black/5">
                      <Icon className="h-8 w-8 text-orange-500" aria-hidden="true" />
                      <p className="mt-8 text-lg font-bold text-slate-950">{label}</p>
                    </div>
                    {index < copy.networkLabels.length - 1 ? (
                      <ChevronRight className="mx-auto hidden h-6 w-6 self-center text-orange-400 md:block" aria-hidden="true" />
                    ) : null}
                  </div>
                );
              })}
            </div>
            <div className="mt-6 flex gap-3 rounded-2xl bg-slate-950 px-5 py-4 text-sm leading-6 text-slate-200 shadow-lg sm:items-center">
              <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-orange-400 sm:mt-0" aria-hidden="true" />
              <p>{copy.networkPrivacy}</p>
            </div>
          </div>
        </section>

        <section className="scroll-mt-24 px-4 py-20 sm:px-6 lg:px-8 lg:py-28" id="agents">
          <div className="mx-auto max-w-7xl">
            <div className="max-w-3xl">
              <span className="text-sm font-bold uppercase tracking-[0.16em] text-orange-600">{copy.tasksEyebrow}</span>
              <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">{copy.tasksTitle}</h2>
              <p className="mt-5 text-lg leading-8 text-slate-600">{copy.tasksIntro}</p>
            </div>
            <div className="mt-12 grid gap-5 md:grid-cols-2 lg:grid-cols-6">
              {copy.tasks.map((task, index) => {
                const Icon = taskIcons[index];
                return (
                  <article className={`rounded-2xl bg-white p-6 shadow-[0_18px_50px_rgba(15,23,42,0.08)] ring-1 ring-black/5 ${index < 3 ? "lg:col-span-2" : "lg:col-span-3"}`} key={task.title}>
                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-orange-100 text-orange-700">
                      <Icon className="h-5 w-5" aria-hidden="true" />
                    </div>
                    <h3 className="mt-6 text-xl font-bold leading-7">{task.title}</h3>
                    <p className="mt-3 leading-7 text-slate-600">{task.description}</p>
                  </article>
                );
              })}
            </div>
            <div className="mt-6 flex gap-3 rounded-2xl bg-orange-50 px-5 py-4 text-sm leading-6 text-slate-700 ring-1 ring-orange-100">
              <Check className="mt-0.5 h-5 w-5 shrink-0 text-orange-600" aria-hidden="true" />
              <p>{copy.retentionNote}</p>
            </div>
          </div>
        </section>

        <section className="bg-slate-950 px-4 py-20 text-white sm:px-6 lg:px-8 lg:py-28">
          <div className="mx-auto max-w-7xl">
            <div className="max-w-4xl">
              <span className="text-sm font-bold uppercase tracking-[0.16em] text-orange-400">{copy.workEyebrow}</span>
              <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">{copy.workTitle}</h2>
              <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-300">{copy.workIntro}</p>
            </div>
            <ol className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-5">
              {copy.steps.map((step, index) => {
                const Icon = stepIcons[index];
                return (
                  <li className="rounded-2xl bg-white/[0.06] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]" key={step.title}>
                    <div className="flex items-center justify-between">
                      <Icon className="h-6 w-6 text-orange-400" aria-hidden="true" />
                      <span className="tabular-nums text-sm font-bold text-slate-500">0{index + 1}</span>
                    </div>
                    <h3 className="mt-7 text-lg font-bold leading-6">{step.title}</h3>
                    <p className="mt-3 text-sm leading-6 text-slate-300">{step.description}</p>
                  </li>
                );
              })}
            </ol>
            <p className="mt-8 max-w-4xl rounded-2xl bg-orange-500 px-6 py-5 text-lg font-semibold leading-8 text-white shadow-xl shadow-orange-950/30">{copy.workSummary}</p>
          </div>
        </section>

        <section className="px-4 py-20 sm:px-6 lg:px-8 lg:py-28">
          <div className="mx-auto max-w-7xl">
            <div className="max-w-3xl">
              <span className="text-sm font-bold uppercase tracking-[0.16em] text-orange-600">{copy.casesEyebrow}</span>
              <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">{copy.casesTitle}</h2>
              <p className="mt-5 text-lg leading-8 text-slate-600">{copy.casesIntro}</p>
            </div>
            <div className="mt-12 grid gap-6 lg:grid-cols-3">
              {publishedCases.slice(0, 3).map((caseItem) => (
                <article className="flex h-full flex-col rounded-2xl bg-white p-6 shadow-[0_18px_50px_rgba(15,23,42,0.09)] ring-1 ring-black/5" key={caseItem.slug}>
                  <div className="flex flex-wrap gap-2">
                    {caseItem.metrics.map((metric) => (
                      <span className="rounded-full bg-orange-50 px-3 py-1.5 text-sm font-semibold text-orange-700" key={metric.label}>
                        <span className="tabular-nums">{metric.value}</span> {metric.label}
                      </span>
                    ))}
                  </div>
                  <h3 className="mt-6 text-2xl font-bold leading-8">{caseItem.title}</h3>
                  <dl className="mt-6 flex-1 space-y-5 text-sm leading-6">
                    <div>
                      <dt className="font-bold uppercase tracking-[0.1em] text-slate-400">{copy.situation}</dt>
                      <dd className="mt-1 text-slate-600">{caseItem.situation}</dd>
                    </div>
                    <div>
                      <dt className="font-bold uppercase tracking-[0.1em] text-slate-400">{copy.workDone}</dt>
                      <dd className="mt-2">
                        <ul className="space-y-2 text-slate-600">
                          {caseItem.actions.slice(0, 2).map((action) => <li className="flex gap-2" key={action}><Check className="mt-1 h-4 w-4 shrink-0 text-orange-500" aria-hidden="true" />{action}</li>)}
                        </ul>
                      </dd>
                    </div>
                    <div>
                      <dt className="font-bold uppercase tracking-[0.1em] text-slate-400">{copy.result}</dt>
                      <dd className="mt-1 text-slate-600">{caseItem.result}</dd>
                    </div>
                  </dl>
                  <Link className="mt-7 inline-flex min-h-10 items-center font-semibold text-orange-600 transition-colors hover:text-orange-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 focus-visible:ring-offset-2" to={`/cases/${caseItem.slug}`}>
                    {caseItem.title}
                    <ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
                  </Link>
                </article>
              ))}
            </div>
            <Button asChild className="mt-8 min-h-12 rounded-xl px-6" variant="outline">
              <Link to="/cases">{copy.allCases}<ArrowRight className="h-4 w-4" aria-hidden="true" /></Link>
            </Button>
          </div>
        </section>

        <section className="bg-orange-50 px-4 py-16 sm:px-6 lg:px-8">
          <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-7 rounded-[2rem] bg-white p-7 shadow-[0_24px_70px_rgba(15,23,42,0.10)] ring-1 ring-black/5 sm:p-10 lg:flex-row lg:items-center">
            <div className="max-w-3xl">
              <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">{copy.auditTitle}</h2>
              <p className="mt-4 text-lg leading-8 text-slate-600">{copy.auditText}</p>
            </div>
            <Button className="min-h-12 shrink-0 rounded-xl px-6" onClick={scrollToAudit} size="lg">
              {copy.submit}<ArrowRight className="h-5 w-5" aria-hidden="true" />
            </Button>
          </div>
        </section>

        <section className="bg-orange-500 px-4 py-20 text-white sm:px-6 lg:px-8 lg:py-28" id="cta">
          <div className="mx-auto max-w-5xl text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">{copy.finalTitle}</h2>
            <p className="mx-auto mt-6 max-w-3xl text-lg leading-8 text-orange-50 sm:text-xl">{copy.finalText}</p>
            <div className="mt-9 flex flex-col justify-center gap-3 sm:flex-row">
              <Button asChild className="min-h-12 rounded-xl bg-slate-950 px-7 text-base text-white hover:bg-slate-800" size="lg">
                <Link to="/login">{copy.tryFree}<ArrowRight className="h-5 w-5" aria-hidden="true" /></Link>
              </Button>
              <Button asChild className="min-h-12 rounded-xl border-white/60 bg-white px-7 text-base text-slate-950 hover:bg-orange-50 hover:text-slate-950" size="lg" variant="outline">
                <Link to="/contact">{copy.talkExpert}</Link>
              </Button>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
};

export default Index;
