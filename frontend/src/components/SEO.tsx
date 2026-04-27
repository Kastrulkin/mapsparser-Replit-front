import { useEffect } from "react";

type SEOProps = {
  title: string;
  description: string;
  canonicalPath: string;
  type?: "website" | "article";
  jsonLd?: object;
};

const SITE_ORIGIN = "https://localos.pro";

const upsertMeta = (selector: string, create: () => HTMLMetaElement, content: string) => {
  const existing = document.head.querySelector(selector);
  const meta = existing instanceof HTMLMetaElement ? existing : create();
  meta.setAttribute("content", content);
  if (!meta.parentElement) {
    document.head.appendChild(meta);
  }
};

const upsertLink = (selector: string, create: () => HTMLLinkElement, href: string) => {
  const existing = document.head.querySelector(selector);
  const link = existing instanceof HTMLLinkElement ? existing : create();
  link.setAttribute("href", href);
  if (!link.parentElement) {
    document.head.appendChild(link);
  }
};

const SEO = ({ title, description, canonicalPath, type = "website", jsonLd }: SEOProps) => {
  useEffect(() => {
    const canonicalUrl = `${SITE_ORIGIN}${canonicalPath}`;
    document.title = title;

    upsertMeta(
      'meta[name="description"]',
      () => {
        const meta = document.createElement("meta");
        meta.setAttribute("name", "description");
        return meta;
      },
      description,
    );
    upsertMeta(
      'meta[property="og:title"]',
      () => {
        const meta = document.createElement("meta");
        meta.setAttribute("property", "og:title");
        return meta;
      },
      title,
    );
    upsertMeta(
      'meta[property="og:description"]',
      () => {
        const meta = document.createElement("meta");
        meta.setAttribute("property", "og:description");
        return meta;
      },
      description,
    );
    upsertMeta(
      'meta[property="og:type"]',
      () => {
        const meta = document.createElement("meta");
        meta.setAttribute("property", "og:type");
        return meta;
      },
      type,
    );
    upsertMeta(
      'meta[property="og:url"]',
      () => {
        const meta = document.createElement("meta");
        meta.setAttribute("property", "og:url");
        return meta;
      },
      canonicalUrl,
    );
    upsertMeta(
      'meta[name="twitter:card"]',
      () => {
        const meta = document.createElement("meta");
        meta.setAttribute("name", "twitter:card");
        return meta;
      },
      "summary_large_image",
    );
    upsertLink(
      'link[rel="canonical"]',
      () => {
        const link = document.createElement("link");
        link.setAttribute("rel", "canonical");
        return link;
      },
      canonicalUrl,
    );

    const scriptId = "localos-page-jsonld";
    const existingScript = document.getElementById(scriptId);
    if (existingScript) {
      existingScript.remove();
    }
    if (jsonLd) {
      const script = document.createElement("script");
      script.id = scriptId;
      script.type = "application/ld+json";
      script.textContent = JSON.stringify(jsonLd);
      document.head.appendChild(script);
    }
  }, [title, description, canonicalPath, type, jsonLd]);

  return null;
};

export default SEO;
