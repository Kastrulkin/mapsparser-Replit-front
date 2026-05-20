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
import type { ArticleContent, ContentSection } from "@/content/contentTypes";
import { SITE_URL, makeBreadcrumbSchema } from "./contentSeo";

const STATS_SECTION_TITLE = "Масштаб проблемы";
const STATS_SECTION_END = "примерно каждый второй владелец бизнеса.";
const SCHEME_SECTION_TITLE = "Рост без системы усиливает хаос";
const SCHEME_SECTION_END = "хаос начинает расти быстрее самого бизнеса.";

const articleVisualClassName = "mt-6 mb-10 h-auto w-full rounded-[20px]";

const renderArticleVisual = (src: string, alt: string) => (
  <img
    alt={alt}
    className={articleVisualClassName}
    height="1024"
    src={src}
    width="1536"
  />
);

const renderInlineArticleVisual = (article: ArticleContent, section: ContentSection) => {
  const body = section.body?.trim();

  if (
    article.statsImage &&
    section.title === STATS_SECTION_TITLE &&
    body?.endsWith(STATS_SECTION_END)
  ) {
    return renderArticleVisual(article.statsImage, article.statsImageAlt ?? "");
  }

  if (
    article.schemeImage &&
    section.title === SCHEME_SECTION_TITLE &&
    body?.endsWith(SCHEME_SECTION_END)
  ) {
    return renderArticleVisual(article.schemeImage, article.schemeImageAlt ?? "");
  }

  return null;
};

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
      <main className={`px-4 pb-14 sm:px-6 lg:px-8 ${article.coverImage ? "pt-6" : "pt-14"}`}>
        <article className="mx-auto max-w-4xl">
          {article.coverImage ? (
            <img
              alt={article.coverAlt ?? article.title}
              className="mb-8 h-52 w-full rounded-[20px] object-cover sm:h-80 lg:h-[420px]"
              height="1024"
              loading="eager"
              src={article.coverImage}
              width="1536"
            />
          ) : null}
          <SectionRenderer
            renderAfterSection={(section) => renderInlineArticleVisual(article, section)}
            sections={article.body}
          />
          <RelatedMaterials items={[...article.related, ...otherArticles]} />
          <BottomCta />
        </article>
      </main>
    </PageFrame>
  );
};

export default ArticleDetailPage;
