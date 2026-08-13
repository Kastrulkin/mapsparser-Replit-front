import { useEffect, useMemo, useState } from "react";
import SeoMeta from "@/components/SeoMeta";
import { useLanguage } from "@/i18n/LanguageContext";
import { contentCopy } from "@/content/contentCopy";
import { collectionCopy } from "@/content/collectionCopy";
import { useLocalizedCases } from "@/content/useLocalizedCollections";
import {
  Breadcrumbs,
  FilterPills,
  ListHero,
  MaterialCard,
  PageFrame,
} from "./ContentShared";
import { makeBreadcrumbSchema } from "./contentSeo";

const CasesPage = () => {
  const { language } = useLanguage();
  const copy = collectionCopy[language];
  const navigationTitle = contentCopy[language].navigation.cases.name;
  const { cases, isLoading } = useLocalizedCases(language);
  const [activeIndustry, setActiveIndustry] = useState(copy.all);

  useEffect(() => {
    setActiveIndustry(copy.all);
  }, [copy.all]);

  const filteredCases = useMemo(() => {
    if (activeIndustry === copy.all) {
      return cases;
    }

    return cases.filter((caseItem) => caseItem.industry === activeIndustry);
  }, [activeIndustry, cases, copy.all]);

  const filters = [copy.all, ...Array.from(new Set(cases.map((caseItem) => caseItem.industry)))];

  return (
    <PageFrame>
      <SeoMeta
        description={copy.cases.seoDescription}
        path="/cases"
        schema={makeBreadcrumbSchema([
          { name: "LocalOS", path: "/" },
          { name: navigationTitle, path: "/cases" },
        ])}
        title={copy.cases.seoTitle}
      />
      <ListHero
        description={copy.cases.description}
        eyebrow={copy.cases.eyebrow}
        title={copy.cases.title}
      />
      <main className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <Breadcrumbs sectionHref="/cases" sectionTitle={navigationTitle} />
          <div className="mb-8 flex flex-col justify-between gap-5 md:flex-row md:items-center">
            <div>
              <h2 className="text-3xl font-bold text-gray-950">{copy.cases.library}</h2>
              <p className="mt-2 text-gray-600">{copy.cases.libraryDescription}</p>
            </div>
            <FilterPills activeValue={activeIndustry} onChange={setActiveIndustry} values={filters} />
          </div>
          <div aria-busy={isLoading} className="grid gap-6 md:grid-cols-2">
            {filteredCases.map((caseItem) => (
              <MaterialCard
                accent="slate"
                date={caseItem.publishedAt}
                excerpt={caseItem.excerpt}
                href={`/cases/${caseItem.slug}`}
                key={caseItem.slug}
                label={caseItem.industry}
                tags={caseItem.tags}
                title={caseItem.title}
              />
            ))}
          </div>
        </div>
      </main>
    </PageFrame>
  );
};

export default CasesPage;
