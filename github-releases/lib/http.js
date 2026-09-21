'use strict';

const http = require('node:http');
const https = require('node:https');
const { createError } = require('./errors');

const TIMEOUT_MS = 10_000;
const MAX_BODY_BYTES = 5 * 1024 * 1024;
const MAX_REDIRECTS = 5;

function fetchText(url, options = {}, redirectCount = 0) {
  return new Promise((resolve, reject) => {
    let parsed;
    try {
      parsed = new URL(url);
    } catch {
      reject(createError('INVALID_URL', `Invalid URL: ${url}`));
      return;
    }

    if (!['http:', 'https:'].includes(parsed.protocol)) {
      reject(createError('INVALID_URL', `Unsupported URL protocol: ${parsed.protocol}`));
      return;
    }

    const transport = parsed.protocol === 'https:' ? https : http;
    const request = transport.get(parsed, {
      headers: {
        'User-Agent': 'github-releases-skill/1.0',
        Accept: options.accept || 'application/vnd.github+json, text/plain;q=0.9, */*;q=0.1'
      }
    }, (response) => {
      const status = response.statusCode || 0;

      if (status >= 300 && status < 400 && response.headers.location) {
        response.resume();
        if (redirectCount >= MAX_REDIRECTS) {
          reject(createError('TOO_MANY_REDIRECTS', `Too many redirects for ${url}.`));
          return;
        }
        let next;
        try {
          next = new URL(response.headers.location, parsed).toString();
        } catch {
          reject(createError('BAD_REDIRECT', `Invalid redirect from ${url}.`));
          return;
        }
        fetchText(next, options, redirectCount + 1).then(resolve, reject);
        return;
      }

      if (status < 200 || status >= 300) {
        response.resume();
        reject(createError('HTTP_ERROR', `HTTP ${status} for ${url}.`));
        return;
      }

      const chunks = [];
      let bytes = 0;
      response.on('data', (chunk) => {
        bytes += chunk.length;
        if (bytes > MAX_BODY_BYTES) {
          request.destroy(createError('RESPONSE_TOO_LARGE', `Response exceeded ${MAX_BODY_BYTES} bytes.`));
          return;
        }
        chunks.push(chunk);
      });
      response.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    });

    request.setTimeout(TIMEOUT_MS, () => {
      request.destroy(createError('TIMEOUT', `Request timed out after ${TIMEOUT_MS} ms.`));
    });
    request.on('error', reject);
  });
}

async function fetchJson(url, options = {}) {
  const text = await fetchText(url, { ...options, accept: 'application/vnd.github+json' });
  try {
    return JSON.parse(text);
  } catch {
    throw createError('JSON_PARSE_ERROR', `Invalid JSON returned from ${url}.`);
  }
}

module.exports = { fetchJson, fetchText };
