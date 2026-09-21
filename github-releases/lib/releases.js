'use strict';

const { createError } = require('./errors');
const { fetchJson, fetchText } = require('./http');

const VERSION_TAG = /^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/i;
const PAGE_SIZE = 20;
const MAX_PAGES = 50;

function normalizeRepo(repo) {
  const value = String(repo || '').trim();
  if (!/^[A-Za-z0-9_-][A-Za-z0-9_.-]*\/[A-Za-z0-9_-][A-Za-z0-9_.-]*$/.test(value)) {
    throw createError('INVALID_REPO', 'Repository must be in owner/repo form.');
  }
  return value;
}

function normalizeTag(tag) {
  const value = String(tag || '').trim();
  if (!value) throw createError('INVALID_TAG', 'Release tag must not be empty.');
  return value;
}

function apiUrl(repo) { return `https://api.github.com/repos/${repo}/releases`; }

function normalizeApiRelease(release) {
  if (!release || typeof release.tag_name !== 'string' || !release.tag_name.trim() ||
      typeof release.draft !== 'boolean' || typeof release.prerelease !== 'boolean' ||
      (!release.draft && (typeof release.published_at !== 'string' ||
        !Number.isFinite(Date.parse(release.published_at)))) ||
      typeof release.html_url !== 'string') {
    throw createError('INVALID_RESPONSE', 'GitHub returned invalid release metadata.');
  }
  return {
    tag: release.tag_name, title: release.name || release.tag_name,
    url: release.html_url, published_at: release.published_at,
    draft: release.draft, prerelease: release.prerelease,
    body: String(release.body || '').trim()
  };
}

function included(entry, options) {
  return !entry.draft && (options.includePrereleases || !entry.prerelease) &&
    (options.includeNonversion || VERSION_TAG.test(entry.tag));
}

function metadata({ body, ...entry }) { return entry; }

function result(command, repository, entries, extra = {}) {
  return {
    schema_version: 2, command, ok: true, repository,
    source: 'github_releases', entry_count: entries.length, entries, ...extra
  };
}

function integer(value, fallback, min, max, name) {
  const number = value === undefined ? fallback : Number(value);
  if (!Number.isSafeInteger(number) || number < min || number > max) {
    throw createError('USAGE_ERROR', `${name} must be an integer between ${min} and ${max}.`);
  }
  return number;
}

function bodyPage(entry, options = {}, body = entry.body, source = entry.url) {
  const limit = integer(options.maxBodyChars, 12000, 1, 50000, 'max-body-chars');
  const offset = integer(options.offset, 0, 0, body.length, 'offset');
  let end = Math.min(offset + limit, body.length);
  // Keep UTF-16 surrogate pairs intact, even with a one-unit page budget.
  if (end < body.length && /[\uD800-\uDBFF]/.test(body[end - 1]) && /[\uDC00-\uDFFF]/.test(body[end])) end++;
  if (offset > 0 && /[\uDC00-\uDFFF]/.test(body[offset]) && /[\uD800-\uDBFF]/.test(body[offset - 1])) {
    throw createError('USAGE_ERROR', 'offset splits a Unicode character; use next_offset from the previous page.');
  }
  return {
    ...metadata(entry), body: body.slice(offset, end), body_source: source,
    body_length: body.length, body_offset: offset,
    body_truncated: offset > 0 || end < body.length,
    next_offset: end < body.length ? end : null
  };
}

async function publishedReleases(repository, options, dependencies) {
  const getJson = dependencies.fetchJson || fetchJson;
  const byTag = new Map();
  // ponytail: bounded full scan avoids relying on GitHub's non-publication ordering;
  // use a persistent release-ID index if histories exceed 1,000 entries.
  for (let page = 1; page <= MAX_PAGES; page++) {
    const releases = await getJson(`${apiUrl(repository)}?per_page=${PAGE_SIZE}&page=${page}`);
    if (!Array.isArray(releases)) throw createError('INVALID_RESPONSE', 'GitHub Releases API did not return an array.');
    for (const raw of releases) {
      const entry = normalizeApiRelease(raw);
      if (included(entry, options)) byTag.set(entry.tag, entry);
    }
    if (releases.length < PAGE_SIZE) {
      return [...byTag.values()].sort((a, b) => Date.parse(b.published_at) - Date.parse(a.published_at) ||
        (a.tag < b.tag ? -1 : a.tag > b.tag ? 1 : 0));
    }
  }
  throw createError('HISTORY_LIMIT', `Release history exceeds ${MAX_PAGES} pages; refusing a partial result.`);
}

async function getRelease(repository, tag, dependencies) {
  const getJson = dependencies.fetchJson || fetchJson;
  const entry = normalizeApiRelease(await getJson(`${apiUrl(repository)}/tags/${encodeURIComponent(normalizeTag(tag))}`));
  if (entry.draft || entry.tag !== tag) throw createError('RELEASES_NOT_FOUND', `No published release for exact tag ${tag}.`);
  return entry;
}

async function latestRelease(repo, options = {}, dependencies = {}) {
  const repository = normalizeRepo(repo);
  // GitHub's designated latest stable release is a single compact API request.
  if (!options.includePrereleases && !options.includeNonversion) {
    const getJson = dependencies.fetchJson || fetchJson;
    try {
      const entry = normalizeApiRelease(await getJson(`${apiUrl(repository)}/latest`));
      if (included(entry, options)) return result('latest', repository, [metadata(entry)], { selection: 'github_latest' });
    } catch (error) {
      if (error.status !== 404) throw error;
    }
  }
  const entries = await publishedReleases(repository, options, dependencies);
  if (!entries.length) throw createError('RELEASES_NOT_FOUND', 'No matching published releases.');
  return result('latest', repository, [metadata(entries[0])], { selection: 'published_at' });
}

async function listReleases(repo, options = {}, dependencies = {}) {
  const repository = normalizeRepo(repo);
  const limit = integer(options.limit, 20, 1, 1000, 'limit');
  let entries = await publishedReleases(repository, options, dependencies);
  if (options.since) {
    const baseline = entries.find((entry) => entry.tag === normalizeTag(options.since));
    if (!baseline) throw createError('BASELINE_NOT_FOUND', 'Baseline is missing or excluded by the current filters; preserve monitor state.');
    // Include equal timestamps to avoid silently losing a simultaneous publication.
    // The monitor deduplicates exact tags at its publication-time boundary.
    entries = entries.filter((entry) => entry.tag !== baseline.tag && Date.parse(entry.published_at) >= Date.parse(baseline.published_at));
  }
  const total = entries.length;
  if (options.since && total > limit) throw createError('RESULT_LIMIT', `Found ${total} new releases; rerun with --limit ${total}.`);
  return result('list', repository, entries.slice(0, limit).map(metadata), {
    since_tag: options.since || null, total_count: total, has_more: total > limit
  });
}

function linkedNotes(repository, entry) {
  // Only Markdown links explicitly labelled as release notes/changelog in this repository.
  for (const match of entry.body.matchAll(/\[([^\]]+)\]\((https:\/\/[^\s)]+)\)/g)) {
    if (!/^(?:plain markdown|changelog|release notes)(?:\b|$)/i.test(match[1])) continue;
    let url;
    try { url = new URL(match[2]); } catch { continue; }
    if (url.username || url.password || url.port || url.search) continue;
    const prefix = `/${repository}/`;
    if (!url.pathname.startsWith(prefix)) continue;
    let parts = url.pathname.slice(prefix.length).split('/');
    if (url.hostname === 'github.com' && parts[0] === 'blob') parts = parts.slice(1);
    else if (url.hostname !== 'raw.githubusercontent.com') continue;
    const [ref, ...path] = parts;
    if (!ref || !path.length || !/\.md$/i.test(path.join('/'))) continue;
    if (!['main', 'master', encodeURIComponent(entry.tag)].includes(ref) && !/^[a-f0-9]{40}$/i.test(ref)) continue;
    if (path.some((part) => /%(?:2e|2f|5c)/i.test(part) || part === '..' || part === '.')) continue;
    const pinnedRef = /^[a-f0-9]{40}$/i.test(ref) ? ref : encodeURIComponent(entry.tag);
    return `https://raw.githubusercontent.com/${repository}/${pinnedRef}/${path.join('/')}`;
  }
  return null;
}

async function releaseNotes(repo, tag, options = {}, dependencies = {}) {
  const repository = normalizeRepo(repo);
  const entry = await getRelease(repository, normalizeTag(tag), dependencies);
  const source = options.releaseBody ? null : linkedNotes(repository, entry);
  const body = source ? await (dependencies.fetchText || fetchText)(source, { allowRedirects: false }) : entry.body;
  return result('notes', repository, [bodyPage(entry, options, body, source || entry.url)]);
}

async function compareReleases(repo, fromTag, toTag, dependencies = {}, options = {}) {
  const repository = normalizeRepo(repo);
  const from = normalizeTag(fromTag);
  const to = normalizeTag(toTag);
  const entries = await publishedReleases(repository, options, dependencies);
  const fromEntry = entries.find((entry) => entry.tag === from);
  const toEntry = entries.find((entry) => entry.tag === to);
  if (!fromEntry || !toEntry) throw createError('RELEASES_NOT_FOUND', 'Both exact tags must be published and match the selected filters.');
  const low = Math.min(Date.parse(fromEntry.published_at), Date.parse(toEntry.published_at));
  const high = Math.max(Date.parse(fromEntry.published_at), Date.parse(toEntry.published_at));
  const selected = entries.filter((entry) => from === to ? entry.tag === from :
    Date.parse(entry.published_at) >= low && Date.parse(entry.published_at) <= high);
  if (selected.length > 20) throw createError('RESULT_LIMIT', 'Comparison exceeds 20 releases; use a narrower range or list plus notes.');
  return result('compare', repository, selected.map((entry) => bodyPage(entry, options)), { from_tag: from, to_tag: to });
}

module.exports = { compareReleases, latestRelease, listReleases, releaseNotes, normalizeRepo, normalizeTag };
