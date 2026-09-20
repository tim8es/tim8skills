'use strict';

const { parseFeedXml } = require('./feed');
const { fetchUrl } = require('./http');
const { createError } = require('./errors');

function semverCompare(a, b) {
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);
  for (let i = 0; i < 3; i += 1) {
    if ((pa[i] || 0) > (pb[i] || 0)) return 1;
    if ((pa[i] || 0) < (pb[i] || 0)) return -1;
  }
  return 0;
}

async function compareReleases(repo, fromTag, toTag) {
  const cleanFrom = fromTag.replace(/^v/, '');
  const cleanTo = toTag.replace(/^v/, '');
  let changelog = '';

  try {
    changelog = await fetchUrl(`https://raw.githubusercontent.com/${repo}/main/CHANGELOG.md`);
  } catch {
    try {
      changelog = await fetchUrl(`https://raw.githubusercontent.com/${repo}/master/CHANGELOG.md`);
    } catch {
      const atomUrl = `https://github.com/${repo}/releases.atom`;
      const parsed = parseFeedXml(await fetchUrl(atomUrl), atomUrl);
      const entries = parsed.items
        .map((entry) => {
          const match = entry.title.match(/v?(\d+\.\d+\.\d+)/i);
          return match ? { ...entry, version: match[1] } : null;
        })
        .filter(Boolean)
        .filter((entry) => semverCompare(entry.version, cleanFrom) >= 0 && semverCompare(entry.version, cleanTo) <= 0);

      if (!entries.length) {
        throw createError('RELEASES_NOT_FOUND', `No releases found between ${fromTag} and ${toTag}.`);
      }
      return entries.map((entry) => `## ${entry.title}\n${entry.description}`).join('\n\n');
    }
  }

  const lines = changelog.split('\n');
  const headers = [];
  for (let i = 0; i < lines.length; i += 1) {
    const match = lines[i].match(/^(##+)\s+\[?v?(\d+\.\d+\.\d+)\]?/i);
    if (match) headers.push({ line: i, version: match[2] });
  }

  const toIndex = headers.findIndex((header) => header.version === cleanTo);
  const fromIndex = headers.findIndex((header) => header.version === cleanFrom);
  if (toIndex === -1 || fromIndex === -1) {
    throw createError('RELEASES_NOT_FOUND', `Could not find exact headers for ${fromTag} and ${toTag} in CHANGELOG.md.`);
  }
  const start = headers[toIndex].line;
  const nextHeader = headers[fromIndex + 1];
  return lines.slice(start, nextHeader ? nextHeader.line : lines.length).join('\n');
}

module.exports = { compareReleases };
