import { Navigate, useParams } from "react-router-dom";
import SeoMeta from "@/components/SeoMeta";
import { findArticleBySlug, publishedArticles } from "@/content/articles";
import {
  BottomCta,
  DetailHeader,
  PageFrame,
  RelatedMaterials,
  SectionRenderer,
} from "./ContentShared";
import { SITE_URL, makeBreadcrumbSchema } from "./contentSeo";

const ArticleDetailPage = () => {
  const { slug } = useParams();
  const article = findArticleBySlug(slug);

  if (!article) {
    return <Navigate replace to="/articles" />;
  }

  const schema = [
    {
      "@context": "https://schema.org",
      "@type": "Article",
      headline: article.title,
      description: article.excerpt,
      datePublished: article.publishedAt,
      dateModified: article.updatedAt,
      mainEntityOfPage: `${SITE_URL}/articles/${article.slug}`,
      author: {
        "@type": "Organization",
        name: "LocalOS",
      },
      publisher: {
        "@type": "Organization",
        name: "LocalOS",
      },
    },
    makeBreadcrumbSchema([
      { name: "LocalOS", path: "/" },
      { name: "Статьи", path: "/articles" },
      { name: article.title, path: `/articles/${article.slug}` },
    ]),
  ];

  const otherArticles = publishedArticles
    .filter((item) => item.slug !== article.slug)
    .slice(0, 2)
    .map((item) => ({
      title: item.title,
      href: `/articles/${item.slug}`,
      label: item.category,
    }));

  return (
    <PageFrame>
      <SeoMeta
        description={article.seoDescription}
        ogType="article"
        path={`/articles/${article.slug}`}
        schema={schema}
        title={article.seoTitle}
      />
      <DetailHeader
        backHref="/articles"
        backLabel="Назад к статьям"
        date={article.publishedAt}
        excerpt={article.excerpt}
        label={article.category}
        tags={article.tags}
        title={article.title}
      />
      <main className="px-4 py-14 sm:px-6 lg:px-8">
        <article className="mx-auto max-w-4xl">
          <SectionRenderer sections={article.body} />
          <RelatedMaterials items={[...article.related, ...otherArticles]} />
          <BottomCta />
        </article>
      </main>
    </PageFrame>
  );
};

export default ArticleDetailPage;
