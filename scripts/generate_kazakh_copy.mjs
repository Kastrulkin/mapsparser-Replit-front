import { readFile, readdir, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "../frontend/node_modules/typescript/lib/typescript.js";

const root = fileURLToPath(new URL("../", import.meta.url));
const cache = new Map();
const cachePath = "/tmp/localos-kazakh-translation-cache.json";
if (existsSync(cachePath)) {
  Object.entries(JSON.parse(await readFile(cachePath, "utf8"))).forEach(([key, value]) => cache.set(key, value));
}
const cyrillic = /[\u0400-\u04FF]/;
const armenian = /[\u0531-\u058F]/;
const protectedTokens = /\{\{[^{}]+\}\}|\$\{[^}]+\}|\{[\p{L}_][\p{L}\p{N}_]*\}|%[sd]/gu;

const walk = async (directory) => {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? walk(path) : [path];
  }));
  return files.flat();
};

const marker = (index) => `[[[LOCALOS_SPLIT_${String(index).padStart(4, "0")}]]]`;
const makeBatches = (values) => {
  const batches = [];
  let batch = [];
  let length = 0;
  values.forEach((value, index) => {
    const size = value.length + marker(index).length + 2;
    if (batch.length && length + size > 3200) {
      batches.push(batch);
      batch = [];
      length = 0;
    }
    batch.push({ index, value, marker: marker(index) });
    length += size;
  });
  if (batch.length) batches.push(batch);
  return batches;
};

const translateBatch = async (batch, sourceLanguage = "ru", attempt = 1) => {
  const query = batch.length === 1
    ? batch[0].value
    : batch.map((item) => `${item.marker}\n${item.value}`).join("\n");
  try {
    const form = new URLSearchParams({ client: "gtx", sl: sourceLanguage, tl: "kk", dt: "t", q: query });
    const response = await fetch("https://translate.googleapis.com/translate_a/single", {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded;charset=UTF-8" },
      body: form,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    const translated = payload[0].map((part) => part[0]).join("");
    if (batch.length === 1) return [{ index: batch[0].index, value: translated.trim() }];
    if (batch.some((item) => !translated.includes(item.marker))) {
      const middle = Math.ceil(batch.length / 2);
      const halves = await Promise.all([
        translateBatch(batch.slice(0, middle), sourceLanguage),
        translateBatch(batch.slice(middle), sourceLanguage),
      ]);
      return halves.flat();
    }
    return batch.map((item, position) => {
      const start = translated.indexOf(item.marker) + item.marker.length;
      const end = batch[position + 1]
        ? translated.indexOf(batch[position + 1].marker)
        : translated.length;
      return { index: item.index, value: translated.slice(start, end).trim() };
    });
  } catch (error) {
    if (attempt >= 8) throw error;
    const rateLimited = String(error).includes("429");
    await new Promise((resolve) => setTimeout(resolve, rateLimited ? Math.min(attempt * 10000, 60000) : attempt * 1500));
    return translateBatch(batch, sourceLanguage, attempt + 1);
  }
};

const translateValues = async (values, sourceLanguage = "ru") => {
  const sourceScript = sourceLanguage === "hy" ? armenian : cyrillic;
  const unique = [...new Set(values.filter((value) => sourceScript.test(value)))];
  const unseen = unique.filter((value) => !cache.has(`${sourceLanguage}:${value}`));
  const batches = makeBatches(unseen);
  const concurrency = sourceLanguage === "hy" ? 1 : 3;
  for (let index = 0; index < batches.length; index += concurrency) {
    const translated = (await Promise.all(batches.slice(index, index + concurrency)
      .map((batch) => translateBatch(batch, sourceLanguage)))).flat();
    translated.forEach(({ index: valueIndex, value }) => {
      const source = unseen[valueIndex];
      const before = source.match(protectedTokens) ?? [];
      const after = value.match(protectedTokens) ?? [];
      cache.set(`${sourceLanguage}:${source}`, JSON.stringify(before) === JSON.stringify(after) ? value : source);
    });
    await writeFile(cachePath, JSON.stringify(Object.fromEntries(cache)));
    if (sourceLanguage === "hy") await new Promise((resolve) => setTimeout(resolve, 1000));
    if (index % 10 === 0) process.stdout.write(`${sourceLanguage}: ${Math.min(index + concurrency, batches.length)}/${batches.length} batches\n`);
  }
  return (value) => cache.get(`${sourceLanguage}:${value}`) ?? value;
};

const sourceFileFor = (path, source) => ts.createSourceFile(path, source, ts.ScriptTarget.Latest, true);
const textLiterals = (node) => {
  const result = [];
  const visit = (child) => {
    if ((ts.isStringLiteral(child) || ts.isNoSubstitutionTemplateLiteral(child))
      && !(ts.isPropertyAssignment(child.parent) && child.parent.name === child)
      && cyrillic.test(child.text)) result.push(child);
    ts.forEachChild(child, visit);
  };
  visit(node);
  return result;
};

const translatedNodeText = (node, sourceFile, source, lookup) => {
  const start = node.getStart(sourceFile);
  const end = node.getEnd();
  let text = source.slice(start, end);
  const edits = textLiterals(node).map((literal) => ({
    start: literal.getStart(sourceFile) - start,
    end: literal.getEnd() - start,
    value: ts.isNoSubstitutionTemplateLiteral(literal)
      ? `\`${lookup(literal.text).replaceAll("`", "\\`")}\``
      : JSON.stringify(lookup(literal.text)),
  })).sort((a, b) => b.start - a.start);
  edits.forEach((edit) => { text = `${text.slice(0, edit.start)}${edit.value}${text.slice(edit.end)}`; });
  return text;
};

const candidateFiles = (await walk(join(root, "frontend/src")))
  .filter((path) => path.endsWith(".ts") || path.endsWith(".tsx"));
const candidates = [];
for (const path of candidateFiles) {
  if (path.endsWith("/i18n/locales/ru.ts")) continue;
  const source = await readFile(path, "utf8");
  if (!source.includes("hy:") || !source.includes("ru:")) continue;
  const sourceFile = sourceFileFor(path, source);
  const additions = [];
  const visit = (node) => {
    if (ts.isObjectLiteralExpression(node)) {
      const ru = node.properties.find((property) => ts.isPropertyAssignment(property) && property.name.getText(sourceFile) === "ru");
      const hy = node.properties.find((property) => (ts.isPropertyAssignment(property) || ts.isShorthandPropertyAssignment(property)) && property.name.getText(sourceFile) === "hy");
      const kk = node.properties.find((property) => ts.isPropertyAssignment(property) && property.name.getText(sourceFile) === "kk");
      if (ru && hy && !kk) additions.push({ ru, hy });
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  if (additions.length) candidates.push({ path, source, sourceFile, additions });
}

const ruLocalePath = join(root, "frontend/src/i18n/locales/ru.ts");
const ruLocale = await readFile(ruLocalePath, "utf8");
const ruLocaleAst = sourceFileFor(ruLocalePath, ruLocale);
const kkLocalePath = join(root, "frontend/src/i18n/locales/kk.ts");
const allRussian = [
  ...(existsSync(kkLocalePath) ? [] : textLiterals(ruLocaleAst).map((node) => node.text)),
  ...candidates.flatMap(({ additions }) => additions.flatMap(({ ru }) => textLiterals(ru.initializer).map((node) => node.text))),
];
process.stdout.write(`TS candidates: ${candidates.length} files, ${allRussian.length} strings\n`);
const lookup = await translateValues(allRussian);

if (!existsSync(kkLocalePath)) {
  let kkLocale = translatedNodeText(ruLocaleAst, ruLocaleAst, ruLocale, lookup);
  kkLocale = kkLocale.replace("export const ru =", "export const kk =");
  await writeFile(kkLocalePath, kkLocale);
}

for (const { path, source, sourceFile, additions } of candidates) {
  let output = source;
  const edits = additions.map(({ ru, hy }) => {
    const next = hy.getEnd();
    const hasComma = source.slice(next).match(/^\s*,/);
    const position = hasComma ? next + hasComma[0].length : next;
    const line = source.slice(0, hy.getStart(sourceFile)).split("\n").at(-1) ?? "";
    const indent = line.match(/^\s*/)?.[0] ?? "";
    const translated = translatedNodeText(ru.initializer, sourceFile, source, lookup);
    return { position, text: `${hasComma ? "" : ","}\n${indent}kk: ${translated},` };
  }).sort((a, b) => b.position - a.position);
  edits.forEach(({ position, text }) => { output = `${output.slice(0, position)}${text}${output.slice(position)}`; });
  await writeFile(path, output);
  process.stdout.write(`${relative(root, path)}: ${edits.length} blocks\n`);
}

const namedCandidates = [];
for (const path of candidateFiles) {
  const source = await readFile(path, "utf8");
  if (!source.includes("const ru") || !source.includes("const hy") || source.includes("const kk")) continue;
  const sourceFile = sourceFileFor(path, source);
  const declarations = sourceFile.statements
    .filter(ts.isVariableStatement)
    .flatMap((statement) => statement.declarationList.declarations.map((declaration) => ({ statement, declaration })));
  const named = (name) => declarations.find(({ declaration }) => ts.isIdentifier(declaration.name) && declaration.name.text === name);
  const ru = named("ru");
  const hy = named("hy");
  if (ru?.declaration.initializer && hy?.declaration.initializer) namedCandidates.push({ path, source, sourceFile, ru, hy });
}
const namedValues = namedCandidates.flatMap(({ ru }) => textLiterals(ru.declaration.initializer).map((node) => node.text));
const namedLookup = await translateValues(namedValues);
for (const { path, source, sourceFile, ru, hy } of namedCandidates) {
  const type = hy.declaration.type?.getText(sourceFile);
  const translated = translatedNodeText(ru.declaration.initializer, sourceFile, source, namedLookup);
  const insertion = `\nconst kk${type ? `: ${type}` : ""} = ${translated};`;
  const position = hy.statement.getEnd();
  await writeFile(path, `${source.slice(0, position)}${insertion}${source.slice(position)}`);
  process.stdout.write(`${relative(root, path)}: named copy\n`);
}

const translateJson = async (sourcePath, targetPath, sourceLanguage) => {
  const source = JSON.parse(await readFile(sourcePath, "utf8"));
  const values = [];
  const collect = (value) => {
    if (typeof value === "string") values.push(value);
    else if (Array.isArray(value)) value.forEach(collect);
    else if (value && typeof value === "object") Object.values(value).forEach(collect);
  };
  collect(source);
  const jsonLookup = await translateValues(values, sourceLanguage);
  const replace = (value, key = "") => {
    if (typeof value === "string") {
      if (["slug", "href", "url", "publishedAt", "updatedAt", "coverImage", "statsImage", "schemeImage"].includes(key)) return value;
      return jsonLookup(value);
    }
    if (Array.isArray(value)) return value.map((item) => replace(item));
    if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([childKey, item]) => [childKey, replace(item, childKey)]));
    return value;
  };
  await writeFile(targetPath, `${JSON.stringify(replace(source), null, 2)}\n`);
  process.stdout.write(`${relative(root, targetPath)}: ${values.length} strings\n`);
};

const jsonBase = join(root, "frontend/src/content");
for (const [source, target] of [
  ["docs-hy.json", "docs-kk.json"],
  ["collection-locales/cases-hy.json", "collection-locales/cases-kk.json"],
  ["collection-locales/documents-hy.json", "collection-locales/documents-kk.json"],
]) await translateJson(join(jsonBase, source), join(jsonBase, target), "hy");

const homePath = join(root, "frontend/src/i18n/homeLandingTranslations.json");
const home = JSON.parse(await readFile(homePath, "utf8"));
const homeValues = [];
const collectHome = (value) => {
  if (typeof value === "string") homeValues.push(value);
  else if (Array.isArray(value)) value.forEach(collectHome);
  else if (value && typeof value === "object") Object.values(value).forEach(collectHome);
};
collectHome(home.hy);
const homeLookup = await translateValues(homeValues, "hy");
const replaceHome = (value, key = "") => {
  if (typeof value === "string") return ["href", "url"].includes(key) ? value : homeLookup(value);
  if (Array.isArray(value)) return value.map((item) => replaceHome(item));
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([childKey, item]) => [childKey, replaceHome(item, childKey)]));
  return value;
};
home.kk = replaceHome(home.hy);
await writeFile(homePath, `${JSON.stringify(home, null, 2)}\n`);
process.stdout.write(`Kazakh draft generated\n`);
