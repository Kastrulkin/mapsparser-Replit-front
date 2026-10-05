import type { ArticleContent, DocumentContent } from "./contentTypes";
export function publicContentSchema(item: ArticleContent | DocumentContent, collection: "articles" | "documents", label: string) {
  const url = `https://localos.pro/${collection}/${item.slug}`;
  const schema: unknown[] = [{ "@context": "https://schema.org", "@type": "Article", headline: item.title, description: item.excerpt, datePublished: item.publishedAt, dateModified: item.updatedAt, mainEntityOfPage: url, author: { "@type": "Organization", name: "LocalOS" }, publisher: { "@type": "Organization", name: "LocalOS" } }, { "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: [{ "@type": "ListItem", position: 1, name: "LocalOS", item: "https://localos.pro/" }, { "@type": "ListItem", position: 2, name: label, item: `https://localos.pro/${collection}` }, { "@type": "ListItem", position: 3, name: item.title, item: url }] }];
  if ("video" in item && item.video) schema.push({ "@context": "https://schema.org", "@type": "VideoObject", name: item.video.title, description: item.excerpt, embedUrl: `https://www.youtube-nocookie.com/embed/${item.video.youtubeId}`, contentUrl: `https://www.youtube.com/watch?v=${item.video.youtubeId}`, thumbnailUrl: `https://i.ytimg.com/vi/${item.video.youtubeId}/hqdefault.jpg` });
  return schema;
}
