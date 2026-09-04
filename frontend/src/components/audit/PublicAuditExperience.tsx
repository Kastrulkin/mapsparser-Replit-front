import { useState, type ReactNode } from 'react';
import {
  Camera,
  Check,
  ChevronDown,
  ExternalLink,
  ImagePlus,
  MessageSquareText,
  Newspaper,
  Sparkles,
} from 'lucide-react';

export type PublicAuditProblem = {
  id: string;
  title: string;
  importance: string;
  actions: string[];
  problem?: string;
  evidence?: string;
  outcome?: string;
};

export type PublicAuditService = {
  name: string;
  category?: string;
  description?: string;
  improvedName?: string;
  price?: string;
};

export type PublicAuditReview = {
  author: string;
  rating?: number;
  text?: string;
  reply?: string;
};

export type PublicAuditNews = {
  id: string;
  title?: string;
  date?: string;
  text?: string;
};

export type PublicAuditLabels = {
  score: string;
  fixYourself: string;
  prepareWithLocalOS: string;
  fixToday: string;
  fixTodayHint: string;
  whyImportant: string;
  actions: string;
  details: string;
  hideDetails: string;
  strengths: string;
  noStrengths: string;
  customerUnderstanding: string;
  strongAnswers: string;
  weakAnswers: string;
  missingPhotos: string;
  needPhoto: string;
  cardData: string;
  services: string;
  photos: string;
  reviews: string;
  news: string;
  showMore: string;
  showLess: string;
  noReply: string;
  hasReply: string;
  showFull: string;
  hideFull: string;
  fullPlan: string;
  fullPlanHint: string;
  hidePlan: string;
  openMap: string;
  companyLogo: string;
};

type LanguageLink = {
  code: string;
  label: string;
  href: string;
  active: boolean;
};

export type PublicAuditExperienceProps = {
  direction?: 'ltr' | 'rtl';
  eyebrow: string;
  title: string;
  diagnosis: string;
  score?: number;
  status: string;
  logoUrl?: string;
  labels: PublicAuditLabels;
  languages?: LanguageLink[];
  problems: PublicAuditProblem[];
  strengths: string[];
  strongDemand: string[];
  weakDemand: string[];
  missingPhotos: string[];
  services: PublicAuditService[];
  photos: string[];
  reviews: PublicAuditReview[];
  news: PublicAuditNews[];
  photoAlt: (index: number) => string;
  onPrepareWithLocalOS: () => void;
  fullPlan: ReactNode;
  contentPlan?: ReactNode;
  auditTabLabel?: string;
  contentTabLabel?: string;
  initialView?: 'audit' | 'content';
  mapUrl?: string;
};

const surfaceShadow = 'shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_1px_2px_-1px_rgba(15,23,42,0.06),0_12px_32px_rgba(15,23,42,0.05)]';
const focusRing = 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2';

const ToggleIcon = ({ open }: { open: boolean }) => (
  <ChevronDown className={`h-4 w-4 shrink-0 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
);

const stars = (rating?: number): string => {
  if (!rating) return '';
  const rounded = Math.max(1, Math.min(5, Math.round(rating)));
  return `${'★'.repeat(rounded)}${'☆'.repeat(5 - rounded)}`;
};

export const PublicAuditExperience = ({
  direction = 'ltr',
  eyebrow,
  title,
  diagnosis,
  score,
  status,
  logoUrl,
  labels,
  languages = [],
  problems,
  strengths,
  strongDemand,
  weakDemand,
  missingPhotos,
  services,
  photos,
  reviews,
  news,
  photoAlt,
  onPrepareWithLocalOS,
  fullPlan,
  contentPlan,
  auditTabLabel = 'Аудит карточки',
  contentTabLabel = 'Контент-план',
  initialView = 'audit',
  mapUrl,
}: PublicAuditExperienceProps) => {
  const [expandedProblems, setExpandedProblems] = useState<Set<string>>(new Set());
  const [expandedNews, setExpandedNews] = useState<Set<string>>(new Set());
  const [servicesExpanded, setServicesExpanded] = useState(false);
  const [planExpanded, setPlanExpanded] = useState(false);
  const [activeView, setActiveView] = useState<'audit' | 'content'>(initialView);

  const toggleProblem = (id: string) => {
    setExpandedProblems((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleNews = (id: string) => {
    setExpandedNews((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const visibleServices = servicesExpanded ? services : services.slice(0, 4);
  const hasCardData = services.length > 0 || photos.length > 0 || reviews.length > 0 || news.length > 0;

  return (
    <div dir={direction} className="min-h-screen bg-[radial-gradient(ellipse_at_top_right,_rgba(56,189,248,0.16),_transparent_42%),radial-gradient(ellipse_at_bottom_left,_rgba(249,115,22,0.10),_transparent_38%),linear-gradient(to_bottom,_#f8fafc,_#ffffff)] antialiased">
      <main className="mx-auto max-w-5xl space-y-5 px-4 py-6 md:py-8">
        <section className={`overflow-hidden rounded-[2rem] bg-white ${surfaceShadow}`}>
          <div className="p-5 md:p-8">
            <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
              <div className="flex min-w-0 items-start gap-4">
                {logoUrl ? (
                  <img
                    src={logoUrl}
                    alt={labels.companyLogo}
                    className="h-14 w-14 shrink-0 rounded-2xl bg-white object-cover outline outline-1 -outline-offset-1 outline-black/10 md:h-16 md:w-16"
                  />
                ) : null}
                <div className="min-w-0">
                  <div className="text-xs font-bold uppercase tracking-[0.2em] text-orange-600">{eyebrow}</div>
                  <h1 className="mt-2 max-w-3xl text-balance text-3xl font-black tracking-tight text-slate-950 md:text-5xl">{title}</h1>
                </div>
              </div>
              {languages.length > 1 ? (
                <nav aria-label="Language" className="flex flex-wrap gap-2 md:justify-end">
                  {languages.map((language) => (
                    <a
                      key={language.code}
                      href={language.href}
                      className={`inline-flex min-h-10 items-center rounded-full px-3 text-xs font-semibold shadow-[0_0_0_1px_rgba(15,23,42,0.10)] transition-[background-color,color,box-shadow] active:scale-[0.96] ${focusRing} ${
                        language.active
                          ? 'bg-sky-50 text-sky-700 shadow-[0_0_0_1px_rgba(14,165,233,0.55)]'
                          : 'bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-950'
                      }`}
                    >
                      {language.label}
                    </a>
                  ))}
                </nav>
              ) : null}
            </div>

            <div className="mt-6 flex flex-wrap items-center gap-2">
              <span className="inline-flex min-h-10 items-center rounded-full bg-slate-950 px-4 text-sm font-bold text-white">
                {status}
              </span>
              {score ? (
                <span className="inline-flex min-h-10 items-center rounded-full bg-slate-100 px-4 text-sm font-semibold text-slate-700">
                  {labels.score}: <span className="ms-1 font-black tabular-nums text-slate-950">{score}/100</span>
                </span>
              ) : null}
            </div>

            <p className="mt-4 max-w-3xl text-pretty text-base leading-7 text-slate-650 md:text-lg">{diagnosis}</p>

          </div>
        </section>

        {contentPlan ? (
          <div
            role="tablist"
            aria-label="Разделы отчёта"
            className={`grid grid-cols-2 gap-2 rounded-2xl bg-white p-2 ${surfaceShadow}`}
          >
            <button
              type="button"
              role="tab"
              aria-selected={activeView === 'audit'}
              aria-controls="public-audit-panel"
              onClick={() => setActiveView('audit')}
              className={`flex min-h-14 items-center justify-center gap-2 rounded-xl px-3 text-center text-sm font-bold leading-5 transition-[background-color,box-shadow,color,transform] active:scale-[0.96] sm:px-5 ${focusRing} ${
                activeView === 'audit'
                  ? 'bg-slate-950 text-white shadow-[0_8px_24px_rgba(15,23,42,0.20)] hover:bg-slate-800'
                  : 'bg-white text-slate-700 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.10)] hover:bg-amber-50'
              }`}
            >
              <Check className={`h-4 w-4 shrink-0 ${activeView === 'audit' ? 'opacity-100' : 'opacity-0'}`} />
              {auditTabLabel}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeView === 'content'}
              aria-controls="public-content-panel"
              onClick={() => setActiveView('content')}
              className={`flex min-h-14 items-center justify-center gap-2 rounded-xl px-3 text-center text-sm font-bold leading-5 transition-[background-color,box-shadow,color,transform] active:scale-[0.96] sm:px-5 ${focusRing} ${
                activeView === 'content'
                  ? 'bg-slate-950 text-white shadow-[0_8px_24px_rgba(15,23,42,0.20)] hover:bg-slate-800'
                  : 'bg-white text-slate-700 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.10)] hover:bg-amber-50'
              }`}
            >
              <Check className={`h-4 w-4 shrink-0 ${activeView === 'content' ? 'opacity-100' : 'opacity-0'}`} />
              {contentTabLabel}
            </button>
          </div>
        ) : null}

        {activeView === 'audit' || !contentPlan ? <div id="public-audit-panel" role="tabpanel" className="space-y-5">
        <section id="priority-actions" className={`scroll-mt-5 rounded-[2rem] bg-white p-5 md:p-6 ${surfaceShadow}`}>
          <h2 className="text-balance text-2xl font-black tracking-tight text-slate-950">{labels.fixToday}</h2>
          <p className="mt-2 max-w-2xl text-pretty text-sm leading-6 text-slate-600">{labels.fixTodayHint}</p>
          <div className="mt-5 flex flex-col gap-3 sm:flex-row">
            <a
              href="#priority-actions"
              className={`inline-flex min-h-11 items-center justify-center rounded-xl bg-slate-950 px-4 text-sm font-semibold text-white transition-[background-color,transform] hover:bg-slate-800 active:scale-[0.96] ${focusRing}`}
            >
              {labels.fixYourself}
            </a>
            <button
              type="button"
              onClick={onPrepareWithLocalOS}
              className={`btn-iridescent inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm ${focusRing}`}
            >
              <Sparkles className="h-4 w-4" />
              {labels.prepareWithLocalOS}
            </button>
          </div>
          <div className="mt-5 space-y-3">
            {problems.map((problem, index) => {
              const open = expandedProblems.has(problem.id);
              const expandable = Boolean(problem.problem || problem.evidence || problem.outcome);
              return (
                <article key={problem.id} id={`priority-${problem.id}`} className="scroll-mt-5 rounded-3xl bg-slate-50 p-4 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.05)] md:p-5">
                  <div className="flex items-start gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white text-sm font-black tabular-nums text-orange-600 shadow-sm">{index + 1}</span>
                    <div className="min-w-0 flex-1">
                      <h3 className="text-balance text-lg font-bold text-slate-950">{problem.title}</h3>
                      <p className="mt-1 text-pretty text-sm leading-6 text-slate-700">
                        <span className="font-semibold text-slate-950">{labels.whyImportant}: </span>
                        {problem.importance}
                      </p>
                    </div>
                  </div>
                  {problem.actions.length > 0 ? (
                    <div className="ms-12 mt-4">
                      <div className="text-xs font-bold uppercase tracking-[0.16em] text-emerald-700">{labels.actions}</div>
                      <ul className="mt-2 grid gap-2 md:grid-cols-2">
                        {problem.actions.slice(0, 4).map((action) => (
                          <li key={action} className="flex items-start gap-2 text-pretty text-sm leading-6 text-slate-700">
                            <Check className="mt-1 h-4 w-4 shrink-0 text-emerald-600" />
                            <span>{action}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {expandable ? (
                    <div className="ms-12 mt-3">
                      <button
                        type="button"
                        aria-expanded={open}
                        aria-controls={`problem-details-${problem.id}`}
                        onClick={() => toggleProblem(problem.id)}
                        className={`inline-flex min-h-10 items-center gap-2 rounded-lg px-2 text-sm font-semibold text-sky-700 transition-[background-color,color,transform] hover:bg-sky-50 hover:text-sky-900 active:scale-[0.96] ${focusRing}`}
                      >
                        {open ? labels.hideDetails : labels.details}
                        <ToggleIcon open={open} />
                      </button>
                      {open ? (
                        <div id={`problem-details-${problem.id}`} className="mt-2 grid gap-3 border-t border-slate-200 pt-4 md:grid-cols-3">
                          {problem.problem ? <p className="text-pretty text-sm leading-6 text-slate-700">{problem.problem}</p> : null}
                          {problem.evidence ? <p className="text-pretty text-sm leading-6 text-slate-600">{problem.evidence}</p> : null}
                          {problem.outcome ? <p className="text-pretty text-sm leading-6 text-slate-600">{problem.outcome}</p> : null}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        </section>

        <section className={`rounded-[2rem] bg-white p-5 md:p-6 ${surfaceShadow}`}>
          <h2 className="text-balance text-2xl font-black tracking-tight text-slate-950">{labels.strengths}</h2>
          {strengths.length > 0 ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {strengths.slice(0, 4).map((strength) => (
                <div key={strength} className="flex items-start gap-2 rounded-2xl bg-emerald-50 p-3 text-pretty text-sm leading-6 text-emerald-950 shadow-[inset_0_0_0_1px_rgba(16,185,129,0.10)]">
                  <Check className="mt-1 h-4 w-4 shrink-0 text-emerald-600" />
                  <span>{strength}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-pretty text-sm leading-6 text-slate-600">{labels.noStrengths}</p>
          )}
        </section>

        {(strongDemand.length > 0 || weakDemand.length > 0 || missingPhotos.length > 0) ? (
          <section className={`rounded-[2rem] bg-white p-5 md:p-6 ${surfaceShadow}`}>
            <h2 className="text-balance text-2xl font-black tracking-tight text-slate-950">{labels.customerUnderstanding}</h2>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <div className="rounded-3xl bg-emerald-50 p-4 shadow-[inset_0_0_0_1px_rgba(16,185,129,0.12)]">
                <div className="font-bold text-emerald-950">{labels.strongAnswers}</div>
                <ul className="mt-3 space-y-2">
                  {strongDemand.map((item) => <li key={item} className="flex items-start gap-2 text-pretty text-sm leading-6 text-emerald-950"><Check className="mt-1 h-4 w-4 shrink-0 text-emerald-600" />{item}</li>)}
                </ul>
              </div>
              <div className="rounded-3xl bg-rose-50 p-4 shadow-[inset_0_0_0_1px_rgba(244,63,94,0.10)]">
                <div className="font-bold text-rose-950">{labels.weakAnswers}</div>
                <ul className="mt-3 space-y-2">
                  {weakDemand.map((item) => <li key={item} className="flex items-start gap-2 text-pretty text-sm leading-6 text-rose-950"><span aria-hidden="true" className="mt-0.5 text-rose-600">×</span>{item}</li>)}
                </ul>
              </div>
            </div>
            {missingPhotos.length > 0 ? (
              <div className="mt-5">
                <h3 className="text-balance text-lg font-bold text-slate-950">{labels.missingPhotos}</h3>
                <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
                  {missingPhotos.map((item) => (
                    <div key={item} className="rounded-2xl bg-amber-50 p-3 shadow-[inset_0_0_0_1px_rgba(245,158,11,0.14)]">
                      <Camera className="h-5 w-5 text-amber-700" />
                      <div className="mt-2 text-pretty text-sm font-semibold text-slate-900">{item}</div>
                      <div className="mt-1 text-xs text-amber-800">{labels.needPhoto}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </section>
        ) : null}

        {hasCardData ? (
          <section className={`rounded-[2rem] bg-white p-5 md:p-6 ${surfaceShadow}`}>
            <h2 className="text-balance text-2xl font-black tracking-tight text-slate-950">{labels.cardData}</h2>
            {services.length > 0 ? (
              <div className="mt-5">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-bold text-slate-950">{labels.services}</h3>
                  <span className="text-sm tabular-nums text-slate-500">{services.length}</span>
                </div>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  {visibleServices.map((service, index) => (
                    <article key={`${service.name}-${index}`} className="rounded-2xl bg-slate-50 p-3 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.05)]">
                      <div className="text-pretty text-sm font-semibold text-slate-950">{service.name}</div>
                      {service.category ? <div className="mt-1 text-xs text-slate-500">{service.category}</div> : null}
                      {service.description ? <p className="mt-2 line-clamp-2 text-pretty text-sm leading-5 text-slate-600">{service.description}</p> : null}
                      {service.improvedName ? <p className="mt-2 text-pretty text-sm font-medium text-sky-700">{service.improvedName}</p> : null}
                      {service.price ? <div className="mt-2 text-xs font-semibold tabular-nums text-slate-700">{service.price}</div> : null}
                    </article>
                  ))}
                </div>
                {services.length > 4 ? (
                  <button
                    type="button"
                    aria-expanded={servicesExpanded}
                    onClick={() => setServicesExpanded((current) => !current)}
                    className={`mt-3 inline-flex min-h-10 items-center gap-2 rounded-lg px-2 text-sm font-semibold text-sky-700 transition-[background-color,color,transform] hover:bg-sky-50 hover:text-sky-900 active:scale-[0.96] ${focusRing}`}
                  >
                    {servicesExpanded ? labels.showLess : labels.showMore}
                    <ToggleIcon open={servicesExpanded} />
                  </button>
                ) : null}
              </div>
            ) : null}

            {photos.length > 0 ? (
              <div className="mt-6 border-t border-slate-100 pt-5">
                <h3 className="flex items-center gap-2 font-bold text-slate-950"><ImagePlus className="h-4 w-4 text-sky-600" />{labels.photos}</h3>
                <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
                  {photos.slice(0, 8).map((photo, index) => (
                    <img key={`${photo}-${index}`} src={photo} alt={photoAlt(index)} className="h-24 w-full rounded-xl object-cover outline outline-1 -outline-offset-1 outline-black/10" />
                  ))}
                </div>
              </div>
            ) : null}

            {(reviews.length > 0 || news.length > 0) ? (
              <div className="mt-6 grid gap-4 border-t border-slate-100 pt-5 md:grid-cols-2">
                {reviews.length > 0 ? (
                  <div>
                    <h3 className="flex items-center gap-2 font-bold text-slate-950"><MessageSquareText className="h-4 w-4 text-sky-600" />{labels.reviews}</h3>
                    <div className="mt-3 space-y-3">
                      {reviews.slice(0, 3).map((review, index) => (
                        <article key={`${review.author}-${index}`} className="border-b border-slate-100 pb-3 last:border-b-0">
                          {review.rating ? <div aria-label={`${review.rating}/5`} className="text-sm tracking-wide text-amber-500">{stars(review.rating)}</div> : null}
                          {review.text ? <p className="mt-1 line-clamp-2 text-pretty text-sm leading-5 text-slate-700">“{review.text}”</p> : null}
                          <div className={`mt-2 text-xs font-semibold ${review.reply ? 'text-emerald-700' : 'text-rose-700'}`}>{review.reply ? labels.hasReply : labels.noReply}</div>
                        </article>
                      ))}
                    </div>
                  </div>
                ) : null}
                {news.length > 0 ? (
                  <div>
                    <h3 className="flex items-center gap-2 font-bold text-slate-950"><Newspaper className="h-4 w-4 text-sky-600" />{labels.news}</h3>
                    <div className="mt-3 space-y-3">
                      {news.slice(0, 3).map((item) => {
                        const open = expandedNews.has(item.id);
                        return (
                          <article key={item.id} className="border-b border-slate-100 pb-3 last:border-b-0">
                            {item.date ? <div className="text-xs text-slate-500">{item.date}</div> : null}
                            {item.title ? <div className="mt-1 text-pretty text-sm font-semibold text-slate-950">{item.title}</div> : null}
                            {item.text ? <p className={`mt-1 whitespace-pre-wrap text-pretty text-sm leading-5 text-slate-700 ${open ? '' : 'line-clamp-2'}`}>{item.text}</p> : null}
                            {item.text ? (
                              <button
                                type="button"
                                aria-expanded={open}
                                onClick={() => toggleNews(item.id)}
                                className={`mt-1 inline-flex min-h-10 items-center gap-2 rounded-lg px-2 text-xs font-semibold text-sky-700 transition-[background-color,color,transform] hover:bg-sky-50 active:scale-[0.96] ${focusRing}`}
                              >
                                {open ? labels.hideFull : labels.showFull}
                                <ToggleIcon open={open} />
                              </button>
                            ) : null}
                          </article>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </section>
        ) : null}

        <section className={`overflow-hidden rounded-[2rem] bg-white ${surfaceShadow}`}>
          <button
            type="button"
            aria-expanded={planExpanded}
            aria-controls="public-audit-full-plan"
            onClick={() => setPlanExpanded((current) => !current)}
            className={`flex min-h-20 w-full items-center gap-4 p-5 text-start transition-[background-color,transform] hover:bg-slate-50 active:scale-[0.99] md:p-6 ${focusRing}`}
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-sky-50 text-sky-700"><Sparkles className="h-5 w-5" /></span>
            <span className="min-w-0 flex-1">
              <span className="block text-balance text-lg font-bold text-slate-950">{planExpanded ? labels.hidePlan : labels.fullPlan}</span>
              <span className="mt-1 block text-pretty text-sm leading-5 text-slate-600">{labels.fullPlanHint}</span>
            </span>
            <ToggleIcon open={planExpanded} />
          </button>
          {planExpanded ? <div id="public-audit-full-plan" className="border-t border-slate-100 p-5 md:p-6">{fullPlan}</div> : null}
        </section>
        </div> : (
          <section id="public-content-panel" role="tabpanel" className={`rounded-[2rem] bg-white p-5 md:p-8 ${surfaceShadow}`}>
            {contentPlan}
          </section>
        )}

        {mapUrl ? (
          <footer>
            <a href={mapUrl} target="_blank" rel="noreferrer" className={`inline-flex min-h-11 items-center gap-2 rounded-xl bg-white px-4 text-sm font-semibold text-slate-800 shadow-[0_0_0_1px_rgba(15,23,42,0.08)] transition-[background-color,color,transform] hover:bg-sky-50 hover:text-sky-800 active:scale-[0.96] ${focusRing}`}>
              {labels.openMap}
              <ExternalLink className="h-4 w-4" />
            </a>
          </footer>
        ) : null}
      </main>
    </div>
  );
};
