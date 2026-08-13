import { ArrowLeft, ArrowRight, CalendarDays, Check, CheckCircle2, Download, Loader2, Sparkles } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import Footer from "@/components/Footer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { ContentSection, RelatedLink } from "@/content/contentTypes";
import { formatContentDate } from "./contentSeo";
import { useLanguage } from "@/i18n/LanguageContext";
import { contentCopy } from "@/content/contentCopy";

type PageFrameProps = {
  children: ReactNode;
};

type ListHeroProps = {
  eyebrow: string;
  title: string;
  description: string;
};

type FilterPillsProps = {
  values: string[];
  activeValue: string;
  onChange: (value: string) => void;
};

type MaterialCardProps = {
  href: string;
  label: string;
  title: string;
  excerpt: string;
  date: string;
  tags: string[];
  accent?: string;
};

type BreadcrumbsProps = {
  sectionTitle: string;
  sectionHref: string;
  current?: string;
};

type DetailHeaderProps = {
  backHref: string;
  backLabel: string;
  label: string;
  title: string;
  excerpt: string;
  date: string;
  tags: string[];
};

type RelatedMaterialsProps = {
  items: RelatedLink[];
};

type DownloadBlockProps = {
  available: boolean;
  materialSlug: string;
};

type SectionRendererProps = {
  sections: ContentSection[];
  renderAfterSection?: (section: ContentSection) => ReactNode;
};

const inlineLinkClassName = "font-semibold text-orange-600 underline underline-offset-4 hover:text-orange-700";

const renderLinkedText = (text: string, links: ContentSection["bodyLinks"] = []) => {
  const nodes: ReactNode[] = [];
  const unresolvedLinks: NonNullable<ContentSection["bodyLinks"]> = [];
  let remaining = text;
  let key = 0;

  links.forEach((link) => {
    const index = remaining.indexOf(link.text);

    if (index < 0) {
      unresolvedLinks.push(link);
      return;
    }

    const before = remaining.slice(0, index);

    if (before) {
      nodes.push(before);
    }

    nodes.push(
      <Link className={inlineLinkClassName} key={`${link.href}-${key}`} to={link.href}>
        {link.text}
      </Link>
    );
    key += 1;
    remaining = remaining.slice(index + link.text.length);
  });

  if (remaining) {
    nodes.push(remaining);
  }

  unresolvedLinks.forEach((link) => {
    nodes.push(" ");
    nodes.push(
      <Link className={inlineLinkClassName} key={`${link.href}-fallback-${key}`} to={link.href}>
        {link.text}
      </Link>
    );
    key += 1;
  });

  return nodes;
};

export const PageFrame = ({ children }: PageFrameProps) => (
  <div className="min-h-screen bg-background">
    {children}
    <Footer />
  </div>
);

export const ListHero = ({ eyebrow, title, description }: ListHeroProps) => (
  <section className="px-4 py-20 sm:px-6 lg:px-8 bg-gradient-to-br from-orange-50 via-white to-amber-50">
    <div className="mx-auto max-w-7xl">
      <Badge className="mb-6 rounded-full bg-orange-100 px-4 py-1.5 text-orange-700 hover:bg-orange-100">
        {eyebrow}
      </Badge>
      <h1 className="max-w-4xl text-4xl font-bold tracking-tight text-gray-950 sm:text-5xl lg:text-6xl">
        {title}
      </h1>
      <p className="mt-6 max-w-3xl text-lg leading-8 text-gray-600 sm:text-xl">{description}</p>
    </div>
  </section>
);

export const FilterPills = ({ values, activeValue, onChange }: FilterPillsProps) => (
  <div className="flex flex-wrap gap-3">
    {values.map((value) => {
      const isActive = value === activeValue;

      return (
        <button
          className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
            isActive
              ? "border-orange-500 bg-orange-500 text-white shadow-lg shadow-orange-500/20"
              : "border-orange-200 bg-white text-gray-700 hover:border-orange-400 hover:text-orange-700"
          }`}
          key={value}
          onClick={() => onChange(value)}
          type="button"
        >
          {value}
        </button>
      );
    })}
  </div>
);

export const MaterialCard = ({ href, label, title, excerpt, date, tags, accent = "orange" }: MaterialCardProps) => {
  const { language } = useLanguage();
  const copy = contentCopy[language].shared;

  return <Link className="group block h-full" to={href}>
    <Card className="h-full overflow-hidden border-orange-100 bg-white transition duration-300 hover:-translate-y-1 hover:border-orange-300 hover:shadow-2xl hover:shadow-orange-500/10">
      <div
        className={`h-2 ${
          accent === "amber" ? "bg-amber-400" : accent === "slate" ? "bg-slate-800" : "bg-orange-500"
        }`}
      />
      <CardContent className="flex h-full flex-col p-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <Badge variant="secondary" className="rounded-full bg-orange-50 text-orange-700">
            {label}
          </Badge>
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <CalendarDays className="h-3.5 w-3.5" />
            {formatContentDate(date, language)}
          </span>
        </div>
        <h2 className="text-2xl font-bold leading-tight text-gray-950 transition group-hover:text-orange-600">
          {title}
        </h2>
        <p className="mt-4 flex-1 text-base leading-7 text-gray-600">{excerpt}</p>
        <div className="mt-6 flex flex-wrap gap-2">
          {tags.slice(0, 3).map((tag) => (
            <span className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600" key={tag}>
              {tag}
            </span>
          ))}
        </div>
        <div className="mt-6 flex items-center text-sm font-semibold text-orange-600">
          {copy.readMore}
          <ArrowRight className="ml-2 h-4 w-4 transition group-hover:translate-x-1" />
        </div>
      </CardContent>
    </Card>
  </Link>;
};

export const Breadcrumbs = ({ sectionTitle, sectionHref, current }: BreadcrumbsProps) => (
  <nav className="mb-8 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
    <Link className="hover:text-orange-600" to="/">
      LocalOS
    </Link>
    <span>/</span>
    <Link className="hover:text-orange-600" to={sectionHref}>
      {sectionTitle}
    </Link>
    {current ? (
      <>
        <span>/</span>
        <span className="text-gray-700">{current}</span>
      </>
    ) : null}
  </nav>
);

export const DetailHeader = ({ backHref, backLabel, label, title, excerpt, date, tags }: DetailHeaderProps) => {
  const { language } = useLanguage();

  return <section className="px-4 py-12 sm:px-6 lg:px-8 bg-gradient-to-br from-orange-50 via-white to-amber-50">
    <div className="mx-auto max-w-4xl">
      <Link className="mb-8 inline-flex items-center text-sm font-semibold text-orange-600 hover:text-orange-700" to={backHref}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        {backLabel}
      </Link>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <Badge className="rounded-full bg-orange-100 px-4 py-1.5 text-orange-700 hover:bg-orange-100">{label}</Badge>
        <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <CalendarDays className="h-4 w-4" />
          {formatContentDate(date, language)}
        </span>
      </div>
      <h1 className="text-4xl font-bold tracking-tight text-gray-950 sm:text-5xl">{title}</h1>
      <p className="mt-6 text-xl leading-8 text-gray-600">{excerpt}</p>
      <div className="mt-8 flex flex-wrap gap-2">
        {tags.map((tag) => (
          <span className="rounded-full bg-white px-3 py-1 text-sm text-gray-600 shadow-sm" key={tag}>
            {tag}
          </span>
        ))}
      </div>
    </div>
  </section>;
};

export const SectionRenderer = ({ sections, renderAfterSection }: SectionRendererProps) => (
  <div className="space-y-10">
    {sections.map((section) => (
      <section key={section.title}>
        <h2 className="text-2xl font-bold text-gray-950">{section.title}</h2>
        {section.body ? (
          <p className="mt-4 text-lg leading-8 text-gray-700">
            {renderLinkedText(section.body, section.bodyLinks)}
          </p>
        ) : null}
        {section.items ? (
          <ul className="mt-5 space-y-3">
            {section.items.map((item) => (
              <li className="flex gap-3 text-lg leading-7 text-gray-700" key={item}>
                <CheckCircle2 className="mt-1 h-5 w-5 flex-shrink-0 text-orange-500" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        ) : null}
        {renderAfterSection ? renderAfterSection(section) : null}
      </section>
    ))}
  </div>
);

export const RelatedMaterials = ({ items }: RelatedMaterialsProps) => {
  const { language } = useLanguage();
  if (items.length === 0) {
    return null;
  }

  return (
    <section className="mt-16">
      <div className="mb-6 flex items-center gap-2">
        <Sparkles className="h-5 w-5 text-orange-500" />
        <h2 className="text-2xl font-bold text-gray-950">{contentCopy[language].shared.related}</h2>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {items.map((item) => (
          <Link
            className="rounded-2xl border border-orange-100 bg-orange-50/60 p-5 transition hover:border-orange-300 hover:bg-orange-50"
            key={item.href}
            to={item.href}
          >
            <Badge className="mb-3 bg-white text-orange-700 hover:bg-white">{item.label}</Badge>
            <div className="font-semibold leading-6 text-gray-950">{item.title}</div>
          </Link>
        ))}
      </div>
    </section>
  );
};

export const BottomCta = () => {
  const { language } = useLanguage();
  const copy = contentCopy[language].shared;

  return <section className="mt-16 rounded-3xl border border-orange-200 bg-gradient-to-br from-orange-500 to-amber-500 p-8 text-white shadow-2xl shadow-orange-500/20 sm:p-10">
    <h2 className="text-3xl font-bold">{copy.ctaTitle}</h2>
    <p className="mt-4 max-w-2xl text-lg text-white/90">{copy.ctaDescription}</p>
    <div className="mt-7 flex flex-col gap-3 sm:flex-row">
      <Button asChild className="bg-white text-orange-600 hover:bg-orange-50">
        <Link to="/login">{copy.audit}</Link>
      </Button>
      <Button asChild className="border-white bg-white text-orange-700 shadow-sm hover:bg-orange-50 hover:text-orange-800" variant="outline">
        <Link to="/contact">{copy.discuss}</Link>
      </Button>
    </div>
  </section>;
};

export const DownloadBlock = ({ available, materialSlug }: DownloadBlockProps) => {
  const { language } = useLanguage();
  const isMarketingTable = materialSlug === "tablica-kontrolya-lokalnogo-marketinga";
  const downloadCopy = language === "ru" ? {
    title: isMarketingTable ? "Скачать рабочую таблицу" : "Скачать чек-лист",
    description: isMarketingTable
      ? "XLSX-таблица для еженедельного контроля карт, отзывов, публикаций, партнёрств и повторных касаний. Укажите email и подтвердите согласие — скачивание начнётся сразу."
      : "PDF с проверками карточки компании. Укажите email и подтвердите согласие — скачивание начнётся сразу.",
    privacyNote: "Без подписки на рассылку. Email нужен для получения материала.",
    consent: "Я согласен на обработку персональных данных и принимаю",
    policy: "политику обработки персональных данных",
    submit: isMarketingTable ? "Получить таблицу" : "Получить чек-лист",
    submitting: "Подготавливаем файл…",
    repeat: "Скачать ещё раз",
    success: "Скачивание началось. Если файл не открылся, нажмите кнопку ещё раз.",
    unavailable: "Материал готовится. Мы добавим файл на эту страницу.",
    error: "Не удалось подготовить скачивание. Попробуйте ещё раз.",
  } : {
    title: isMarketingTable ? "Download the working spreadsheet" : "Download the checklist",
    description: isMarketingTable
      ? "An XLSX spreadsheet for weekly tracking of maps, reviews, posts, partnerships, and customer follow-ups. Enter your email and confirm consent to start the download."
      : "A PDF checklist for your business listing. Enter your email and confirm consent to start the download.",
    privacyNote: "No newsletter subscription. Your email is used to provide the material.",
    consent: "I consent to the processing of personal data and accept the",
    policy: "personal data processing policy",
    submit: isMarketingTable ? "Get the spreadsheet" : "Get the checklist",
    submitting: "Preparing the file…",
    repeat: "Download again",
    success: "Your download has started. If the file did not open, use the button again.",
    unavailable: "This material is being prepared. We will add the file to this page.",
    error: "We could not prepare the download. Please try again.",
  };
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [companySite, setCompanySite] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [downloadUrl, setDownloadUrl] = useState("");

  if (!available) {
    return (
      <section className="mt-10 rounded-3xl bg-orange-50 p-6 shadow-[0_0_0_1px_rgba(249,115,22,0.24),0_10px_30px_rgba(249,115,22,0.06)] sm:p-8">
        <h2 className="text-balance text-2xl font-bold text-gray-950">{downloadCopy.title}</h2>
        <p className="mt-3 text-pretty text-gray-700">{downloadCopy.unavailable}</p>
      </section>
    );
  }

  const startDownload = (url: string) => {
    const link = document.createElement("a");
    link.href = url;
    link.download = "";
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      const response = await fetch("/api/public/material-downloads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          material_slug: materialSlug,
          personal_data_consent: consent,
          source_language: language,
          company_site: companySite,
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.download_url) {
        throw new Error(payload.message || downloadCopy.error);
      }

      setDownloadUrl(payload.download_url);
      startDownload(payload.download_url);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : downloadCopy.error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="mt-10 overflow-hidden rounded-3xl bg-orange-50 p-6 shadow-[0_0_0_1px_rgba(249,115,22,0.24),0_10px_30px_rgba(249,115,22,0.08)] sm:p-8">
      <div className="grid gap-7 md:grid-cols-[minmax(0,0.9fr)_minmax(320px,1.1fr)] md:items-start">
        <div>
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-orange-500 text-white shadow-[0_8px_20px_rgba(249,115,22,0.22)]">
            <Download className="h-5 w-5" aria-hidden="true" />
          </div>
          <h2 className="mt-5 text-balance text-2xl font-bold text-gray-950 sm:text-3xl">{downloadCopy.title}</h2>
          <p className="mt-3 max-w-lg text-pretty leading-7 text-gray-700">
            {downloadCopy.description}
          </p>
          <p className="mt-4 text-sm text-gray-500">{downloadCopy.privacyNote}</p>
        </div>

        <form className="rounded-2xl bg-white p-4 shadow-[0_0_0_1px_rgba(0,0,0,0.06),0_2px_4px_rgba(0,0,0,0.04)] sm:p-5" onSubmit={handleSubmit}>
          <label className="block text-sm font-semibold text-gray-950" htmlFor={`material-email-${materialSlug}`}>
            Email
          </label>
          <Input
            autoComplete="email"
            className="mt-2 min-h-11 rounded-xl border-gray-200 bg-white focus-visible:ring-orange-500"
            id={`material-email-${materialSlug}`}
            inputMode="email"
            onChange={(event) => setEmail(event.target.value)}
            placeholder="name@company.ru"
            required
            type="email"
            value={email}
          />
          <input
            aria-hidden="true"
            autoComplete="off"
            className="absolute h-px w-px overflow-hidden opacity-0"
            name="company_site"
            onChange={(event) => setCompanySite(event.target.value)}
            tabIndex={-1}
            value={companySite}
          />

          <label className="mt-4 flex min-h-11 cursor-pointer items-start gap-3 rounded-xl p-2 text-sm leading-5 text-gray-600 transition-[background-color] duration-150 hover:bg-orange-50/80">
            <input
              checked={consent}
              className="mt-0.5 h-5 w-5 flex-shrink-0 rounded border-gray-300 accent-orange-500"
              onChange={(event) => setConsent(event.target.checked)}
              required
              type="checkbox"
            />
            <span>
              {downloadCopy.consent}{" "}
              <Link className="font-semibold text-orange-700 underline underline-offset-2 hover:text-orange-800" target="_blank" to="/privacy">
                {downloadCopy.policy}
              </Link>
            </span>
          </label>

          {error ? <p aria-live="polite" className="mt-3 text-pretty text-sm font-medium text-red-600" role="alert">{error}</p> : null}
          {downloadUrl && !error ? (
            <p aria-live="polite" className="mt-3 flex items-center gap-2 text-pretty text-sm font-medium text-emerald-700">
              <Check className="h-4 w-4" aria-hidden="true" />
              {downloadCopy.success}
            </p>
          ) : null}

          <Button
            className="mt-4 min-h-11 w-full bg-orange-500 pl-4 pr-3.5 transition-[background-color,scale] duration-150 hover:bg-orange-600 active:scale-[0.96]"
            disabled={isSubmitting || !consent || !email.trim()}
            onClick={downloadUrl && !error ? (event) => {
              event.preventDefault();
              startDownload(downloadUrl);
            } : undefined}
            type="submit"
          >
            {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden="true" /> : <Download className="mr-2 h-4 w-4" aria-hidden="true" />}
            {isSubmitting ? downloadCopy.submitting : downloadUrl && !error ? downloadCopy.repeat : downloadCopy.submit}
          </Button>
        </form>
      </div>
    </section>
  );
};
