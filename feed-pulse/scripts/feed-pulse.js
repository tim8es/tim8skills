#!/usr/bin/env node
'use strict';

const runtime = require('../lib/runtime');
const feed = require('../lib/feed');
const config = require('../lib/config');
const { fetchUrl } = require('../lib/http');

if (require.main === module) {
  runtime.main().then((code) => {
    process.exitCode = code;
  });
}

module.exports = {
  ...runtime,
  ...feed,
  ...config,
  fetchUrl
};
