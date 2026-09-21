'use strict';

const { createError } = require('./errors');
const { compareReleases } = require('./releases');

const SCHEMA_VERSION = 1;

function parseArgs(argv) {
  const args = [...argv];
  const command = args.shift();
  const options = {};
  const valueOptions = new Set(['--repo', '--from', '--to', '--format']);

  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (valueOptions.has(arg)) {
      if (!args[i + 1] || args[i + 1].startsWith('--')) {
        throw createError('USAGE_ERROR', `Missing value for ${arg}.`);
      }
      options[arg.slice(2)] = args[++i];
    } else if (arg === '--help' || arg === '-h') {
      options.help = true;
    } else {
      throw createError('USAGE_ERROR', `Unknown argument: ${arg}`);
    }
  }

  return { command, options };
}

function usage() {
  return `GitHub Releases\n\nCommands:\n  compare --repo <owner/repo> --from <tag> --to <tag> [--format json|text]\n\nAliases:\n  compare-releases\n`;
}

function printText(payload) {
  console.log(`${payload.repository}: ${payload.from_tag} → ${payload.to_tag} (${payload.source})\n`);
  for (const entry of payload.entries) {
    console.log(`## ${entry.title || entry.tag}`);
    if (entry.published_at) console.log(`Published: ${entry.published_at}`);
    if (entry.url) console.log(entry.url);
    if (entry.body) console.log(`\n${entry.body}`);
    console.log();
  }
}

async function main(argv = process.argv.slice(2), dependencies = {}) {
  let format = 'json';
  try {
    const { command, options } = parseArgs(argv);
    format = options.format || 'json';

    if (!command || options.help || command === 'help') {
      console.log(usage());
      return 0;
    }

    if (!['json', 'text'].includes(format)) {
      throw createError('USAGE_ERROR', '--format must be one of: json, text.');
    }

    if (!['compare', 'compare-releases'].includes(command)) {
      throw createError('USAGE_ERROR', `Unknown command: ${command}`);
    }

    if (!options.repo || !options.from || !options.to) {
      throw createError('USAGE_ERROR', 'Usage: compare --repo <owner/repo> --from <tag> --to <tag>');
    }

    const payload = await compareReleases(options.repo, options.from, options.to, dependencies);
    if (format === 'json') console.log(JSON.stringify(payload, null, 2));
    else printText(payload);
    return 0;
  } catch (error) {
    const payload = {
      schema_version: SCHEMA_VERSION,
      ok: false,
      error: { code: error.code || 'ERROR', message: error.message }
    };
    if (format === 'text') console.error(`Error [${payload.error.code}]: ${payload.error.message}`);
    else console.log(JSON.stringify(payload, null, 2));
    return 1;
  }
}

module.exports = { main, parseArgs, printText, usage };
