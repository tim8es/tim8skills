'use strict';

const http = require('http');
const https = require('https');
const { validateHttpUrl } = require('./config');
const { createError } = require('./errors');

const HTTP_TIMEOUT_MS = 10_000;
const MAX_RESPONSE_BYTES = 5 * 1024 * 1024;
const MAX_REDIRECTS = 5;

function fetchUrl(url, { redirects = 0 } = {}) {
  const normalizedUrl = validateHttpUrl(url);
  if (redirects > MAX_REDIRECTS) {
    return Promise.reject(createError('TOO_MANY_REDIRECTS', `More than ${MAX_REDIRECTS} redirects.`));
  }

  return new Promise((resolve, reject) => {
    const parsed = new URL(normalizedUrl);
    const client = parsed.protocol === 'https:' ? https : http;
    const req = client.get(parsed, {
      headers: {
        'User-Agent': 'feed-pulse-skill/1.0',
        Accept: 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.5'
      }
    }, (res) => {
      const status = res.statusCode || 0;
      if (status >= 300 && status < 400 && res.headers.location) {
        res.resume();
        let nextUrl;
        try {
          nextUrl = new URL(res.headers.location, normalizedUrl).toString();
        } catch {
          reject(createError('BAD_REDIRECT', `Invalid redirect location from ${normalizedUrl}.`));
          return;
        }
        fetchUrl(nextUrl, { redirects: redirects + 1 }).then(resolve, reject);
        return;
      }

      if (status !== 200) {
        res.resume();
        reject(createError('HTTP_ERROR', `HTTP ${status} for ${normalizedUrl}`));
        return;
      }

      const declaredLength = Number(res.headers['content-length'] || 0);
      if (declaredLength > MAX_RESPONSE_BYTES) {
        res.resume();
        reject(createError('RESPONSE_TOO_LARGE', `Response exceeds ${MAX_RESPONSE_BYTES} bytes.`));
        return;
      }

      const chunks = [];
      let size = 0;
      res.on('data', (chunk) => {
        size += chunk.length;
        if (size > MAX_RESPONSE_BYTES) {
          res.destroy(createError('RESPONSE_TOO_LARGE', `Response exceeds ${MAX_RESPONSE_BYTES} bytes.`));
          return;
        }
        chunks.push(chunk);
      });
      res.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
      res.on('error', reject);
    });

    req.setTimeout(HTTP_TIMEOUT_MS, () => {
      req.destroy(createError('TIMEOUT', `Request timed out after ${HTTP_TIMEOUT_MS} ms.`));
    });
    req.on('error', reject);
  });
}

module.exports = { fetchUrl };
