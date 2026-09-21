'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const http = require('node:http');
const { fetchText, fetchJson } = require('../lib/http');

test('HTTP boundaries: status, redirects, oversized and incomplete bodies', async (t) => {
  let targetHits = 0;
  const server = http.createServer((req, res) => {
    if (req.url === '/redirect') { res.writeHead(302, { Location: '/target' }); res.end(); }
    else if (req.url === '/target') { targetHits++; res.end('ok'); }
    else if (req.url === '/missing') { res.writeHead(404); res.end('missing'); }
    else if (req.url === '/large') res.end(Buffer.alloc(5 * 1024 * 1024 + 1));
    else if (req.url === '/abort') {
      res.writeHead(200, { 'Content-Length': '100' }); res.write('short');
      setImmediate(() => res.destroy());
    } else res.end('invalid json');
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  t.after(() => { server.closeAllConnections(); return new Promise((resolve) => server.close(resolve)); });
  const base = `http://127.0.0.1:${server.address().port}`;
  await assert.rejects(fetchText(`${base}/missing`), { code: 'HTTP_ERROR', status: 404 });
  await assert.rejects(fetchText(`${base}/redirect`, { allowRedirects: false }), { code: 'UNSAFE_REDIRECT' });
  assert.equal(targetHits, 0);
  assert.equal(await fetchText(`${base}/redirect`), 'ok');
  await assert.rejects(fetchText(`${base}/large`), { code: 'RESPONSE_TOO_LARGE' });
  await assert.rejects(fetchText(`${base}/abort`), { code: 'RESPONSE_ABORTED' });
  await assert.rejects(fetchJson(`${base}/bad-json`), { code: 'JSON_PARSE_ERROR' });
});
