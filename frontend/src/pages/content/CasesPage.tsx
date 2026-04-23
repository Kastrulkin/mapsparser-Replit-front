import { useMemo, useState } from "react";
import SeoMeta from "@/components/SeoMeta";
import { caseIndustries, publishedCases } from "@/content/cases";
import {
  Breadcrumbs,
  FilterPills,
  ListHero,
  MaterialCard,
  PageFrame,
} from "./ContentShared";
import { makeBreadcrumbSchema } from "./contentSeo";

const allIndustry = "Все";

const CasesPage = () => {
  const [activeIndustry, setActiveIndustry] = useState(allIndustry);

  const filteredCases = useMemo(() => {
    if (activeIndustry === allIndustry) {
      return publishedCases;
    }

    return publishedCases.filter((caseItem) => caseItem.industry === activeIndustry);
  }, [activeIndustry]);

  const filters = [allIndustry, ...caseIndustries];

  return (
    <PageFrame>
      <SeoMeta
        description="Кейсы LocalOS о росте заявок, отзывов, записей и повторных клиентов для салонов, кафе и локального бизнеса."
        path="/cases"
        schema={makeBreadcrumbSchema([
          { name: "LocalOS", path: "/" },
          { name: "Кейсы", path: "/cases" },
        ])}
        title="Кейсы локального бизнеса — LocalOS"
      />
      <ListHero
        description="Истории роста в формате проблема, действия и результат: что изменили в картах, отзывах и коммуникации с клиентами."
        eyebrow="Результаты LocalOS"
        title="Кейсы: как локальный бизнес получает больше заявок"
      />
      <main className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <Breadcrumbs sectionHref="/cases" sectionTitle="Кейсы" />
          <div className="mb-8 flex flex-col justify-between gap-5 md:flex-row md:items-center">
            <div>
              <h2 className="text-3xl font-bold text-gray-950">Разборы внедрений</h2>
              <p className="mt-2 text-gray-600">Смотрите на цифры, действия и контекст, а не на красивые обещания.</p>
            </div>
            <FilterPills activeValue={activeIndustry} onChange={setActiveIndustry} values={filters} />
          </div>
          <div className="grid gap-6 md:grid-cols-2">
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
