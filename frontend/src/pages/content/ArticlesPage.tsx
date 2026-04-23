import { useMemo, useState } from "react";
import SeoMeta from "@/components/SeoMeta";
import { articleCategories, publishedArticles } from "@/content/articles";
import {
  Breadcrumbs,
  FilterPills,
  ListHero,
  MaterialCard,
  PageFrame,
} from "./ContentShared";
import { makeBreadcrumbSchema } from "./contentSeo";

const allCategory = "Все";

const ArticlesPage = () => {
  const [activeCategory, setActiveCategory] = useState(allCategory);

  const filteredArticles = useMemo(() => {
    if (activeCategory === allCategory) {
      return publishedArticles;
    }

    return publishedArticles.filter((article) => article.category === activeCategory);
  }, [activeCategory]);

  const filters = [allCategory, ...articleCategories];

  return (
    <PageFrame>
      <SeoMeta
        description="Статьи LocalOS о картах, отзывах, локальном маркетинге и привлечении клиентов без лишних рекламных затрат."
        path="/articles"
        schema={makeBreadcrumbSchema([
          { name: "LocalOS", path: "/" },
          { name: "Статьи", path: "/articles" },
        ])}
        title="Статьи о локальном маркетинге — LocalOS"
      />
      <ListHero
        description="Разборы для локального бизнеса: как расти в картах, работать с отзывами, получать больше заявок и удерживать клиентов."
        eyebrow="Материалы LocalOS"
        title="Статьи о клиентах, картах и росте локального бизнеса"
      />
      <main className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <Breadcrumbs sectionHref="/articles" sectionTitle="Статьи" />
          <div className="mb-8 flex flex-col justify-between gap-5 md:flex-row md:items-center">
            <div>
              <h2 className="text-3xl font-bold text-gray-950">Последние статьи</h2>
              <p className="mt-2 text-gray-600">Выберите тему и начните с самого практичного материала.</p>
            </div>
            <FilterPills activeValue={activeCategory} onChange={setActiveCategory} values={filters} />
          </div>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
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
