'use strict';

const { createError } = require('./errors');
const { fetchJson, fetchText } = require('./http');

const SCHEMA_VERSION = 1;

function normalizeRepo(repo) {
  const value = String(repo || '').trim();
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(value)) {
    throw createError('INVALID_REPO', 'Repository must be in owner/repo form.');
  }
  return value;
}

function normalizeTag(tag) {
  const value = String(tag || '').trim();
  if (!value) throw createError('INVALID_TAG', 'Release tag must not be empty.');
  return value.replace(/^v(?=\d)/i, '');
}

function parseChangelog(changelog) {
  const lines = String(changelog || '').split(/\r?\n/);
  const headers = [];

  for (let i = 0; i < lines.length; i += 1) {
    const match = lines[i].match(/^(##+)\s+(?:\[)?v?(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)(?:\])?(?:\s*[-–—].*)?$/i);
    if (match) headers.push({ line: i, tag: match[2], title: lines[i].replace(/^##+\s+/, '').trim() });
  }

  return headers.map((header, index) => {
    const next = headers[index + 1];
    return {
      tag: header.tag,
      title: header.title,
      body: lines.slice(header.line + 1, next ? next.line : lines.length).join('\n').trim(),
      url: null,
      published_at: null
    };
  });
}

function selectRange(entries, fromTag, toTag) {
  const from = normalizeTag(fromTag).toLowerCase();
  const to = normalizeTag(toTag).toLowerCase();
  const fromIndex = entries.findIndex((entry) => normalizeTag(entry.tag).toLowerCase() === from);
  const toIndex = entries.findIndex((entry) => normalizeTag(entry.tag).toLowerCase() === to);

  if (fromIndex === -1 || toIndex === -1) return null;

  const start = Math.min(fromIndex, toIndex);
  const end = Math.max(fromIndex, toIndex);
  return entries.slice(start, end + 1);
}

function normalizeApiRelease(release) {
  return {
    tag: String(release.tag_name || '').trim(),
    title: String(release.name || release.tag_name || '').trim(),
    body: String(release.body || '').trim(),
    url: release.html_url || null,
    published_at: release.published_at || release.created_at || null
  };
}

async function compareReleases(repo, fromTag, toTag, dependencies = {}) {
  const repository = normalizeRepo(repo);
  normalizeTag(fromTag);
  normalizeTag(toTag);

  const getText = dependencies.fetchText || fetchText;
  const getJson = dependencies.fetchJson || fetchJson;
  const changelogUrls = [
    `https://raw.githubusercontent.com/${repository}/main/CHANGELOG.md`,
    `https://raw.githubusercontent.com/${repository}/master/CHANGELOG.md`
  ];

  for (const url of changelogUrls) {
    try {
      const entries = selectRange(parseChangelog(await getText(url)), fromTag, toTag);
      if (entries && entries.length) {
        return {
          schema_version: SCHEMA_VERSION,
          command: 'compare',
          ok: true,
          repository,
          from_tag: fromTag,
          to_tag: toTag,
          source: 'changelog',
          entry_count: entries.length,
          entries
        };
      }
    } catch {
      // Fall through to the next changelog location or GitHub Releases API.
    }
  }

  let releases;
  try {
    releases = await getJson(`https://api.github.com/repos/${repository}/releases?per_page=100`);
  } catch (error) {
    throw createError(error.code || 'RETRIEVAL_ERROR', error.message);
  }

  if (!Array.isArray(releases)) {
    throw createError('INVALID_RESPONSE', 'GitHub Releases API returned an unexpected response.');
  }

  const entries = selectRange(releases.map(normalizeApiRelease).filter((entry) => entry.tag), fromTag, toTag);
  if (!entries || !entries.length) {
    throw createError('RELEASES_NOT_FOUND', `Could not resolve both ${fromTag} and ${toTag} for ${repository}.`);
  }

  return {
    schema_version: SCHEMA_VERSION,
    command: 'compare',
    ok: true,
    repository,
    from_tag: fromTag,
    to_tag: toTag,
    source: 'github_releases',
    entry_count: entries.length,
    entries
  };
}

module.exports = {
  compareReleases,
  normalizeRepo,
  normalizeTag,
  parseChangelog,
  selectRange
};
