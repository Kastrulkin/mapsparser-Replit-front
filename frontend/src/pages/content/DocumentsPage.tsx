import { useEffect, useMemo, useState } from "react";
import SeoMeta from "@/components/SeoMeta";
import { useLanguage } from "@/i18n/LanguageContext";
import { contentCopy } from "@/content/contentCopy";
import { collectionCopy } from "@/content/collectionCopy";
import { useLocalizedDocuments } from "@/content/useLocalizedCollections";
import {
  Breadcrumbs,
  FilterPills,
  ListHero,
  MaterialCard,
  PageFrame,
} from "./ContentShared";
import { makeBreadcrumbSchema } from "./contentSeo";

const DocumentsPage = () => {
  const { language } = useLanguage();
  const copy = collectionCopy[language];
  const navigationTitle = contentCopy[language].navigation.documents.name;
  const { documents, isLoading } = useLocalizedDocuments(language);
  const [activeType, setActiveType] = useState(copy.all);

  useEffect(() => {
    setActiveType(copy.all);
  }, [copy.all]);

  const filteredDocuments = useMemo(() => {
    if (activeType === copy.all) {
      return documents;
    }

    return documents.filter((documentItem) => documentItem.documentType === activeType);
  }, [activeType, copy.all, documents]);

  const filters = [copy.all, ...Array.from(new Set(documents.map((documentItem) => documentItem.documentType)))];

  return (
    <PageFrame>
      <SeoMeta
        description={copy.documents.seoDescription}
        path="/documents"
        schema={makeBreadcrumbSchema([
          { name: "LocalOS", path: "/" },
          { name: navigationTitle, path: "/documents" },
        ])}
        title={copy.documents.seoTitle}
      />
      <ListHero
        description={copy.documents.description}
        eyebrow={copy.documents.eyebrow}
        title={copy.documents.title}
      />
      <main className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <Breadcrumbs sectionHref="/documents" sectionTitle={navigationTitle} />
          <div className="mb-8 flex flex-col justify-between gap-5 md:flex-row md:items-center">
            <div>
              <h2 className="text-3xl font-bold text-gray-950">{copy.documents.library}</h2>
              <p className="mt-2 text-gray-600">{copy.documents.libraryDescription}</p>
            </div>
            <FilterPills activeValue={activeType} onChange={setActiveType} values={filters} />
          </div>
          <div aria-busy={isLoading} className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
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
