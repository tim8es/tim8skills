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
        'User-Agent': 'github-releases-skill/2.0',
        Accept: options.accept || 'application/vnd.github+json, text/plain;q=0.9, */*;q=0.1'
      }
    }, (response) => {
      const status = response.statusCode || 0;
      response.on('error', reject);
      response.on('aborted', () => reject(createError('RESPONSE_ABORTED', 'Response ended before the complete body arrived.')));

      if (status >= 300 && status < 400 && response.headers.location) {
        response.resume();
        if (options.allowRedirects === false) {
          reject(createError('UNSAFE_REDIRECT', 'Redirects are disabled for linked release notes.'));
          return;
        }
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
        const error = createError('HTTP_ERROR', `HTTP ${status} for ${url}.`);
        error.status = status;
        reject(error);
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
    const deadline = setTimeout(() => request.destroy(createError('TIMEOUT', 'Request exceeded its total deadline.')), TIMEOUT_MS);
    request.on('close', () => clearTimeout(deadline));
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
