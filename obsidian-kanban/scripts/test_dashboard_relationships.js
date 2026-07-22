const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const dashboardPath = path.join(__dirname, '..', 'assets', 'kanban-dashboard.html');
const html = fs.readFileSync(dashboardPath, 'utf8');
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)];
assert(scripts.length > 0, 'dashboard script blocks must be present');
scripts.forEach((match) => new Function(match[1]));

const start = html.indexOf('function uniqueLinks(links)');
const end = html.indexOf('function patchSpecStatus(');

assert(start >= 0 && end > start, 'relationship parser block must be present');

const parserSource = html.slice(start, end);
const context = {};
vm.createContext(context);
vm.runInContext(
  `const RE_LINK_G = /\\[\\[([^\\]|]+)(?:\\|([^\\]]*))?\\]\\]/g;
${parserSource}
this.relationshipApi = { parseSpec, structuredLinks, blockingLinks };`,
  context,
);

const markdown = `---
status: in-progress
dependsOn: [task-b, "task-c"]
blocks: [task-d]
---
# Task A

## Dependencies
- Depends on: [[task-b|Task B]]

## Related
- [[task-e|Task E]]

## Description
Ordinary mention: [[task-f|Task F]].
`;

const parsed = JSON.parse(JSON.stringify(context.relationshipApi.parseSpec(markdown)));
assert.deepStrictEqual(parsed.deps, ['task-b', 'task-c']);
assert.deepStrictEqual(parsed.blocks, ['task-d']);
assert.deepStrictEqual(parsed.related, ['task-e']);
assert.deepStrictEqual(parsed.mentions, ['task-f']);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(context.relationshipApi.blockingLinks(parsed))),
  ['task-b', 'task-c', 'task-d'],
);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(context.relationshipApi.structuredLinks(parsed))),
  ['task-b', 'task-c', 'task-d', 'task-e'],
);
assert(
  html.includes('const cardLinks = blockingLinks(sp);'),
  'compact cards must show only dependencies and blockers',
);
const relationsStart = html.indexOf('function renderRelations(card)');
const relationsEnd = html.indexOf('async function applyEditor()', relationsStart);
const relationsSource = html.slice(relationsStart, relationsEnd);
assert(relationsStart >= 0 && relationsEnd > relationsStart, 'relations panel source must be present');
assert(relationsSource.includes("list('Depends on', sp.deps)"));
assert(relationsSource.includes("list('Blocks', sp.blocks)"));
assert(relationsSource.includes("list('Mentions', mentions)"));
assert(!relationsSource.includes("list('Related'"), 'Related must be folded into Mentions');
assert(!relationsSource.includes("list('Mentioned in'"), 'backlinks must be folded into Mentions');
assert(!relationsSource.includes("list('Artifacts'"), 'task relations panel has exactly three categories');
assert(
  html.includes('if (blockingLinks(v).includes(card.slug)) return;'),
  'backlinks must exclude only already-labeled blocking relations',
);

console.log('dashboard relationship regression: OK');
