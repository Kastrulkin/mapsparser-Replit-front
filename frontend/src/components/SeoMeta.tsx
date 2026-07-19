import { useEffect } from "react";

const SITE_URL = "https://localos.pro";

type SeoMetaProps = {
  title: string;
  description: string;
  path: string;
  ogType?: string;
  image?: string;
  schema?: unknown;
};

const ensureMeta = (attribute: "name" | "property", key: string) => {
  const selector = `meta[${attribute}="${key}"]`;
  const existing = document.head.querySelector(selector);

  if (existing instanceof HTMLMetaElement) {
    return existing;
  }

  const meta = document.createElement("meta");
  meta.setAttribute(attribute, key);
  document.head.appendChild(meta);
  return meta;
};

const ensureCanonical = () => {
  const existing = document.head.querySelector('link[rel="canonical"]');

  if (existing instanceof HTMLLinkElement) {
    return existing;
  }

  const link = document.createElement("link");
  link.rel = "canonical";
  document.head.appendChild(link);
  return link;
};

const normalizePath = (path: string) => {
  if (path.startsWith("/")) {
    return path;
  }

  return `/${path}`;
};

const SeoMeta = ({ title, description, path, ogType = "website", image, schema }: SeoMetaProps) => {
  useEffect(() => {
    const url = `${SITE_URL}${normalizePath(path)}`;
    const imageUrl = image ? `${SITE_URL}${normalizePath(image)}` : null;

    const applyMeta = () => {
      document.title = title;
      ensureMeta("name", "description").content = description;
      ensureMeta("property", "og:title").content = title;
      ensureMeta("property", "og:description").content = description;
      ensureMeta("property", "og:type").content = ogType;
      ensureMeta("property", "og:url").content = url;
      ensureMeta("property", "og:site_name").content = "LocalOS";
      ensureMeta("name", "twitter:card").content = "summary_large_image";
      if (imageUrl) {
        ensureMeta("property", "og:image").content = imageUrl;
        ensureMeta("property", "og:image:width").content = "1200";
        ensureMeta("property", "og:image:height").content = "630";
        ensureMeta("name", "twitter:image").content = imageUrl;
      }
      ensureCanonical().href = url;
    };

    applyMeta();
    const timeoutId = window.setTimeout(applyMeta, 0);

    const scriptId = "localos-jsonld";
    document.getElementById(scriptId)?.remove();

    if (schema) {
      const script = document.createElement("script");
      script.id = scriptId;
      script.type = "application/ld+json";
      script.textContent = JSON.stringify(schema);
      document.head.appendChild(script);
    }

    return () => {
      window.clearTimeout(timeoutId);
      document.getElementById(scriptId)?.remove();
    };
  }, [description, image, ogType, path, schema, title]);

  return null;
};

export default SeoMeta;
