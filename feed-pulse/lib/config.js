'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { createError } = require('./errors');

const DEFAULT_CONFIG = Object.freeze({
  version: 1,
  feeds: [],
  settings: {
    maxItemsPerFeed: 10
  }
});

function dataDir() {
  return process.env.FEED_PULSE_DATA_DIR || path.join(os.homedir(), '.feed-pulse');
}

function feedsFile() {
  return path.join(dataDir(), 'feeds.json');
}

function cloneDefaultConfig() {
  return JSON.parse(JSON.stringify(DEFAULT_CONFIG));
}

function validateHttpUrl(value) {
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    throw createError('INVALID_URL', `Invalid URL: ${value}`);
  }
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw createError('INVALID_URL', `Only http:// and https:// URLs are supported: ${value}`);
  }
  return parsed.toString();
}

function rawText(value) {
  if (value == null) return '';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) return value.map(rawText).filter(Boolean).join(' ');
  if (typeof value === 'object') {
    if (value['#text'] != null) return rawText(value['#text']);
    if (value['#cdata'] != null) return rawText(value['#cdata']);
  }
  return '';
}

function normalizeText(value) {
  return rawText(value)
    .replace(/<[^>]*>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function normalizeCategory(value) {
  return normalizeText(value).toLowerCase() || 'general';
}

function normalizeIsoOrNull(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function validateConfig(config) {
  if (!config || typeof config !== 'object' || Array.isArray(config)) {
    throw createError('CONFIG_INVALID', 'Feed configuration must be a JSON object.');
  }
  if (!Array.isArray(config.feeds)) {
    throw createError('CONFIG_INVALID', 'Feed configuration field "feeds" must be an array.');
  }

  const settings = config.settings && typeof config.settings === 'object' ? config.settings : {};
  const maxItemsPerFeed = Number.isInteger(settings.maxItemsPerFeed) && settings.maxItemsPerFeed > 0
    ? settings.maxItemsPerFeed
    : DEFAULT_CONFIG.settings.maxItemsPerFeed;

  return {
    version: Number.isInteger(config.version) ? config.version : 1,
    feeds: config.feeds.map((feed, index) => {
      if (!feed || typeof feed !== 'object' || !feed.url) {
        throw createError('CONFIG_INVALID', `Feed at index ${index} is missing a URL.`);
      }
      return {
        url: validateHttpUrl(feed.url),
        name: normalizeText(feed.name) || feed.url,
        category: normalizeCategory(feed.category),
        enabled: feed.enabled !== false,
        lastChecked: normalizeIsoOrNull(feed.lastChecked),
        lastItemDate: normalizeIsoOrNull(feed.lastItemDate)
      };
    }),
    settings: { maxItemsPerFeed }
  };
}

function loadConfig() {
  const file = feedsFile();
  if (!fs.existsSync(file)) return cloneDefaultConfig();

  let parsed;
  try {
    parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (error) {
    throw createError('CONFIG_PARSE_ERROR', `Cannot parse ${file}: ${error.message}`);
  }
  return validateConfig(parsed);
}

function saveConfig(config) {
  const dir = dataDir();
  const file = feedsFile();
  fs.mkdirSync(dir, { recursive: true });

  const normalized = validateConfig(config);
  const temporaryFile = path.join(
    dir,
    `.feeds.json.${process.pid}.${Date.now()}.tmp`
  );

  try {
    fs.writeFileSync(temporaryFile, `${JSON.stringify(normalized, null, 2)}\n`);
    fs.renameSync(temporaryFile, file);
  } finally {
    if (fs.existsSync(temporaryFile)) fs.rmSync(temporaryFile, { force: true });
  }
}

function toPublicFeed(feed) {
  return {
    url: feed.url,
    name: feed.name,
    category: feed.category,
    enabled: feed.enabled,
    last_checked: feed.lastChecked,
    last_item_date: feed.lastItemDate
  };
}

module.exports = {
  dataDir,
  loadConfig,
  normalizeCategory,
  normalizeText,
  rawText,
  saveConfig,
  toPublicFeed,
  validateHttpUrl
};
