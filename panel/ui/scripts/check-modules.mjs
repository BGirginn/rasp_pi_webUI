import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve('src');
const productionModules = [];

function walk(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      walk(file);
    } else if (
      /\.(js|jsx)$/.test(entry.name)
      && !entry.name.includes('.test.')
      && file !== path.join(root, 'test/setup.js')
    ) {
      productionModules.push(file);
    }
  }
}

const reachable = new Set();
const importPattern = /(?:from\s*|import\s*\()\s*['"]([^'"]+)['"]/g;

function visit(file) {
  if (reachable.has(file) || !fs.existsSync(file)) return;
  reachable.add(file);

  for (const match of fs.readFileSync(file, 'utf8').matchAll(importPattern)) {
    if (!match[1].startsWith('.')) continue;
    const base = path.resolve(path.dirname(file), match[1]);
    const candidates = [
      base,
      `${base}.js`,
      `${base}.jsx`,
      path.join(base, 'index.js'),
      path.join(base, 'index.jsx'),
    ];
    const dependency = candidates.find((candidate) => fs.existsSync(candidate));
    if (dependency) visit(dependency);
  }
}

walk(root);
visit(path.join(root, 'main.jsx'));

const orphans = productionModules.filter((file) => !reachable.has(file));
if (orphans.length) {
  console.error('Unreachable production modules:');
  for (const file of orphans) console.error(`- ${path.relative(root, file)}`);
  process.exit(1);
}

console.log(`All ${productionModules.length} production modules are reachable from src/main.jsx.`);
