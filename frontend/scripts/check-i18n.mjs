// Fails if any locale is missing keys present in the reference locale (SDD §8.5).
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../src/locales/', import.meta.url));
const reference = 'ru';
const locales = readdirSync(root);

const flatten = (obj, prefix = '') =>
  Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === 'object' ? flatten(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
const load = (lng, ns) => JSON.parse(readFileSync(join(root, lng, ns), 'utf8'));

let problems = 0;
for (const ns of readdirSync(join(root, reference))) {
  const expected = new Set(flatten(load(reference, ns)));
  for (const lng of locales) {
    let actual;
    try {
      actual = new Set(flatten(load(lng, ns)));
    } catch {
      console.error(`✗ ${lng}/${ns}: file missing`);
      problems++;
      continue;
    }
    for (const key of expected)
      if (!actual.has(key)) (problems++, console.error(`✗ ${lng}/${ns}: missing "${key}"`));
    for (const key of actual)
      if (!expected.has(key)) (problems++, console.error(`✗ ${lng}/${ns}: extra "${key}"`));
  }
}
if (problems) process.exit(1);
console.log(`✓ i18n: ${locales.join(', ')} are complete`);
