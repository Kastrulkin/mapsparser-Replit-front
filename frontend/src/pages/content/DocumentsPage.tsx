import { useMemo, useState } from "react";
import SeoMeta from "@/components/SeoMeta";
import { documentTypes, publishedDocuments } from "@/content/documents";
import {
  Breadcrumbs,
  FilterPills,
  ListHero,
  MaterialCard,
  PageFrame,
} from "./ContentShared";
import { makeBreadcrumbSchema } from "./contentSeo";

const allType = "Все";

const DocumentsPage = () => {
  const [activeType, setActiveType] = useState(allType);

  const filteredDocuments = useMemo(() => {
    if (activeType === allType) {
      return publishedDocuments;
    }

    return publishedDocuments.filter((documentItem) => documentItem.documentType === activeType);
  }, [activeType]);

  const filters = [allType, ...documentTypes];

  return (
    <PageFrame>
      <SeoMeta
        description="Прикладные документы LocalOS: чек-листы, шаблоны, таблицы и инструкции для управления локальным маркетингом."
        path="/documents"
        schema={makeBreadcrumbSchema([
          { name: "LocalOS", path: "/" },
          { name: "Документы", path: "/documents" },
        ])}
        title="Документы для локального маркетинга — LocalOS"
      />
      <ListHero
        description="Готовые материалы, которые можно использовать в работе: чек-листы аудита, шаблоны ответов, таблицы контроля и инструкции."
        eyebrow="Практические материалы"
        title="Документы для управления ростом локального бизнеса"
      />
      <main className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <Breadcrumbs sectionHref="/documents" sectionTitle="Документы" />
          <div className="mb-8 flex flex-col justify-between gap-5 md:flex-row md:items-center">
            <div>
              <h2 className="text-3xl font-bold text-gray-950">Библиотека документов</h2>
              <p className="mt-2 text-gray-600">Не статьи, а рабочие заготовки для команды и собственника.</p>
            </div>
            <FilterPills activeValue={activeType} onChange={setActiveType} values={filters} />
          </div>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {filteredDocuments.map((documentItem) => (
              <MaterialCard
                accent="amber"
                date={documentItem.publishedAt}
                excerpt={documentItem.excerpt}
                href={`/documents/${documentItem.slug}`}
                key={documentItem.slug}
                label={documentItem.documentType}
                tags={documentItem.tags}
                title={documentItem.title}
              />
            ))}
          </div>
        </div>
      </main>
    </PageFrame>
  );
};

export default DocumentsPage;
