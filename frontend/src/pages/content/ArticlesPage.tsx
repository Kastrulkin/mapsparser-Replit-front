import { useEffect, useMemo, useState } from "react";
import SeoMeta from "@/components/SeoMeta";
import { useLanguage } from "@/i18n/LanguageContext";
import { contentCopy } from "@/content/contentCopy";
import { useLocalizedArticles } from "@/content/useLocalizedArticles";
import {
  Breadcrumbs,
  FilterPills,
  ListHero,
  MaterialCard,
  PageFrame,
} from "./ContentShared";
import { makeBreadcrumbSchema } from "./contentSeo";

const ArticlesPage = () => {
  const { language } = useLanguage();
  const copy = contentCopy[language].articles;
  const { articles, isLoading } = useLocalizedArticles(language);
  const [activeCategory, setActiveCategory] = useState(copy.all);

  useEffect(() => {
    setActiveCategory(copy.all);
  }, [copy.all]);

  const filteredArticles = useMemo(() => {
    if (activeCategory === copy.all) {
      return articles;
    }

    return articles.filter((article) => article.category === activeCategory);
  }, [activeCategory, articles, copy.all]);

  const filters = [copy.all, ...Array.from(new Set(articles.map((article) => article.category)))];

  return (
    <PageFrame>
      <SeoMeta
        description={copy.seoDescription}
        path="/articles"
        schema={makeBreadcrumbSchema([
          { name: "LocalOS", path: "/" },
          { name: copy.latest, path: "/articles" },
        ])}
        title={copy.seoTitle}
      />
      <ListHero
        description={copy.description}
        eyebrow={copy.eyebrow}
        title={copy.title}
      />
      <main className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <Breadcrumbs sectionHref="/articles" sectionTitle={contentCopy[language].navigation.articles.name} />
          <div className="mb-8 flex flex-col justify-between gap-5 md:flex-row md:items-center">
            <div>
              <h2 className="text-3xl font-bold text-gray-950">{copy.latest}</h2>
              <p className="mt-2 text-gray-600">{copy.chooseTopic}</p>
            </div>
            <FilterPills activeValue={activeCategory} onChange={setActiveCategory} values={filters} />
          </div>
          <div aria-busy={isLoading} className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {filteredArticles.map((article) => (
              <MaterialCard
                date={article.publishedAt}
                excerpt={article.excerpt}
                href={`/articles/${article.slug}`}
                key={article.slug}
                label={article.category}
                tags={article.tags}
                title={article.title}
              />
            ))}
          </div>
        </div>
      </main>
    </PageFrame>
  );
};

export default ArticlesPage;
