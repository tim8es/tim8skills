'use strict';

const { createError } = require('./errors');
const { compareReleases, latestRelease, listReleases, releaseNotes } = require('./releases');

const COMMON = ['repo', 'format'];
const FILTERS = ['include-prereleases', 'include-nonversion'];
const OPTIONS = {
  latest: [...COMMON, ...FILTERS],
  list: [...COMMON, ...FILTERS, 'since', 'limit'],
  notes: [...COMMON, 'tag', 'max-body-chars', 'offset', 'release-body'],
  compare: [...COMMON, ...FILTERS, 'from', 'to', 'max-body-chars']
};

function parseArgs(argv) {
  const args = [...argv];
  let command = args.shift();
  if (command === 'compare-releases') command = 'compare';
  if (['--help', '-h'].includes(command)) command = 'help';
  const options = {};
  const flags = new Set([...FILTERS, 'release-body']);
  const values = new Set(Object.values(OPTIONS).flat().filter((key) => !flags.has(key)));
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    const key = arg.slice(2);
    if (arg === '--help' || arg === '-h') { options.help = true; continue; }
    if (!arg.startsWith('--') || (!flags.has(key) && !values.has(key))) throw createError('USAGE_ERROR', `Unknown argument: ${arg}`);
    if (Object.hasOwn(options, key)) throw createError('USAGE_ERROR', `Duplicate argument: ${arg}`);
    if (flags.has(key)) options[key] = true;
    else {
      if (!args[i + 1] || args[i + 1].startsWith('--')) throw createError('USAGE_ERROR', `Missing value for ${arg}.`);
      options[key] = args[++i];
    }
  }
  return { command, options };
}

function usage() {
  return `GitHub Releases\n\nCommands (JSON by default):
  latest --repo owner/repo
  list --repo owner/repo [--since exact-tag] [--limit 20]
  notes --repo owner/repo --tag exact-tag [--max-body-chars 12000] [--offset 0] [--release-body]
  compare --repo owner/repo --from exact-tag --to exact-tag [--max-body-chars 12000]

latest/list/compare: --include-prereleases --include-nonversion
All commands: --format json|text
Alias: compare-releases\n`;
}

function printText(payload) {
  console.log(`${payload.repository}: ${payload.command} (${payload.source})\n`);
  for (const entry of payload.entries) {
    console.log(`## ${entry.title} (${entry.tag})\nPublished: ${entry.published_at}\n${entry.url}`);
    if (entry.body_source) console.log(`Notes: ${entry.body_source}`);
    if (entry.body) console.log(`\n${entry.body}`);
    if (entry.body_truncated) console.log(`\nPartial body; next_offset=${entry.next_offset}`);
  }
  if (payload.has_more) console.log(`Showing ${payload.entry_count} of ${payload.total_count}; increase --limit.`);
}

async function main(argv = process.argv.slice(2), dependencies = {}) {
  let format = 'json';
  try {
    const { command, options } = parseArgs(argv);
    format = options.format || 'json';
    if (!command || command === 'help' || options.help) { console.log(usage()); return 0; }
    if (!['json', 'text'].includes(format)) throw createError('USAGE_ERROR', '--format must be json or text.');
    if (!Object.hasOwn(OPTIONS, command)) throw createError('USAGE_ERROR', `Unknown command: ${command}`);
    for (const key of Object.keys(options)) {
      if (!OPTIONS[command].includes(key)) throw createError('USAGE_ERROR', `--${key} is not supported by ${command}.`);
    }
    const required = ['repo', ...(command === 'notes' ? ['tag'] : command === 'compare' ? ['from', 'to'] : [])];
    if (required.some((key) => !options[key])) throw createError('USAGE_ERROR', `${command} requires ${required.map((key) => `--${key}`).join(', ')}.`);
    const settings = {
      includePrereleases: options['include-prereleases'], includeNonversion: options['include-nonversion'],
      maxBodyChars: options['max-body-chars'], releaseBody: options['release-body'],
      offset: options.offset, limit: options.limit, since: options.since
    };
    let payload;
    if (command === 'latest') payload = await latestRelease(options.repo, settings, dependencies);
    else if (command === 'list') payload = await listReleases(options.repo, settings, dependencies);
    else if (command === 'notes') payload = await releaseNotes(options.repo, options.tag, settings, dependencies);
    else payload = await compareReleases(options.repo, options.from, options.to, dependencies, settings);
    if (format === 'json') console.log(JSON.stringify(payload, null, 2));
    else printText(payload);
    return 0;
  } catch (error) {
    const payload = { schema_version: 2, ok: false, error: { code: error.code || 'ERROR', message: error.message } };
    if (format === 'text') console.error(`Error [${payload.error.code}]: ${payload.error.message}`);
    else console.log(JSON.stringify(payload, null, 2));
    return 1;
  }
}

module.exports = { main, parseArgs, printText, usage };
