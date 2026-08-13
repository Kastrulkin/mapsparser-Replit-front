import { Navigate, useParams } from "react-router-dom";
import SeoMeta from "@/components/SeoMeta";
import { useLanguage } from "@/i18n/LanguageContext";
import { contentCopy } from "@/content/contentCopy";
import { useLocalizedArticles } from "@/content/useLocalizedArticles";
import {
  BottomCta,
  DetailHeader,
  PageFrame,
  RelatedMaterials,
  SectionRenderer,
} from "./ContentShared";
import type { ArticleContent } from "@/content/contentTypes";
import { SITE_URL, makeBreadcrumbSchema } from "./contentSeo";

const BURNOUT_ARTICLE_SLUG = "pochemu-predprinimateli-vygorayut";
const STATS_SECTION_INDEX = 4;
const SCHEME_SECTION_INDEX = 9;

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

const renderInlineArticleVisual = (article: ArticleContent, sectionIndex: number) => {
  if (article.slug === BURNOUT_ARTICLE_SLUG && article.statsImage && sectionIndex === STATS_SECTION_INDEX) {
    return renderArticleVisual(article.statsImage, article.statsImageAlt ?? "");
  }

  if (article.slug === BURNOUT_ARTICLE_SLUG && article.schemeImage && sectionIndex === SCHEME_SECTION_INDEX) {
    return renderArticleVisual(article.schemeImage, article.schemeImageAlt ?? "");
  }

  return null;
};

const ArticleDetailPage = () => {
  const { slug } = useParams();
  const { language } = useLanguage();
  const { articles, isLoading } = useLocalizedArticles(language);
  const article = articles.find((item) => item.slug === slug?.trim().replace(/[\\/]+$/g, ""));

  if (isLoading) {
    return <PageFrame><main className="flex min-h-[55vh] items-center justify-center px-4 text-muted-foreground">{contentCopy[language].shared.loading}</main></PageFrame>;
  }

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
      { name: contentCopy[language].navigation.articles.name, path: "/articles" },
      { name: article.title, path: `/articles/${article.slug}` },
    ]),
  ];

  const otherArticles = articles
    .filter((item) => item.slug !== article.slug)
    .slice(0, 2)
    .map((item) => ({
      title: item.title,
      href: `/articles/${item.slug}`,
      label: item.category,
    }));
  const relatedItems = [...article.related, ...otherArticles].filter(
    (item, index, items) => items.findIndex((candidate) => candidate.href === item.href) === index,
  );

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
        backLabel={contentCopy[language].articles.back}
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
            renderAfterSection={(section) => renderInlineArticleVisual(article, article.body.indexOf(section))}
            sections={article.body}
          />
          <RelatedMaterials items={relatedItems} />
          <BottomCta />
        </article>
      </main>
    </PageFrame>
  );
};

export default ArticleDetailPage;
