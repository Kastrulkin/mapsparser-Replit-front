import { readFileSync, readdirSync, mkdirSync, writeFileSync } from 'node:fs';
import { join, basename } from 'node:path';
import { pathToFileURL } from 'node:url';

// A renamed Vite entry must not coexist with lazy chunks importing the old
// entry: that instantiates two React contexts and may mount the application twice.
export function repairEntryGraph(files, currentEntry, previousEntry, release) {
  if (!files.has(currentEntry) || !files.has(previousEntry)) throw new Error('Missing entry');
  if (!/^[a-z0-9-]+$/.test(release)) throw new Error('Invalid release label');
  const references = (body) => Array.from(body.matchAll(/["'](?:\.\/|\/?assets\/)?([A-Za-z0-9_.-]+\.js)["']/g), match => match[1]).filter(name => files.has(name));
  const reachable = new Set();
  const visit = name => {
    // Collapse the old entry into the current one before traversing its imports.
    if (name === previousEntry) name = currentEntry;
    if (reachable.has(name)) return;
    reachable.add(name);
    references(files.get(name)).forEach(visit);
  };
  visit(currentEntry);
  const changed = new Set([currentEntry, previousEntry]);
  let grew = true;
  while (grew) {
    grew = false;
    for (const name of reachable) {
      if (!changed.has(name) && references(files.get(name)).some(ref => changed.has(ref))) {
        changed.add(name);
        grew = true;
      }
    }
  }
  const names = new Map(Array.from(changed, name => [name, name.replace(/\.js$/, `-${release}.js`)]));
  names.set(previousEntry, names.get(currentEntry));
  const rewrite = body => body.replace(/(["'])(\.\/|\/?assets\/)?([A-Za-z0-9_.-]+\.js)(["'])/g, (whole, open, prefix = '', name, close) => names.has(name) ? `${open}${prefix}${names.get(name)}${close}` : whole);
  const output = new Map();
  for (const name of reachable) {
    if (changed.has(name)) output.set(names.get(name), rewrite(files.get(name)));
  }
  for (const body of output.values()) {
    if (references(body).some(name => changed.has(name))) throw new Error('Old module reference remains');
  }
  return { output, rewrite, entry: names.get(currentEntry), reachable };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [source, destination, currentEntry, previousEntry, release] = process.argv.slice(2);
  if (!release) throw new Error('Usage: script source-dist output-dist current-entry previous-entry release');
  const assets = join(source, 'assets');
  const files = new Map(readdirSync(assets).filter(name => name.endsWith('.js')).map(name => [name, readFileSync(join(assets, name), 'utf8')]));
  const result = repairEntryGraph(files, currentEntry, previousEntry, release);
  mkdirSync(join(destination, 'assets'), { recursive: true });
  for (const [name, body] of result.output) writeFileSync(join(destination, 'assets', basename(name)), body);
  for (const name of ['index.html', 'public-seo-index.html']) writeFileSync(join(destination, name), result.rewrite(readFileSync(join(source, name), 'utf8')));
  console.log(JSON.stringify({ entry: result.entry, changedAssets: result.output.size, reachableAssets: result.reachable.size }));
}
