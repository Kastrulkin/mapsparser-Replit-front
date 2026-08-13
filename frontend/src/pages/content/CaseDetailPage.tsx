import { Navigate, useParams } from "react-router-dom";
import SeoMeta from "@/components/SeoMeta";
import { useLanguage } from "@/i18n/LanguageContext";
import { contentCopy } from "@/content/contentCopy";
import { collectionCopy } from "@/content/collectionCopy";
import { useLocalizedCases } from "@/content/useLocalizedCollections";
import {
  BottomCta,
  DetailHeader,
  PageFrame,
  RelatedMaterials,
  SectionRenderer,
} from "./ContentShared";
import { SITE_URL, makeBreadcrumbSchema } from "./contentSeo";

const CaseDetailPage = () => {
  const { slug } = useParams();
  const { language } = useLanguage();
  const copy = collectionCopy[language];
  const navigationTitle = contentCopy[language].navigation.cases.name;
  const { cases, isLoading } = useLocalizedCases(language);
  const caseItem = cases.find((item) => item.slug === slug?.trim().replace(/[\\/]+$/g, ""));

  if (isLoading) {
    return <PageFrame><main className="flex min-h-[55vh] items-center justify-center px-4 text-muted-foreground">{contentCopy[language].shared.loading}</main></PageFrame>;
  }

  if (!caseItem) {
    return <Navigate replace to="/cases" />;
  }

  const schema = [
    {
      "@context": "https://schema.org",
      "@type": "CreativeWork",
      name: caseItem.title,
      description: caseItem.excerpt,
      datePublished: caseItem.publishedAt,
      dateModified: caseItem.updatedAt,
      url: `${SITE_URL}/cases/${caseItem.slug}`,
      about: caseItem.industry,
      publisher: {
        "@type": "Organization",
        name: "LocalOS",
      },
    },
    makeBreadcrumbSchema([
      { name: "LocalOS", path: "/" },
      { name: navigationTitle, path: "/cases" },
      { name: caseItem.title, path: `/cases/${caseItem.slug}` },
    ]),
  ];

  return (
    <PageFrame>
      <SeoMeta
        description={caseItem.seoDescription}
        path={`/cases/${caseItem.slug}`}
        schema={schema}
        title={caseItem.seoTitle}
      />
      <DetailHeader
        backHref="/cases"
        backLabel={copy.cases.back}
        date={caseItem.publishedAt}
        excerpt={caseItem.excerpt}
        label={caseItem.industry}
        tags={caseItem.tags}
        title={caseItem.title}
      />
      <main className="px-4 py-14 sm:px-6 lg:px-8">
        <article className="mx-auto max-w-4xl">
          <section className="mb-12 grid gap-4 sm:grid-cols-3">
            {caseItem.metrics.map((metric) => (
              <div className="rounded-3xl border border-orange-100 bg-white p-6 shadow-xl shadow-orange-500/5" key={metric.label}>
                <div className="text-3xl font-bold text-orange-600">{metric.value}</div>
                <div className="mt-2 text-sm font-medium text-gray-600">{metric.label}</div>
              </div>
            ))}
          </section>
          <section className="mb-12 grid gap-5">
            <div className="rounded-3xl bg-gray-950 p-6 text-white">
              <h2 className="text-2xl font-bold">{copy.cases.situation}</h2>
              <p className="mt-4 text-lg leading-8 text-white/80">{caseItem.situation}</p>
            </div>
            <div className="rounded-3xl border border-orange-100 bg-white p-6">
              <h2 className="text-2xl font-bold text-gray-950">{copy.cases.actions}</h2>
              <ul className="mt-5 space-y-3">
                {caseItem.actions.map((action) => (
                  <li className="flex gap-3 text-lg leading-7 text-gray-700" key={action}>
                    <span className="mt-2 h-2 w-2 flex-shrink-0 rounded-full bg-orange-500" />
                    <span>{action}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="rounded-3xl border border-amber-200 bg-amber-50 p-6">
              <h2 className="text-2xl font-bold text-gray-950">{copy.cases.result}</h2>
              <p className="mt-4 text-lg leading-8 text-gray-700">{caseItem.result}</p>
            </div>
          </section>
          <SectionRenderer sections={caseItem.body} />
          <RelatedMaterials items={caseItem.related} />
          <BottomCta />
        </article>
      </main>
    </PageFrame>
  );
};

export default CaseDetailPage;
