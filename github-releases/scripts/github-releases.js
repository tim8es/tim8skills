#!/usr/bin/env node
'use strict';

const runtime = require('../lib/runtime');

if (require.main === module) {
  runtime.main().then((code) => {
    process.exitCode = code;
  });
}

module.exports = runtime;
