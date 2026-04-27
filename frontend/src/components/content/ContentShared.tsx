import { Link } from "react-router-dom";
import { ArrowLeft, ArrowRight, Download, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import type { ContentSection, RelatedLink } from "@/content/contentTypes";

export const formatDate = (value: string) =>
  new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(value));

export const ContentShell = ({ children }: { children: React.ReactNode }) => (
  <main className="min-h-screen bg-gradient-to-br from-orange-50/60 via-white to-amber-50/40">
    {children}
  </main>
);

export const ContentBreadcrumbs = ({
  sectionHref,
  sectionTitle,
  currentTitle,
}: {
  sectionHref: string;
  sectionTitle: string;
  currentTitle?: string;
}) => (
  <Breadcrumb className="mb-8">
    <BreadcrumbList>
      <BreadcrumbItem>
        <BreadcrumbLink asChild>
          <Link to="/">LocalOS</Link>
        </BreadcrumbLink>
      </BreadcrumbItem>
      <BreadcrumbSeparator />
      <BreadcrumbItem>
        {currentTitle ? (
          <BreadcrumbLink asChild>
            <Link to={sectionHref}>{sectionTitle}</Link>
          </BreadcrumbLink>
        ) : (
          <BreadcrumbPage>{sectionTitle}</BreadcrumbPage>
        )}
      </BreadcrumbItem>
      {currentTitle ? (
        <>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{currentTitle}</BreadcrumbPage>
          </BreadcrumbItem>
        </>
      ) : null}
    </BreadcrumbList>
  </Breadcrumb>
);

export const CategoryPills = ({
  values,
  active,
  onChange,
}: {
  values: string[];
  active: string;
  onChange: (value: string) => void;
}) => (
  <div className="flex flex-wrap gap-2">
    {["Все", ...values].map((value) => (
      <button
        key={value}
        type="button"
        onClick={() => onChange(value)}
        className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
          active === value
            ? "border-orange-500 bg-orange-500 text-white shadow-lg shadow-orange-500/20"
            : "border-orange-200 bg-white text-slate-700 hover:border-orange-400 hover:text-orange-700"
        }`}
      >
        {value}
      </button>
    ))}
  </div>
);

export const ContentCard = ({
  href,
  eyebrow,
  title,
  excerpt,
  date,
  tags,
}: {
  href: string;
  eyebrow: string;
  title: string;
  excerpt: string;
  date: string;
  tags: string[];
}) => (
  <Link to={href} className="group block">
    <Card className="h-full overflow-hidden border-orange-100 bg-white/90 shadow-sm transition duration-300 hover:-translate-y-1 hover:border-orange-300 hover:shadow-2xl hover:shadow-orange-500/10">
      <CardContent className="flex h-full flex-col p-6">
        <div className="mb-5 flex items-center justify-between gap-3">
          <Badge variant="outline" className="border-orange-200 bg-orange-50 text-orange-700">
            {eyebrow}
          </Badge>
          <span className="text-xs text-slate-500">{formatDate(date)}</span>
        </div>
        <h2 className="text-2xl font-bold leading-tight text-slate-950 transition group-hover:text-orange-700">
          {title}
        </h2>
        <p className="mt-4 flex-1 text-base leading-7 text-slate-600">{excerpt}</p>
        <div className="mt-6 flex flex-wrap gap-2">
          {tags.slice(0, 3).map((tag) => (
            <span key={tag} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
              {tag}
            </span>
          ))}
        </div>
        <div className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-orange-600">
          Читать материал <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
        </div>
      </CardContent>
    </Card>
  </Link>
);

export const ContentBody = ({ sections }: { sections: ContentSection[] }) => (
  <div className="space-y-10">
    {sections.map((section) => (
      <section key={section.title} className="rounded-3xl border border-orange-100 bg-white p-6 shadow-sm sm:p-8">
        <h2 className="text-2xl font-bold text-slate-950">{section.title}</h2>
        {section.body ? <p className="mt-4 text-lg leading-8 text-slate-700">{section.body}</p> : null}
        {section.items ? (
          <ul className="mt-5 space-y-3">
            {section.items.map((item) => (
              <li key={item} className="flex gap-3 text-base leading-7 text-slate-700">
                <span className="mt-2 h-2 w-2 flex-none rounded-full bg-orange-500" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    ))}
  </div>
);

export const RelatedMaterials = ({ items }: { items: RelatedLink[] }) => (
  <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
    <h2 className="text-2xl font-bold text-slate-950">Читайте также</h2>
    <div className="mt-5 grid gap-4 sm:grid-cols-2">
      {items.map((item) => (
        <Link
          key={`${item.href}-${item.title}`}
          to={item.href}
          className="rounded-2xl border border-orange-100 bg-orange-50/50 p-5 transition hover:border-orange-300 hover:bg-orange-50"
        >
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-orange-600">{item.label}</div>
          <div className="mt-2 text-lg font-bold text-slate-950">{item.title}</div>
        </Link>
      ))}
    </div>
  </section>
);

export const ContentCTA = () => (
  <section className="overflow-hidden rounded-[2rem] bg-slate-950 p-8 text-white shadow-2xl shadow-orange-500/10 sm:p-10">
    <div className="max-w-3xl">
      <p className="text-sm font-semibold uppercase tracking-[0.22em] text-orange-300">LocalOS</p>
      <h2 className="mt-3 text-3xl font-bold sm:text-4xl">Хотите понять, где бизнес теряет клиентов?</h2>
      <p className="mt-4 text-lg leading-8 text-slate-300">
        Сделаем быстрый аудит карточки, отзывов и точек роста. Покажем, что можно улучшить без лишних затрат на рекламу.
      </p>
      <div className="mt-7 flex flex-col gap-3 sm:flex-row">
        <Button asChild size="lg" className="bg-orange-500 text-white hover:bg-orange-600">
          <Link to="/#hero-form">Получить бесплатный аудит</Link>
        </Button>
        <Button asChild size="lg" variant="outline" className="border-white/30 bg-white/10 text-white hover:bg-white/20">
          <Link to="/about#pricing">Посмотреть тарифы</Link>
        </Button>
      </div>
    </div>
  </section>
);

export const BackToSection = ({ href, label }: { href: string; label: string }) => (
  <Link to={href} className="mb-8 inline-flex items-center gap-2 text-sm font-semibold text-orange-700 hover:text-orange-900">
    <ArrowLeft className="h-4 w-4" />
    {label}
  </Link>
);

export const DownloadButton = ({ href }: { href?: string }) => (
  <Button asChild className="bg-orange-500 text-white hover:bg-orange-600">
    <a href={href || "#download-soon"}>
      <Download className="mr-2 h-4 w-4" />
      Скачать материал
    </a>
  </Button>
);

export const DocumentPlaceholder = () => (
  <div className="rounded-3xl border border-dashed border-orange-300 bg-orange-50/70 p-6">
    <div className="flex items-start gap-4">
      <div className="rounded-2xl bg-white p-3 text-orange-600 shadow-sm">
        <FileText className="h-6 w-6" />
      </div>
      <div>
        <h2 className="text-xl font-bold text-slate-950">Файл скоро будет доступен</h2>
        <p className="mt-2 text-slate-700">
          Сейчас это демо-страница документа. Когда подключим файловое хранилище, здесь появится прямая ссылка на скачивание.
        </p>
      </div>
    </div>
  </div>
);
