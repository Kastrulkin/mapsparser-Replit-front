import { Navigate, useParams, Link } from "react-router-dom";
import SeoMeta from "@/components/SeoMeta";
import { solutions } from "@/content/solutions";
import { PageFrame, ListHero, SectionRenderer, RelatedMaterials } from "./ContentShared";
import { Button } from "@/components/ui/button";
export default function SolutionPage() {
  const { slug } = useParams();
  const solution = solutions.find((item) => item.slug === slug);
  if (!solution) return <Navigate to="/articles" replace />;
  return <PageFrame><SeoMeta title={solution.seoTitle} description={solution.seoDescription} path={`/solutions/${solution.slug}`} /><ListHero eyebrow="Решения LocalOS" title={solution.title} description={solution.excerpt} /><main className="px-4 py-14 sm:px-6 lg:px-8"><article className="mx-auto max-w-4xl"><SectionRenderer sections={solution.body} /><RelatedMaterials items={solution.related} /><Button asChild><Link to="/demo">Посмотреть демо LocalOS</Link></Button></article></main></PageFrame>;
}
