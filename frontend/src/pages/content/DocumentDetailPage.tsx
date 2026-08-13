import { Navigate, useParams } from "react-router-dom";
import SeoMeta from "@/components/SeoMeta";
import { useLanguage } from "@/i18n/LanguageContext";
import { contentCopy } from "@/content/contentCopy";
import { collectionCopy } from "@/content/collectionCopy";
import { useLocalizedDocuments } from "@/content/useLocalizedCollections";
import {
  BottomCta,
  DetailHeader,
  DownloadBlock,
  PageFrame,
  RelatedMaterials,
  SectionRenderer,
} from "./ContentShared";
import { SITE_URL, makeBreadcrumbSchema } from "./contentSeo";

const DocumentDetailPage = () => {
  const { slug } = useParams();
  const { language } = useLanguage();
  const copy = collectionCopy[language];
  const navigationTitle = contentCopy[language].navigation.documents.name;
  const { documents, isLoading } = useLocalizedDocuments(language);
  const documentItem = documents.find((item) => item.slug === slug?.trim().replace(/[\\/]+$/g, ""));

  if (isLoading) {
    return <PageFrame><main className="flex min-h-[55vh] items-center justify-center px-4 text-muted-foreground">{contentCopy[language].shared.loading}</main></PageFrame>;
  }

  if (!documentItem) {
    return <Navigate replace to="/documents" />;
  }

  const schema = [
    {
      "@context": "https://schema.org",
      "@type": "CreativeWork",
      name: documentItem.title,
      description: documentItem.excerpt,
      datePublished: documentItem.publishedAt,
      dateModified: documentItem.updatedAt,
      url: `${SITE_URL}/documents/${documentItem.slug}`,
      publisher: {
        "@type": "Organization",
        name: "LocalOS",
      },
    },
    makeBreadcrumbSchema([
      { name: "LocalOS", path: "/" },
      { name: navigationTitle, path: "/documents" },
      { name: documentItem.title, path: `/documents/${documentItem.slug}` },
    ]),
  ];

  return (
    <PageFrame>
      <SeoMeta
        description={documentItem.seoDescription}
        path={`/documents/${documentItem.slug}`}
        schema={schema}
        title={documentItem.seoTitle}
      />
      <DetailHeader
        backHref="/documents"
        backLabel={copy.documents.back}
        date={documentItem.publishedAt}
        excerpt={documentItem.excerpt}
        label={documentItem.documentType}
        tags={documentItem.tags}
        title={documentItem.title}
      />
      <main className="px-4 py-14 sm:px-6 lg:px-8">
        <article className="mx-auto max-w-4xl">
          <section className="mb-12 rounded-3xl border border-orange-100 bg-white p-6 shadow-xl shadow-orange-500/5">
            <h2 className="text-2xl font-bold text-gray-950">{copy.documents.inside}</h2>
            <ul className="mt-5 space-y-3">
              {documentItem.inside.map((item) => (
                <li className="flex gap-3 text-lg leading-7 text-gray-700" key={item}>
                  <span className="mt-2 h-2 w-2 flex-shrink-0 rounded-full bg-orange-500" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </section>
          <SectionRenderer sections={documentItem.body} />
          <DownloadBlock available={Boolean(documentItem.downloadable)} materialSlug={documentItem.slug} />
          <RelatedMaterials items={documentItem.related} />
          <BottomCta />
        </article>
      </main>
    </PageFrame>
  );
};

export default DocumentDetailPage;
