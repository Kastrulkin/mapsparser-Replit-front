import { mkdir, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const sourcePath = process.argv[2];
const outputDirectory = process.argv[3];

if (!sourcePath || !outputDirectory) {
  throw new Error("Usage: node generate_article_translations.mjs <bundled-articles.mjs> <output-directory>");
}

const { publishedArticles } = await import(pathToFileURL(sourcePath).href);
const requestedLanguages = process.argv.slice(4);
const languages = requestedLanguages.length
  ? requestedLanguages
  : ["en", "fr", "es", "el", "de", "th", "ar", "ha", "tr"];
const skippedKeys = new Set(["slug", "publishedAt", "updatedAt", "coverImage", "statsImage", "schemeImage", "href"]);

const collectTextSlots = (value, key = "", slots = []) => {
  if (typeof value === "string") {
    if (!skippedKeys.has(key)) {
      slots.push({ value });
    }
    return slots;
  }

  if (Array.isArray(value)) {
    value.forEach((item) => collectTextSlots(item, key, slots));
    return slots;
  }

  if (value && typeof value === "object") {
    Object.entries(value).forEach(([childKey, childValue]) => collectTextSlots(childValue, childKey, slots));
  }

  return slots;
};

const replaceTextSlots = (value, translations, key = "", cursor = { index: 0 }) => {
  if (typeof value === "string") {
    if (skippedKeys.has(key)) {
      return value;
    }
    const translated = translations[cursor.index];
    cursor.index += 1;
    return translated;
  }

  if (Array.isArray(value)) {
    return value.map((item) => replaceTextSlots(item, translations, key, cursor));
  }

  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([childKey, childValue]) => [
        childKey,
        replaceTextSlots(childValue, translations, childKey, cursor),
      ]),
    );
  }

  return value;
};

const replaceTerm = (value, from, to) => {
  if (!from || from === to) return value;
  if (typeof value === "string") return value.split(from).join(to);
  if (Array.isArray(value)) return value.map((item) => replaceTerm(item, from, to));
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, replaceTerm(item, from, to)]));
  }
  return value;
};

const preserveProductTerms = (translatedArticles) => {
  const translatedLocalOs = translatedArticles[0]?.tags?.[4] ?? "LocalOS";
  const normalized = replaceTerm(translatedArticles, translatedLocalOs, "LocalOS");
  const compiledArticle = normalized[0];

  if (compiledArticle) {
    compiledArticle.title = `Compiled AI:${compiledArticle.title.includes(":") ? compiledArticle.title.slice(compiledArticle.title.indexOf(":") + 1) : ` ${compiledArticle.title}`}`;
    compiledArticle.seoTitle = `Compiled AI:${compiledArticle.seoTitle.includes(":") ? compiledArticle.seoTitle.slice(compiledArticle.seoTitle.indexOf(":") + 1) : ` ${compiledArticle.seoTitle}`}`;
    compiledArticle.tags[0] = "Compiled AI";
  }

  normalized.forEach((article, articleIndex) => {
    article.body.forEach((section, sectionIndex) => {
      section.bodyLinks?.forEach((link, linkIndex) => {
        if (link.href.includes("arxiv.org")) {
          link.text = publishedArticles[articleIndex].body[sectionIndex].bodyLinks[linkIndex].text;
        }
      });
    });
  });

  return normalized;
};

const makeBatches = (values) => {
  const batches = [];
  let current = [];
  let length = 0;

  values.forEach((value, index) => {
    const marker = `[[[LOCALOS_SPLIT_${String(index).padStart(4, "0")}]]]`;
    const nextLength = value.length + marker.length + 2;
    if (current.length && length + nextLength > 3600) {
      batches.push(current);
      current = [];
      length = 0;
    }
    current.push({ index, value, marker });
    length += nextLength;
  });

  if (current.length) batches.push(current);
  return batches;
};

const translateBatch = async (language, batch, attempt = 1) => {
  const separator = "\n";
  const query = batch.length === 1
    ? batch[0].value
    : batch.map((item) => `${item.marker}${separator}${item.value}`).join(separator);
  const form = new URLSearchParams({ client: "gtx", sl: "ru", tl: language, dt: "t", q: query });
  const response = await fetch("https://translate.googleapis.com/translate_a/single", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded;charset=UTF-8" },
    body: form,
  });

  if (!response.ok) {
    if (attempt < 4) {
      await new Promise((resolve) => setTimeout(resolve, attempt * 1000));
      return translateBatch(language, batch, attempt + 1);
    }
    throw new Error(`Translation failed for ${language}: ${response.status}`);
  }

  const payload = await response.json();
  const translatedText = payload[0].map((part) => part[0]).join("");

  if (batch.length === 1) {
    return [{ index: batch[0].index, value: translatedText.trim() }];
  }

  const results = [];
  const markerLost = batch.some((item) => translatedText.indexOf(item.marker) < 0);

  if (markerLost && batch.length > 1) {
    const midpoint = Math.ceil(batch.length / 2);
    const halves = await Promise.all([
      translateBatch(language, batch.slice(0, midpoint)),
      translateBatch(language, batch.slice(midpoint)),
    ]);
    return halves.flat();
  }

  batch.forEach((item, position) => {
    const start = translatedText.indexOf(item.marker);
    const nextMarker = batch[position + 1]?.marker;
    const end = nextMarker ? translatedText.indexOf(nextMarker) : translatedText.length;
    if (start < 0 || end < 0) {
      throw new Error(`Translation marker lost for ${language}: ${item.marker}`);
    }
    results.push({ index: item.index, value: translatedText.slice(start + item.marker.length, end).trim() });
  });

  return results;
};

await mkdir(outputDirectory, { recursive: true });
const slots = collectTextSlots(publishedArticles);
const values = slots.map((slot) => slot.value);
const batches = makeBatches(values);

for (const language of languages) {
  const translatedValues = new Array(values.length);
  for (let index = 0; index < batches.length; index += 3) {
    const group = batches.slice(index, index + 3);
    const translatedGroups = await Promise.all(group.map((batch) => translateBatch(language, batch)));
    translatedGroups.flat().forEach((item) => {
      translatedValues[item.index] = item.value;
    });
  }

  const translatedArticles = preserveProductTerms(replaceTextSlots(publishedArticles, translatedValues));
  await writeFile(`${outputDirectory}/${language}.json`, `${JSON.stringify(translatedArticles, null, 2)}\n`);
  process.stdout.write(`${language}: ${translatedValues.length} strings\n`);
}
