import { ArrowLeft, ArrowRight, CalendarDays, CheckCircle2, Download, Sparkles } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import Footer from "@/components/Footer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { ContentSection, RelatedLink } from "@/content/contentTypes";
import { formatContentDate } from "./contentSeo";

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
  href: string;
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

export const MaterialCard = ({ href, label, title, excerpt, date, tags, accent = "orange" }: MaterialCardProps) => (
  <Link className="group block h-full" to={href}>
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
            {formatContentDate(date)}
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
          Читать дальше
          <ArrowRight className="ml-2 h-4 w-4 transition group-hover:translate-x-1" />
        </div>
      </CardContent>
    </Card>
  </Link>
);

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

export const DetailHeader = ({ backHref, backLabel, label, title, excerpt, date, tags }: DetailHeaderProps) => (
  <section className="px-4 py-12 sm:px-6 lg:px-8 bg-gradient-to-br from-orange-50 via-white to-amber-50">
    <div className="mx-auto max-w-4xl">
      <Link className="mb-8 inline-flex items-center text-sm font-semibold text-orange-600 hover:text-orange-700" to={backHref}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        {backLabel}
      </Link>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <Badge className="rounded-full bg-orange-100 px-4 py-1.5 text-orange-700 hover:bg-orange-100">{label}</Badge>
        <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <CalendarDays className="h-4 w-4" />
          {formatContentDate(date)}
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
  </section>
);

export const SectionRenderer = ({ sections }: { sections: ContentSection[] }) => (
  <div className="space-y-10">
    {sections.map((section) => (
      <section key={section.title}>
        <h2 className="text-2xl font-bold text-gray-950">{section.title}</h2>
        {section.body ? <p className="mt-4 text-lg leading-8 text-gray-700">{section.body}</p> : null}
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
      </section>
    ))}
  </div>
);

export const RelatedMaterials = ({ items }: RelatedMaterialsProps) => {
  if (items.length === 0) {
    return null;
  }

  return (
    <section className="mt-16">
      <div className="mb-6 flex items-center gap-2">
        <Sparkles className="h-5 w-5 text-orange-500" />
        <h2 className="text-2xl font-bold text-gray-950">Читайте также</h2>
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

export const BottomCta = () => (
  <section className="mt-16 rounded-3xl border border-orange-200 bg-gradient-to-br from-orange-500 to-amber-500 p-8 text-white shadow-2xl shadow-orange-500/20 sm:p-10">
    <h2 className="text-3xl font-bold">Хотите понять, где LocalOS даст рост именно вам?</h2>
    <p className="mt-4 max-w-2xl text-lg text-white/90">
      Запустите бесплатный аудит карточки: покажем сильные места, слабые сценарии спроса и первые действия без бюджета на рекламу.
    </p>
    <div className="mt-7 flex flex-col gap-3 sm:flex-row">
      <Button asChild className="bg-white text-orange-600 hover:bg-orange-50">
        <Link to="/login">Получить бесплатный аудит</Link>
      </Button>
      <Button asChild className="border-white/70 text-white hover:bg-white/10" variant="outline">
        <Link to="/contact">Обсудить внедрение</Link>
      </Button>
    </div>
  </section>
);

export const DownloadBlock = ({ href }: DownloadBlockProps) => (
  <div className="mt-10 rounded-3xl border border-orange-200 bg-orange-50 p-6">
    <h2 className="text-2xl font-bold text-gray-950">Скачать материал</h2>
    <p className="mt-3 text-gray-700">
      Файловое хранилище для материалов можно подключить следующим этапом. Пока кнопка оставлена как место под скачивание.
    </p>
    <Button asChild className="mt-5 bg-orange-500 hover:bg-orange-600">
      <a href={href}>
        <Download className="mr-2 h-4 w-4" />
        Скачать скоро
      </a>
    </Button>
  </div>
);
